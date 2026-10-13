"""Lista 69-B del SAT: estado visible para todos y administración (importar / subir) solo para administradores
de la plataforma (spec 2026-10-13-efos-69b-design)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from .. import auditoria, efos, efos_datos
from ..deps import get_current_user, require_admin, validar_upload

router = APIRouter(tags=["EFOS (69-B)"])

_EXTENSIONES = (".csv",)
_CONTENT_TYPES = ("text/csv", "application/csv", "application/vnd.ms-excel", "text/plain", "application/octet-stream")


def _importar(contenido: bytes, usuario_id: str, via: str) -> dict:
    try:
        resultado = efos_datos.importar(contenido, "manual", usuario_id)
    except efos.ErrorImportacion as exc:
        auditoria.registrar_evento(usuario_id, "efos_importacion_fallida", entidad="efos", metadata={"via": via, "motivo": str(exc)})
        raise HTTPException(status_code=422, detail=str(exc))
    auditoria.registrar_evento(usuario_id, "efos_importado", entidad="efos", metadata={"via": via, **resultado})
    return resultado


@router.get("/api/v1/efos/estado")
async def estado_lista(current_user: dict = Depends(get_current_user)):
    """Fecha del archivo del SAT, de la última importación y si la lista está desactualizada (más de 45 días)."""
    return efos_datos.estado()


@router.post("/api/v1/admin/efos/importar")
async def forzar_importacion(admin: dict = Depends(require_admin)):
    """Descarga ahora la lista del SAT e importa. Solo administradores de la plataforma."""
    try:
        contenido = efos_datos.descargar()
    except efos.ErrorImportacion as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        efos_datos._registrar("manual", admin["user_id"], "fallida", f"No se pudo descargar: {exc}")
        raise HTTPException(status_code=502, detail=f"No se pudo descargar la lista del SAT: {exc}")
    return _importar(contenido, admin["user_id"], "descarga")


@router.post("/api/v1/admin/efos/subir")
async def subir_lista(archivo: UploadFile = File(...), admin: dict = Depends(require_admin)):
    """Importa un CSV subido a mano (respaldo si el SAT cambia la URL o va desfasado). Solo administradores."""
    contenido = await archivo.read()
    validar_upload(archivo, contenido, _EXTENSIONES, _CONTENT_TYPES, max_bytes=efos.MAX_BYTES)
    return _importar(contenido, admin["user_id"], "subida")
