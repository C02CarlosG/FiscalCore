from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from .. import db
from ..deps import get_current_user, crear_token, hash_password, verify_password, serializar
from ..schemas import RegisterRequest, LoginRequest, ActualizarPerfilRequest

_log = logging.getLogger(__name__)

router = APIRouter(tags=["Auth"])


@router.post("/api/v1/auth/register", status_code=status.HTTP_201_CREATED)
async def registrar(data: RegisterRequest):
    """Registra un contador (usuario). Retorna JWT. Las empresas se agregan después con POST /mis-empresas."""
    email_existente = db.query_one("SELECT id FROM usuarios WHERE email = %s", (data.email,))
    if email_existente:
        raise HTTPException(status_code=409, detail="El correo ya está registrado")

    password_hash = hash_password(data.password)
    usuario = db.execute(
        "INSERT INTO usuarios (email, password_hash, nombre) VALUES (%s, %s, %s) RETURNING *",
        (data.email, password_hash, data.nombre),
        returning=True,
    )

    rol = usuario.get("rol", "contador")
    token = crear_token({"user_id": str(usuario["id"]), "email": data.email, "rol": rol})

    return {
        "access_token": token,
        "token_type":   "bearer",
        "user_id":      str(usuario["id"]),
        "email":        data.email,
        "nombre":       data.nombre,
        "rol":          rol,
        "empresas":     [],
    }


@router.post("/api/v1/auth/login")
async def login(data: LoginRequest):
    """Autentica un contador y retorna JWT + lista de empresas que administra."""
    usuario = db.query_one(
        "SELECT * FROM usuarios WHERE email = %s AND activo = TRUE",
        (data.email,),
    )
    if not usuario or not verify_password(data.password, usuario["password_hash"]):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    empresas = db.query_all(
        """
        SELECT e.id AS empresa_id, e.rfc, e.razon_social, e.regimen_fiscal
        FROM empresas e
        JOIN usuario_empresas ue ON ue.empresa_id = e.id
        WHERE ue.usuario_id = %s AND e.activo = TRUE
        ORDER BY ue.created_at ASC
        """,
        (str(usuario["id"]),),
    )

    rol = usuario.get("rol", "contador")
    token = crear_token({"user_id": str(usuario["id"]), "email": data.email, "rol": rol})

    return {
        "access_token": token,
        "token_type":   "bearer",
        "user_id":      str(usuario["id"]),
        "nombre":       usuario.get("nombre"),
        "rol":          rol,
        "empresas":     [serializar(e) for e in empresas],
    }


@router.get("/api/v1/auth/me")
async def me(current_user: dict = Depends(get_current_user)):
    """Retorna info del usuario autenticado y sus empresas."""
    usuario = db.query_one(
        """
        SELECT id, email, nombre, telefono, rfc, nombre_despacho, cedula_profesional, rol
        FROM usuarios WHERE id = %s
        """,
        (current_user["user_id"],),
    )
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    empresas = db.query_all(
        """
        SELECT e.id AS empresa_id, e.rfc, e.razon_social, e.regimen_fiscal
        FROM empresas e
        JOIN usuario_empresas ue ON ue.empresa_id = e.id
        WHERE ue.usuario_id = %s AND e.activo = TRUE
        ORDER BY ue.created_at ASC
        """,
        (current_user["user_id"],),
    )

    return {**serializar(usuario), "empresas": [serializar(e) for e in empresas]}


@router.patch("/api/v1/usuarios/perfil")
async def actualizar_perfil(
    data: ActualizarPerfilRequest,
    current_user: dict = Depends(get_current_user),
):
    """Actualiza los datos de perfil del contador autenticado."""
    campos = {k: v for k, v in data.model_dump().items() if v is not None}
    if not campos:
        raise HTTPException(status_code=400, detail="Sin campos para actualizar")

    sets   = ", ".join(f"{k} = %s" for k in campos)
    valores = list(campos.values()) + [current_user["user_id"]]
    usuario = db.execute(
        f"UPDATE usuarios SET {sets}, updated_at = NOW() WHERE id = %s RETURNING id, email, nombre, telefono, rfc, nombre_despacho, cedula_profesional",
        tuple(valores),
        returning=True,
    )
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return serializar(usuario)
