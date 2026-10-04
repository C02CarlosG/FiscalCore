"""Router de Inicio (DB mockeada): permisos, validación y delegación."""
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

import backend.main_api as main
from backend import inicio_datos
from backend.deps import get_current_user
from backend.routers import inicio as router_inicio

client = TestClient(main.app)
BASE = "/api/v1/empresas/emp-1/inicio"


@pytest.fixture
def con_acceso(monkeypatch):
    main.app.dependency_overrides[get_current_user] = lambda: {"user_id": "u1"}
    monkeypatch.setattr(router_inicio, "validar_acceso_empresa", lambda *a, **k: None)
    monkeypatch.setattr(router_inicio, "empresa_or_404", lambda eid: {"id": eid, "rfc": "AAA010101AAA"})
    yield
    main.app.dependency_overrides.clear()


def test_resumen_delega_y_serializa_importes_como_numero(con_acceso, monkeypatch):
    visto = {}

    def _agregados(empresa_id, rfc, periodo):
        visto.update(empresa_id=empresa_id, rfc=rfc, periodo=periodo)
        return [{"mes": "2026-09", "lado": "emitido", "tipo": "I", "base": Decimal("1000.50"), "cuenta": 2}]

    monkeypatch.setattr(inicio_datos, "cargar_agregados", _agregados)

    r = client.get(f"{BASE}/resumen", params={"periodo": "2026-09"})

    assert r.status_code == 200, r.text
    assert visto == {"empresa_id": "emp-1", "rfc": "AAA010101AAA", "periodo": "2026-09"}
    d = r.json()
    assert d["empresa_id"] == "emp-1" and d["ejercicio"] == 2026
    assert d["ingresos"]["periodo"] == {"facturado": 1000.5, "notas_credito": 0.0, "neto": 1000.5, "cfdi": 2}
    assert len(d["meses"]) == 12


@pytest.mark.parametrize("periodo", ["2026-13", "2026-9", "abc", "1999-01", "2026-09; DROP"])
def test_resumen_rechaza_periodo_invalido(con_acceso, monkeypatch, periodo):
    monkeypatch.setattr(inicio_datos, "cargar_agregados", lambda *a: pytest.fail("no debía consultar"))

    assert client.get(f"{BASE}/resumen", params={"periodo": periodo}).status_code == 422


def test_resumen_exige_periodo(con_acceso):
    assert client.get(f"{BASE}/resumen").status_code == 422


def test_iva_anual_delega_con_ejercicio_y_periodo(con_acceso, monkeypatch):
    visto = {}

    def _iva(empresa_id, rfc, ejercicio, periodo=None):
        visto.update(empresa_id=empresa_id, rfc=rfc, ejercicio=ejercicio, periodo=periodo)
        return [], [{"codigo": "x", "mensaje": "aviso", "cfdi": 1}]

    monkeypatch.setattr(inicio_datos, "cargar_iva_ejercicio", _iva)

    r = client.get(f"{BASE}/iva-anual", params={"ejercicio": 2026, "periodo": "2026-03"})

    assert r.status_code == 200, r.text
    assert visto == {"empresa_id": "emp-1", "rfc": "AAA010101AAA", "ejercicio": 2026, "periodo": "2026-03"}
    d = r.json()
    assert d["ejercicio"] == 2026 and len(d["meses"]) == 12
    assert d["totales"]["total_a_cargo"] == 0.0 and d["totales"]["total_a_favor"] == 0.0
    assert d["iva_retenido_incluido"] is True
    assert d["advertencias"] == [{"codigo": "x", "mensaje": "aviso", "cfdi": 1}]


@pytest.mark.parametrize("params", [{"ejercicio": 1999}, {"ejercicio": 2100}, {"ejercicio": "x"}, {},
                                    {"ejercicio": 2026, "periodo": "2026-14"},
                                    {"ejercicio": 2026, "periodo": "2025-12"},
                                    {"ejercicio": 2026, "periodo": "2027-01"}])
def test_iva_anual_rechaza_parametros_invalidos(con_acceso, monkeypatch, params):
    monkeypatch.setattr(inicio_datos, "cargar_iva_ejercicio", lambda *a: pytest.fail("no debía consultar"))

    assert client.get(f"{BASE}/iva-anual", params=params).status_code == 422


def test_sin_acceso_a_la_empresa_es_403(monkeypatch):
    from fastapi import HTTPException

    main.app.dependency_overrides[get_current_user] = lambda: {"user_id": "u1"}

    def _sin_acceso(*a, **k):
        raise HTTPException(status_code=403, detail="Sin acceso a esta empresa")

    monkeypatch.setattr(router_inicio, "validar_acceso_empresa", _sin_acceso)
    try:
        assert client.get(f"{BASE}/resumen", params={"periodo": "2026-09"}).status_code == 403
        assert client.get(f"{BASE}/iva-anual", params={"ejercicio": 2026}).status_code == 403
    finally:
        main.app.dependency_overrides.clear()


def test_sin_sesion_es_401():
    assert client.get(f"{BASE}/resumen", params={"periodo": "2026-09"}).status_code in (401, 403)
