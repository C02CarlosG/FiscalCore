"""Router de proveedores (DB mockeada): permisos, validación y delegación."""
import pytest
from fastapi.testclient import TestClient

import backend.main_api as main
from backend import proveedores
from backend.deps import get_current_user
from backend.routers import proveedores as router

client = TestClient(main.app)
BASE = "/api/v1/empresas/emp-1/proveedores"
PID = "11111111-2222-4333-8444-555555555555"
FILA = {"id": PID, "rfc": "PRO010101AAA", "nombre": "PROVEEDOR", "nombre_editado": False, "tipo_tercero": "04",
        "tipo_operacion": "85", "pais": None, "jurisdiccion_detalle": None, "id_fiscal": None, "efectos_fiscales": None,
        "origen": "cfdi", "pendiente": False, "created_at": None, "updated_at": None}


@pytest.fixture
def con_acceso(monkeypatch):
    main.app.dependency_overrides[get_current_user] = lambda: {"user_id": "u1"}
    monkeypatch.setattr(router, "validar_acceso_empresa", lambda *a, **k: None)
    monkeypatch.setattr(router, "empresa_or_404", lambda eid: {"id": eid, "rfc": "AAA010101AAA"})
    yield
    main.app.dependency_overrides.clear()


def test_listar_sincroniza_con_el_usuario_y_filtra(con_acceso, monkeypatch):
    visto = {}
    monkeypatch.setattr(proveedores, "sincronizar", lambda e, rfc, u: visto.update(sync=(e, rfc, u)) or {"agregados": 2, "omitidos": 1})
    monkeypatch.setattr(proveedores, "listar", lambda e, q=None: visto.update(q=q) or [FILA])

    r = client.get(BASE, params={"q": "pro"})

    assert r.status_code == 200, r.text
    assert visto == {"sync": ("emp-1", "AAA010101AAA", "u1"), "q": "pro"}
    assert (r.json()["total"], r.json()["agregados"], r.json()["omitidos"]) == (1, 2, 1)


def test_crear_normaliza_el_rfc_y_pone_la_operacion_por_defecto(con_acceso, monkeypatch):
    visto = {}
    monkeypatch.setattr(proveedores, "crear", lambda e, rfc, datos, u: visto.update(rfc=rfc, datos=datos, usuario=u) or FILA)

    r = client.post(BASE, json={"rfc": " pro010101aaa ", "nombre": "PROVEEDOR", "tipo_tercero": "04"})

    assert r.status_code == 201, r.text
    assert visto["rfc"] == "PRO010101AAA" and visto["usuario"] == "u1"
    assert visto["datos"]["tipo_tercero"] == "04" and visto["datos"]["tipo_operacion"] == "85"


def test_crear_duplicado_es_409(con_acceso, monkeypatch):
    def _dup(*a):
        raise proveedores.Duplicado()

    monkeypatch.setattr(proveedores, "crear", _dup)

    assert client.post(BASE, json={"rfc": "PRO010101AAA"}).status_code == 409


@pytest.mark.parametrize("cuerpo", [
    {"rfc": "no-es-rfc"},
    {"rfc": "PRO010101AAA", "tipo_tercero": "4"},
    {"rfc": "PRO010101AAA", "tipo_tercero": "99"},                    # fuera del catálogo
    {"rfc": "PRO010101AAA", "tipo_operacion": "99"},
    {"rfc": "PRO010101AAA", "tipo_tercero": "04", "tipo_operacion": "87"},     # 87 solo con tercero 15
    {"rfc": "XEXX010101000", "tipo_tercero": "05"},                   # extranjero sin ID fiscal ni país
    {"rfc": "XEXX010101000", "tipo_tercero": "05", "id_fiscal": "1", "pais": "usa1"},
    {"rfc": "XEXX010101000", "tipo_tercero": "04"},                   # nacional con RFC genérico
])
def test_crear_rechaza_datos_invalidos(con_acceso, cuerpo):
    assert client.post(BASE, json=cuerpo).status_code == 422


def test_crear_extranjero_con_id_fiscal_y_pais(con_acceso, monkeypatch):
    visto = {}
    monkeypatch.setattr(proveedores, "crear", lambda e, rfc, datos, u: visto.update(datos=datos) or FILA)

    r = client.post(BASE, json={"rfc": "xexx010101000", "tipo_tercero": "05", "id_fiscal": "12-345", "pais": "usa"})

    assert r.status_code == 201 and visto["datos"]["pais"] == "USA"


def _actualizar_falso(visto=None, base=None):
    """Imita ``proveedores.actualizar``: aplica el validador al estado resultante antes de «guardar»."""
    def _f(e, pid, cambios, u, validar=None):
        if visto is not None:
            visto.update(pid=pid, cambios=cambios, valida=validar is not None)
        if validar is not None:
            errores = validar({**FILA, **(base or {}), **cambios})
            if errores:
                raise proveedores.Invalido(errores)
        return FILA
    return _f


def test_editar_solo_pasa_lo_enviado_y_valida_dentro_de_la_transaccion(con_acceso, monkeypatch):
    visto = {}
    monkeypatch.setattr(proveedores, "actualizar", _actualizar_falso(visto))

    r = client.patch(f"{BASE}/{PID}", json={"tipo_operacion": "06"})

    assert r.status_code == 200 and visto == {"pid": PID, "cambios": {"tipo_operacion": "06"}, "valida": True}


def test_editar_el_nombre_no_dispara_las_reglas_cruzadas(con_acceso, monkeypatch):
    visto = {}
    monkeypatch.setattr(proveedores, "actualizar", _actualizar_falso(visto))

    assert client.patch(f"{BASE}/{PID}", json={"nombre": "NUEVO"}).status_code == 200
    assert visto["valida"] is False


def test_editar_rechaza_un_estado_resultante_invalido(con_acceso, monkeypatch):
    monkeypatch.setattr(proveedores, "actualizar", _actualizar_falso())

    assert client.patch(f"{BASE}/{PID}", json={"tipo_tercero": "05"}).status_code == 422       # sin ID fiscal ni país
    assert client.patch(f"{BASE}/{PID}", json={"tipo_operacion": "87"}).status_code == 422


def test_alta_manual_de_xexx_sin_tipo_aplica_el_05_y_exige_id_fiscal_y_pais(con_acceso, monkeypatch):
    visto = {}
    monkeypatch.setattr(proveedores, "crear", lambda e, rfc, datos, u: visto.update(datos=datos) or FILA)

    assert client.post(BASE, json={"rfc": "XEXX010101000", "nombre": "ACME"}).status_code == 422
    r = client.post(BASE, json={"rfc": "XEXX010101000", "nombre": "ACME", "id_fiscal": "1", "pais": "usa"})
    assert r.status_code == 201 and visto["datos"]["tipo_tercero"] == "05"


@pytest.mark.parametrize("cuerpo", [{"nombre": None}, {"nombre_editado": None}])
def test_editar_rechaza_nulos_en_nombre(con_acceso, cuerpo):
    assert client.patch(f"{BASE}/{PID}", json=cuerpo).status_code == 422


def test_editar_nombre_editado_false_vuelve_a_la_alimentacion(con_acceso, monkeypatch):
    visto = {}
    monkeypatch.setattr(proveedores, "actualizar", lambda e, pid, cambios, u, validar=None: visto.update(cambios=cambios) or FILA)

    assert client.patch(f"{BASE}/{PID}", json={"nombre_editado": False}).status_code == 200
    assert visto["cambios"] == {"nombre_editado": False}


def test_editar_inexistente_o_id_mal_formado_es_404(con_acceso, monkeypatch):
    monkeypatch.setattr(proveedores, "actualizar", lambda *a, **k: None)

    assert client.patch(f"{BASE}/{PID}", json={"nombre": "x"}).status_code == 404
    assert client.patch(f"{BASE}/no-es-uuid", json={"nombre": "x"}).status_code == 404
