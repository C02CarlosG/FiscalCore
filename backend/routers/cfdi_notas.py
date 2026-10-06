"""Etiquetas, comentarios y evidencias de los CFDI (F3.6). La lógica vive en
``cfdi_notas``; aquí se validan permisos, se traducen los errores y se deja
constancia en la auditoría de lo que modifica o descarga archivos."""
from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response

from .. import cfdi_notas
from ..auditoria import registrar_evento
from ..deps import get_current_user, validar_acceso_empresa

router = APIRouter(tags=["CFDI"])

_BASE = "/api/v1/empresas/{empresa_id}"

_ERRORES = (
    (cfdi_notas.NoEncontrado, 404),
    (cfdi_notas.SinPermiso, 403),
    (cfdi_notas.Excede, 413),
    (cfdi_notas.Conflicto, 409),
    (cfdi_notas.Invalido, 422),
)


def _traducir(exc: Exception) -> HTTPException:
    for clase, codigo in _ERRORES:
        if isinstance(exc, clase):
            return HTTPException(status_code=codigo, detail=str(exc))
    raise exc


def _acceso(empresa_id: str, current_user: dict) -> str:
    validar_acceso_empresa(empresa_id, current_user)
    return str(current_user["user_id"])


# --- Etiquetas -------------------------------------------------------------

@router.get(_BASE + "/etiquetas")
async def listar_etiquetas(empresa_id: str, current_user: dict = Depends(get_current_user)):
    """Catálogo de etiquetas de la empresa, con cuántos CFDI tiene cada una."""
    _acceso(empresa_id, current_user)
    return {"items": cfdi_notas.listar_etiquetas(empresa_id)}


@router.post(_BASE + "/etiquetas", status_code=201)
async def crear_etiqueta(empresa_id: str, datos: dict = Body(...), current_user: dict = Depends(get_current_user)):
    usuario_id = _acceso(empresa_id, current_user)
    try:
        etiqueta = cfdi_notas.crear_etiqueta(empresa_id, datos.get("nombre"), datos.get("color", "#64748b"))
    except (cfdi_notas.Invalido, cfdi_notas.Excede, cfdi_notas.Conflicto) as exc:
        raise _traducir(exc)
    registrar_evento(usuario_id, "etiqueta_creada", empresa_id=empresa_id, entidad="etiqueta",
                     entidad_id=etiqueta["id"], metadata={"nombre": etiqueta["nombre"]})
    return etiqueta


@router.patch(_BASE + "/etiquetas/{etiqueta_id}")
async def editar_etiqueta(empresa_id: str, etiqueta_id: str, datos: dict = Body(...),
                          current_user: dict = Depends(get_current_user)):
    usuario_id = _acceso(empresa_id, current_user)
    try:
        etiqueta = cfdi_notas.editar_etiqueta(empresa_id, etiqueta_id, datos.get("nombre"), datos.get("color"))
    except Exception as exc:
        raise _traducir(exc)
    registrar_evento(usuario_id, "etiqueta_editada", empresa_id=empresa_id, entidad="etiqueta", entidad_id=etiqueta["id"])
    return etiqueta


@router.delete(_BASE + "/etiquetas/{etiqueta_id}", status_code=204)
async def borrar_etiqueta(empresa_id: str, etiqueta_id: str, current_user: dict = Depends(get_current_user)):
    usuario_id = _acceso(empresa_id, current_user)
    try:
        borrada = cfdi_notas.borrar_etiqueta(empresa_id, etiqueta_id)
    except Exception as exc:
        raise _traducir(exc)
    registrar_evento(usuario_id, "etiqueta_borrada", empresa_id=empresa_id, entidad="etiqueta",
                     entidad_id=borrada["id"], metadata={"nombre": borrada["nombre"]})
    return Response(status_code=204)


@router.post(_BASE + "/cfdis/etiquetas/lote")
async def etiquetar_lote(empresa_id: str, datos: dict = Body(...), current_user: dict = Depends(get_current_user)):
    """Agrega o quita etiquetas a hasta 500 CFDI. Los UUID que no son de la empresa se ignoran."""
    usuario_id = _acceso(empresa_id, current_user)
    try:
        resultado = cfdi_notas.etiquetar_lote(
            empresa_id, usuario_id, datos.get("uuids"), datos.get("agregar"), datos.get("quitar"))
    except Exception as exc:
        raise _traducir(exc)
    registrar_evento(usuario_id, "cfdi_etiquetas_lote", empresa_id=empresa_id,
                     metadata={**resultado, "agregar": datos.get("agregar") or [], "quitar": datos.get("quitar") or []})
    return resultado


@router.get(_BASE + "/cfdis/{uuid}/etiquetas")
async def etiquetas_del_cfdi(empresa_id: str, uuid: str, current_user: dict = Depends(get_current_user)):
    _acceso(empresa_id, current_user)
    try:
        return {"items": cfdi_notas.etiquetas_de(empresa_id, uuid)}
    except Exception as exc:
        raise _traducir(exc)


# --- Comentarios -----------------------------------------------------------

@router.get(_BASE + "/cfdis/{uuid}/comentarios")
async def listar_comentarios(empresa_id: str, uuid: str, current_user: dict = Depends(get_current_user)):
    usuario_id = _acceso(empresa_id, current_user)
    try:
        return {"items": cfdi_notas.listar_comentarios(empresa_id, usuario_id, uuid)}
    except Exception as exc:
        raise _traducir(exc)


@router.post(_BASE + "/cfdis/{uuid}/comentarios", status_code=201)
async def crear_comentario(empresa_id: str, uuid: str, datos: dict = Body(...),
                           current_user: dict = Depends(get_current_user)):
    usuario_id = _acceso(empresa_id, current_user)
    try:
        comentario = cfdi_notas.crear_comentario(empresa_id, usuario_id, uuid, datos.get("texto"))
    except Exception as exc:
        raise _traducir(exc)
    registrar_evento(usuario_id, "cfdi_comentario_creado", empresa_id=empresa_id, entidad="cfdi", entidad_id=uuid)
    return comentario


@router.delete(_BASE + "/cfdis/{uuid}/comentarios/{comentario_id}", status_code=204)
async def borrar_comentario(empresa_id: str, uuid: str, comentario_id: str,
                            current_user: dict = Depends(get_current_user)):
    usuario_id = _acceso(empresa_id, current_user)
    try:
        cfdi_notas.borrar_comentario(empresa_id, usuario_id, uuid, comentario_id)
    except Exception as exc:
        raise _traducir(exc)
    registrar_evento(usuario_id, "cfdi_comentario_borrado", empresa_id=empresa_id, entidad="cfdi", entidad_id=uuid)
    return Response(status_code=204)


# --- Evidencias ------------------------------------------------------------

@router.get(_BASE + "/cfdis/{uuid}/evidencias")
async def listar_evidencias(empresa_id: str, uuid: str, current_user: dict = Depends(get_current_user)):
    """Metadatos de las evidencias del CFDI; el contenido solo viaja en la descarga."""
    usuario_id = _acceso(empresa_id, current_user)
    try:
        return {"items": cfdi_notas.listar_evidencias(empresa_id, usuario_id, uuid)}
    except Exception as exc:
        raise _traducir(exc)


@router.post(_BASE + "/cfdis/{uuid}/evidencias", status_code=201)
async def subir_evidencia(empresa_id: str, uuid: str, archivo: UploadFile = File(...),
                          current_user: dict = Depends(get_current_user)):
    """Adjunta un archivo (PDF, imagen, XLSX, XML, TXT o CSV de hasta 5 MB). El tipo se
    decide por el contenido, no por lo que declare el cliente."""
    usuario_id = _acceso(empresa_id, current_user)
    # Se lee un byte de más para distinguir "justo en el tope" de "pasa el tope" sin cargar archivos enormes.
    contenido = await archivo.read(cfdi_notas.MAX_EVIDENCIA_BYTES + 1)
    try:
        evidencia = cfdi_notas.subir_evidencia(empresa_id, usuario_id, uuid, archivo.filename, contenido)
    except Exception as exc:
        raise _traducir(exc)
    registrar_evento(usuario_id, "cfdi_evidencia_subida", empresa_id=empresa_id, entidad="cfdi", entidad_id=uuid,
                     metadata={"evidencia_id": evidencia["id"], "nombre": evidencia["nombre"], "tamano": evidencia["tamano"]})
    return evidencia


@router.get(_BASE + "/cfdis/{uuid}/evidencias/{evidencia_id}")
async def descargar_evidencia(empresa_id: str, uuid: str, evidencia_id: str,
                              current_user: dict = Depends(get_current_user)):
    """Descarga siempre como adjunto: la evidencia nunca se muestra en línea desde el dominio de la API."""
    usuario_id = _acceso(empresa_id, current_user)
    try:
        archivo = cfdi_notas.descargar_evidencia(empresa_id, uuid, evidencia_id)
    except Exception as exc:
        raise _traducir(exc)
    registrar_evento(usuario_id, "cfdi_evidencia_descargada", empresa_id=empresa_id, entidad="cfdi", entidad_id=uuid,
                     metadata={"evidencia_id": evidencia_id, "nombre": archivo["nombre"]})
    return Response(
        content=archivo["contenido"],
        media_type=archivo["tipo"],
        headers={
            "Content-Disposition": f'attachment; filename="{archivo["nombre"]}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.delete(_BASE + "/cfdis/{uuid}/evidencias/{evidencia_id}", status_code=204)
async def borrar_evidencia(empresa_id: str, uuid: str, evidencia_id: str,
                           current_user: dict = Depends(get_current_user)):
    usuario_id = _acceso(empresa_id, current_user)
    try:
        borrada = cfdi_notas.borrar_evidencia(empresa_id, usuario_id, uuid, evidencia_id)
    except Exception as exc:
        raise _traducir(exc)
    registrar_evento(usuario_id, "cfdi_evidencia_borrada", empresa_id=empresa_id, entidad="cfdi", entidad_id=uuid,
                     metadata={"evidencia_id": borrada["id"], "nombre": borrada["nombre"]})
    return Response(status_code=204)
