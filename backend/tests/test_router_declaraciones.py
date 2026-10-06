"""Router de declaraciones (DB mockeada): permisos, validación y delegación."""
import pytest
from fastapi.testclient import TestClient

import backend.main_api as main
from backend import declaraciones_datos, isr_flujo_datos, iva_flujo_datos
from backend.deps import get_current_user
from backend.routers import declaraciones as router

client = TestClient(main.app)
BASE = "/api/v1/empresas/emp-1/declaraciones"


@pytest.fixture
def con_acceso(monkeypatch):
    main.app.dependency_overrides[get_current_user] = lambda: {"user_id": "u1"}
    monkeypatch.setattr(router, "validar_acceso_empresa", lambda *a, **k: None)
    monkeypatch.setattr(router, "empresa_or_404", lambda eid: {"id": eid, "rfc": "AAA010101AAA", "regimen_fiscal": "612"})
    yield
    main.app.dependency_overrides.clear()


def test_comparativo_junta_lo_declarado_y_lo_calculado(con_acceso, monkeypatch):
    monkeypatch.setattr(iva_flujo_datos, "cargar_ajustes", lambda e: {})
    monkeypatch.setattr(iva_flujo_datos, "cargar_eventos", lambda e, rfc, p, a: [])
    monkeypatch.setattr(isr_flujo_datos, "cargar_ajustes", lambda e: {})
    monkeypatch.setattr(isr_flujo_datos, "porcentaje_nomina_exenta", lambda e, ej: isr_flujo_datos.isr_flujo.PORCENTAJE_NOMINA_EXENTA)
    monkeypatch.setattr(isr_flujo_datos, "cargar_eventos", lambda e, rfc, p: [])
    monkeypatch.setattr(isr_flujo_datos, "parametros_provisional", lambda e, ej: {
        "ptu_pagada": 0, "ptu_mes_pago": None, "perdidas_pendientes": 0, "arrendamiento_periodicidad": "mensual", "deduccion_opcional_35": False})
    monkeypatch.setattr(declaraciones_datos, "pagos_del_ejercicio", lambda e, ej, i: {})
    monkeypatch.setattr(declaraciones_datos, "cadena",
                        lambda e, p, i: [{"impuesto_trasladado": 10, "impuesto_a_cargo": 0}] if i == "iva" else [])

    r = client.get(f"{BASE}/2026-09")

    assert r.status_code == 200, r.text
    d = r.json()
    assert d["isr"]["estado"] == "sin_declaracion"
    assert d["iva"]["estado"] == "con_diferencias"
    assert {x["clave"]: x for x in d["iva"]["renglones"]}["impuesto_trasladado"]["diferencia"] == 10.0


@pytest.mark.parametrize("ruta", ["2026-13", "2026-9", "x"])
def test_periodo_invalido_es_422(con_acceso, ruta):
    assert client.get(f"{BASE}/{ruta}").status_code == 422
    assert client.put(f"{BASE}/{ruta}/iva", json={}).status_code == 422


def test_impuesto_o_importes_invalidos_son_422(con_acceso):
    assert client.put(f"{BASE}/2026-09/ieps", json={}).status_code == 422
    assert client.put(f"{BASE}/2026-09/iva", json={"monto_pagado": -1}).status_code == 422
    assert client.put(f"{BASE}/2026-09/iva", json={"ingresos": 1.234}).status_code == 422
    assert client.put(f"{BASE}/2026-09/iva", json={"tipo": "otra"}).status_code == 422
    for campo in ("ingresos", "deducciones", "impuesto_trasladado", "impuesto_acreditable", "retenciones",
                  "retenciones_a_terceros", "saldo_a_favor_aplicado"):
        assert client.put(f"{BASE}/2026-09/iva", json={campo: -1}).status_code == 422, campo
    assert client.put(f"{BASE}/2026-09/isr", json={"saldo_a_favor_aplicado": 10}).status_code == 422


def test_guardar_delega_con_el_usuario(con_acceso, monkeypatch):
    visto = {}
    monkeypatch.setattr(declaraciones_datos, "guardar", lambda e, p, i, tipo, datos, u: visto.update(p=p, i=i, tipo=tipo, datos=datos, u=u) or 1)
    monkeypatch.setattr(declaraciones_datos, "cadena", lambda e, p, i: [{"periodo": p, "impuesto": i}])

    r = client.put(f"{BASE}/2026-09/iva", json={"impuesto_a_cargo": "-1100.50", "monto_pagado": 1100})

    assert r.status_code == 200 and visto["u"] == "u1" and visto["tipo"] == "normal"
    assert str(visto["datos"]["impuesto_a_cargo"]) == "-1100.50"


def test_un_conflicto_del_historial_es_409(con_acceso, monkeypatch):
    def conflicto(*a):
        raise declaraciones_datos.ConflictoDeclaracion("Ya hay una complementaria")
    monkeypatch.setattr(declaraciones_datos, "guardar", conflicto)

    assert client.put(f"{BASE}/2026-09/iva", json={}).status_code == 409


def test_eliminar_inexistente_es_404(con_acceso, monkeypatch):
    monkeypatch.setattr(declaraciones_datos, "eliminar_ultima", lambda *a: False)
    assert client.delete(f"{BASE}/2026-09/isr").status_code == 404


def test_estado_del_ejercicio_pide_ejercicio_valido(con_acceso, monkeypatch):
    monkeypatch.setattr(declaraciones_datos, "del_ejercicio", lambda e, ej: [])
    assert client.get(BASE).status_code == 422
    assert client.get(BASE, params={"ejercicio": 1999}).status_code == 422
    assert client.get(BASE, params={"ejercicio": 2026}).json() == {"ejercicio": 2026, "items": []}


def test_comparativo_compara_el_pago_provisional_del_isr_en_612(con_acceso, monkeypatch):
    monkeypatch.setattr(iva_flujo_datos, "cargar_ajustes", lambda e: {})
    monkeypatch.setattr(iva_flujo_datos, "cargar_eventos", lambda e, rfc, p, a: [])
    monkeypatch.setattr(isr_flujo_datos, "cargar_ajustes", lambda e: {})
    monkeypatch.setattr(isr_flujo_datos, "porcentaje_nomina_exenta", lambda e, ej: isr_flujo_datos.isr_flujo.PORCENTAJE_NOMINA_EXENTA)
    monkeypatch.setattr(isr_flujo_datos, "cargar_eventos", lambda e, rfc, p: [])
    monkeypatch.setattr(isr_flujo_datos, "parametros_provisional", lambda e, ej: {
        "ptu_pagada": 0, "ptu_mes_pago": None, "perdidas_pendientes": 0, "arrendamiento_periodicidad": "mensual", "deduccion_opcional_35": False})
    monkeypatch.setattr(declaraciones_datos, "pagos_del_ejercicio", lambda e, ej, i: {})
    monkeypatch.setattr(declaraciones_datos, "cadena", lambda e, p, i: [{"impuesto_a_cargo": 50}] if i == "isr" else [])

    d = client.get(f"{BASE}/2026-09").json()
    a_cargo = {x["clave"]: x for x in d["isr"]["renglones"]}["impuesto_a_cargo"]

    assert a_cargo["calculado"] == 0.0 and a_cargo["declarado"] == 50.0 and a_cargo["estado"] == "diferencia"   # sin movimientos: pago 0
    assert "612" in d["aviso"]
