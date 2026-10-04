"""Router de validaciones de CFDI (V1) con la base mockeada: acceso, validación de
parámetros, forma de la respuesta y configuración."""
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import backend.main_api as main
from backend import db
from backend import validaciones_cfdi_datos as datos
from backend.deps import get_current_user
from backend.routers import validaciones_cfdi as router_v

client = TestClient(main.app)
EMPRESA = "11111111-1111-1111-1111-111111111111"
BASE = f"/api/v1/validaciones-cfdi/empresas/{EMPRESA}"


@pytest.fixture(autouse=True)
def sesion(monkeypatch):
    main.app.dependency_overrides[get_current_user] = lambda: {"user_id": "u1"}
    monkeypatch.setattr(router_v, "validar_acceso_empresa", lambda *a, **k: None)
    monkeypatch.setattr(db, "query_one", lambda sql, params=(): (
        {"id": EMPRESA, "rfc": "VAL010101AB1"} if "FROM empresas" in sql
        else pytest.fail(f"consulta inesperada: {sql}")))
    yield
    main.app.dependency_overrides.clear()


@pytest.fixture
def config(monkeypatch):
    from backend import validaciones_cfdi as v
    actual = {"c": v.Configuracion.desde_json({"inactivas": ["pue_con_rep"]})}
    monkeypatch.setattr(datos, "leer_configuracion", lambda empresa_id: actual["c"])
    return actual


def test_sin_sesion_responde_401():
    main.app.dependency_overrides.clear()
    assert client.get(BASE, params={"periodo": "2026-03"}).status_code == 401


def test_sin_acceso_responde_403(monkeypatch):
    def _negar(*a, **k):
        raise HTTPException(status_code=403, detail="Sin acceso a esta empresa")

    monkeypatch.setattr(router_v, "validar_acceso_empresa", _negar)
    assert client.get(BASE, params={"periodo": "2026-03"}).status_code == 403
    assert client.get(f"{BASE}/configuracion").status_code == 403
    assert client.put(f"{BASE}/configuracion", json={}).status_code == 403


def test_resumen_con_tarjeta_inactiva_en_null(monkeypatch, config):
    llamadas = []

    def _contar(empresa_id, rfc, direccion, periodo, c):
        llamadas.append((direccion, periodo))
        return {"pue_forma_99": (1, 2), "egreso_sin_relacion": (0, 3)} if direccion == "emitidos" else {
            "pue_forma_99": (0, 0), "egreso_sin_relacion": (0, 0), "no_bancarizado": (4, 9)}

    monkeypatch.setattr(datos, "contar", _contar)
    r = client.get(BASE, params={"periodo": "2026-03"})
    assert r.status_code == 200
    cuerpo = r.json()
    assert llamadas == [("emitidos", "2026-03"), ("recibidos", "2026-03")]
    assert cuerpo["configuracion"] == {"inactivas": ["pue_con_rep"], "umbral_efectivo": "2000.00"}
    emitidos = {t["clave"]: t for t in cuerpo["emitidos"]}
    assert list(emitidos) == ["pue_forma_99", "pue_con_rep", "egreso_sin_relacion"]
    assert (emitidos["pue_forma_99"]["periodo"], emitidos["pue_forma_99"]["acumulado"]) == (1, 2)
    assert (emitidos["pue_con_rep"]["activa"], emitidos["pue_con_rep"]["periodo"]) == (False, None)
    assert emitidos["pue_forma_99"]["titulo"]
    assert [t["clave"] for t in cuerpo["recibidos"]][-1] == "no_bancarizado"


@pytest.mark.parametrize("params", [
    {"periodo": "2026-13"},
    {"periodo": "marzo"},
])
def test_resumen_periodo_invalido(params, config):
    assert client.get(BASE, params=params).status_code == 422


@pytest.mark.parametrize("params", [
    {"direccion": "todos", "validacion": "pue_forma_99"},
    {"direccion": "emitidos", "validacion": "inventada"},
    {"direccion": "emitidos", "validacion": "no_bancarizado"},
    {"direccion": "emitidos", "validacion": "pue_forma_99", "alcance": "anual"},
    {"direccion": "emitidos", "validacion": "pue_forma_99", "periodo": "2026-3"},
])
def test_lista_rechaza_parametros_invalidos(monkeypatch, params, config):
    monkeypatch.setattr(datos, "listar", lambda *a, **k: pytest.fail("no debe consultar"))
    assert client.get(f"{BASE}/cfdis", params={"periodo": "2026-03", **params}).status_code == 422


def test_lista_pasa_los_parametros(monkeypatch, config):
    vistos = {}

    def _listar(empresa_id, rfc, direccion, clave, alcance, periodo, c):
        vistos.update(direccion=direccion, clave=clave, alcance=alcance, periodo=periodo)
        return {"cfdis": [{"uuid": "U1", "total": __import__("decimal").Decimal("10.50")}], "total_filas": 1}

    monkeypatch.setattr(datos, "listar", _listar)
    r = client.get(f"{BASE}/cfdis", params={
        "periodo": "2026-03", "direccion": "recibidos", "validacion": "no_bancarizado", "alcance": "acumulado"})
    assert r.status_code == 200
    assert r.json() == {"cfdis": [{"uuid": "U1", "total": 10.5}], "total_filas": 1}
    assert vistos == {"direccion": "recibidos", "clave": "no_bancarizado", "alcance": "acumulado", "periodo": "2026-03"}


def test_guarda_configuracion_y_audita(monkeypatch):
    guardado, auditado = {}, []
    monkeypatch.setattr(datos, "guardar_configuracion", lambda e, c, u: guardado.update(e=e, c=c.a_json(), u=u))
    monkeypatch.setattr(router_v, "registrar_evento", lambda *a, **k: auditado.append(a[1]))
    r = client.put(f"{BASE}/configuracion", json={"inactivas": ["no_bancarizado"], "umbral_efectivo": 2500})
    assert r.status_code == 200
    assert r.json() == {"inactivas": ["no_bancarizado"], "umbral_efectivo": "2500.00"}
    assert guardado == {"e": EMPRESA, "c": r.json(), "u": "u1"}
    assert auditado == ["validaciones_cfdi.configurar"]


@pytest.mark.parametrize("cuerpo", [
    {"inactivas": ["inventada"]},
    {"umbral_efectivo": -5},
    {"umbral_efectivo": "mucho"},
])
def test_configuracion_invalida_responde_422(monkeypatch, cuerpo):
    monkeypatch.setattr(datos, "guardar_configuracion", lambda *a: pytest.fail("no debe guardar"))
    assert client.put(f"{BASE}/configuracion", json=cuerpo).status_code == 422
