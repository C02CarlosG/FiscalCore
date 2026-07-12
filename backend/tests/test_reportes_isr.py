from decimal import Decimal

from fastapi.testclient import TestClient

import backend.main_api as main
from backend.deps import get_current_user
from backend.routers import reportes

client = TestClient(main.app)


def _config(**kw):
    base = {
        "coeficiente_utilidad": Decimal("0.0850"),
        "tasa_isr": Decimal("0.30"),
        "ptu_pagada": Decimal("0"),
        "perdidas_pendientes": Decimal("0"),
    }
    base.update(kw)
    return base


def _fixture_caso_a_marzo():
    """Caso A de la spec: acumulado ene-mar 2026 -> pago de marzo = 20,400."""
    ingresos_por_mes = {1: Decimal("1000000"), 2: Decimal("2200000"), 3: Decimal("3000000")}
    return _config(), ingresos_por_mes, Decimal("0")


def _fixture_con_retencion():
    """Caso B: enero con retención de ISR 1,500 -> pago 24,000."""
    ingresos_por_mes = {1: Decimal("1000000")}
    return _config(), ingresos_por_mes, Decimal("1500")


def _fixture_sin_config():
    return None, {}, Decimal("0")


def _override(monkeypatch, fixture=_fixture_caso_a_marzo):
    main.app.dependency_overrides[get_current_user] = lambda: {"id": "u1"}
    monkeypatch.setattr(reportes, "validar_acceso_empresa", lambda *a, **k: None)
    monkeypatch.setattr(reportes, "_cargar_datos_isr", lambda emp, per: fixture())


def test_isr_provisional_caso_a_marzo(monkeypatch):
    _override(monkeypatch, _fixture_caso_a_marzo)
    try:
        resp = client.get("/api/v1/empresas/emp-1/isr-provisional/2026-03")
    finally:
        main.app.dependency_overrides.clear()
    assert resp.status_code == 200
    body = resp.json()
    assert body["periodo"] == "2026-03"
    assert body["ejercicio"] == 2026
    assert body["ingreso_nominal_acumulado"] == 3000000.0
    assert body["isr_acumulado"] == 76500.0
    assert body["pagos_provisionales_anteriores"] == 56100.0
    assert body["resultado"]["pago_del_mes"] == 20400.0


def test_isr_provisional_con_retencion(monkeypatch):
    _override(monkeypatch, _fixture_con_retencion)
    try:
        resp = client.get("/api/v1/empresas/emp-1/isr-provisional/2026-01")
    finally:
        main.app.dependency_overrides.clear()
    assert resp.status_code == 200
    body = resp.json()
    assert body["isr_retenido"] == 1500.0
    assert body["resultado"]["pago_del_mes"] == 24000.0


def test_isr_provisional_periodo_invalido(monkeypatch):
    _override(monkeypatch)
    try:
        r_mes = client.get("/api/v1/empresas/emp-1/isr-provisional/2026-13")
        r_fmt = client.get("/api/v1/empresas/emp-1/isr-provisional/2026-1")
    finally:
        main.app.dependency_overrides.clear()
    assert r_mes.status_code == 422
    assert r_fmt.status_code == 422


def test_isr_provisional_sin_config_404(monkeypatch):
    _override(monkeypatch, _fixture_sin_config)
    try:
        resp = client.get("/api/v1/empresas/emp-1/isr-provisional/2026-01")
    finally:
        main.app.dependency_overrides.clear()
    assert resp.status_code == 404
