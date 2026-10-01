"""Tests del router backend/routers/riesgos.py.

Cubren el control de acceso de los dos endpoints que modifican detecciones:
exigen token y que el usuario tenga acceso a la empresa dueña de la detección.
DB mockeada sobre `backend.db`; `validar_acceso_empresa` se monkeypatchea a
nivel de módulo (igual que en conciliacion/empresas).
"""
from fastapi import HTTPException
from fastapi.testclient import TestClient

import backend.main_api as main
from backend import db
from backend.deps import get_current_user
from backend.routers import riesgos

client = TestClient(main.app)

DET = "11111111-1111-1111-1111-111111111111"


def _auth(monkeypatch, con_acceso=True):
    main.app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "user_id": "u1"}
    accesos = []

    def _validar(empresa_id, current_user):
        accesos.append(empresa_id)
        if not con_acceso:
            raise HTTPException(status_code=403, detail="Sin acceso a esta empresa")

    monkeypatch.setattr(riesgos, "validar_acceso_empresa", _validar)
    return accesos


def _teardown():
    main.app.dependency_overrides.clear()


def _db(monkeypatch, deteccion):
    """`deteccion` es la fila que devuelve el SELECT (None = no existe)."""
    execute_calls = []
    monkeypatch.setattr(db, "query_one", lambda sql, params=(): deteccion)

    def _execute(sql, params=(), returning=False):
        execute_calls.append((sql, params))
        return {"id": DET, "estado": "resuelto"} if returning else None

    monkeypatch.setattr(db, "execute", _execute)
    return execute_calls


# ─── PATCH /riesgos/{id}/resolver ──────────────────────────────────────────────

def test_resolver_sin_token_da_401(monkeypatch):
    execute_calls = _db(monkeypatch, {"empresa_id": "emp-1", "estado": "abierto"})
    r = client.patch(f"/api/v1/riesgos/{DET}/resolver")
    assert r.status_code == 401
    assert execute_calls == []


def test_resolver_de_otra_empresa_da_403_y_no_modifica(monkeypatch):
    accesos = _auth(monkeypatch, con_acceso=False)
    execute_calls = _db(monkeypatch, {"empresa_id": "emp-ajena", "estado": "abierto"})
    try:
        r = client.patch(f"/api/v1/riesgos/{DET}/resolver")
    finally:
        _teardown()
    assert r.status_code == 403
    assert accesos == ["emp-ajena"]
    assert execute_calls == []


def test_resolver_inexistente_da_404(monkeypatch):
    _auth(monkeypatch)
    execute_calls = _db(monkeypatch, None)
    try:
        r = client.patch(f"/api/v1/riesgos/{DET}/resolver")
    finally:
        _teardown()
    assert r.status_code == 404
    assert execute_calls == []


def test_resolver_con_acceso_actualiza(monkeypatch):
    accesos = _auth(monkeypatch)
    execute_calls = _db(monkeypatch, {"empresa_id": "emp-1", "estado": "abierto"})
    try:
        r = client.patch(f"/api/v1/riesgos/{DET}/resolver", params={"notas": "ok"})
    finally:
        _teardown()
    assert r.status_code == 200
    assert r.json()["estado"] == "resuelto"
    assert accesos == ["emp-1"]
    assert len(execute_calls) == 1
    assert execute_calls[0][1] == ("ok", DET)


# ─── POST /acciones/{id}/ejecutar ──────────────────────────────────────────────

def test_ejecutar_accion_sin_token_da_401(monkeypatch):
    execute_calls = _db(monkeypatch, {"empresa_id": "emp-1", "estado": "abierto"})
    r = client.post(f"/api/v1/acciones/{DET}/ejecutar", json={"tipo": "descartar"})
    assert r.status_code == 401
    assert execute_calls == []


def test_ejecutar_accion_de_otra_empresa_da_403_y_no_modifica(monkeypatch):
    _auth(monkeypatch, con_acceso=False)
    execute_calls = _db(monkeypatch, {"empresa_id": "emp-ajena", "estado": "abierto"})
    try:
        r = client.post(f"/api/v1/acciones/{DET}/ejecutar", json={"tipo": "descartar"})
    finally:
        _teardown()
    assert r.status_code == 403
    assert execute_calls == []


def test_ejecutar_accion_inexistente_da_404(monkeypatch):
    _auth(monkeypatch)
    _db(monkeypatch, None)
    try:
        r = client.post(f"/api/v1/acciones/{DET}/ejecutar", json={"tipo": "descartar"})
    finally:
        _teardown()
    assert r.status_code == 404


def test_ejecutar_accion_desconocida_da_400(monkeypatch):
    _auth(monkeypatch)
    execute_calls = _db(monkeypatch, {"empresa_id": "emp-1", "estado": "abierto"})
    try:
        r = client.post(f"/api/v1/acciones/{DET}/ejecutar", json={"tipo": "no-existe"})
    finally:
        _teardown()
    assert r.status_code == 400
    assert execute_calls == []


def test_ejecutar_accion_con_acceso_cambia_estado(monkeypatch):
    _auth(monkeypatch)
    execute_calls = _db(monkeypatch, {"empresa_id": "emp-1", "estado": "abierto"})
    try:
        r = client.post(f"/api/v1/acciones/{DET}/ejecutar", json={"tipo": "descartar", "notas": "n/a"})
    finally:
        _teardown()
    assert r.status_code == 200
    assert r.json() == {"deteccion_id": DET, "estado_anterior": "abierto", "estado_nuevo": "descartado"}
    assert len(execute_calls) == 1
