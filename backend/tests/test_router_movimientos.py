"""Tests del router backend/routers/movimientos.py (Día 23).

DB mockeada sobre `backend.db`. `validar_acceso_empresa`/`empresa_or_404` se
monkeypatchean a nivel de módulo, igual que en conciliacion/reportes.
"""
from datetime import date

from fastapi.testclient import TestClient

import backend.main_api as main
from backend import db
from backend.deps import get_current_user
from backend.routers import movimientos

client = TestClient(main.app)

EMPRESA = "emp-1"


def _auth(monkeypatch):
    main.app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "user_id": "u1"}
    monkeypatch.setattr(movimientos, "validar_acceso_empresa", lambda *a, **k: None)
    monkeypatch.setattr(movimientos, "empresa_or_404", lambda eid: {"id": eid})


def _dispatch(monkeypatch, query_one_por_marca=None, query_all_por_marca=None):
    query_one_por_marca = query_one_por_marca or []
    query_all_por_marca = query_all_por_marca or []

    def _query_one(sql, params=()):
        for marca, valor in query_one_por_marca:
            if marca in sql:
                return valor
        return None

    def _query_all(sql, params=()):
        for marca, valor in query_all_por_marca:
            if marca in sql:
                return valor
        return []

    monkeypatch.setattr(db, "query_one", _query_one)
    monkeypatch.setattr(db, "query_all", _query_all)


def _teardown():
    main.app.dependency_overrides.clear()


# ─── asegurar_seed (función interna, probada directo sin HTTP) ────────────────

def test_asegurar_seed_siembra_categorias_y_reglas_si_vacio(monkeypatch):
    monkeypatch.setattr(db, "query_one", lambda *a, **k: None)
    inserts_cat, inserts_regla = [], []

    def _execute(sql, params=(), returning=False):
        if "INSERT INTO categorias_movimiento" in sql:
            inserts_cat.append(params)
            return {"id": params[1]}
        if "INSERT INTO reglas_categorizacion" in sql:
            inserts_regla.append(params)
        return None

    monkeypatch.setattr(db, "execute", _execute)

    movimientos.asegurar_seed(EMPRESA)

    assert len(inserts_cat) == len(movimientos.CATEGORIAS_BASE)
    assert len(inserts_regla) == len(movimientos.REGLAS_BASE)


def test_asegurar_seed_no_hace_nada_si_ya_existen(monkeypatch):
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {"x": 1})
    llamadas = []
    monkeypatch.setattr(db, "execute", lambda *a, **k: llamadas.append(a))

    movimientos.asegurar_seed(EMPRESA)

    assert llamadas == []


# ─── GET /movimientos/cuentas ─────────────────────────────────────────────────

def test_listar_cuentas(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_all", lambda *a, **k: [
        {"banco": "BBVA", "cuenta": "1234", "total": 10},
    ])
    try:
        r = client.get(f"/api/v1/empresas/{EMPRESA}/movimientos/cuentas")
    finally:
        _teardown()

    assert r.status_code == 200
    assert r.json() == {"cuentas": [{"banco": "BBVA", "cuenta": "1234", "total": 10}]}


# ─── GET /movimientos ──────────────────────────────────────────────────────────

_MOV_ROW = {
    "id": "m1", "fecha": date(2026, 1, 10), "concepto": "PAGO NOMINA quincena",
    "referencia": "REF1", "rfc_detectado": None, "rfc_manual": False,
    "monto": "-5000.00", "tipo": "cargo", "saldo": "10000.00",
    "conciliado": False, "diferencia_monto": None,
    "categoria_id": None, "categoria_confirmada": False,
}


def test_listar_movimientos_sugiere_categoria_por_regla(monkeypatch):
    _auth(monkeypatch)
    _dispatch(
        monkeypatch,
        query_one_por_marca=[
            ("categorias_movimiento WHERE empresa_id = %s LIMIT 1", {"x": 1}),
            ("FILTER (WHERE tipo = 'deposito')", {
                "total": 1, "total_depositos": "0", "total_retiros": "5000.00", "conciliados": 0,
            }),
        ],
        query_all_por_marca=[
            ("ORDER BY fecha DESC, id LIMIT", [dict(_MOV_ROW)]),
            ("FROM reglas_categorizacion WHERE empresa_id = %s", [{
                "palabra_clave": "NOMINA", "tipo_match": "concepto", "categoria_id": "cat-nomina",
                "origen": "regla", "peso": 1, "tipo": "retiro",
            }]),
        ],
    )

    try:
        r = client.get(f"/api/v1/empresas/{EMPRESA}/movimientos")
    finally:
        _teardown()

    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["movimientos"][0]["categoria_sugerida"] == "cat-nomina"
    assert body["resumen"]["total_retiros"] == "5000.00"


def test_listar_movimientos_con_categoria_ya_asignada_no_sugiere(monkeypatch):
    _auth(monkeypatch)
    row = dict(_MOV_ROW, categoria_id="cat-existente")
    _dispatch(
        monkeypatch,
        query_one_por_marca=[
            ("categorias_movimiento WHERE empresa_id = %s LIMIT 1", {"x": 1}),
            ("FILTER (WHERE tipo = 'deposito')", {
                "total": 1, "total_depositos": "0", "total_retiros": "5000.00", "conciliados": 0,
            }),
        ],
        query_all_por_marca=[
            ("ORDER BY fecha DESC, id LIMIT", [row]),
            ("FROM reglas_categorizacion WHERE empresa_id = %s", []),
        ],
    )

    try:
        r = client.get(f"/api/v1/empresas/{EMPRESA}/movimientos")
    finally:
        _teardown()

    assert r.json()["movimientos"][0]["categoria_sugerida"] is None


def test_listar_movimientos_filtros_arman_where_y_params(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {
        "total": 0, "total_depositos": "0", "total_retiros": "0", "conciliados": 0,
    })
    llamadas = []

    def _query_all(sql, params=()):
        llamadas.append((sql, params))
        return []

    monkeypatch.setattr(db, "query_all", _query_all)

    try:
        r = client.get(
            f"/api/v1/empresas/{EMPRESA}/movimientos",
            params={
                "banco": "BBVA", "cuenta": "1234", "tipo": "retiro",
                "conciliado": "true", "categoria": "cat-1", "q": "nomina",
                "limit": 50, "offset": 10,
            },
        )
    finally:
        _teardown()

    assert r.status_code == 200
    sql, params = llamadas[0]
    assert "banco = %s" in sql and "cuenta = %s" in sql and "tipo = %s" in sql
    assert "conciliado = %s" in sql and "categoria_id = %s" in sql
    assert "concepto ILIKE %s OR rfc_detectado ILIKE %s" in sql
    assert params == (
        EMPRESA, "BBVA", "1234", "cargo", True, "cat-1", "%nomina%", "%nomina%", 50, 10,
    )


# ─── PATCH /movimientos/{mov_id} ──────────────────────────────────────────────

_MARCA_MOV_INICIAL = "SELECT id::text AS id, concepto, rfc_detectado, tipo"
_MARCA_MOV_FINAL = "monto::text AS monto, tipo, saldo::text AS saldo, conciliado"
_MARCA_CATEGORIA = "SELECT tipo FROM categorias_movimiento"


def test_actualizar_movimiento_no_encontrado_da_404(monkeypatch):
    _auth(monkeypatch)
    _dispatch(monkeypatch, query_one_por_marca=[(_MARCA_MOV_INICIAL, None)])

    try:
        r = client.patch(f"/api/v1/empresas/{EMPRESA}/movimientos/mov-x", json={"rfc_detectado": "X"})
    finally:
        _teardown()

    assert r.status_code == 404


def test_actualizar_movimiento_rfc_invalido_da_400(monkeypatch):
    _auth(monkeypatch)
    _dispatch(monkeypatch, query_one_por_marca=[
        (_MARCA_MOV_INICIAL, {"id": "m1", "concepto": "X", "rfc_detectado": None, "tipo": "cargo"}),
    ])

    try:
        r = client.patch(
            f"/api/v1/empresas/{EMPRESA}/movimientos/m1",
            json={"rfc_detectado": "NO-ES-UN-RFC"},
        )
    finally:
        _teardown()

    assert r.status_code == 400


def test_actualizar_movimiento_categoria_inexistente_da_400(monkeypatch):
    _auth(monkeypatch)
    _dispatch(monkeypatch, query_one_por_marca=[
        (_MARCA_MOV_INICIAL, {"id": "m1", "concepto": "X", "rfc_detectado": None, "tipo": "cargo"}),
        (_MARCA_CATEGORIA, None),
    ])

    try:
        r = client.patch(
            f"/api/v1/empresas/{EMPRESA}/movimientos/m1",
            json={"categoria_id": "cat-inexistente"},
        )
    finally:
        _teardown()

    assert r.status_code == 400
    assert "inexistente" in r.json()["detail"].lower()


def test_actualizar_movimiento_categoria_tipo_incompatible_da_400(monkeypatch):
    _auth(monkeypatch)
    _dispatch(monkeypatch, query_one_por_marca=[
        (_MARCA_MOV_INICIAL, {"id": "m1", "concepto": "X", "rfc_detectado": None, "tipo": "deposito"}),
        (_MARCA_CATEGORIA, {"tipo": "retiro"}),
    ])

    try:
        r = client.patch(
            f"/api/v1/empresas/{EMPRESA}/movimientos/m1",
            json={"categoria_id": "cat-retiro"},
        )
    finally:
        _teardown()

    assert r.status_code == 400
    assert "deposito" in r.json()["detail"]


def test_actualizar_movimiento_sin_cambios_da_400(monkeypatch):
    _auth(monkeypatch)
    _dispatch(monkeypatch, query_one_por_marca=[
        (_MARCA_MOV_INICIAL, {"id": "m1", "concepto": "X", "rfc_detectado": None, "tipo": "cargo"}),
    ])

    try:
        r = client.patch(f"/api/v1/empresas/{EMPRESA}/movimientos/m1", json={})
    finally:
        _teardown()

    assert r.status_code == 400


def test_actualizar_movimiento_exitoso_refuerza_historial(monkeypatch):
    _auth(monkeypatch)
    _dispatch(monkeypatch, query_one_por_marca=[
        (_MARCA_MOV_INICIAL, {
            "id": "m1", "concepto": "PAGO NOMINA quincena",
            "rfc_detectado": "PROV010101AAA", "tipo": "cargo",
        }),
        (_MARCA_CATEGORIA, {"tipo": "ambos"}),
        (_MARCA_MOV_FINAL, {
            "id": "m1", "fecha": date(2026, 1, 10), "concepto": "PAGO NOMINA quincena",
            "referencia": "REF1", "rfc_detectado": "PROV010101AAA", "rfc_manual": False,
            "monto": "-5000.00", "tipo": "cargo", "saldo": "10000.00", "conciliado": False,
            "categoria_id": "cat-1", "categoria_confirmada": True,
        }),
    ])
    execute_calls = []
    monkeypatch.setattr(db, "execute", lambda sql, params=(): execute_calls.append((sql, params)))

    try:
        r = client.patch(
            f"/api/v1/empresas/{EMPRESA}/movimientos/m1",
            json={"categoria_id": "cat-1"},
        )
    finally:
        _teardown()

    assert r.status_code == 200
    assert r.json()["categoria_id"] == "cat-1"
    assert any("UPDATE movimientos_bancarios" in sql for sql, _ in execute_calls)
    refuerzos = [c for c in execute_calls if "reglas_categorizacion" in c[0]]
    assert len(refuerzos) == 2  # por RFC y por concepto


def test_actualizar_movimiento_borra_categoria_con_string_vacio(monkeypatch):
    _auth(monkeypatch)
    _dispatch(monkeypatch, query_one_por_marca=[
        (_MARCA_MOV_INICIAL, {"id": "m1", "concepto": "X", "rfc_detectado": None, "tipo": "cargo"}),
        (_MARCA_MOV_FINAL, {
            "id": "m1", "fecha": date(2026, 1, 10), "concepto": "X", "referencia": None,
            "rfc_detectado": None, "rfc_manual": False, "monto": "-100.00", "tipo": "cargo",
            "saldo": "0.00", "conciliado": False, "categoria_id": None, "categoria_confirmada": False,
        }),
    ])
    execute_calls = []
    monkeypatch.setattr(db, "execute", lambda sql, params=(): execute_calls.append((sql, params)))

    try:
        r = client.patch(
            f"/api/v1/empresas/{EMPRESA}/movimientos/m1",
            json={"categoria_id": ""},
        )
    finally:
        _teardown()

    assert r.status_code == 200
    assert r.json()["categoria_id"] is None
    assert len(execute_calls) == 1  # solo el UPDATE, sin refuerzo de historial
    assert "categoria_id = NULL" in execute_calls[0][0]


# ─── GET/POST/PATCH/DELETE /categorias ────────────────────────────────────────

def test_listar_categorias(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {"x": 1})
    monkeypatch.setattr(db, "query_all", lambda *a, **k: [
        {"id": "cat-1", "nombre": "Ventas", "tipo": "deposito", "color": "#22C55E"},
    ])

    try:
        r = client.get(f"/api/v1/empresas/{EMPRESA}/categorias")
    finally:
        _teardown()

    assert r.status_code == 200
    assert r.json()["categorias"][0]["nombre"] == "Ventas"


def test_crear_categoria_exitosa(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_one", lambda *a, **k: None)
    monkeypatch.setattr(db, "execute", lambda *a, **k: {
        "id": "cat-nueva", "nombre": "Marketing", "tipo": "retiro", "color": "#6B7280",
    })

    try:
        r = client.post(
            f"/api/v1/empresas/{EMPRESA}/categorias",
            json={"nombre": "Marketing", "tipo": "retiro", "color": "#6B7280"},
        )
    finally:
        _teardown()

    assert r.status_code == 200
    assert r.json()["id"] == "cat-nueva"


def test_crear_categoria_tipo_invalido_da_400(monkeypatch):
    _auth(monkeypatch)

    try:
        r = client.post(
            f"/api/v1/empresas/{EMPRESA}/categorias",
            json={"nombre": "X", "tipo": "no-valido"},
        )
    finally:
        _teardown()

    assert r.status_code == 400


def test_crear_categoria_duplicada_da_409(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {"x": 1})

    try:
        r = client.post(
            f"/api/v1/empresas/{EMPRESA}/categorias",
            json={"nombre": "Ventas", "tipo": "deposito"},
        )
    finally:
        _teardown()

    assert r.status_code == 409


def test_actualizar_categoria_exitosa(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "execute", lambda *a, **k: {
        "id": "cat-1", "nombre": "Nuevo Nombre", "tipo": "ambos", "color": "#000000",
    })

    try:
        r = client.patch(
            f"/api/v1/empresas/{EMPRESA}/categorias/cat-1",
            json={"nombre": "Nuevo Nombre"},
        )
    finally:
        _teardown()

    assert r.status_code == 200
    assert r.json()["nombre"] == "Nuevo Nombre"


def test_actualizar_categoria_tipo_invalido_da_400(monkeypatch):
    _auth(monkeypatch)

    try:
        r = client.patch(
            f"/api/v1/empresas/{EMPRESA}/categorias/cat-1",
            json={"tipo": "no-valido"},
        )
    finally:
        _teardown()

    assert r.status_code == 400


def test_actualizar_categoria_sin_cambios_da_400(monkeypatch):
    _auth(monkeypatch)

    try:
        r = client.patch(f"/api/v1/empresas/{EMPRESA}/categorias/cat-1", json={})
    finally:
        _teardown()

    assert r.status_code == 400


def test_actualizar_categoria_no_encontrada_da_404(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "execute", lambda *a, **k: None)

    try:
        r = client.patch(
            f"/api/v1/empresas/{EMPRESA}/categorias/cat-x",
            json={"nombre": "X"},
        )
    finally:
        _teardown()

    assert r.status_code == 404


def test_borrar_categoria_exitosa(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {"x": 1})
    monkeypatch.setattr(db, "execute", lambda *a, **k: None)

    try:
        r = client.delete(f"/api/v1/empresas/{EMPRESA}/categorias/cat-1")
    finally:
        _teardown()

    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_borrar_categoria_no_encontrada_da_404(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_one", lambda *a, **k: None)

    try:
        r = client.delete(f"/api/v1/empresas/{EMPRESA}/categorias/cat-x")
    finally:
        _teardown()

    assert r.status_code == 404
