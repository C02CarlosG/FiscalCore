from fastapi.testclient import TestClient

import backend.main_api as main
from backend.deps import get_current_user
from backend.routers import cfdi

client = TestClient(main.app)

RFC = "COP010101AAA"
EMPRESA = {"id": "emp-1", "rfc": RFC}


def _override(monkeypatch, rows):
    main.app.dependency_overrides[get_current_user] = lambda: {"id": "u1"}
    monkeypatch.setattr(cfdi, "validar_acceso_empresa", lambda *a, **k: None)
    monkeypatch.setattr(cfdi, "empresa_or_404", lambda eid: EMPRESA)
    monkeypatch.setattr(cfdi.db, "query_all", lambda *a, **k: rows)


def test_visor_sat_clasifica_direccion_y_resumen(monkeypatch):
    rows = [
        {
            "uuid": "U1", "tipo_comprobante": "I", "serie": "A", "folio": "1",
            "fecha": "2026-01-10", "rfc_emisor": RFC, "nombre_emisor": "Copla Sur",
            "rfc_receptor": "XAXX010101000", "nombre_receptor": "Cliente",
            "total": 1160, "iva_trasladado": 160, "estado": "vigente",
        },
        {
            "uuid": "U2", "tipo_comprobante": "I", "serie": "B", "folio": "2",
            "fecha": "2026-01-12", "rfc_emisor": "PROV010101AAA", "nombre_emisor": "Proveedor",
            "rfc_receptor": RFC, "nombre_receptor": "Copla Sur",
            "total": 500, "iva_trasladado": 69, "estado": "cancelado",
        },
    ]
    _override(monkeypatch, rows)
    try:
        resp = client.get("/api/v1/empresas/emp-1/cfdi/visor?periodo=2026-01")
    finally:
        main.app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["resumen"]["total_cfdi"] == 2
    assert body["resumen"]["emitidos"] == 1
    assert body["resumen"]["recibidos"] == 1
    assert body["resumen"]["vigentes"] == 1
    assert body["resumen"]["canceladas"] == 1
    assert body["cfdi"][0]["direccion"] == "emitido"
    assert body["cfdi"][1]["direccion"] == "recibido"


def test_visor_sat_periodo_requerido(monkeypatch):
    _override(monkeypatch, [])
    try:
        resp = client.get("/api/v1/empresas/emp-1/cfdi/visor")
    finally:
        main.app.dependency_overrides.clear()
    assert resp.status_code == 422


def test_visor_sat_periodo_con_formato_invalido(monkeypatch):
    _override(monkeypatch, [])
    try:
        resp = client.get("/api/v1/empresas/emp-1/cfdi/visor?periodo=2026-1")
    finally:
        main.app.dependency_overrides.clear()
    assert resp.status_code == 422


def test_visor_sat_periodo_con_mes_invalido(monkeypatch):
    _override(monkeypatch, [])
    try:
        resp = client.get("/api/v1/empresas/emp-1/cfdi/visor?periodo=2026-13")
    finally:
        main.app.dependency_overrides.clear()
    assert resp.status_code == 400


def test_cfdi_nomina_resumen(monkeypatch):
    rows = [
        {
            "uuid": "N1", "serie": None, "folio": "10", "fecha": "2026-01-15",
            "rfc_receptor": "EMPL010101AAA", "nombre_receptor": "Empleado Uno",
            "subtotal": 10000, "total": 10000, "estado": "vigente",
        },
        {
            "uuid": "N2", "serie": None, "folio": "11", "fecha": "2026-01-15",
            "rfc_receptor": "EMPL020202BBB", "nombre_receptor": "Empleado Dos",
            "subtotal": 8000, "total": 8000, "estado": "cancelado",
        },
    ]
    _override(monkeypatch, rows)
    try:
        resp = client.get("/api/v1/empresas/emp-1/cfdi/nomina?periodo=2026-01")
    finally:
        main.app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["resumen"]["num_recibos"] == 2
    assert body["resumen"]["total_nomina"] == 18000.0
    assert body["resumen"]["vigentes"] == 1
    assert body["resumen"]["canceladas"] == 1
    assert body["recibos"][0]["rfc_receptor"] == "EMPL010101AAA"
