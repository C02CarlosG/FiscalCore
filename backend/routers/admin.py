from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from .. import db
from ..deps import require_admin, serializar

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


class ActualizarUsuarioRequest(BaseModel):
    activo: Optional[bool] = None
    rol: Optional[str] = None


@router.get("/usuarios")
async def listar_usuarios(admin: dict = Depends(require_admin)):
    """Lista todos los usuarios de la plataforma con sus empresas."""
    usuarios = db.query_all(
        """
        SELECT u.id, u.email, u.nombre, u.rol, u.activo, u.created_at,
               COALESCE(
                   json_agg(
                       json_build_object('empresa_id', e.id, 'rfc', e.rfc, 'razon_social', e.razon_social)
                   ) FILTER (WHERE e.id IS NOT NULL),
                   '[]'
               ) AS empresas
        FROM usuarios u
        LEFT JOIN usuario_empresas ue ON ue.usuario_id = u.id
        LEFT JOIN empresas e ON e.id = ue.empresa_id AND e.activo = TRUE
        GROUP BY u.id
        ORDER BY u.created_at ASC
        """
    )
    return [serializar(u) for u in usuarios]


@router.patch("/usuarios/{user_id}")
async def actualizar_usuario(
    user_id: str,
    data: ActualizarUsuarioRequest,
    admin: dict = Depends(require_admin),
):
    """Activa/desactiva un usuario o cambia su rol."""
    if admin["user_id"] == user_id and data.rol is not None and data.rol != "admin":
        raise HTTPException(status_code=400, detail="No puedes quitarte el rol admin")

    campos = {k: v for k, v in data.model_dump().items() if v is not None}
    if not campos:
        raise HTTPException(status_code=400, detail="Sin campos para actualizar")

    if "rol" in campos and campos["rol"] not in ("admin", "contador"):
        raise HTTPException(status_code=400, detail="Rol inválido: usa 'admin' o 'contador'")

    sets = ", ".join(f"{k} = %s" for k in campos)
    valores = list(campos.values()) + [user_id]
    usuario = db.execute(
        f"UPDATE usuarios SET {sets} WHERE id = %s RETURNING id, email, nombre, rol, activo",
        tuple(valores),
        returning=True,
    )
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return serializar(usuario)


@router.get("/stats")
async def estadisticas(admin: dict = Depends(require_admin)):
    """Estadísticas generales de la plataforma."""
    totales = db.query_one(
        """
        SELECT
            (SELECT COUNT(*) FROM usuarios WHERE activo = TRUE)  AS usuarios_activos,
            (SELECT COUNT(*) FROM usuarios WHERE rol = 'admin')  AS admins,
            (SELECT COUNT(*) FROM empresas  WHERE activo = TRUE) AS empresas_activas,
            (SELECT COUNT(*) FROM cfdi)                          AS cfdi_total
        """
    )
    return serializar(totales) if totales else {}
