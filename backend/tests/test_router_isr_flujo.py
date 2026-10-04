"""Router del ISR por flujo (DB mockeada): permisos, validación y delegación."""
import pytest
from fastapi.testclient import TestClient

import backend.main_api as main
from backend import isr_flujo_datos
from backend.deps import get_current_user
from backend.routers import isr_flujo as router

client = TestClient(main.app)
BASE = "/api/v1/empresas/emp-1/isr-flujo"


@pytest.fixture
def con_acceso(monkeypatch):
    main.app.dependency_overrides[get_current_user] = lambda: {"user_id": "u1"}
    monkeypatch.setattr(router, "validar_acceso_empresa", lambda *a, **k: None)
    monkeypatch.setattr(router, "empresa_or_404", lambda eid: {"id": eid, "rfc": "AAA010101AAA", "regimen_fiscal": "612 - PFAE"})
    yield
    main.app.dependency_overrides.clear()


def test_resumen_delega_y_trae_la_aplicabilidad_del_regimen(con_acceso, monkeypatch):
    visto = {}
    monkeypatch.setattr(isr_flujo_datos, "cargar_ajustes", lambda e: {})
    monkeypatch.setattr(isr_flujo_datos, "porcentaje_nomina_exenta", lambda e, ej: visto.update(ejercicio=ej) or isr_flujo_datos.isr_flujo.PORCENTAJE_NOMINA_EXENTA)
    monkeypatch.setattr(isr_flujo_datos, "cargar_eventos", lambda e, rfc, p: visto.update(rfc=rfc, periodo=p) or [])
    monkeypatch.setattr(router, "registrar_evento", lambda *a, **k: None)

    r = client.get(f"{BASE}/2026-09")

    assert r.status_code == 200, r.text
    assert visto == {"ejercicio": 2026, "rfc": "AAA010101AAA", "periodo": "2026-09"}
    d = r.json()
    assert d["regimen"] == {"codigo": "612", "modulo": "flujo"} and d["porcentaje_nomina_exenta"] == 0.47
    assert d["mes"]["utilidad_fiscal_estimada"] == 0.0


@pytest.mark.parametrize("periodo", ["2026-13", "2026-9", "x", "1999-01"])
def test_resumen_rechaza_periodo_invalido(con_acceso, periodo):
    assert client.get(f"{BASE}/{periodo}").status_code == 422


@pytest.mark.parametrize("cuerpo", [{"pct_nomina_exenta": 1.5}, {"pct_nomina_exenta": -0.1}, {}])
def test_config_rechaza_porcentajes_invalidos(con_acceso, cuerpo):
    assert client.put(f"{BASE}/config/2026", json=cuerpo).status_code == 422


def test_config_guarda_con_el_usuario(con_acceso, monkeypatch):
    visto = {}
    monkeypatch.setattr(isr_flujo_datos, "guardar_porcentaje", lambda e, ej, pct, u: visto.update(ej=ej, pct=str(pct), u=u))

    r = client.put(f"{BASE}/config/2026", json={"pct_nomina_exenta": 0.53})

    assert r.status_code == 200 and visto == {"ej": 2026, "pct": "0.53", "u": "u1"}


def test_ajuste_exige_motivo_con_texto(con_acceso):
    cuerpo = {"uuid": "U1", "lado": "ingreso"}
    assert client.put(f"{BASE}/ajustes", json={**cuerpo, "motivo": "   "}).status_code == 422
    assert client.put(f"{BASE}/ajustes", json={**cuerpo, "lado": "otro", "motivo": "x"}).status_code == 422


def test_detalle_valida_bloque_y_lado(con_acceso):
    assert client.get(f"{BASE}/2026-09/detalle", params={"lado": "ingreso", "bloque": "otro"}).status_code == 422
    assert client.get(f"{BASE}/2026-09/detalle", params={"lado": "x", "bloque": "contado"}).status_code == 422
