"""Router de proveedores (DB mockeada): permisos, validación y delegación."""
import pytest
from fastapi.testclient import TestClient

import backend.main_api as main
from backend import proveedores
from backend.deps import get_current_user
from backend.routers import proveedores as router

client = TestClient(main.app)
BASE = "/api/v1/empresas/emp-1/proveedores"
FILA = {"rfc": "PRO010101AAA", "nombre": "PROVEEDOR", "nombre_editado": False, "tipo_tercero": None, "tipo_operacion": None,
        "pais": None, "id_fiscal": None, "origen": "cfdi", "created_at": None, "updated_at": None}


@pytest.fixture
def con_acceso(monkeypatch):
    main.app.dependency_overrides[get_current_user] = lambda: {"user_id": "u1"}
    monkeypatch.setattr(router, "validar_acceso_empresa", lambda *a, **k: None)
    monkeypatch.setattr(router, "empresa_or_404", lambda eid: {"id": eid, "rfc": "AAA010101AAA"})
    yield
    main.app.dependency_overrides.clear()


def test_listar_sincroniza_y_filtra(con_acceso, monkeypatch):
    visto = {}
    monkeypatch.setattr(proveedores, "sincronizar", lambda e, rfc: visto.update(sync=(e, rfc)) or 2)
    monkeypatch.setattr(proveedores, "listar", lambda e, q=None: visto.update(q=q) or [FILA])

    r = client.get(BASE, params={"q": "pro"})

    assert r.status_code == 200, r.text
    assert visto == {"sync": ("emp-1", "AAA010101AAA"), "q": "pro"}
    assert r.json()["total"] == 1 and r.json()["agregados"] == 2


def test_crear_normaliza_el_rfc_y_audita_con_el_usuario(con_acceso, monkeypatch):
    visto = {}

    def _crear(empresa_id, rfc, datos, usuario_id):
        visto.update(rfc=rfc, datos=datos, usuario=usuario_id)
        return FILA

    monkeypatch.setattr(proveedores, "crear", _crear)

    r = client.post(BASE, json={"rfc": " pro010101aaa ", "nombre": "PROVEEDOR", "tipo_tercero": "04"})

    assert r.status_code == 201, r.text
    assert visto["rfc"] == "PRO010101AAA" and visto["usuario"] == "u1" and visto["datos"]["tipo_tercero"] == "04"


def test_crear_duplicado_es_409(con_acceso, monkeypatch):
    monkeypatch.setattr(proveedores, "crear", lambda *a: None)

    assert client.post(BASE, json={"rfc": "PRO010101AAA"}).status_code == 409


@pytest.mark.parametrize("cuerpo", [{"rfc": "no-es-rfc"}, {"rfc": "PRO010101AAA", "tipo_tercero": "4"},
                                    {"rfc": "PRO010101AAA", "tipo_operacion": "ab"}])
def test_crear_rechaza_datos_invalidos(con_acceso, cuerpo):
    assert client.post(BASE, json=cuerpo).status_code == 422


def test_editar_solo_pasa_lo_enviado(con_acceso, monkeypatch):
    visto = {}
    monkeypatch.setattr(proveedores, "actualizar", lambda e, rfc, cambios, u: visto.update(cambios=cambios) or FILA)

    r = client.patch(f"{BASE}/pro010101aaa", json={"tipo_operacion": "85"})

    assert r.status_code == 200 and visto["cambios"] == {"tipo_operacion": "85"}


def test_editar_inexistente_es_404(con_acceso, monkeypatch):
    monkeypatch.setattr(proveedores, "actualizar", lambda *a: None)

    assert client.patch(f"{BASE}/PRO010101AAA", json={"nombre": "x"}).status_code == 404
