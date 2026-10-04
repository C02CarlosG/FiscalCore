"""
usuarios_empresa.py
Reglas de U1 (carril D): correo, rol, contraseña y quién administra una empresa.
Módulo puro: recibe los vínculos ya leídos de `usuario_empresas`.
"""
from __future__ import annotations

import re
from typing import Iterable, Optional

ROLES = ("administrador", "contador")
MIN_CONTRASENA = 8
MAX_CONTRASENA = 128  # bcrypt solo usa los primeros 72 bytes; el tope evita abusos
_CORREO_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class DatoInvalido(ValueError):
    """Entrada inválida (422); el mensaje se muestra tal cual."""


class UltimoAdministrador(ValueError):
    """La empresa se quedaría sin administrador (409)."""


class NoEsMiembro(LookupError):
    """El usuario no está vinculado a la empresa (404)."""


def normalizar_correo(correo: Optional[str]) -> str:
    limpio = (correo or "").strip().lower()
    if len(limpio) > 255 or not _CORREO_RE.fullmatch(limpio):
        raise DatoInvalido("Correo electrónico inválido")
    return limpio


def validar_rol(rol: Optional[str]) -> str:
    if rol not in ROLES:
        raise DatoInvalido("rol debe ser 'administrador' o 'contador'")
    return rol


def validar_contrasena(nueva: Optional[str], actual: Optional[str] = None) -> str:
    if not isinstance(nueva, str) or len(nueva) < MIN_CONTRASENA:
        raise DatoInvalido(f"La contraseña debe tener al menos {MIN_CONTRASENA} caracteres")
    if len(nueva) > MAX_CONTRASENA:
        raise DatoInvalido(f"La contraseña no puede tener más de {MAX_CONTRASENA} caracteres")
    if actual is not None and nueva == actual:
        raise DatoInvalido("La contraseña nueva debe ser distinta de la actual")
    return nueva


def roles_efectivos(miembros: Iterable[dict]) -> dict:
    """``{usuario_id: rol}``. Si nadie es administrador, el primer vinculado actúa como tal.

    Es la regla de la migración 062 aplicada al leer: `POST /mis-empresas` (carril B)
    todavía vincula al creador con el rol por defecto.
    """
    miembros = sorted(miembros, key=lambda m: (m["created_at"], str(m["usuario_id"])))
    roles = {str(m["usuario_id"]): (m["rol"] if m["rol"] in ROLES else "contador") for m in miembros}
    if miembros and "administrador" not in roles.values():
        roles[str(miembros[0]["usuario_id"])] = "administrador"
    return roles


def puede_administrar(usuario_id: str, roles: dict, rol_plataforma: Optional[str]) -> bool:
    return rol_plataforma == "admin" or roles.get(str(usuario_id)) == "administrador"


def _administradores(roles: dict) -> int:
    return sum(1 for r in roles.values() if r == "administrador")


def validar_cambio_rol(roles: dict, usuario_id: str, nuevo: str) -> None:
    actual = roles.get(str(usuario_id))
    if actual is None:
        raise NoEsMiembro(usuario_id)
    if actual == "administrador" and nuevo != "administrador" and _administradores(roles) == 1:
        raise UltimoAdministrador("La empresa debe conservar al menos un administrador")


def validar_baja(roles: dict, usuario_id: str) -> None:
    actual = roles.get(str(usuario_id))
    if actual is None:
        raise NoEsMiembro(usuario_id)
    if actual == "administrador" and _administradores(roles) == 1:
        raise UltimoAdministrador("La empresa debe conservar al menos un administrador")
