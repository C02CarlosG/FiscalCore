from decimal import Decimal

from fastapi.testclient import TestClient

import backend.main_api as main
from backend.deps import get_current_user
from backend.routers import reportes

client = TestClient(main.app)

RFC = "COP010101AAA"
PROV = "PROV010101AAA"


def _cfdi(**kw):
    base = {
        "uuid": "U1",
        "tipo_comprobante": "I",
        "metodo_pago": "PUE",
        "estado": "vigente",
        "es_anticipo_sat": False,
        "uso_cfdi": "G03",
        "rfc_emisor": PROV,
        "rfc_receptor": RFC,
        "forma_pago": "03",
        "fecha_emision": "2026-01-15",
        "subtotal": Decimal("0"),
        "total": Decimal("0"),
    }
    base.update(kw)
    return base


def _fixture_caso_a_b():
    """Casos A (enero) + B (febrero) de la spec, combinados."""
    cfdis = [
        _cfdi(uuid="RENTA", subtotal=Decimal("20000"), total=Decimal("20000")),
        _cfdi(uuid="HON", metodo_pago="PPD", subtotal=Decimal("15000"), total=Decimal("15000")),
        _cfdi(uuid="NC-RENTA", tipo_comprobante="E", subtotal=Decimal("2000"), total=Decimal("2000")),
        _cfdi(uuid="MERCANCIA-ENE", uso_cfdi="G01", subtotal=Decimal("80000"), total=Decimal("80000")),
        _cfdi(uuid="MERCANCIA-FEB", uso_cfdi="G01", fecha_emision="2026-02-10",
              subtotal=Decimal("40000"), total=Decimal("40000")),
        _cfdi(uuid="SERVICIOS-FEB", fecha_emision="2026-02-10", subtotal=Decimal("10000"), total=Decimal("10000")),
    ]
    pagos = [{"cfdi_uuid": "HON", "importe_pagado": Decimal("15000"), "fecha_pago": "2026-01-20"}]
    return RFC, cfdis, pagos


def _fixture_vacio():
    return RFC, [], []


def _override(monkeypatch, fixture=_fixture_caso_a_b):
    main.app.dependency_overrides[get_current_user] = lambda: {"id": "u1"}
    monkeypatch.setattr(reportes, "validar_acceso_empresa", lambda *a, **k: None)
    monkeypatch.setattr(reportes, "_cargar_datos_deducciones", lambda emp, per: fixture())


def test_deducciones_del_mes_y_acumulado(monkeypatch):
    _override(monkeypatch)
    try:
        resp = client.get("/api/v1/empresas/emp-1/deducciones/2026-02")
    finally:
        main.app.dependency_overrides.clear()
    assert resp.status_code == 200
    body = resp.json()
    assert body["periodo"] == "2026-02"
    assert body["ejercicio"] == 2026

    assert body["del_mes"]["gasto"] == 10000.0
    assert body["del_mes"]["costo_identificado"] == 40000.0
    assert body["total_deducible_mes"] == 10000.0

    assert body["acumulado_ejercicio"]["gasto"] == 43000.0
    assert body["acumulado_ejercicio"]["costo_identificado"] == 120000.0
    assert body["total_deducible_acumulado"] == 43000.0


def test_deducciones_sin_cfdis_devuelve_ceros(monkeypatch):
    _override(monkeypatch, _fixture_vacio)
    try:
        resp = client.get("/api/v1/empresas/emp-1/deducciones/2026-01")
    finally:
        main.app.dependency_overrides.clear()
    assert resp.status_code == 200
    body = resp.json()
    assert body["del_mes"]["gasto"] == 0.0
    assert body["total_deducible_mes"] == 0.0


def test_deducciones_periodo_invalido(monkeypatch):
    _override(monkeypatch)
    try:
        r_mes = client.get("/api/v1/empresas/emp-1/deducciones/2026-13")
        r_fmt = client.get("/api/v1/empresas/emp-1/deducciones/2026-1")
    finally:
        main.app.dependency_overrides.clear()
    assert r_mes.status_code == 422
    assert r_fmt.status_code == 422
