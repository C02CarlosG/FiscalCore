"""E2E de U1 contra Postgres real: alta, roles, baja y cambio de contraseña con login
real. Se salta sin DB."""
import pytest

from backend.tests.conftest import db_disponible

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]

RFC = "CTA010101AB1"
DUENO = "u1-dueno@test.local"
NUEVO = "u1-nuevo@test.local"
EXISTENTE = "u1-existente@test.local"
CLAVE = "Clave-Duena-1"


def _limpiar(db):
    db.execute("DELETE FROM empresas WHERE rfc = %s", (RFC,))
    db.execute("DELETE FROM usuarios WHERE email IN (%s, %s, %s)", (DUENO, NUEVO, EXISTENTE))


def _login(client, email, password):
    from backend.deps import limiter
    limiter.reset()  # el login permite 5 por minuto
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return r


def _headers(client, email, password):
    r = _login(client, email, password)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def entorno():
    from fastapi.testclient import TestClient

    import backend.main_api as main
    from backend import db
    from backend.deps import hash_password, limiter

    db.init_db()
    _limpiar(db)
    limiter.reset()
    client = TestClient(main.app)
    try:
        db.execute("INSERT INTO usuarios (email, password_hash, nombre) VALUES (%s, %s, 'Dueña')",
                   (DUENO, hash_password(CLAVE)))
        db.execute("INSERT INTO usuarios (email, password_hash, nombre) VALUES (%s, %s, 'Ya existía')",
                   (EXISTENTE, hash_password("Clave-Existente-1")))
        headers = _headers(client, DUENO, CLAVE)
        r = client.post("/api/v1/mis-empresas", headers=headers, json={"rfc": RFC, "razon_social": "Cuenta E2E"})
        assert r.status_code == 201, r.text
        yield db, client, headers, r.json()["empresa_id"]
    finally:
        limiter.reset()
        _limpiar(db)


def _usuarios(client, headers, empresa_id):
    return client.get(f"/api/v1/cuenta/empresas/{empresa_id}/usuarios", headers=headers)


def test_flujo_de_usuarios(entorno):
    db, client, headers, empresa_id = entorno
    base = f"/api/v1/cuenta/empresas/{empresa_id}/usuarios"

    # El creador administra aunque mis-empresas lo vinculó con el rol por defecto.
    lista = _usuarios(client, headers, empresa_id).json()
    assert (lista["mi_rol"], lista["puede_administrar"]) == ("administrador", True)

    # Alta de una cuenta nueva con contraseña temporal.
    r = client.post(base, headers=headers, json={
        "email": " U1-Nuevo@Test.local ", "rol": "contador", "nombre": "Nuevo", "password_temporal": "Temporal-123"})
    assert r.status_code == 201, r.text
    assert r.json()["cuenta_creada"] is True
    nuevo_id = r.json()["usuario"]["usuario_id"]
    h_nuevo = _headers(client, NUEVO, "Temporal-123")
    assert client.get(f"/api/v1/empresas/{empresa_id}", headers=h_nuevo).status_code == 200

    # Vínculo de una cuenta existente: no cambia su contraseña.
    r = client.post(base, headers=headers, json={"email": EXISTENTE, "rol": "administrador",
                                                  "password_temporal": "No-Se-Usa-123"})
    assert r.status_code == 201, r.text
    assert r.json()["cuenta_creada"] is False
    existente_id = r.json()["usuario"]["usuario_id"]
    assert _login(client, EXISTENTE, "Clave-Existente-1").status_code == 200
    assert client.post(base, headers=headers, json={"email": EXISTENTE, "rol": "contador"}).status_code == 409

    # Un contador no administra.
    lista = _usuarios(client, h_nuevo, empresa_id).json()
    assert (lista["mi_rol"], lista["puede_administrar"]) == ("contador", False)
    assert client.post(base, headers=h_nuevo, json={"email": "otro@test.local", "rol": "contador",
                                                     "nombre": "x", "password_temporal": "12345678"}).status_code == 403
    assert client.patch(f"{base}/{existente_id}", headers=h_nuevo, json={"rol": "contador"}).status_code == 403
    assert client.delete(f"{base}/{existente_id}", headers=h_nuevo).status_code == 403

    # Con dos administradores se puede degradar a uno; al último, no.
    dueno_id = next(u["usuario_id"] for u in lista["usuarios"] if u["email"] == DUENO)
    assert client.patch(f"{base}/{existente_id}", headers=headers, json={"rol": "contador"}).status_code == 200
    r = client.patch(f"{base}/{dueno_id}", headers=headers, json={"rol": "contador"})
    assert r.status_code == 409
    assert client.delete(f"{base}/{dueno_id}", headers=headers).status_code == 409

    # Quitar el acceso no borra la cuenta.
    assert client.delete(f"{base}/{nuevo_id}", headers=headers).status_code == 204
    assert client.get(f"/api/v1/empresas/{empresa_id}", headers=h_nuevo).status_code == 403
    assert _login(client, NUEVO, "Temporal-123").status_code == 200
    assert client.delete(f"{base}/{nuevo_id}", headers=headers).status_code == 404

    acciones = {f["accion"] for f in db.query_all(
        "SELECT accion FROM auditoria WHERE empresa_id = %s", (empresa_id,))}
    assert {"cuenta.alta_usuario", "cuenta.cambiar_rol", "cuenta.quitar_usuario"} <= acciones


def test_cambio_de_contrasena(entorno):
    _db, client, headers, _empresa_id = entorno
    url = "/api/v1/cuenta/contrasena"
    assert client.post(url, headers=headers, json={"actual": "incorrecta", "nueva": "Nueva-Clave-1"}).status_code == 400
    assert client.post(url, headers=headers, json={"actual": CLAVE, "nueva": "corta"}).status_code == 422
    assert client.post(url, headers=headers, json={"actual": CLAVE, "nueva": "Nueva-Clave-1"}).status_code == 204
    assert _login(client, DUENO, CLAVE).status_code == 401
    assert _login(client, DUENO, "Nueva-Clave-1").status_code == 200
