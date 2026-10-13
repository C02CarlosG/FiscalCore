"""Router del criterio de efectivo (spec 2026-10-13). DB mockeada."""
import pytest
from fastapi.testclient import TestClient

import backend.main_api as main
from backend import criterio_efectivo
from backend.deps import get_current_user
from backend.routers import criterio_efectivo as router

client = TestClient(main.app)
URL = "/api/v1/empresas/emp-1/criterio-efectivo"


@pytest.fixture
def sesion(monkeypatch):
    main.app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "user_id": "u1"}
    monkeypatch.setattr(router, "validar_acceso_empresa", lambda *a, **k: None)
    yield monkeypatch
    main.app.dependency_overrides.clear()


def _como(monkeypatch, *, administrador: bool, plataforma=None):
    monkeypatch.setattr(router, "_roles_de_empresa", lambda eid: {"u1": "administrador" if administrador else "contador"})
    monkeypatch.setattr(router, "_rol_plataforma", lambda uid: plataforma)


def test_get_devuelve_criterio_y_umbral(sesion):
    sesion.setattr(criterio_efectivo, "leer", lambda e: "estricto")
    r = client.get(URL)
    assert r.status_code == 200
    assert r.json() == {"criterio_efectivo": "estricto", "umbral_efectivo": 0.0}


def test_put_como_administrador_guarda_y_devuelve(sesion):
    _como(sesion, administrador=True)
    visto = {}
    sesion.setattr(criterio_efectivo, "guardar",
                   lambda e, n, u: visto.update(e=e, n=n, u=u) or {"criterio_efectivo": n, "anterior": "legal"})
    r = client.put(URL, json={"criterio": "estricto"})
    assert r.status_code == 200
    assert r.json() == {"criterio_efectivo": "estricto", "umbral_efectivo": 0.0}
    assert visto == {"e": "emp-1", "n": "estricto", "u": "u1"}


@pytest.mark.parametrize("cuerpo", [{}, {"criterio": None}, {"criterio": ""}, {"criterio": "Legal"},
                                    {"criterio": "laxo"}, {"criterio": 1}])
def test_put_rechaza_valores_invalidos_con_422(sesion, cuerpo):
    _como(sesion, administrador=True)
    sesion.setattr(criterio_efectivo, "guardar", lambda *a: pytest.fail("no debe guardar"))
    assert client.put(URL, json=cuerpo).status_code == 422


def test_put_sin_rol_de_administrador_da_403_y_no_guarda(sesion):
    _como(sesion, administrador=False)
    sesion.setattr(criterio_efectivo, "guardar", lambda *a: pytest.fail("no debe guardar"))
    assert client.put(URL, json={"criterio": "estricto"}).status_code == 403


def test_put_como_admin_de_plataforma_puede(sesion):
    _como(sesion, administrador=False, plataforma="admin")
    sesion.setattr(criterio_efectivo, "guardar", lambda e, n, u: {"criterio_efectivo": n, "anterior": "legal"})
    assert client.put(URL, json={"criterio": "legal"}).status_code == 200


def test_put_empresa_inexistente_da_404(sesion):
    _como(sesion, administrador=True)

    def _no_existe(*a):
        raise LookupError("Empresa no encontrada")

    sesion.setattr(criterio_efectivo, "guardar", _no_existe)
    assert client.put(URL, json={"criterio": "legal"}).status_code == 404


def test_put_sin_token_da_401():
    assert client.put(URL, json={"criterio": "legal"}).status_code == 401
