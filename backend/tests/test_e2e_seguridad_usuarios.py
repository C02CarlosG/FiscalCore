"""Seguridad de cuentas de punta a punta: correos sin distinguir mayúsculas, token_version y rol administrador."""
import uuid

import pytest
from fastapi.testclient import TestClient

from backend.tests.conftest import db_disponible

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


@pytest.fixture()
def api():
    import backend.main_api as main
    from backend import db
    from backend.deps import limiter

    db.init_db()
    limiter.reset()
    sufijo = uuid.uuid4().hex[:8]
    yield TestClient(main.app), db, sufijo
    limiter.reset()
    db.execute("DELETE FROM usuario_empresas WHERE usuario_id IN (SELECT id FROM usuarios WHERE email LIKE %s)", (f"%{sufijo}%",))
    db.execute("DELETE FROM empresas WHERE razon_social = %s", (f"Empresa seg {sufijo}",))
    db.execute("DELETE FROM usuarios WHERE email LIKE %s", (f"%{sufijo}%",))


def _registrar(client, email):
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "Test1234!", "nombre": "Seg"})
    assert r.status_code == 201, r.text
    return r.json()


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_register_guarda_el_correo_en_minusculas_y_rechaza_variantes(api):
    client, db, s = api
    cuerpo = _registrar(client, f"  Ana.{s}@Test.LOCAL ")
    assert cuerpo["email"] == f"ana.{s}@test.local"
    assert db.query_one("SELECT 1 FROM usuarios WHERE email = %s", (f"ana.{s}@test.local",))
    r = client.post("/api/v1/auth/register", json={"email": f"ANA.{s}@test.local", "password": "Test1234!"})
    assert r.status_code == 409


def test_login_no_distingue_mayusculas_en_el_correo(api):
    client, db, s = api
    _registrar(client, f"luis.{s}@test.local")
    r = client.post("/api/v1/auth/login", json={"email": f" LUIS.{s}@Test.Local", "password": "Test1234!"})
    assert r.status_code == 200 and r.json()["access_token"]


def test_token_emitido_lleva_la_version_y_se_invalida_al_incrementarla(api):
    from backend.deps import verificar_token

    client, db, s = api
    cuerpo = _registrar(client, f"v.{s}@test.local")
    assert verificar_token(cuerpo["access_token"])["tv"] == 0
    assert client.get("/api/v1/auth/me", headers=_auth(cuerpo["access_token"])).status_code == 200

    db.execute("UPDATE usuarios SET token_version = token_version + 1 WHERE id = %s", (cuerpo["user_id"],))
    r = client.get("/api/v1/auth/me", headers=_auth(cuerpo["access_token"]))
    assert r.status_code == 401

    nuevo = client.post("/api/v1/auth/login", json={"email": f"v.{s}@test.local", "password": "Test1234!"}).json()
    assert verificar_token(nuevo["access_token"])["tv"] == 1
    assert client.get("/api/v1/auth/me", headers=_auth(nuevo["access_token"])).status_code == 200


def test_token_de_usuario_desactivado_o_borrado_da_401(api):
    client, db, s = api
    cuerpo = _registrar(client, f"d.{s}@test.local")
    db.execute("UPDATE usuarios SET activo = FALSE WHERE id = %s", (cuerpo["user_id"],))
    assert client.get("/api/v1/auth/me", headers=_auth(cuerpo["access_token"])).status_code == 401
    db.execute("DELETE FROM usuarios WHERE id = %s", (cuerpo["user_id"],))
    assert client.get("/api/v1/auth/me", headers=_auth(cuerpo["access_token"])).status_code == 401


def test_token_anterior_sin_claim_tv_sigue_valiendo_mientras_la_version_sea_cero(api):
    from backend.deps import crear_token

    client, db, s = api
    cuerpo = _registrar(client, f"o.{s}@test.local")
    viejo = crear_token({"user_id": cuerpo["user_id"], "email": f"o.{s}@test.local"})
    assert client.get("/api/v1/auth/me", headers=_auth(viejo)).status_code == 200
    db.execute("UPDATE usuarios SET token_version = 1 WHERE id = %s", (cuerpo["user_id"],))
    assert client.get("/api/v1/auth/me", headers=_auth(viejo)).status_code == 401


def test_admin_que_desactiva_o_cambia_rol_invalida_las_sesiones(api):
    from backend.deps import crear_token

    client, db, s = api
    admin = _registrar(client, f"adm.{s}@test.local")
    objetivo = _registrar(client, f"obj.{s}@test.local")
    db.execute("UPDATE usuarios SET rol = 'admin' WHERE id = %s", (admin["user_id"],))
    r = client.patch(f"/api/v1/admin/usuarios/{objetivo['user_id']}", headers=_auth(admin["access_token"]),
                     json={"rol": "contador", "activo": True})
    assert r.status_code == 200
    assert client.get("/api/v1/auth/me", headers=_auth(objetivo["access_token"])).status_code == 401


def test_quien_crea_una_empresa_queda_como_administrador(api):
    client, db, s = api
    cuerpo = _registrar(client, f"e.{s}@test.local")
    rfc = "SEG010101" + uuid.uuid4().hex[:3].upper()
    r = client.post("/api/v1/mis-empresas", headers=_auth(cuerpo["access_token"]),
                    json={"rfc": rfc, "razon_social": f"Empresa seg {s}"})
    assert r.status_code == 201, r.text
    fila = db.query_one("SELECT rol FROM usuario_empresas WHERE usuario_id = %s AND empresa_id = %s",
                        (cuerpo["user_id"], r.json()["empresa_id"]))
    assert fila["rol"] == "administrador"
