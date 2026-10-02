"""Router del listado de CFDI (DB mockeada): validación, permisos y delegación."""
import pytest
from fastapi.testclient import TestClient

import backend.main_api as main
from backend import cfdi_listado, db
from backend.deps import get_current_user
from backend.routers import cfdis

client = TestClient(main.app)
BASE = "/api/v1/empresas/emp-1/cfdis"
OK = {"direccion": "emitidos", "periodo": "2026-09"}


@pytest.fixture
def con_acceso(monkeypatch):
    main.app.dependency_overrides[get_current_user] = lambda: {"user_id": "u1"}
    monkeypatch.setattr(cfdis, "validar_acceso_empresa", lambda *a, **k: None)
    monkeypatch.setattr(cfdis, "empresa_or_404", lambda eid: {"id": eid, "rfc": "AAA010101AAA"})
    yield
    main.app.dependency_overrides.clear()


def test_listado_delega_con_la_consulta_validada(con_acceso, monkeypatch):
    recibido = {}

    def _listar(empresa_id, rfc, consulta):
        recibido.update(empresa_id=empresa_id, rfc=rfc, consulta=consulta)
        return {"items": [], "total": 0, "pagina": 2, "por_pagina": 50}

    monkeypatch.setattr(cfdi_listado, "listar", _listar)
    r = client.get(BASE, params={**OK, "tipo": "E", "estado": "todos", "metodo": "PPD", "pago": "pendientes",
                                 "q": " acme ", "orden": "total", "dir": "desc", "pagina": 2, "por_pagina": 50})

    assert r.status_code == 200
    assert r.json() == {"items": [], "total": 0, "pagina": 2, "por_pagina": 50}
    c = recibido["consulta"]
    assert (recibido["empresa_id"], recibido["rfc"]) == ("emp-1", "AAA010101AAA")
    assert (c.tipo, c.estado, c.metodo, c.pago, c.q, c.orden, c.dir, c.pagina, c.por_pagina) == (
        "E", "todos", "PPD", "pendientes", "acme", "total", "desc", 2, 50)


def test_resumen_delega(con_acceso, monkeypatch):
    monkeypatch.setattr(cfdi_listado, "resumen", lambda e, r, c: {"conteos": {}, "totales": {}, "advertencias": []})

    r = client.get(f"{BASE}/resumen", params=OK)

    assert r.status_code == 200
    assert r.json() == {"conteos": {}, "totales": {}, "advertencias": []}


@pytest.mark.parametrize("params", [
    {"direccion": "ambos"},
    {"periodo": "2026-13"},
    {"tipo": "X"},
    {"por_pagina": 31},
    {"pagina": 0},
    {"orden": "fecha_emision; DROP TABLE cfdi"},
    {"dir": "asc; DROP TABLE cfdi"},
    {"filtros": "no es json"},
    {"filtros": '[{"campo": "total", "op": "mayor; DROP TABLE cfdi", "valor": 1}]'},
    {"filtros": '[{"campo": "total) OR (1=1", "op": "igual", "valor": 1}]'},
    {"periodo": "0000-01"},
    {"pagina": 10 ** 30},
    {"q": "a\x00b"},
    {"filtros": "[" * 3000},
])
def test_parametros_invalidos_responden_422_sin_tocar_la_base(con_acceso, monkeypatch, params):
    def _no_debe_consultar(*a, **k):
        raise AssertionError("no debe llegar a la base")

    monkeypatch.setattr(db, "query_all", _no_debe_consultar)
    monkeypatch.setattr(db, "query_one", _no_debe_consultar)

    solo_listado = {"por_pagina", "pagina", "orden", "dir"}   # el resumen no pagina ni ordena
    rutas = [""] if solo_listado & set(params) else ["", "/resumen"]
    for ruta in rutas:
        r = client.get(f"{BASE}{ruta}", params={**OK, **params})
        assert r.status_code == 422, (ruta, r.text)


def test_faltan_parametros_obligatorios(con_acceso):
    assert client.get(BASE, params={"periodo": "2026-09"}).status_code == 422
    assert client.get(BASE, params={"direccion": "emitidos"}).status_code == 422


def test_columnas_devuelve_el_catalogo(con_acceso):
    r = client.get(f"{BASE}/columnas", params={"direccion": "recibidos", "tipo": "I"})

    assert r.status_code == 200
    cuerpo = r.json()
    claves = {c["clave"]: c for c in cuerpo["encabezado"]}
    assert claves["rfc_contraparte"]["etiqueta"] == "RFC emisor"
    assert set(cuerpo["encabezado"][0]) == {
        "clave", "etiqueta", "tipo_dato", "grupo", "visible_por_defecto", "ordenable", "filtrable", "opciones"}
    assert cuerpo["concepto"][0]["clave"] == "clave_prod_serv"
    assert client.get(f"{BASE}/columnas", params={"direccion": "ambos"}).status_code == 422


@pytest.mark.parametrize("ruta", ["", "/resumen", "/columnas"])
def test_sin_sesion_responde_401(ruta):
    assert client.get(f"{BASE}{ruta}", params=OK).status_code == 401


@pytest.mark.parametrize("ruta", ["", "/resumen", "/columnas"])
def test_sin_acceso_a_la_empresa_responde_403(monkeypatch, ruta):
    main.app.dependency_overrides[get_current_user] = lambda: {"user_id": "u1"}
    monkeypatch.setattr(db, "query_one", lambda *a, **k: None)   # sin fila en usuario_empresas
    try:
        r = client.get(f"{BASE}{ruta}", params=OK)
    finally:
        main.app.dependency_overrides.clear()

    assert r.status_code == 403
