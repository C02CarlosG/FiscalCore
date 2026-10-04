"""Preferencias de tabla (DB mockeada): validación de la vista y de las columnas."""
import pytest
from fastapi.testclient import TestClient

import backend.main_api as main
from backend import db
from backend.deps import get_current_user

client = TestClient(main.app)
URL = "/api/v1/preferencias/tablas/{}"


@pytest.fixture(autouse=True)
def usuario():
    main.app.dependency_overrides[get_current_user] = lambda: {"user_id": "u1"}
    yield
    main.app.dependency_overrides.clear()


def test_sin_preferencia_devuelve_null(monkeypatch):
    monkeypatch.setattr(db, "query_one", lambda *a, **k: None)
    r = client.get(URL.format("cfdi-emitidos-I"))
    assert r.status_code == 200
    assert r.json() == {"columnas": None}


def test_lee_lo_guardado_solo_del_usuario_actual(monkeypatch):
    visto = {}

    def _query(sql, params):
        visto["params"] = params
        return {"config": {"columnas": [{"clave": "total", "visible": True}]}}

    monkeypatch.setattr(db, "query_one", _query)
    r = client.get(URL.format("cfdi-emitidos-I"))
    assert r.json() == {"columnas": [{"clave": "total", "visible": True}]}
    assert visto["params"] == ("u1", "cfdi-emitidos-I")


def test_guarda_en_el_orden_recibido(monkeypatch):
    guardado = {}
    monkeypatch.setattr(db, "execute", lambda sql, params=None, **k: guardado.update(params=params))
    cuerpo = {"columnas": [{"clave": "total", "visible": True}, {"clave": "uuid", "visible": False}]}
    r = client.put(URL.format("cfdi-emitidos-I"), json=cuerpo)
    assert r.status_code == 200
    assert r.json() == cuerpo
    assert guardado["params"][:2] == ("u1", "cfdi-emitidos-I")


@pytest.mark.parametrize("vista", ["a b", "x;DROP", "-inicio", "a" * 81, "a_b"])
def test_vista_invalida_responde_422(monkeypatch, vista):
    monkeypatch.setattr(db, "query_one", lambda *a, **k: pytest.fail("no debe tocar la base"))
    monkeypatch.setattr(db, "execute", lambda *a, **k: pytest.fail("no debe tocar la base"))
    assert client.get(URL.format(vista)).status_code in (404, 422)
    assert client.put(URL.format(vista), json={"columnas": []}).status_code in (404, 422)


@pytest.mark.parametrize("columnas", [
    [{"clave": "Total", "visible": True}],
    [{"clave": "total; DROP", "visible": True}],
    [{"clave": "total", "visible": True}, {"clave": "total", "visible": False}],
    [{"clave": "total"}],
    [{"clave": f"c{i}", "visible": True} for i in range(201)],
])
def test_columnas_invalidas_responden_422(monkeypatch, columnas):
    monkeypatch.setattr(db, "execute", lambda *a, **k: pytest.fail("no debe tocar la base"))
    assert client.put(URL.format("cfdi-emitidos-I"), json={"columnas": columnas}).status_code == 422


def test_sin_sesion_responde_401():
    main.app.dependency_overrides.clear()
    assert client.get(URL.format("cfdi-emitidos-I")).status_code == 401


def test_restablecer_borra_la_preferencia(monkeypatch):
    visto = {}
    monkeypatch.setattr(db, "execute", lambda sql, params=None, **k: visto.update(sql=sql, params=params))
    r = client.delete(URL.format("cfdi-emitidos-I"))
    assert r.status_code == 204
    assert "DELETE" in visto["sql"] and visto["params"] == ("u1", "cfdi-emitidos-I")
