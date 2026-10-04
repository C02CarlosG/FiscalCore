"""
Router de cuenta (U1, carril D): cambio de contraseña y usuarios de una empresa con
su rol. El perfil se edita con `GET /auth/me` y `PATCH /usuarios/perfil` (carril B).
Las reglas viven en `backend/usuarios_empresa.py`.

NOTA: sin `from __future__ import annotations`: el cambio de contraseña va envuelto
por @limiter.limit (slowapi) y FastAPI no resolvería los forward-refs (ver routers/sat.py).
"""
import uuid
from typing import Optional

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from .. import db
from .. import usuarios_empresa as ue
from ..auditoria import registrar_evento
from ..deps import get_current_user, hash_password, limiter, validar_acceso_empresa, verify_password

router = APIRouter(prefix="/api/v1/cuenta", tags=["Cuenta"])


class CambioContrasena(BaseModel):
    actual: str
    nueva: str


class AltaUsuario(BaseModel):
    email: str
    rol: str
    nombre: Optional[str] = None
    password_temporal: Optional[str] = None


class CambioRol(BaseModel):
    rol: str


def _422(e: Exception):
    return HTTPException(status_code=422, detail=str(e))


# ─── Contraseña ──────────────────────────────────────────────────────────────

@router.post("/contrasena", status_code=204)
@limiter.limit("5/minute")  # exige la contraseña actual: mismo cuidado que el login
async def cambiar_contrasena(
    request: Request,
    cuerpo: CambioContrasena,
    current_user: dict = Depends(get_current_user),
):
    usuario = db.query_one("SELECT password_hash FROM usuarios WHERE id = %s", (current_user["user_id"],))
    if not usuario or not verify_password(cuerpo.actual, usuario["password_hash"]):
        raise HTTPException(status_code=400, detail="La contraseña actual no es correcta")
    try:
        ue.validar_contrasena(cuerpo.nueva, actual=cuerpo.actual)
    except ue.DatoInvalido as e:
        raise _422(e)
    db.execute(
        "UPDATE usuarios SET password_hash = %s, updated_at = NOW() WHERE id = %s",
        (hash_password(cuerpo.nueva), current_user["user_id"]),
    )
    registrar_evento(current_user["user_id"], "cuenta.cambiar_contrasena", entidad="usuario",
                     entidad_id=current_user["user_id"])
    return Response(status_code=204)


# ─── Usuarios de una empresa ─────────────────────────────────────────────────

def _miembros(empresa_id: str) -> list[dict]:
    return db.query_all(
        """
        SELECT ue.usuario_id, ue.rol, ue.created_at, u.email, u.nombre
        FROM usuario_empresas ue
        JOIN usuarios u ON u.id = ue.usuario_id
        WHERE ue.empresa_id = %s
        ORDER BY ue.created_at, ue.usuario_id
        """,
        (empresa_id,),
    )


def _contexto(empresa_id: uuid.UUID, current_user: dict) -> tuple[str, list[dict], dict, bool]:
    """Valida el acceso y devuelve (empresa_id, miembros, roles efectivos, puede administrar)."""
    eid = str(empresa_id)
    yo = db.query_one("SELECT rol FROM usuarios WHERE id = %s", (current_user["user_id"],)) or {}
    rol_plataforma = yo.get("rol")
    if rol_plataforma != "admin":
        validar_acceso_empresa(eid, current_user)
    if not db.query_one("SELECT id FROM empresas WHERE id = %s", (eid,)):
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    miembros = _miembros(eid)
    roles = ue.roles_efectivos(miembros)
    return eid, miembros, roles, ue.puede_administrar(current_user["user_id"], roles, rol_plataforma)


def _fijar_administradores(eid: str, miembros: list[dict], roles: dict) -> None:
    """Guarda como explícito al administrador implícito (primer vinculado sin marcar).

    Sin esto, al dar de alta o promover a otro administrador, el creador dejaría de
    serlo: la regla del primer vinculado solo aplica cuando no hay ninguno marcado.
    """
    for m in miembros:
        uid = str(m["usuario_id"])
        if roles.get(uid) == "administrador" and m["rol"] != "administrador":
            db.execute("UPDATE usuario_empresas SET rol = 'administrador' WHERE empresa_id = %s AND usuario_id = %s",
                       (eid, uid))


def _exigir_administrador(puede: bool) -> None:
    if not puede:
        raise HTTPException(status_code=403, detail="Solo un administrador de la empresa puede gestionar usuarios")


def _usuario(m: dict, roles: dict, yo: str) -> dict:
    uid = str(m["usuario_id"])
    return {
        "usuario_id": uid, "email": m["email"], "nombre": m.get("nombre"),
        "rol": roles.get(uid, m.get("rol")), "desde": m["created_at"].isoformat() if m.get("created_at") else None,
        "soy_yo": uid == str(yo),
    }


@router.get("/empresas/{empresa_id}/usuarios")
async def listar_usuarios(empresa_id: uuid.UUID, current_user: dict = Depends(get_current_user)):
    _eid, miembros, roles, puede = _contexto(empresa_id, current_user)
    yo = current_user["user_id"]
    return {
        "mi_rol": roles.get(str(yo)),
        "puede_administrar": puede,
        "usuarios": [_usuario(m, roles, yo) for m in miembros],
    }


@router.post("/empresas/{empresa_id}/usuarios", status_code=201)
async def alta_usuario(empresa_id: uuid.UUID, cuerpo: AltaUsuario, current_user: dict = Depends(get_current_user)):
    """Vincula una cuenta existente o crea una nueva con contraseña temporal."""
    eid, miembros, roles, puede = _contexto(empresa_id, current_user)
    _exigir_administrador(puede)
    try:
        email = ue.normalizar_correo(cuerpo.email)
        rol = ue.validar_rol(cuerpo.rol)
    except ue.DatoInvalido as e:
        raise _422(e)

    existente = db.query_one("SELECT id FROM usuarios WHERE LOWER(email) = %s", (email,))
    cuenta_creada = existente is None
    if cuenta_creada:
        nombre = (cuerpo.nombre or "").strip()
        if not nombre:
            raise HTTPException(status_code=422, detail="El nombre es obligatorio para crear la cuenta")
        try:
            ue.validar_contrasena(cuerpo.password_temporal)
        except ue.DatoInvalido as e:
            raise _422(e)
        password_hash = hash_password(cuerpo.password_temporal)

    _fijar_administradores(eid, miembros, roles)
    try:
        with db.get_conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if cuenta_creada:
                cur.execute(
                    "INSERT INTO usuarios (email, password_hash, nombre) VALUES (%s, %s, %s) RETURNING id",
                    (email, password_hash, nombre[:255]),
                )
                usuario_id = cur.fetchone()["id"]
            else:
                usuario_id = existente["id"]
            cur.execute(
                "INSERT INTO usuario_empresas (usuario_id, empresa_id, rol) VALUES (%s, %s, %s)",
                (usuario_id, eid, rol),
            )
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="Esa persona ya tiene acceso a la empresa")

    registrar_evento(
        current_user["user_id"], "cuenta.alta_usuario", empresa_id=eid, entidad="usuario",
        entidad_id=str(usuario_id), metadata={"email": email, "rol": rol, "cuenta_creada": cuenta_creada},
    )
    miembro = next(m for m in _miembros(eid) if str(m["usuario_id"]) == str(usuario_id))
    return {
        "usuario": _usuario(miembro, {str(usuario_id): rol}, current_user["user_id"]),
        "cuenta_creada": cuenta_creada,
    }


@router.patch("/empresas/{empresa_id}/usuarios/{usuario_id}")
async def cambiar_rol(
    empresa_id: uuid.UUID,
    usuario_id: uuid.UUID,
    cuerpo: CambioRol,
    current_user: dict = Depends(get_current_user),
):
    eid, miembros, roles, puede = _contexto(empresa_id, current_user)
    _exigir_administrador(puede)
    try:
        rol = ue.validar_rol(cuerpo.rol)
        ue.validar_cambio_rol(roles, str(usuario_id), rol)
    except ue.DatoInvalido as e:
        raise _422(e)
    except ue.NoEsMiembro:
        raise HTTPException(status_code=404, detail="Ese usuario no tiene acceso a la empresa")
    except ue.UltimoAdministrador as e:
        raise HTTPException(status_code=409, detail=str(e))

    _fijar_administradores(eid, miembros, roles)
    db.execute("UPDATE usuario_empresas SET rol = %s WHERE empresa_id = %s AND usuario_id = %s",
               (rol, eid, str(usuario_id)))
    registrar_evento(
        current_user["user_id"], "cuenta.cambiar_rol", empresa_id=eid, entidad="usuario",
        entidad_id=str(usuario_id), metadata={"de": roles.get(str(usuario_id)), "a": rol},
    )
    miembro = next(m for m in miembros if str(m["usuario_id"]) == str(usuario_id))
    return _usuario(miembro, {str(usuario_id): rol}, current_user["user_id"])


@router.delete("/empresas/{empresa_id}/usuarios/{usuario_id}", status_code=204)
async def quitar_usuario(
    empresa_id: uuid.UUID,
    usuario_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
):
    """Quita el acceso a la empresa; la cuenta de la persona no se borra."""
    eid, miembros, roles, puede = _contexto(empresa_id, current_user)
    _exigir_administrador(puede)
    try:
        ue.validar_baja(roles, str(usuario_id))
    except ue.NoEsMiembro:
        raise HTTPException(status_code=404, detail="Ese usuario no tiene acceso a la empresa")
    except ue.UltimoAdministrador as e:
        raise HTTPException(status_code=409, detail=str(e))

    _fijar_administradores(eid, miembros, roles)
    db.execute("DELETE FROM usuario_empresas WHERE empresa_id = %s AND usuario_id = %s", (eid, str(usuario_id)))
    registrar_evento(
        current_user["user_id"], "cuenta.quitar_usuario", empresa_id=eid, entidad="usuario",
        entidad_id=str(usuario_id),
    )
    return Response(status_code=204)
