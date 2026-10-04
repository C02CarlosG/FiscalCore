"""Router del IVA por flujo (DB mockeada): permisos, validación, delegación y auditoría."""
from datetime import datetime

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import backend.main_api as main
from backend import iva_flujo_datos
from backend.deps import get_current_user
from backend.routers import iva_flujo as router

client = TestClient(main.app)
BASE = "/api/v1/empresas/emp-1/iva-flujo"
UUID = "1F3A0001-0000-4000-8000-000000000000"


@pytest.fixture
def con_acceso(monkeypatch):
    main.app.dependency_overrides[get_current_user] = lambda: {"user_id": "u1"}
    monkeypatch.setattr(router, "validar_acceso_empresa", lambda *a, **k: None)
    monkeypatch.setattr(router, "empresa_or_404", lambda eid: {"id": eid, "rfc": "AAA010101AAA"})
    yield
    main.app.dependency_overrides.clear()


def test_resumen_delega_y_serializa(con_acceso, monkeypatch):
    visto = {}
    monkeypatch.setattr(iva_flujo_datos, "cargar_ajustes", lambda e: {})

    def _eventos(empresa_id, rfc, periodo, ajustes):
        visto.update(empresa_id=empresa_id, rfc=rfc, periodo=periodo)
        return []

    monkeypatch.setattr(iva_flujo_datos, "cargar_eventos", _eventos)

    r = client.get(f"{BASE}/2026-09", params={"factor": 0.5})

    assert r.status_code == 200, r.text
    assert visto == {"empresa_id": "emp-1", "rfc": "AAA010101AAA", "periodo": "2026-09"}
    d = r.json()
    assert d["periodo"] == "2026-09" and d["factor_prorrateo"] == 0.5
    assert d["resultado"]["iva_por_pagar"] == 0.0 and d["advertencias"] == []


@pytest.mark.parametrize("periodo", ["2026-13", "2026-9", "x", "1999-01"])
def test_resumen_rechaza_periodo_invalido(con_acceso, periodo):
    assert client.get(f"{BASE}/{periodo}").status_code == 422


@pytest.mark.parametrize("factor", [-0.1, 1.5])
def test_resumen_rechaza_factor_fuera_de_rango(con_acceso, factor):
    assert client.get(f"{BASE}/2026-09", params={"factor": factor}).status_code == 422


def test_detalle_valida_origen_y_direccion(con_acceso, monkeypatch):
    monkeypatch.setattr(iva_flujo_datos, "cargar_ajustes", lambda e: {})
    monkeypatch.setattr(iva_flujo_datos, "cargar_eventos", lambda *a: [])

    ok = client.get(f"{BASE}/2026-09/detalle", params={"direccion": "trasladado", "origen": "contado"})
    mal_origen = client.get(f"{BASE}/2026-09/detalle", params={"direccion": "trasladado", "origen": "x"})
    mal_dir = client.get(f"{BASE}/2026-09/detalle", params={"direccion": "y", "origen": "contado"})
    mal_pag = client.get(f"{BASE}/2026-09/detalle", params={"direccion": "trasladado", "origen": "contado", "por_pagina": 0})

    assert ok.status_code == 200 and ok.json() == {"items": [], "total": 0, "pagina": 1, "por_pagina": 50}
    assert (mal_origen.status_code, mal_dir.status_code, mal_pag.status_code) == (422, 422, 422)


def test_detalle_exige_direccion_y_origen(con_acceso):
    assert client.get(f"{BASE}/2026-09/detalle").status_code == 422


def test_ajustes_no_se_confunde_con_un_periodo(con_acceso, monkeypatch):
    monkeypatch.setattr(router.db, "query_all", lambda *a, **k: [])

    r = client.get(f"{BASE}/ajustes")

    assert r.status_code == 200 and r.json() == {"items": []}


# ── ajustes ──────────────────────────────────────────────────────────────────

def _cfdi(**kw):
    base = {"uuid": UUID, "tipo_comprobante": "I", "metodo_pago": "PUE", "fecha_emision": datetime(2026, 9, 10),
            "rfc_emisor": "AAA010101AAA", "rfc_receptor": "XAXX010101000"}
    base.update(kw)
    return base


@pytest.fixture
def ajustes_db(con_acceso, monkeypatch):
    estado = {"cfdi": _cfdi(), "guardados": []}
    monkeypatch.setattr(router.db, "query_one", lambda *a, **k: estado["cfdi"])
    monkeypatch.setattr(iva_flujo_datos, "guardar_ajuste", lambda *a: estado["guardados"].append(a))
    return estado


def test_excluir_guarda_con_el_motivo_limpio(ajustes_db):
    r = client.put(f"{BASE}/ajustes", json={"uuid": UUID.lower(), "direccion": "trasladado", "accion": "excluir", "motivo": " duplicado "})

    assert r.status_code == 200, r.text
    assert r.json() == {"uuid": UUID, "direccion": "trasladado", "accion": "excluir", "periodo_destino": None, "motivo": "duplicado"}
    assert ajustes_db["guardados"] == [("emp-1", UUID, "trasladado", "excluir", None, "duplicado", "u1")]


def test_si_la_auditoria_falla_el_ajuste_responde_500(ajustes_db, monkeypatch):
    def _falla(*a):
        raise RuntimeError("auditoría caída")

    monkeypatch.setattr(iva_flujo_datos, "guardar_ajuste", _falla)
    sin_propagar = TestClient(main.app, raise_server_exceptions=False)

    r = sin_propagar.put(f"{BASE}/ajustes", json={"uuid": UUID, "direccion": "trasladado", "accion": "excluir", "motivo": "x"})

    assert r.status_code == 500


def test_reasignar_guarda_el_periodo_destino(ajustes_db):
    r = client.put(f"{BASE}/ajustes", json={"uuid": UUID, "direccion": "trasladado", "accion": "reasignar", "periodo_destino": "2026-10", "motivo": "se cobró en octubre"})

    assert r.status_code == 200 and r.json()["periodo_destino"] == "2026-10"


@pytest.mark.parametrize("cuerpo", [
    {"accion": "reasignar"},                                          # falta el destino
    {"accion": "reasignar", "periodo_destino": "2026-13"},
    {"accion": "reasignar", "periodo_destino": "2026-09"},            # el mismo mes de emisión del PUE
    {"accion": "excluir", "periodo_destino": "2026-10"},              # excluir no lleva destino
    {"accion": "inventar"},
])
def test_ajuste_invalido_es_422_y_no_escribe(ajustes_db, cuerpo):
    r = client.put(f"{BASE}/ajustes", json={"uuid": UUID, "direccion": "trasladado", "motivo": "x", **cuerpo})

    assert r.status_code == 422
    assert ajustes_db["guardados"] == []


def test_reasignar_un_ppd_al_mes_de_su_emision_si_se_permite(ajustes_db):
    ajustes_db["cfdi"] = _cfdi(metodo_pago="PPD")

    r = client.put(f"{BASE}/ajustes", json={"uuid": UUID, "direccion": "trasladado", "accion": "reasignar", "periodo_destino": "2026-09", "motivo": "x"})

    assert r.status_code == 200          # un PPD tiene un efecto por cada pago: no hay un solo mes natural


@pytest.mark.parametrize("motivo", [None, "", "   "])
def test_el_motivo_es_obligatorio(ajustes_db, motivo):
    cuerpo = {"uuid": UUID, "direccion": "trasladado", "accion": "excluir"}
    if motivo is not None:
        cuerpo["motivo"] = motivo

    r = client.put(f"{BASE}/ajustes", json=cuerpo)

    assert r.status_code == 422
    assert ajustes_db["guardados"] == []


def test_cfdi_inexistente_o_de_otra_direccion_es_404(ajustes_db):
    ajustes_db["cfdi"] = None
    inexistente = client.put(f"{BASE}/ajustes", json={"uuid": UUID, "direccion": "trasladado", "accion": "excluir", "motivo": "x"})
    ajustes_db["cfdi"] = _cfdi(rfc_emisor="OTRO010101AAA")        # la empresa no es la emisora
    direccion = client.put(f"{BASE}/ajustes", json={"uuid": UUID, "direccion": "trasladado", "accion": "excluir", "motivo": "x"})
    ajustes_db["cfdi"] = _cfdi(tipo_comprobante="P")
    tipo = client.put(f"{BASE}/ajustes", json={"uuid": UUID, "direccion": "trasladado", "accion": "excluir", "motivo": "x"})

    assert (inexistente.status_code, direccion.status_code, tipo.status_code) == (404, 404, 404)
    assert ajustes_db["guardados"] == []


def test_uuid_demasiado_largo_es_422(ajustes_db):
    r = client.put(f"{BASE}/ajustes", json={"uuid": "X" * 40, "direccion": "trasladado", "accion": "excluir", "motivo": "x"})

    assert r.status_code == 422


def test_quitar_ajuste_delega_con_el_usuario(con_acceso, monkeypatch):
    visto = []
    monkeypatch.setattr(iva_flujo_datos, "quitar_ajuste", lambda *a: visto.append(a) or {"accion": "excluir", "periodo_destino": None})

    r = client.delete(f"{BASE}/ajustes/trasladado/{UUID}")

    assert r.status_code == 204
    assert visto == [("emp-1", UUID, "trasladado", "u1")]


def test_quitar_ajuste_inexistente_es_404(con_acceso, monkeypatch):
    monkeypatch.setattr(iva_flujo_datos, "quitar_ajuste", lambda *a: None)

    assert client.delete(f"{BASE}/ajustes/trasladado/{UUID}").status_code == 404
    assert client.delete(f"{BASE}/ajustes/otra/{UUID}").status_code == 422


def test_sin_acceso_es_403(monkeypatch):
    main.app.dependency_overrides[get_current_user] = lambda: {"user_id": "u1"}

    def _sin_acceso(*a, **k):
        raise HTTPException(status_code=403, detail="Sin acceso a esta empresa")

    monkeypatch.setattr(router, "validar_acceso_empresa", _sin_acceso)
    try:
        for metodo, ruta, kw in (
            ("get", f"{BASE}/2026-09", {}),
            ("get", f"{BASE}/2026-09/detalle?direccion=trasladado&origen=contado", {}),
            ("get", f"{BASE}/ajustes", {}),
            ("put", f"{BASE}/ajustes", {"json": {"uuid": UUID, "direccion": "trasladado", "accion": "excluir", "motivo": "x"}}),
            ("delete", f"{BASE}/ajustes/trasladado/{UUID}", {}),
        ):
            assert getattr(client, metodo)(ruta, **kw).status_code == 403, (metodo, ruta)
    finally:
        main.app.dependency_overrides.clear()
