"""Criterio de efectivo de la empresa (spec 2026-10-13): consulta y cambio, solo para administradores."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import criterio_efectivo, db, usuarios_empresa
from ..deps import get_current_user, validar_acceso_empresa

router = APIRouter(tags=["Criterio de efectivo"])

_RUTA = "/api/v1/empresas/{empresa_id}/criterio-efectivo"


class CriterioIn(BaseModel):
    criterio: Literal["legal", "estricto"]


def _rol_plataforma(usuario_id: str):
    return (db.query_one("SELECT rol FROM usuarios WHERE id = %s", (usuario_id,)) or {}).get("rol")


def _roles_de_empresa(empresa_id: str) -> dict:
    miembros = db.query_all(
        "SELECT usuario_id, rol, created_at FROM usuario_empresas WHERE empresa_id = %s", (empresa_id,))
    return usuarios_empresa.roles_efectivos(miembros)


def _respuesta(criterio: str) -> dict:
    return {"criterio_efectivo": criterio, "umbral_efectivo": float(criterio_efectivo.umbral(criterio))}


@router.get(_RUTA)
async def leer_criterio(empresa_id: str, current_user: dict = Depends(get_current_user)):
    """Criterio de efectivo vigente de la empresa y el umbral que implica."""
    validar_acceso_empresa(empresa_id, current_user)
    return _respuesta(criterio_efectivo.leer(empresa_id))


@router.put(_RUTA)
async def cambiar_criterio(empresa_id: str, datos: CriterioIn, current_user: dict = Depends(get_current_user)):
    """Cambia el criterio de efectivo (``legal`` o ``estricto``) y lo audita. Solo administradores."""
    validar_acceso_empresa(empresa_id, current_user)
    usuario_id = current_user["user_id"]
    if not usuarios_empresa.puede_administrar(usuario_id, _roles_de_empresa(empresa_id), _rol_plataforma(usuario_id)):
        raise HTTPException(status_code=403, detail="Solo un administrador de la empresa puede cambiar el criterio de efectivo")
    try:
        resultado = criterio_efectivo.guardar(empresa_id, datos.criterio, usuario_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    return _respuesta(resultado["criterio_efectivo"])
