"""Tests del router backend/routers/admin.py (Día 24).

DB mockeada sobre `backend.db`. `require_admin` se sobreescribe vía
`dependency_overrides` para los happy paths (igual que `get_current_user`
en los demás routers); el caso "no admin" deja `require_admin` correr de
verdad contra un `get_current_user` mockeado, para cubrir la verificación
de rol 403 tal cual ocurre en producción.
"""
from fastapi.testclient import TestClient

import backend.main_api as main
from backend import db
from backend.deps import get_current_user, require_admin

client = TestClient(main.app)

ADMIN = {"id": "admin-1", "user_id": "admin-1"}


def _auth_admin():
    main.app.dependency_overrides[require_admin] = lambda: ADMIN


def _teardown():
    main.app.dependency_overrides.clear()


# ─── GET /admin/usuarios ───────────────────────────────────────────────────────

def test_listar_usuarios(monkeypatch):
    _auth_admin()
    monkeypatch.setattr(db, "query_all", lambda *a, **k: [
        {"id": "u1", "email": "ana@test.local", "nombre": "Ana", "rol": "contador",
         "activo": True, "created_at": None, "empresas": []},
    ])

    try:
        r = client.get("/api/v1/admin/usuarios")
    finally:
        _teardown()

    assert r.status_code == 200
    assert r.json()[0]["email"] == "ana@test.local"


def test_listar_usuarios_sin_token_da_401():
    r = client.get("/api/v1/admin/usuarios")
    assert r.status_code == 401


def test_listar_usuarios_sin_rol_admin_da_403(monkeypatch):
    main.app.dependency_overrides[get_current_user] = lambda: {"user_id": "u1"}
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {"rol": "contador"})

    try:
        r = client.get("/api/v1/admin/usuarios")
    finally:
        _teardown()

    assert r.status_code == 403


# ─── PATCH /admin/usuarios/{user_id} ───────────────────────────────────────────

def test_actualizar_usuario_exitoso(monkeypatch):
    _auth_admin()
    monkeypatch.setattr(db, "execute", lambda *a, **k: {
        "id": "u2", "email": "b@test.local", "nombre": "B", "rol": "admin", "activo": True,
    })

    try:
        r = client.patch("/api/v1/admin/usuarios/u2", json={"rol": "admin"})
    finally:
        _teardown()

    assert r.status_code == 200
    assert r.json()["rol"] == "admin"


def test_actualizar_usuario_no_puede_quitarse_admin_a_si_mismo(monkeypatch):
    _auth_admin()

    try:
        r = client.patch(f"/api/v1/admin/usuarios/{ADMIN['user_id']}", json={"rol": "contador"})
    finally:
        _teardown()

    assert r.status_code == 400


def test_actualizar_usuario_sin_campos_da_400(monkeypatch):
    _auth_admin()

    try:
        r = client.patch("/api/v1/admin/usuarios/u2", json={})
    finally:
        _teardown()

    assert r.status_code == 400


def test_actualizar_usuario_rol_invalido_da_400(monkeypatch):
    _auth_admin()

    try:
        r = client.patch("/api/v1/admin/usuarios/u2", json={"rol": "superadmin"})
    finally:
        _teardown()

    assert r.status_code == 400


def test_actualizar_usuario_no_encontrado_da_404(monkeypatch):
    _auth_admin()
    monkeypatch.setattr(db, "execute", lambda *a, **k: None)

    try:
        r = client.patch("/api/v1/admin/usuarios/u-x", json={"activo": False})
    finally:
        _teardown()

    assert r.status_code == 404


# ─── GET /admin/stats ───────────────────────────────────────────────────────────

def test_estadisticas(monkeypatch):
    _auth_admin()
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {
        "usuarios_activos": 5, "admins": 1, "empresas_activas": 3, "cfdi_total": 120,
    })

    try:
        r = client.get("/api/v1/admin/stats")
    finally:
        _teardown()

    assert r.status_code == 200
    assert r.json()["cfdi_total"] == 120


def test_estadisticas_sin_datos_da_dict_vacio(monkeypatch):
    _auth_admin()
    monkeypatch.setattr(db, "query_one", lambda *a, **k: None)

    try:
        r = client.get("/api/v1/admin/stats")
    finally:
        _teardown()

    assert r.status_code == 200
    assert r.json() == {}


# ─── GET /admin/metricas ────────────────────────────────────────────────────────

def test_metricas_globales(monkeypatch):
    _auth_admin()
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {
        "total_usuarios": 10, "usuarios_activos": 8, "total_empresas": 4,
        "total_cfdi": 500, "total_riesgos": 12, "riesgos_criticos": 2,
    })

    try:
        r = client.get("/api/v1/admin/metricas")
    finally:
        _teardown()

    assert r.status_code == 200
    assert r.json()["riesgos_criticos"] == 2
