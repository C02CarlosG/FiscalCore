"""Tests del router backend/routers/emitidos.py (Día 23): /emitidos y /recibidos.

DB mockeada sobre `backend.db`. `validar_acceso_empresa`/`empresa_or_404` se
monkeypatchean a nivel de módulo.
"""
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

import backend.main_api as main
from backend import db
from backend.deps import get_current_user
from backend.routers import emitidos

client = TestClient(main.app)

EMPRESA = "emp-1"
RFC_EMPRESA = "EMP010101AAA"


def _auth(monkeypatch):
    main.app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "user_id": "u1"}
    monkeypatch.setattr(emitidos, "validar_acceso_empresa", lambda *a, **k: None)
    monkeypatch.setattr(emitidos, "empresa_or_404", lambda eid: {"id": eid, "rfc": RFC_EMPRESA})


def _teardown():
    main.app.dependency_overrides.clear()


def _cfdi_emitido(**kw):
    base = {
        "uuid": "UUID-1", "tipo_comprobante": "I", "serie": "A", "folio": "100",
        "fecha": date(2026, 1, 10), "rfc_receptor": "CLI010101AAA", "nombre_receptor": "Cliente Uno",
        "subtotal": Decimal("1000.00"), "descuento": Decimal("0"), "total": Decimal("1160.00"),
        "iva_trasladado": Decimal("160.00"), "metodo_pago": "PUE", "forma_pago": "03",
        "uso_cfdi": "G03", "moneda": "MXN", "estado": "vigente", "estado_pago": None,
        "cfdi_relacionados": [], "es_anticipo_sat": False,
    }
    base.update(kw)
    return base


# ─── GET /emitidos ─────────────────────────────────────────────────────────────

def test_get_emitidos_venta_normal_sin_anticipo(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_all", lambda *a, **k: [_cfdi_emitido()])
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {"n": 0})

    try:
        r = client.get(f"/api/v1/empresas/{EMPRESA}/emitidos", params={"periodo": "2026-01"})
    finally:
        _teardown()

    assert r.status_code == 200
    body = r.json()
    assert len(body["ingresos"]["ventas_servicios"]) == 1
    assert body["ingresos"]["anticipos"] == []
    assert body["resumen"]["subtotal"] == 1000.0
    assert body["resumen"]["iva_trasladado"] == 160.0
    assert body["resumen"]["total_facturado"] == 1160.0
    assert body["resumen"]["vigentes"] == 1
    assert body["resumen"]["canceladas"] == 0
    assert body["resumen"]["advertencias"] == []


def test_get_emitidos_anticipo_sat_se_clasifica_aparte(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_all", lambda *a, **k: [_cfdi_emitido(
        uuid="UUID-ANT", es_anticipo_sat=True,
        subtotal=Decimal("5000.00"), total=Decimal("5000.00"), iva_trasladado=Decimal("0"),
    )])
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {"n": 0})

    try:
        r = client.get(f"/api/v1/empresas/{EMPRESA}/emitidos", params={"periodo": "2026-01"})
    finally:
        _teardown()

    body = r.json()
    assert len(body["ingresos"]["anticipos"]) == 1
    assert body["ingresos"]["anticipos"][0]["es_anticipo"] is True
    assert body["resumen"]["total_anticipos_acumulados"] == 5000.0
    assert body["ingresos"]["ventas_servicios"] == []


def test_get_emitidos_factura_con_anticipo_y_aplicacion_sin_advertencia(monkeypatch):
    _auth(monkeypatch)
    factura = _cfdi_emitido(
        uuid="UUID-FAC", cfdi_relacionados=[{"tipo_relacion": "07", "uuids": ["UUID-ANT"]}],
    )
    egreso_aplicacion = _cfdi_emitido(
        uuid="UUID-EGR", tipo_comprobante="E", forma_pago="30",
        cfdi_relacionados=[{"tipo_relacion": "07", "uuids": ["UUID-FAC"]}],
        total=Decimal("1160.00"), subtotal=Decimal("1000.00"), iva_trasladado=Decimal("160.00"),
    )
    monkeypatch.setattr(db, "query_all", lambda *a, **k: [factura, egreso_aplicacion])
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {"n": 0})

    try:
        r = client.get(f"/api/v1/empresas/{EMPRESA}/emitidos", params={"periodo": "2026-01"})
    finally:
        _teardown()

    body = r.json()
    assert len(body["ingresos"]["facturas_con_anticipo"]) == 1
    assert body["ingresos"]["facturas_con_anticipo"][0]["es_factura_con_anticipo"] is True
    assert len(body["egresos"]["aplicaciones_anticipo"]) == 1
    assert body["egresos"]["notas_credito"] == []
    assert body["resumen"]["advertencias"] == []


def test_get_emitidos_factura_con_anticipo_sin_aplicacion_genera_advertencia(monkeypatch):
    _auth(monkeypatch)
    factura = _cfdi_emitido(
        uuid="UUID-FAC", cfdi_relacionados=[{"tipo_relacion": "07", "uuids": ["UUID-ANT"]}],
    )
    monkeypatch.setattr(db, "query_all", lambda *a, **k: [factura])
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {"n": 0})

    try:
        r = client.get(f"/api/v1/empresas/{EMPRESA}/emitidos", params={"periodo": "2026-01"})
    finally:
        _teardown()

    body = r.json()
    advertencias = body["resumen"]["advertencias"]
    assert len(advertencias) == 1
    assert advertencias[0]["tipo"] == "sin_egreso_anticipo"
    assert advertencias[0]["uuid_factura"] == "UUID-FAC"


def test_get_emitidos_nota_credito_sin_forma_pago_30(monkeypatch):
    _auth(monkeypatch)
    nota = _cfdi_emitido(uuid="UUID-NC", tipo_comprobante="E", forma_pago="03")
    monkeypatch.setattr(db, "query_all", lambda *a, **k: [nota])
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {"n": 0})

    try:
        r = client.get(f"/api/v1/empresas/{EMPRESA}/emitidos", params={"periodo": "2026-01"})
    finally:
        _teardown()

    body = r.json()
    assert len(body["egresos"]["notas_credito"]) == 1
    assert body["egresos"]["aplicaciones_anticipo"] == []


def test_get_emitidos_cuenta_complementos_de_pago(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_all", lambda *a, **k: [])
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {"n": 3})

    try:
        r = client.get(f"/api/v1/empresas/{EMPRESA}/emitidos", params={"periodo": "2026-01"})
    finally:
        _teardown()

    body = r.json()
    assert body["resumen"]["num_tipo_p"] == 3
    assert body["resumen"]["total_cfdi_periodo"] == 3


def test_get_emitidos_cfdi_cancelado_no_cuenta_como_vigente(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_all", lambda *a, **k: [_cfdi_emitido(estado="cancelado")])
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {"n": 0})

    try:
        r = client.get(f"/api/v1/empresas/{EMPRESA}/emitidos", params={"periodo": "2026-01"})
    finally:
        _teardown()

    body = r.json()
    assert body["resumen"]["vigentes"] == 0
    assert body["resumen"]["canceladas"] == 1


def test_get_emitidos_sin_periodo_da_422(monkeypatch):
    _auth(monkeypatch)
    try:
        r = client.get(f"/api/v1/empresas/{EMPRESA}/emitidos")
    finally:
        _teardown()
    assert r.status_code == 422


# ─── GET /recibidos ────────────────────────────────────────────────────────────

def _cfdi_recibido(**kw):
    base = {
        "uuid": "UUID-R1", "tipo_comprobante": "I", "serie": "B", "folio": "50",
        "fecha": date(2026, 1, 15), "rfc_emisor": "PROV010101AAA", "nombre_emisor": "Proveedor Uno",
        "subtotal": Decimal("2000.00"), "descuento": Decimal("0"), "total": Decimal("2320.00"),
        "iva_trasladado": Decimal("320.00"), "metodo_pago": "PUE", "forma_pago": "03",
        "moneda": "MXN", "estado": "vigente",
    }
    base.update(kw)
    return base


def test_get_recibidos_separa_compras_y_egresos(monkeypatch):
    _auth(monkeypatch)
    compra = _cfdi_recibido()
    egreso = _cfdi_recibido(uuid="UUID-R2", tipo_comprobante="E", total=Decimal("100.00"),
                             subtotal=Decimal("86.21"), iva_trasladado=Decimal("13.79"))
    monkeypatch.setattr(db, "query_all", lambda *a, **k: [compra, egreso])

    try:
        r = client.get(f"/api/v1/empresas/{EMPRESA}/recibidos", params={"periodo": "2026-01"})
    finally:
        _teardown()

    assert r.status_code == 200
    body = r.json()
    assert len(body["compras"]) == 1
    assert len(body["egresos"]) == 1
    assert body["resumen"]["subtotal"] == 2000.0
    assert body["resumen"]["iva_acreditable"] == 320.0
    assert body["resumen"]["total"] == 2320.0
    assert body["resumen"]["num_compras"] == 1
    assert body["resumen"]["num_egresos"] == 1
    assert body["resumen"]["vigentes"] == 1
    assert body["resumen"]["canceladas"] == 0


def test_get_recibidos_cancelado_no_cuenta_vigente(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_all", lambda *a, **k: [_cfdi_recibido(estado="cancelado")])

    try:
        r = client.get(f"/api/v1/empresas/{EMPRESA}/recibidos", params={"periodo": "2026-01"})
    finally:
        _teardown()

    body = r.json()
    assert body["resumen"]["vigentes"] == 0
    assert body["resumen"]["canceladas"] == 1


def test_get_recibidos_sin_periodo_da_422(monkeypatch):
    _auth(monkeypatch)
    try:
        r = client.get(f"/api/v1/empresas/{EMPRESA}/recibidos")
    finally:
        _teardown()
    assert r.status_code == 422
