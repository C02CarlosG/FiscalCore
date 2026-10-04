"""Preferencias de tabla por usuario: orden y visibilidad de columnas. Lo que se guarda
es solo una lista de {clave, visible}; qué columnas existen lo decide el catálogo, así
que las claves desconocidas se ignoran en el cliente y nunca rompen la lectura."""
from __future__ import annotations

import re
from typing import List

import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import db
from ..deps import get_current_user

router = APIRouter(tags=["Preferencias"])

_VISTA_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,79}$")
_CLAVE_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
MAX_COLUMNAS = 200


class ColumnaPreferida(BaseModel):
    clave: str
    visible: bool


class PreferenciaTabla(BaseModel):
    columnas: List[ColumnaPreferida] = Field(..., max_length=MAX_COLUMNAS)


def _vista(vista: str) -> str:
    if not _VISTA_RE.fullmatch(vista):
        raise HTTPException(status_code=422, detail="vista inválida")
    return vista


@router.get("/api/v1/preferencias/tablas/{vista}")
async def leer_preferencia(vista: str, current_user: dict = Depends(get_current_user)):
    """Columnas guardadas para la vista, o ``{"columnas": null}`` si no hay."""
    fila = db.query_one(
        "SELECT config FROM preferencias_tabla WHERE usuario_id = %s AND vista = %s",
        (current_user["user_id"], _vista(vista)),
    )
    config = (fila or {}).get("config") or {}
    return {"columnas": config.get("columnas")}


@router.put("/api/v1/preferencias/tablas/{vista}")
async def guardar_preferencia(
    vista: str, cuerpo: PreferenciaTabla, current_user: dict = Depends(get_current_user)
):
    vista = _vista(vista)
    claves = [c.clave for c in cuerpo.columnas]
    if any(not _CLAVE_RE.fullmatch(k) for k in claves) or len(set(claves)) != len(claves):
        raise HTTPException(status_code=422, detail="Claves de columna inválidas o repetidas")
    columnas = [c.model_dump() for c in cuerpo.columnas]
    db.execute(
        """
        INSERT INTO preferencias_tabla (usuario_id, vista, config, updated_at)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (usuario_id, vista)
        DO UPDATE SET config = EXCLUDED.config, updated_at = NOW()
        """,
        (current_user["user_id"], vista, psycopg2.extras.Json({"columnas": columnas})),
    )
    return {"columnas": columnas}


@router.delete("/api/v1/preferencias/tablas/{vista}", status_code=204)
async def restablecer_preferencia(vista: str, current_user: dict = Depends(get_current_user)):
    """Vuelve al orden y la visibilidad del catálogo."""
    db.execute(
        "DELETE FROM preferencias_tabla WHERE usuario_id = %s AND vista = %s",
        (current_user["user_id"], _vista(vista)),
    )
