"""
Router de información fiscal (F8, carril D): constancia de situación fiscal y opinión
del cumplimiento de obligaciones fiscales, cargadas a mano en PDF por empresa
(decisión D4). Las reglas viven en `backend/informacion_fiscal.py`; aquí solo se
valida el acceso, se guarda y se entrega el PDF.

NOTA: sin `from __future__ import annotations`: la carga va envuelta por
@limiter.limit (slowapi) y FastAPI no resolvería los forward-refs (ver routers/sat.py).
"""
import hashlib
import os
import uuid
from datetime import date
from typing import Optional
from urllib.parse import quote

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool

from .. import db
from .. import informacion_fiscal as inf
from ..auditoria import registrar_evento
from ..deps import get_current_user, limiter, validar_acceso_empresa, validar_upload

router = APIRouter(
    prefix="/api/v1/informacion-fiscal/empresas/{empresa_id}",
    tags=["Información fiscal"],
)

_EXTENSIONES = (".pdf",)
_CONTENT_TYPES = ("application/pdf", "application/octet-stream")
_COLUMNAS = "id, tipo, nombre_archivo, tamano_bytes, rfc, fecha_emision, datos, created_at"


def _hoy() -> date:
    return inf.hoy_mexico()


def _tipo(tipo: str) -> str:
    if tipo not in inf.TIPOS:
        raise HTTPException(status_code=422, detail="tipo debe ser 'constancia' u 'opinion'")
    return tipo


def _empresa(empresa_id: uuid.UUID, current_user: dict) -> dict:
    validar_acceso_empresa(str(empresa_id), current_user)
    empresa = db.query_one("SELECT id, rfc FROM empresas WHERE id = %s", (str(empresa_id),))
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    return empresa


def _documento(fila: dict) -> dict:
    """Fila de la tabla (sin el PDF) más la antigüedad y, en la opinión, su vigencia."""
    fecha = fila.get("fecha_emision")
    hoy = _hoy()
    datos = fila.get("datos") or {}
    vigencia = (
        inf.estado_opinion(fecha, datos.get("sentido"), hoy) if fila["tipo"] == "opinion"
        else {"vigente_hasta": None, "vigente": None, "motivo": None}
    )
    return {
        "id": str(fila["id"]),
        "tipo": fila["tipo"],
        "nombre_archivo": fila["nombre_archivo"],
        "tamano_bytes": fila["tamano_bytes"],
        "rfc": fila["rfc"],
        "fecha_emision": fecha.isoformat() if fecha else None,
        "created_at": fila["created_at"].isoformat(),
        "datos": datos,
        "antiguedad_dias": inf.antiguedad_dias(fecha, hoy),
        **vigencia,
    }


def _nombre_seguro(nombre: Optional[str]) -> str:
    base = os.path.basename((nombre or "").replace("\\", "/")).strip()
    return (base or "documento.pdf")[:255]


@router.get("")
async def resumen(empresa_id: uuid.UUID, current_user: dict = Depends(get_current_user)):
    """Último documento de cada tipo, o ``null`` si nunca se ha subido."""
    _empresa(empresa_id, current_user)
    filas = db.query_all(
        f"""
        SELECT DISTINCT ON (tipo) {_COLUMNAS}
        FROM documentos_fiscales
        WHERE empresa_id = %s
        ORDER BY tipo, created_at DESC
        """,
        (str(empresa_id),),
    )
    resultado = {tipo: None for tipo in inf.TIPOS}
    for fila in filas:
        resultado[fila["tipo"]] = _documento(fila)
    return resultado


@router.get("/documentos")
async def historial(
    empresa_id: uuid.UUID,
    tipo: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """Documentos subidos (sin el PDF), del más reciente al más antiguo."""
    _empresa(empresa_id, current_user)
    if tipo is None:
        filas = db.query_all(
            f"SELECT {_COLUMNAS} FROM documentos_fiscales WHERE empresa_id = %s ORDER BY created_at DESC",
            (str(empresa_id),),
        )
    else:
        filas = db.query_all(
            f"SELECT {_COLUMNAS} FROM documentos_fiscales WHERE empresa_id = %s AND tipo = %s "
            "ORDER BY created_at DESC",
            (str(empresa_id), _tipo(tipo)),
        )
    return [_documento(f) for f in filas]


@router.post("/documentos/{tipo}", status_code=201)
@limiter.limit("20/minute")  # leer el PDF cuesta CPU; una carga normal es esporádica
async def subir(
    request: Request,
    empresa_id: uuid.UUID,
    tipo: str,
    archivo: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """Valida el PDF (tipo, tamaño, que sea del tipo indicado y del RFC de la empresa) y lo guarda."""
    empresa = _empresa(empresa_id, current_user)
    tipo = _tipo(tipo)
    # Se lee un byte de más para saber si excede el tope sin cargar archivos enormes.
    contenido = await archivo.read(inf.MAX_BYTES + 1)
    validar_upload(archivo, contenido, _EXTENSIONES, _CONTENT_TYPES, max_bytes=inf.MAX_BYTES)

    try:
        # pdfplumber es CPU intensivo: fuera del event loop para no congelar el worker.
        leido = await run_in_threadpool(inf.analizar_documento, tipo, contenido, empresa["rfc"], _hoy())
    except inf.DocumentoInvalido as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        fila = db.execute(
            f"""
            INSERT INTO documentos_fiscales
                (empresa_id, tipo, nombre_archivo, contenido, tamano_bytes, sha256, rfc,
                 fecha_emision, datos, usuario_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING {_COLUMNAS}
            """,
            (
                str(empresa_id), tipo, _nombre_seguro(archivo.filename),
                contenido, len(contenido),
                hashlib.sha256(contenido).hexdigest(), leido["rfc"], leido["fecha_emision"],
                psycopg2.extras.Json(leido["datos"]), current_user["user_id"],
            ),
            returning=True,
        )
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="Este documento ya está cargado para la empresa.")

    registrar_evento(
        current_user["user_id"], "informacion_fiscal.subir", empresa_id=str(empresa_id),
        entidad="documento_fiscal", entidad_id=str(fila["id"]),
        metadata={"tipo": tipo, "fecha_emision": leido["fecha_emision"]},
    )
    return _documento(fila)


@router.get("/documentos/{documento_id}/pdf")
async def pdf(
    empresa_id: uuid.UUID,
    documento_id: uuid.UUID,
    descargar: bool = False,
    current_user: dict = Depends(get_current_user),
):
    """El PDF tal como se subió: ``inline`` para el visor, ``attachment`` para descargar."""
    _empresa(empresa_id, current_user)
    fila = db.query_one(
        "SELECT nombre_archivo, contenido FROM documentos_fiscales WHERE id = %s AND empresa_id = %s",
        (str(documento_id), str(empresa_id)),
    )
    if not fila:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    modo = "attachment" if descargar else "inline"
    nombre = quote(fila["nombre_archivo"])
    return Response(
        content=bytes(fila["contenido"]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"{modo}; filename*=UTF-8''{nombre}",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
            # Si alguien abre la URL directo, el PDF no puede ejecutar scripts en el origen de la API.
            "Content-Security-Policy": "sandbox",
        },
    )


@router.delete("/documentos/{documento_id}", status_code=204)
async def eliminar(
    empresa_id: uuid.UUID,
    documento_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
):
    _empresa(empresa_id, current_user)
    fila = db.execute(
        "DELETE FROM documentos_fiscales WHERE id = %s AND empresa_id = %s RETURNING id",
        (str(documento_id), str(empresa_id)),
        returning=True,
    )
    if not fila:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    registrar_evento(
        current_user["user_id"], "informacion_fiscal.eliminar", empresa_id=str(empresa_id),
        entidad="documento_fiscal", entidad_id=str(documento_id),
    )
    return Response(status_code=204)
