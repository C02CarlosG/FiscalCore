from __future__ import annotations

import json
import logging
from typing import Optional

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from .. import db
from ..deps import get_current_user, empresa_or_404, validar_acceso_empresa, serializar, validar_upload
from ..schemas import AgregarEmpresaRequest, ImpuestosRequest

_CONSTANCIA_EXTENSIONES = (".pdf",)
_CONSTANCIA_CONTENT_TYPES = ("application/pdf", "application/octet-stream")

_log = logging.getLogger(__name__)

router = APIRouter(tags=["Empresas"])


@router.post("/api/v1/constancia/parsear", tags=["Constancia"])
async def parsear_constancia_pdf(
    archivo: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """Extrae datos fiscales de la Constancia de Situación Fiscal (PDF SAT).

    El PDF se procesa en memoria y no se conserva: nada en la app lo consulta
    después, y guardarlo dejaba datos fiscales de terceros en disco sin dueño.
    """
    contenido = await archivo.read()
    validar_upload(archivo, contenido, _CONSTANCIA_EXTENSIONES, _CONSTANCIA_CONTENT_TYPES)

    try:
        from ..constancia_parser import parsear_constancia
        datos = parsear_constancia(contenido)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"No se pudo leer el PDF: {str(e)}")

    return datos


@router.get("/api/v1/empresas")
async def listar_empresas(current_user: dict = Depends(get_current_user)):
    """Retorna las empresas que administra el contador autenticado."""
    rows = db.query_all(
        """
        SELECT e.* FROM empresas e
        JOIN usuario_empresas ue ON ue.empresa_id = e.id
        WHERE ue.usuario_id = %s AND e.activo = TRUE
        ORDER BY ue.created_at ASC
        """,
        (current_user["user_id"],),
    )
    return [serializar(r) for r in rows]


@router.post("/api/v1/mis-empresas", status_code=status.HTTP_201_CREATED)
async def agregar_empresa(
    data: AgregarEmpresaRequest,
    current_user: dict = Depends(get_current_user),
):
    """Crea una empresa y la vincula al contador autenticado.

    Si el RFC ya está registrado solo responde con éxito cuando el usuario ya
    estaba vinculado (idempotente). Conocer un RFC no da derecho a ver los datos
    de esa empresa: vincularse a una empresa existente se rechaza con 409.
    """
    empresa = db.query_one("SELECT * FROM empresas WHERE rfc = %s", (data.rfc,))
    creada = False

    if not empresa:
        try:
            empresa = db.execute(
                """
                INSERT INTO empresas (
                    rfc, razon_social, regimen_fiscal, cp_fiscal, curp, obligaciones,
                    representante_legal, rfc_representante
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    data.rfc, data.razon_social, data.regimen_fiscal,
                    data.cp_fiscal, data.curp,
                    json.dumps(data.obligaciones) if data.obligaciones else None,
                    data.representante_legal,
                    data.rfc_representante,
                ),
                returning=True,
            )
            creada = True
        except psycopg2.errors.UniqueViolation:
            # Otra petición la creó entre el SELECT y el INSERT: ya no es nuestra.
            empresa = db.query_one("SELECT * FROM empresas WHERE rfc = %s", (data.rfc,))

    ya_vinculada = db.query_one(
        "SELECT 1 FROM usuario_empresas WHERE usuario_id = %s AND empresa_id = %s",
        (current_user["user_id"], str(empresa["id"])),
    )
    if not ya_vinculada:
        if not creada:
            _log.warning(
                "Intento de vincular empresa existente: usuario=%s rfc=%s",
                current_user["user_id"], data.rfc,
            )
            raise HTTPException(
                status_code=409,
                detail="Ya existe una empresa registrada con ese RFC. "
                       "Solicita acceso a quien la administra.",
            )
        db.execute(
            "INSERT INTO usuario_empresas (usuario_id, empresa_id) VALUES (%s, %s)",
            (current_user["user_id"], str(empresa["id"])),
        )

    return {
        "mensaje":    "Empresa vinculada correctamente",
        "empresa_id": str(empresa["id"]),
        "rfc":        empresa["rfc"],
        "razon_social": empresa["razon_social"],
    }


@router.get("/api/v1/empresas/{empresa_id}")
async def obtener_empresa(empresa_id: str, current_user: dict = Depends(get_current_user)):
    validar_acceso_empresa(empresa_id, current_user)
    return serializar(empresa_or_404(empresa_id))


@router.patch("/api/v1/empresas/{empresa_id}/impuestos")
async def actualizar_impuestos(
    empresa_id: str,
    body: ImpuestosRequest,
    current_user: dict = Depends(get_current_user),
):
    """Actualiza la lista de impuestos a declarar para una empresa."""
    validar_acceso_empresa(empresa_id, current_user)
    empresa_or_404(empresa_id)
    db.execute(
        "UPDATE empresas SET impuestos_declarar = %s::jsonb WHERE id = %s",
        (json.dumps(body.impuestos), empresa_id),
    )
    return {"ok": True, "impuestos": body.impuestos}
