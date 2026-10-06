"""Router de suscripción (M7.1) con la base mockeada: sesión, permisos de admin y
validaciones."""
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

import backend.main_api as main
from backend import db
from backend import suscripcion_datos as datos
from backend.deps import get_current_user

client = TestClient(main.app)
USUARIO = "22222222-2222-2222-2222-222222222222"
PLANES = {
    "prueba": {"clave": "prueba", "nombre": "Prueba", "precio_mensual": Decimal("0"), "max_rfc": 1,
               "por_defecto": True, "activo": True, "orden": 10},
    "viejo": {"clave": "viejo", "nombre": "Viejo", "precio_mensual": Decimal("9"), "max_rfc": 9,
              "por_defecto": False, "activo": False, "orden": 20},
}


@pytest.fixture(autouse=True)
def sesion(monkeypatch):
    main.app.dependency_overrides[get_current_user] = lambda: {"user_id": "u1"}
    monkeypatch.setattr(datos, "planes", lambda: PLANES)
    yield
    main.app.dependency_overrides.clear()


def _rol(monkeypatch, rol, existe=True):
    def _one(sql, params=()):
        if "SELECT rol FROM usuarios" in sql:
            return {"rol": rol}
        if "SELECT id FROM usuarios" in sql:
            return {"id": USUARIO} if existe else None
        raise AssertionError(sql)
    monkeypatch.setattr(db, "query_one", _one)


def test_sin_sesion_responde_401():
    main.app.dependency_overrides.clear()
    assert client.get("/api/v1/suscripcion").status_code == 401


def test_planes_solo_activos_con_precio_en_texto():
    r = client.get("/api/v1/suscripcion/planes")
    assert r.status_code == 200
    assert [(p["clave"], p["precio_mensual"]) for p in r.json()] == [("prueba", "0.00")]


@pytest.mark.parametrize("metodo,ruta,cuerpo", [
    ("get", "/api/v1/suscripcion/admin/cuentas", None),
    ("put", f"/api/v1/suscripcion/admin/cuentas/{USUARIO}", {"plan_clave": "prueba"}),
    ("put", "/api/v1/suscripcion/admin/planes/basico", {"nombre": "B", "precio_mensual": 1, "max_rfc": 1}),
])
def test_admin_exige_rol_admin(monkeypatch, metodo, ruta, cuerpo):
    _rol(monkeypatch, "contador")
    monkeypatch.setattr(datos, "asignar", lambda *a: pytest.fail("no debe asignar"))
    monkeypatch.setattr(datos, "guardar_plan", lambda *a: pytest.fail("no debe guardar"))
    r = getattr(client, metodo)(ruta, json=cuerpo) if cuerpo else getattr(client, metodo)(ruta)
    assert r.status_code == 403


@pytest.mark.parametrize("cuerpo", [{"plan_clave": "inexistente"}, {"plan_clave": "viejo"},
                                    {"plan_clave": "prueba", "estado": "pausada"}])
def test_asignacion_invalida_responde_422(monkeypatch, cuerpo):
    _rol(monkeypatch, "admin")
    monkeypatch.setattr(datos, "asignar", lambda *a: pytest.fail("no debe asignar"))
    assert client.put(f"/api/v1/suscripcion/admin/cuentas/{USUARIO}", json=cuerpo).status_code == 422


def test_asignar_a_cuenta_inexistente_responde_404(monkeypatch):
    _rol(monkeypatch, "admin", existe=False)
    assert client.put(f"/api/v1/suscripcion/admin/cuentas/{USUARIO}", json={"plan_clave": "prueba"}).status_code == 404


@pytest.mark.parametrize("clave,cuerpo", [
    ("Mal", {"nombre": "B", "precio_mensual": 1, "max_rfc": 1}),
    ("basico", {"nombre": "B", "precio_mensual": -1, "max_rfc": 1}),
    ("basico", {"nombre": "B", "precio_mensual": 1, "max_rfc": -1}),
])
def test_plan_invalido_responde_422(monkeypatch, clave, cuerpo):
    _rol(monkeypatch, "admin")
    monkeypatch.setattr(datos, "guardar_plan", lambda *a: pytest.fail("no debe guardar"))
    assert client.put(f"/api/v1/suscripcion/admin/planes/{clave}", json=cuerpo).status_code == 422
