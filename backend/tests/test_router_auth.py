"""Tests del router de auth (register/login/me) con DB mockeada (Día 19).

Sin Postgres real: se monkeypatchea `backend.db` directamente (register/login
no pasan por un loader dedicado como los routers de reportes, llaman a
`db.query_one`/`db.execute`/`db.query_all` en línea).

El rate limit de login (5/minute, slowapi) usa un `Limiter` singleton en
`backend.deps` con estado en memoria compartido entre tests — se resetea
antes y después de cada test de este archivo para no filtrar estado hacia
otros tests que también pegan a /auth/login.
"""
import pytest
from fastapi.testclient import TestClient

import backend.main_api as main
from backend import db
from backend.deps import crear_token, hash_password, limiter

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter.reset()
    yield
    limiter.reset()


# ─── POST /auth/register ────────────────────────────────────────────────────


def test_register_exitoso(monkeypatch):
    monkeypatch.setattr(db, "query_one", lambda *a, **k: None)  # email libre
    monkeypatch.setattr(db, "execute", lambda *a, **k: {"id": "u1"})

    r = client.post("/api/v1/auth/register",
                     json={"email": "nueva@test.local", "password": "Test1234!", "nombre": "Nueva"})

    assert r.status_code == 201
    body = r.json()
    assert body["access_token"]
    assert body["email"] == "nueva@test.local"
    assert body["empresas"] == []


def test_register_email_duplicado_da_409(monkeypatch):
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {"id": "ya-existe"})

    r = client.post("/api/v1/auth/register",
                     json={"email": "repetido@test.local", "password": "Test1234!", "nombre": "X"})

    assert r.status_code == 409


# ─── POST /auth/login ────────────────────────────────────────────────────────


def test_login_exitoso(monkeypatch):
    password_hash = hash_password("Test1234!")
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {
        "id": "u1", "password_hash": password_hash, "nombre": "Ana",
    })
    monkeypatch.setattr(db, "query_all", lambda *a, **k: [])

    r = client.post("/api/v1/auth/login", json={"email": "ana@test.local", "password": "Test1234!"})

    assert r.status_code == 200
    body = r.json()
    assert body["access_token"]
    assert body["nombre"] == "Ana"
    assert body["empresas"] == []


def test_login_password_incorrecta_da_401(monkeypatch):
    password_hash = hash_password("Test1234!")
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {
        "id": "u1", "password_hash": password_hash, "nombre": "Ana",
    })

    r = client.post("/api/v1/auth/login", json={"email": "ana@test.local", "password": "incorrecta"})

    assert r.status_code == 401


def test_login_usuario_inexistente_da_401(monkeypatch):
    monkeypatch.setattr(db, "query_one", lambda *a, **k: None)

    r = client.post("/api/v1/auth/login", json={"email": "no-existe@test.local", "password": "x"})

    assert r.status_code == 401


def test_login_rate_limit_5_por_minuto(monkeypatch):
    monkeypatch.setattr(db, "query_one", lambda *a, **k: None)  # siempre 401, no importa para el límite

    for _ in range(5):
        r = client.post("/api/v1/auth/login", json={"email": "x@test.local", "password": "x"})
        assert r.status_code == 401

    r_sexto = client.post("/api/v1/auth/login", json={"email": "x@test.local", "password": "x"})
    assert r_sexto.status_code == 429


# ─── GET /auth/me ────────────────────────────────────────────────────────────


def test_me_sin_token_da_401():
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401


def test_me_con_token_valido(monkeypatch):
    token = crear_token({"user_id": "u1", "email": "ana@test.local"})
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {
        "id": "u1", "email": "ana@test.local", "nombre": "Ana", "telefono": None,
        "rfc": None, "nombre_despacho": None, "cedula_profesional": None,
    })
    monkeypatch.setattr(db, "query_all", lambda *a, **k: [])

    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert r.status_code == 200
    assert r.json()["email"] == "ana@test.local"


def test_me_usuario_no_encontrado_da_404(monkeypatch):
    token = crear_token({"user_id": "u1", "email": "ana@test.local"})
    monkeypatch.setattr(db, "query_one", lambda *a, **k: None)

    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert r.status_code == 404
