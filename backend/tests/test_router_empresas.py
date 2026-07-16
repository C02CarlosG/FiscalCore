"""Tests del router backend/routers/empresas.py (Día 24).

DB mockeada sobre `backend.db`. `validar_acceso_empresa`/`empresa_or_404` se
monkeypatchean a nivel de módulo (igual que en movimientos/conciliacion).
`parsear_constancia` se mockea en su módulo de origen (`backend.constancia_parser`)
porque `empresas.py` lo importa localmente dentro de la función, no a nivel
de módulo. `validar_upload` se deja correr real: es lógica pura y ya tiene
su propia cobertura directa en `test_deps.py` (Día 19).
"""
import psycopg2

from fastapi.testclient import TestClient

import backend.constancia_parser as constancia_parser
import backend.main_api as main
from backend import db
from backend.deps import get_current_user
from backend.routers import empresas

client = TestClient(main.app)

EMPRESA = "emp-1"


def _auth(monkeypatch):
    main.app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "user_id": "u1"}
    monkeypatch.setattr(empresas, "validar_acceso_empresa", lambda *a, **k: None)
    monkeypatch.setattr(empresas, "empresa_or_404", lambda eid: {"id": eid, "rfc": "TEST010101AAA"})


def _teardown():
    main.app.dependency_overrides.clear()


# ─── POST /constancia/parsear ──────────────────────────────────────────────────

def test_parsear_constancia_exitoso(monkeypatch):
    monkeypatch.setattr(constancia_parser, "parsear_constancia", lambda contenido: {
        "rfc": "TEST010101AAA", "razon_social": "Test SA de CV",
        "regimenes": ["612"], "obligaciones": [], "cp_fiscal": "01000", "curp": None,
        "texto_completo": "...",
    })

    r = client.post(
        "/api/v1/constancia/parsear",
        files={"archivo": ("constancia.pdf", b"%PDF-1.4 contenido", "application/pdf")},
    )

    assert r.status_code == 200
    body = r.json()
    assert body["rfc"] == "TEST010101AAA"
    assert "constancia_path" in body


def test_parsear_constancia_extension_invalida_da_400():
    r = client.post(
        "/api/v1/constancia/parsear",
        files={"archivo": ("constancia.txt", b"no es un pdf", "text/plain")},
    )
    assert r.status_code == 400


def test_parsear_constancia_error_runtime_da_500(monkeypatch):
    def _raise(contenido):
        raise RuntimeError("pdfplumber no instalado")
    monkeypatch.setattr(constancia_parser, "parsear_constancia", _raise)

    r = client.post(
        "/api/v1/constancia/parsear",
        files={"archivo": ("constancia.pdf", b"%PDF-1.4 contenido", "application/pdf")},
    )
    assert r.status_code == 500


def test_parsear_constancia_pdf_corrupto_da_422(monkeypatch):
    def _raise(contenido):
        raise ValueError("No se pudo extraer texto")
    monkeypatch.setattr(constancia_parser, "parsear_constancia", _raise)

    r = client.post(
        "/api/v1/constancia/parsear",
        files={"archivo": ("constancia.pdf", b"%PDF-1.4 contenido", "application/pdf")},
    )
    assert r.status_code == 422


# ─── GET /empresas ──────────────────────────────────────────────────────────────

def test_listar_empresas(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_all", lambda *a, **k: [
        {"id": "emp-1", "rfc": "TEST010101AAA", "razon_social": "Test SA de CV"},
    ])

    try:
        r = client.get("/api/v1/empresas")
    finally:
        _teardown()

    assert r.status_code == 200
    assert r.json()[0]["rfc"] == "TEST010101AAA"


def test_listar_empresas_vacio(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_all", lambda *a, **k: [])

    try:
        r = client.get("/api/v1/empresas")
    finally:
        _teardown()

    assert r.json() == []


# ─── POST /mis-empresas ─────────────────────────────────────────────────────────

def test_agregar_empresa_nueva_la_crea_y_vincula(monkeypatch):
    _auth(monkeypatch)
    execute_calls = []

    def _query_one(sql, params=()):
        if "usuario_empresas" in sql:
            return None  # aún no vinculada
        return None  # empresa no existe por RFC

    def _execute(sql, params=(), returning=False):
        execute_calls.append((sql, params))
        if returning:
            return {"id": "emp-nueva", "rfc": "NUEV010101AAA", "razon_social": "Nueva SA"}
        return None

    monkeypatch.setattr(db, "query_one", _query_one)
    monkeypatch.setattr(db, "execute", _execute)

    try:
        r = client.post("/api/v1/mis-empresas", json={"rfc": "nuev010101aaa", "razon_social": "Nueva SA"})
    finally:
        _teardown()

    assert r.status_code == 201
    body = r.json()
    assert body["empresa_id"] == "emp-nueva"
    assert body["rfc"] == "NUEV010101AAA"
    vinculaciones = [c for c in execute_calls if "usuario_empresas" in c[0]]
    assert len(vinculaciones) == 1


def test_agregar_empresa_existente_ya_vinculada_no_reinserta(monkeypatch):
    _auth(monkeypatch)

    def _query_one(sql, params=()):
        if "FROM empresas WHERE rfc" in sql:
            return {"id": "emp-1", "rfc": "TEST010101AAA", "razon_social": "Test SA de CV"}
        if "usuario_empresas" in sql:
            return {"1": 1}  # ya vinculada
        return None

    execute_calls = []
    monkeypatch.setattr(db, "query_one", _query_one)
    monkeypatch.setattr(db, "execute", lambda sql, params=(), returning=False: execute_calls.append(sql))

    try:
        r = client.post("/api/v1/mis-empresas", json={"rfc": "test010101aaa", "razon_social": "Test SA de CV"})
    finally:
        _teardown()

    assert r.status_code == 201
    assert execute_calls == []  # no crea empresa ni re-vincula


def test_agregar_empresa_race_unique_violation_reutiliza_existente(monkeypatch):
    _auth(monkeypatch)
    llamadas_query_one = []

    def _query_one(sql, params=()):
        llamadas_query_one.append(sql)
        if "FROM empresas WHERE rfc" in sql:
            if len(llamadas_query_one) == 1:
                return None  # primera consulta: no existe
            return {"id": "emp-1", "rfc": "TEST010101AAA", "razon_social": "Test SA de CV"}
        if "usuario_empresas" in sql:
            return None
        return None

    def _execute(sql, params=(), returning=False):
        if returning:
            raise psycopg2.errors.UniqueViolation("duplicate key")
        return None

    monkeypatch.setattr(db, "query_one", _query_one)
    monkeypatch.setattr(db, "execute", _execute)

    try:
        r = client.post("/api/v1/mis-empresas", json={"rfc": "test010101aaa", "razon_social": "Test SA de CV"})
    finally:
        _teardown()

    assert r.status_code == 201
    assert r.json()["empresa_id"] == "emp-1"


# ─── GET /empresas/{id} ──────────────────────────────────────────────────────────

def test_obtener_empresa(monkeypatch):
    _auth(monkeypatch)

    try:
        r = client.get(f"/api/v1/empresas/{EMPRESA}")
    finally:
        _teardown()

    assert r.status_code == 200
    assert r.json()["rfc"] == "TEST010101AAA"


def test_obtener_empresa_sin_acceso_da_403(monkeypatch):
    main.app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "user_id": "u1"}
    from fastapi import HTTPException

    def _sin_acceso(*a, **k):
        raise HTTPException(status_code=403, detail="Sin acceso a esta empresa")
    monkeypatch.setattr(empresas, "validar_acceso_empresa", _sin_acceso)

    try:
        r = client.get(f"/api/v1/empresas/{EMPRESA}")
    finally:
        _teardown()

    assert r.status_code == 403


def test_obtener_empresa_no_encontrada_da_404(monkeypatch):
    main.app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "user_id": "u1"}
    from fastapi import HTTPException

    monkeypatch.setattr(empresas, "validar_acceso_empresa", lambda *a, **k: None)

    def _no_encontrada(eid):
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    monkeypatch.setattr(empresas, "empresa_or_404", _no_encontrada)

    try:
        r = client.get(f"/api/v1/empresas/{EMPRESA}")
    finally:
        _teardown()

    assert r.status_code == 404


# ─── PATCH /empresas/{id}/impuestos ───────────────────────────────────────────────

def test_actualizar_impuestos_exitoso(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "execute", lambda *a, **k: None)

    try:
        r = client.patch(
            f"/api/v1/empresas/{EMPRESA}/impuestos",
            json={"impuestos": ["iva", "isr"]},
        )
    finally:
        _teardown()

    assert r.status_code == 200
    assert r.json()["impuestos"] == ["iva", "isr"]


def test_actualizar_impuestos_clave_invalida_da_422():
    main.app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "user_id": "u1"}

    try:
        r = client.patch(
            f"/api/v1/empresas/{EMPRESA}/impuestos",
            json={"impuestos": ["iva", "no-existe"]},
        )
    finally:
        _teardown()

    assert r.status_code == 422
