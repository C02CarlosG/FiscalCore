from __future__ import annotations

import json
import logging
import uuid as _uuid
from pathlib import Path
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

UPLOADS_DIR = Path("uploads/constancias")
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/api/v1/constancia/parsear", tags=["Constancia"])
async def parsear_constancia_pdf(archivo: UploadFile = File(...)):
    """Extrae datos fiscales de la Constancia de Situación Fiscal (PDF SAT)."""
    contenido = await archivo.read()
    validar_upload(archivo, contenido, _CONSTANCIA_EXTENSIONES, _CONSTANCIA_CONTENT_TYPES)

    try:
        from ..constancia_parser import parsear_constancia
        datos = parsear_constancia(contenido)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"No se pudo leer el PDF: {str(e)}")

    # Guardar PDF
    nombre_archivo = f"{_uuid.uuid4()}.pdf"
    ruta = UPLOADS_DIR / nombre_archivo
    ruta.write_bytes(contenido)
    datos["constancia_path"] = nombre_archivo

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
    """Crea (o encuentra por RFC) una empresa y la vincula al contador autenticado."""
    # Si ya existe empresa con ese RFC, reutilizarla
    empresa = db.query_one("SELECT * FROM empresas WHERE rfc = %s", (data.rfc,))

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
        except psycopg2.errors.UniqueViolation:
            empresa = db.query_one("SELECT * FROM empresas WHERE rfc = %s", (data.rfc,))

    # Vincular al usuario (idempotente)
    ya_vinculada = db.query_one(
        "SELECT 1 FROM usuario_empresas WHERE usuario_id = %s AND empresa_id = %s",
        (current_user["user_id"], str(empresa["id"])),
    )
    if not ya_vinculada:
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
