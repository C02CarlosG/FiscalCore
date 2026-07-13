"""Tests del router backend/routers/conciliacion.py (Día 22).

DB mockeada directamente sobre `backend.db`. `validar_acceso_empresa` y
`empresa_or_404` se monkeypatchean a nivel de módulo (igual que en los tests
de reportes) para no tener que simular esas dos consultas en cada test.
"""
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

import backend.main_api as main
from backend import db
from backend.deps import get_current_user
from backend.routers import conciliacion

client = TestClient(main.app)


def _auth(monkeypatch):
    main.app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "user_id": "u1"}
    monkeypatch.setattr(conciliacion, "validar_acceso_empresa", lambda *a, **k: None)
    monkeypatch.setattr(conciliacion, "empresa_or_404", lambda eid: {"id": eid})


def _dispatch(monkeypatch, query_one_por_marca=None, query_all_por_marca=None):
    """Simula `db.query_one`/`db.query_all` devolviendo un valor distinto según
    un substring reconocible de cada SQL, para endpoints que hacen varias
    consultas distintas en una sola llamada."""
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


# ─── GET /empresas/{id}/periodos ──────────────────────────────────────────────

def test_listar_periodos(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_all", lambda *a, **k: [
        {"periodo": "2026-02"}, {"periodo": "2026-01"},
    ])

    try:
        r = client.get("/api/v1/empresas/emp-1/periodos")
    finally:
        main.app.dependency_overrides.clear()

    assert r.status_code == 200
    assert r.json()["periodos"] == ["2026-02", "2026-01"]


# ─── GET /empresas/{id}/cierre/{periodo} ──────────────────────────────────────

def test_vista_cierre_puede_cerrar_sin_bloqueadores_y_conciliacion_alta(monkeypatch):
    _auth(monkeypatch)
    _dispatch(
        monkeypatch,
        query_one_por_marca=[
            ("tipo_match = 'heuristico'", {"total": 0}),
            ("scoring_fiscal", {"score_total": Decimal("90.0")}),
        ],
        query_all_por_marca=[
            ("JOIN riesgos r", []),
            ("GROUP BY tipo_match", [
                {"tipo_match": "exacto", "total": 8},
                {"tipo_match": "sin_cfdi", "total": 2},
            ]),
        ],
    )

    try:
        r = client.get("/api/v1/empresas/emp-1/cierre/2026-01")
    finally:
        main.app.dependency_overrides.clear()

    assert r.status_code == 200
    body = r.json()
    assert body["puede_cerrar"] is True
    assert body["razon_bloqueo"] is None
    assert body["score"] == 90.0
    assert body["bloqueadores"] == []
    assert body["conciliacion"]["pct_conciliado"] == 80.0
    assert body["conciliacion"]["sin_cfdi"] == 2
    assert body["conciliacion"]["total"] == 10


def test_vista_cierre_bloqueado_por_riesgo_critico(monkeypatch):
    _auth(monkeypatch)
    _dispatch(
        monkeypatch,
        query_one_por_marca=[
            ("tipo_match = 'heuristico'", {"total": 0}),
            ("scoring_fiscal", None),
        ],
        query_all_por_marca=[
            ("JOIN riesgos r", [{
                "id": "d1", "estado": "abierto", "monto_afectado": Decimal("500.00"),
                "descripcion": "Gasto sin CFDI", "periodo": "2026-01",
                "cfdi_id": None, "movimiento_id": "m1", "created_at": None,
                "codigo": "gastos_sin_cfdi", "nombre": "Gasto sin CFDI",
                "severidad": "critico", "accion_sugerida": "Revisar movimiento",
                "cfdi_uuid": None, "cfdi_fecha": None,
                "cfdi_rfc_emisor": None, "cfdi_rfc_receptor": None, "cfdi_total": None,
                "mov_fecha": date(2026, 1, 15), "mov_concepto": "COMISION", "mov_monto": Decimal("500.00"),
                "mov_rfc": None,
            }]),
            ("GROUP BY tipo_match", [
                {"tipo_match": "exacto", "total": 8},
                {"tipo_match": "sin_cfdi", "total": 2},
            ]),
        ],
    )

    try:
        r = client.get("/api/v1/empresas/emp-1/cierre/2026-01")
    finally:
        main.app.dependency_overrides.clear()

    body = r.json()
    assert body["puede_cerrar"] is False
    assert "crítico" in body["razon_bloqueo"]
    assert len(body["bloqueadores"]) == 1
    assert body["acciones"][0]["contexto"]["tipo"] == "movimiento"
    assert body["acciones"][0]["contexto"]["monto"] == 500.0
    assert body["score"] is None


def test_vista_cierre_bloqueado_por_baja_conciliacion(monkeypatch):
    _auth(monkeypatch)
    _dispatch(
        monkeypatch,
        query_one_por_marca=[
            ("tipo_match = 'heuristico'", {"total": 0}),
            ("scoring_fiscal", None),
        ],
        query_all_por_marca=[
            ("JOIN riesgos r", []),
            ("GROUP BY tipo_match", [
                {"tipo_match": "exacto", "total": 5},
                {"tipo_match": "sin_cfdi", "total": 5},
            ]),
        ],
    )

    try:
        r = client.get("/api/v1/empresas/emp-1/cierre/2026-01")
    finally:
        main.app.dependency_overrides.clear()

    body = r.json()
    assert body["puede_cerrar"] is False
    assert "50.0%" in body["razon_bloqueo"]
    assert body["conciliacion"]["pct_conciliado"] == 50.0


def test_vista_cierre_contexto_cfdi(monkeypatch):
    _auth(monkeypatch)
    _dispatch(
        monkeypatch,
        query_one_por_marca=[
            ("tipo_match = 'heuristico'", {"total": 0}),
            ("scoring_fiscal", None),
        ],
        query_all_por_marca=[
            ("JOIN riesgos r", [{
                "id": "d1", "estado": "abierto", "monto_afectado": Decimal("1000.00"),
                "descripcion": "Ingreso no facturado", "periodo": "2026-01",
                "cfdi_id": "c1", "movimiento_id": None, "created_at": None,
                "codigo": "ingresos_no_facturados", "nombre": "Ingreso no facturado",
                "severidad": "medio", "accion_sugerida": "Emitir CFDI",
                "cfdi_uuid": "UUID-1", "cfdi_fecha": date(2026, 1, 5),
                "cfdi_rfc_emisor": "EMP010101AAA", "cfdi_rfc_receptor": "CLI010101AAA",
                "cfdi_total": Decimal("1000.00"),
                "mov_fecha": None, "mov_concepto": None, "mov_monto": None, "mov_rfc": None,
            }]),
            ("GROUP BY tipo_match", []),
        ],
    )

    try:
        r = client.get("/api/v1/empresas/emp-1/cierre/2026-01")
    finally:
        main.app.dependency_overrides.clear()

    body = r.json()
    ctx = body["acciones"][0]["contexto"]
    assert ctx["tipo"] == "cfdi"
    assert ctx["uuid"] == "UUID-1"
    assert ctx["total"] == 1000.0
    # severidad "medio" no bloquea (solo critico/alto)
    assert body["bloqueadores"] == []


# ─── GET /empresas/{id}/conciliaciones/accionables ────────────────────────────

def test_conciliaciones_accionables_sin_periodo_no_filtra(monkeypatch):
    _auth(monkeypatch)
    llamadas = []

    def _query_all(sql, params=()):
        llamadas.append((sql, params))
        return [{
            "id": "c1", "tipo_match": "sin_cfdi", "monto_movimiento": Decimal("100.00"),
            "monto_cfdi": None, "diferencia": None, "porcentaje_match": None,
            "periodo": "2026-01", "movimiento_id": "m1", "mov_fecha": "2026-01-05",
            "concepto": "PAGO", "mov_monto": Decimal("100.00"), "mov_tipo": "cargo",
            "rfc_detectado": None,
        }]

    monkeypatch.setattr(db, "query_all", _query_all)

    try:
        r = client.get("/api/v1/empresas/emp-1/conciliaciones/accionables")
    finally:
        main.app.dependency_overrides.clear()

    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["pares"][0]["monto_movimiento"] == 100.0

    sql, params = llamadas[-1]
    assert params == ("emp-1",)
    assert "AND con.periodo = %s" not in sql


def test_conciliaciones_accionables_filtra_por_periodo(monkeypatch):
    _auth(monkeypatch)
    llamadas = []

    def _query_all(sql, params=()):
        llamadas.append((sql, params))
        return []

    monkeypatch.setattr(db, "query_all", _query_all)

    try:
        r = client.get("/api/v1/empresas/emp-1/conciliaciones/accionables?periodo=2026-01")
    finally:
        main.app.dependency_overrides.clear()

    assert r.status_code == 200
    sql, params = llamadas[-1]
    assert params == ("emp-1", "2026-01")
    assert "con.periodo = %s" in sql


# ─── GET /empresas/{id}/conciliaciones ────────────────────────────────────────

def test_listar_conciliaciones_calcula_pct(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_all", lambda *a, **k: [
        {"tipo_match": "exacto", "total": 6},
        {"tipo_match": "parcial", "total": 2},
        {"tipo_match": "sin_cfdi", "total": 1},
        {"tipo_match": "sin_movimiento", "total": 1},
    ])

    try:
        r = client.get("/api/v1/empresas/emp-1/conciliaciones")
    finally:
        main.app.dependency_overrides.clear()

    body = r.json()
    assert body["total"] == 10
    assert body["exacto"] == 6
    assert body["parcial"] == 2
    assert body["sin_cfdi"] == 1
    assert body["sin_movimiento"] == 1
    assert body["pct_conciliado"] == 80.0


def test_listar_conciliaciones_sin_datos_da_pct_cero(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_all", lambda *a, **k: [])

    try:
        r = client.get("/api/v1/empresas/emp-1/conciliaciones")
    finally:
        main.app.dependency_overrides.clear()

    body = r.json()
    assert body["total"] == 0
    assert body["pct_conciliado"] == 0.0


def test_listar_conciliaciones_filtra_por_periodo(monkeypatch):
    _auth(monkeypatch)
    llamadas = []

    def _query_all(sql, params=()):
        llamadas.append((sql, params))
        return []

    monkeypatch.setattr(db, "query_all", _query_all)

    try:
        r = client.get("/api/v1/empresas/emp-1/conciliaciones?periodo=2026-01")
    finally:
        main.app.dependency_overrides.clear()

    sql, params = llamadas[-1]
    assert params == ("emp-1", "2026-01")
    assert "AND periodo = %s" in sql
