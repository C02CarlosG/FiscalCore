"""Tests de backend/deps.py — JWT, bcrypt, require_admin, validar_upload (Día 19).

Todo lo cubierto aquí es lógica pura o requiere solo un mock mínimo de
`backend.db` (sin Postgres real). Los endpoints que exponen este flujo por
HTTP (register/login/me, rate limiting) se prueban en
`test_router_auth.py`.
"""
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt

from backend import db
from backend.deps import (
    JWT_ALGORITHM,
    JWT_SECRET,
    crear_token,
    get_current_user,
    hash_password,
    require_admin,
    serializar,
    validar_upload,
    verificar_token,
    verify_password,
)


class _FakeUpload:
    def __init__(self, filename, content_type):
        self.filename = filename
        self.content_type = content_type


# ─── JWT ──────────────────────────────────────────────────────────────────


def test_crear_y_verificar_token_roundtrip():
    token = crear_token({"user_id": "u1", "email": "a@b.com"})
    payload = verificar_token(token)
    assert payload["user_id"] == "u1"
    assert payload["email"] == "a@b.com"
    assert "exp" in payload


def test_verificar_token_invalido_da_401():
    with pytest.raises(HTTPException) as exc:
        verificar_token("esto-no-es-un-jwt")
    assert exc.value.status_code == 401


def test_verificar_token_expirado_da_401():
    expirado = jwt.encode(
        {"user_id": "u1", "exp": datetime.utcnow() - timedelta(hours=1)},
        JWT_SECRET, algorithm=JWT_ALGORITHM,
    )
    with pytest.raises(HTTPException) as exc:
        verificar_token(expirado)
    assert exc.value.status_code == 401


def test_verificar_token_firmado_con_otro_secret_da_401():
    token_ajeno = jwt.encode({"user_id": "u1"}, "otro-secreto-distinto", algorithm=JWT_ALGORITHM)
    with pytest.raises(HTTPException) as exc:
        verificar_token(token_ajeno)
    assert exc.value.status_code == 401


def test_get_current_user_sin_credenciales_da_401():
    with pytest.raises(HTTPException) as exc:
        get_current_user(None)
    assert exc.value.status_code == 401


def test_get_current_user_con_token_valido():
    token = crear_token({"user_id": "u1", "email": "a@b.com"})
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    payload = get_current_user(creds)
    assert payload["user_id"] == "u1"


# ─── bcrypt ───────────────────────────────────────────────────────────────


def test_hash_password_usa_salt_distinto_cada_vez():
    h1 = hash_password("Test1234!")
    h2 = hash_password("Test1234!")
    assert h1 != h2


def test_verify_password_correcta():
    hashed = hash_password("Test1234!")
    assert verify_password("Test1234!", hashed) is True


def test_verify_password_incorrecta():
    hashed = hash_password("Test1234!")
    assert verify_password("otra-cosa", hashed) is False


# ─── require_admin ──────────────────────────────────────────────────────────


def test_require_admin_con_rol_admin_pasa(monkeypatch):
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {"rol": "admin"})
    resultado = require_admin(current_user={"user_id": "u1"})
    assert resultado == {"user_id": "u1"}


def test_require_admin_con_rol_no_admin_da_403(monkeypatch):
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {"rol": "user"})
    with pytest.raises(HTTPException) as exc:
        require_admin(current_user={"user_id": "u1"})
    assert exc.value.status_code == 403


def test_require_admin_sin_usuario_da_403(monkeypatch):
    monkeypatch.setattr(db, "query_one", lambda *a, **k: None)
    with pytest.raises(HTTPException) as exc:
        require_admin(current_user={"user_id": "u1"})
    assert exc.value.status_code == 403


# ─── validar_upload ───────────────────────────────────────────────────────


def test_validar_upload_extension_invalida_da_400():
    with pytest.raises(HTTPException) as exc:
        validar_upload(_FakeUpload("doc.txt", "text/plain"), b"hola", (".xml",), ("application/xml",))
    assert exc.value.status_code == 400


def test_validar_upload_content_type_invalido_da_400():
    with pytest.raises(HTTPException) as exc:
        validar_upload(_FakeUpload("doc.xml", "text/plain"), b"hola", (".xml",), ("application/xml",))
    assert exc.value.status_code == 400


def test_validar_upload_excede_tamano_da_413():
    contenido = b"x" * (11 * 1024 * 1024)
    with pytest.raises(HTTPException) as exc:
        validar_upload(_FakeUpload("doc.xml", "application/xml"), contenido, (".xml",), ("application/xml",))
    assert exc.value.status_code == 413


def test_validar_upload_extension_case_insensitive():
    validar_upload(_FakeUpload("doc.XML", "application/xml"), b"ok", (".xml",), ("application/xml",))


def test_validar_upload_sin_content_type_declarado_no_valida_eso():
    """Si el cliente no manda content_type, solo se exige la extensión."""
    validar_upload(_FakeUpload("doc.xml", None), b"ok", (".xml",), ("application/xml",))


# ─── serializar ───────────────────────────────────────────────────────────


def test_serializar_convierte_decimal_y_datetime():
    from decimal import Decimal

    resultado = serializar({
        "monto": Decimal("1000.50"),
        "fecha": datetime(2026, 1, 15, 10, 30),
        "nombre": "texto",
        "nulo": None,
    })
    assert resultado == {
        "monto": 1000.5,
        "fecha": "2026-01-15T10:30:00",
        "nombre": "texto",
        "nulo": None,
    }
