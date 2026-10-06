"""E2E de U1 contra Postgres real: invitaciones, roles, bajas, carreras y cambio de
contraseña con login real. Se salta sin DB."""
import threading

import pytest

from backend.tests.conftest import db_disponible

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]

RFC = "CTA010101AB1"
RFC_OTRA = "CTB010101AB1"
DUENO = "u1-dueno@test.local"
NUEVO = "u1-nuevo@test.local"
EXISTENTE = "u1-existente@test.local"
SEGUNDO = "u1-segundo@test.local"
ATACANTE = "U1-Existente@Test.local"  # mismo correo que EXISTENTE con otras mayúsculas
VICTIMA = "u1-victima@test.local"  # invitada sin cuenta; alguien más se registra con su correo
CORREOS = (DUENO, NUEVO, EXISTENTE, SEGUNDO, ATACANTE, "U1-Victima@Test.local")
CLAVE = "Clave-Duena-1"


def _limpiar(db):
    db.execute("DELETE FROM empresas WHERE rfc IN (%s, %s)", (RFC, RFC_OTRA))
    db.execute("DELETE FROM usuarios WHERE email IN %s", (CORREOS,))
    db.execute("DELETE FROM empresas WHERE rfc = 'CTZ010101AB1'")


def _login(client, email, password):
    from backend.deps import limiter
    limiter.reset()  # el login permite 5 por minuto
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def _headers(client, email, password):
    r = _login(client, email, password)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
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
        for correo, clave in ((DUENO, CLAVE), (EXISTENTE, "Clave-Existente-1"), (SEGUNDO, "Clave-Segundo-1")):
            db.execute("INSERT INTO usuarios (email, password_hash, nombre) VALUES (%s, %s, %s)",
                       (correo, hash_password(clave), f"Nombre real de {correo}"))
        headers = _headers(client, DUENO, CLAVE)
        r = client.post("/api/v1/mis-empresas", headers=headers, json={"rfc": RFC, "razon_social": "Cuenta E2E"})
        assert r.status_code == 201, r.text
        yield db, client, headers, r.json()["empresa_id"]
    finally:
        limiter.reset()
        _limpiar(db)


def _base(empresa_id):
    return f"/api/v1/cuenta/empresas/{empresa_id}"


def _invitar(client, headers, empresa_id, email, rol="contador"):
    from backend.deps import limiter
    limiter.reset()
    return client.post(f"{_base(empresa_id)}/invitaciones", headers=headers, json={"email": email, "rol": rol})


def _aceptar(client, h):
    """La persona acepta su única invitación; devuelve el id."""
    inv = client.get("/api/v1/cuenta/invitaciones", headers=h).json()
    assert len(inv) == 1, inv
    r = client.post(f"/api/v1/cuenta/invitaciones/{inv[0]['id']}/aceptar", headers=h)
    assert r.status_code == 200 and r.json() == {"estado": "aceptada_pendiente"}, r.text
    return inv[0]["id"]


def _unir(client, headers_dueno, empresa_id, email, clave, rol="contador"):
    """Invita, la persona acepta y el administrador aprueba; devuelve los headers de la persona."""
    assert _invitar(client, headers_dueno, empresa_id, email, rol).status_code == 201
    h = _headers(client, email, clave)
    inv_id = _aceptar(client, h)
    assert client.post(f"{_base(empresa_id)}/invitaciones/{inv_id}/aprobar", headers=headers_dueno).status_code == 204
    return h


def test_invitar_no_revela_si_la_cuenta_existe(entorno):
    _db, client, headers, empresa_id = entorno
    sin_cuenta = _invitar(client, headers, empresa_id, " U1-Nuevo@Test.local ")
    con_cuenta = _invitar(client, headers, empresa_id, EXISTENTE)
    assert sin_cuenta.status_code == con_cuenta.status_code == 201
    assert set(sin_cuenta.json()) == set(con_cuenta.json()) == {"id", "email", "rol", "estado", "creada"}
    assert "Nombre real" not in con_cuenta.text
    assert sin_cuenta.json()["email"] == NUEVO

    # Nadie queda vinculado hasta aceptar.
    h_existente = _headers(client, EXISTENTE, "Clave-Existente-1")
    assert client.get(f"/api/v1/empresas/{empresa_id}", headers=h_existente).status_code == 403
    lista = client.get(f"{_base(empresa_id)}/usuarios", headers=headers).json()
    assert {i["email"] for i in lista["invitaciones"]} == {NUEVO, EXISTENTE}

    # Re-invitar actualiza la pendiente, no duplica.
    assert _invitar(client, headers, empresa_id, EXISTENTE, "administrador").json()["rol"] == "administrador"
    assert len(client.get(f"{_base(empresa_id)}/usuarios", headers=headers).json()["invitaciones"]) == 2


def test_aceptar_rechazar_y_cuenta_nueva(entorno):
    db, client, headers, empresa_id = entorno
    h_existente = _unir(client, headers, empresa_id, EXISTENTE, "Clave-Existente-1")
    assert client.get(f"/api/v1/empresas/{empresa_id}", headers=h_existente).status_code == 200
    # Su contraseña no cambió.
    assert _login(client, EXISTENTE, "Clave-Existente-1").status_code == 200

    # Quien no tenía cuenta se registra con ese correo y ve la invitación; la rechaza.
    assert _invitar(client, headers, empresa_id, NUEVO).status_code == 201
    from backend.deps import limiter
    limiter.reset()
    r = client.post("/api/v1/auth/register", json={"email": NUEVO, "password": "Clave-Nuevo-1", "nombre": "Nuevo"})
    assert r.status_code == 201, r.text
    h_nuevo = {"Authorization": f"Bearer {r.json()['access_token']}"}
    inv = client.get("/api/v1/cuenta/invitaciones", headers=h_nuevo).json()
    assert [(i["razon_social"], i["rol"]) for i in inv] == [("Cuenta E2E", "contador")]
    # Otra persona no puede aceptar una invitación que no es suya.
    assert client.post(f"/api/v1/cuenta/invitaciones/{inv[0]['id']}/aceptar", headers=h_existente).status_code == 404
    assert client.post(f"/api/v1/cuenta/invitaciones/{inv[0]['id']}/rechazar", headers=h_nuevo).status_code == 204
    assert client.get(f"/api/v1/empresas/{empresa_id}", headers=h_nuevo).status_code == 403
    assert client.post(f"/api/v1/cuenta/invitaciones/{inv[0]['id']}/aceptar", headers=h_nuevo).status_code == 404

    acciones = {f["accion"] for f in db.query_all("SELECT accion FROM auditoria WHERE empresa_id = %s", (empresa_id,))}
    assert {"cuenta.invitar", "cuenta.aceptar_invitacion", "cuenta.aprobar_invitacion",
            "cuenta.rechazar_invitacion"} <= acciones


def test_aceptar_no_da_acceso_hasta_que_un_administrador_aprueba(entorno):
    """Doble confirmación: alguien se registra con el correo de la invitada (sin cuenta) y
    acepta. Queda por aprobar, sin acceso; el administrador ve su nombre y la fecha de su
    cuenta, un contador no puede resolverla y, al rechazarla, sigue sin acceso."""
    from backend.deps import limiter

    db, client, headers, empresa_id = entorno
    base = _base(empresa_id)
    h_contador = _unir(client, headers, empresa_id, EXISTENTE, "Clave-Existente-1")
    assert _invitar(client, headers, empresa_id, VICTIMA, "administrador").status_code == 201

    limiter.reset()
    r = client.post("/api/v1/auth/register",
                    json={"email": "U1-Victima@Test.local", "password": "Clave-Atacante-1", "nombre": "Impostor"})
    assert r.status_code == 201, r.text
    h_atacante = {"Authorization": f"Bearer {r.json()['access_token']}"}
    inv_id = _aceptar(client, h_atacante)

    # Aceptada, pero sin acceso: la ve como "esperando aprobación" y no puede volver a responder.
    assert client.get(f"/api/v1/empresas/{empresa_id}", headers=h_atacante).status_code == 403
    assert [i["estado"] for i in client.get("/api/v1/cuenta/invitaciones", headers=h_atacante).json()] == ["aceptada_pendiente"]
    assert client.post(f"/api/v1/cuenta/invitaciones/{inv_id}/aceptar", headers=h_atacante).status_code == 404
    lista = client.get(f"{base}/usuarios", headers=headers).json()
    assert lista["invitaciones"] == []
    [pendiente] = lista["por_aprobar"]
    assert (pendiente["id"], pendiente["nombre"], pendiente["rol"]) == (inv_id, "Impostor", "administrador")
    assert pendiente["email"] == "U1-Victima@Test.local"  # el de la cuenta, tal como se registró
    assert pendiente["cuenta_creada"] and pendiente["aceptada"]
    assert client.get(f"{base}/usuarios", headers=h_contador).json()["por_aprobar"] == []

    # Ni un contador ni quien aceptó pueden aprobar.
    assert client.post(f"{base}/invitaciones/{inv_id}/aprobar", headers=h_contador).status_code == 403
    assert client.post(f"{base}/invitaciones/{inv_id}/aprobar", headers=h_atacante).status_code == 403
    # Una invitación de esta empresa no se resuelve desde la ruta de otra (404 uniforme).
    otra = client.post("/api/v1/mis-empresas", headers=headers, json={"rfc": RFC_OTRA, "razon_social": "Otra E2E"})
    assert otra.status_code == 201, otra.text
    assert client.post(f"{_base(otra.json()['empresa_id'])}/invitaciones/{inv_id}/aprobar",
                       headers=headers).status_code == 404

    assert client.post(f"{base}/invitaciones/{inv_id}/rechazar", headers=headers).status_code == 204
    assert client.get(f"/api/v1/empresas/{empresa_id}", headers=h_atacante).status_code == 403
    assert client.post(f"{base}/invitaciones/{inv_id}/aprobar", headers=headers).status_code == 404
    assert client.get("/api/v1/cuenta/invitaciones", headers=h_atacante).json() == []
    assert client.get(f"{base}/usuarios", headers=headers).json()["por_aprobar"] == []
    estado = db.query_one("SELECT estado, resuelta_por FROM invitaciones_empresa WHERE id = %s", (inv_id,))
    assert estado["estado"] == "rechazada_admin" and estado["resuelta_por"] is not None
    acciones = {f["accion"] for f in db.query_all("SELECT accion FROM auditoria WHERE empresa_id = %s", (empresa_id,))}
    assert "cuenta.rechazar_aceptacion" in acciones


def test_aprobar_da_acceso_con_el_rol_invitado(entorno):
    _db, client, headers, empresa_id = entorno
    h = _unir(client, headers, empresa_id, SEGUNDO, "Clave-Segundo-1", rol="administrador")
    assert client.get(f"/api/v1/empresas/{empresa_id}", headers=h).status_code == 200
    lista = client.get(f"{_base(empresa_id)}/usuarios", headers=h).json()
    assert (lista["mi_rol"], lista["puede_administrar"], lista["por_aprobar"]) == ("administrador", True, [])
    # El creador sigue siendo administrador.
    roles = {u["email"]: u["rol"] for u in lista["usuarios"]}
    assert roles == {DUENO: "administrador", SEGUNDO: "administrador"}
    assert client.get("/api/v1/cuenta/invitaciones", headers=h).json() == []


def test_permisos_roles_y_bajas(entorno):
    db, client, headers, empresa_id = entorno
    base = _base(empresa_id)
    h_contador = _unir(client, headers, empresa_id, EXISTENTE, "Clave-Existente-1")
    _unir(client, headers, empresa_id, SEGUNDO, "Clave-Segundo-1", rol="administrador")
    lista = client.get(f"{base}/usuarios", headers=headers).json()
    ids = {u["email"]: u["usuario_id"] for u in lista["usuarios"]}
    assert lista["mi_rol"] == "administrador"

    # Un contador no gestiona.
    contador = client.get(f"{base}/usuarios", headers=h_contador).json()
    assert (contador["mi_rol"], contador["puede_administrar"], contador["invitaciones"]) == ("contador", False, [])
    assert _invitar(client, h_contador, empresa_id, "otro@test.local").status_code == 403
    assert client.patch(f"{base}/usuarios/{ids[SEGUNDO]}", headers=h_contador, json={"rol": "contador"}).status_code == 403
    assert client.delete(f"{base}/usuarios/{ids[SEGUNDO]}", headers=h_contador).status_code == 403

    # No se puede invitar a sí mismo ni a quien ya tiene acceso.
    assert _invitar(client, headers, empresa_id, DUENO).status_code == 422
    assert _invitar(client, headers, empresa_id, EXISTENTE).status_code == 409

    # IDOR: un usuario de otra empresa no es miembro de esta.
    from backend.deps import hash_password
    otro = db.execute("INSERT INTO usuarios (email, password_hash) VALUES (%s, %s) RETURNING id",
                      (NUEVO, hash_password("x" * 8)), returning=True)
    otra = db.execute("INSERT INTO empresas (rfc, razon_social) VALUES (%s, 'Otra') RETURNING id", (RFC_OTRA,), returning=True)
    db.execute("INSERT INTO usuario_empresas (usuario_id, empresa_id, rol) VALUES (%s, %s, 'administrador')",
               (otro["id"], otra["id"]))
    assert client.patch(f"{base}/usuarios/{otro['id']}", headers=headers, json={"rol": "contador"}).status_code == 404
    assert client.delete(f"{base}/usuarios/{otro['id']}", headers=headers).status_code == 404
    assert client.get(f"{_base(otra['id'])}/usuarios", headers=headers).status_code == 403

    # Con dos administradores se puede degradar a uno; al último, no.
    assert client.patch(f"{base}/usuarios/{ids[SEGUNDO]}", headers=headers, json={"rol": "contador"}).status_code == 200
    assert client.patch(f"{base}/usuarios/{ids[DUENO]}", headers=headers, json={"rol": "contador"}).status_code == 409
    assert client.delete(f"{base}/usuarios/{ids[DUENO]}", headers=headers).status_code == 409

    # Quitar el acceso no borra la cuenta.
    assert client.delete(f"{base}/usuarios/{ids[EXISTENTE]}", headers=headers).status_code == 204
    assert client.get(f"/api/v1/empresas/{empresa_id}", headers=h_contador).status_code == 403
    assert _login(client, EXISTENTE, "Clave-Existente-1").status_code == 200
    assert client.delete(f"{base}/usuarios/{ids[EXISTENTE]}", headers=headers).status_code == 404


def test_dos_administradores_que_se_quitan_a_la_vez_dejan_uno(entorno):
    from fastapi.testclient import TestClient

    import backend.main_api as main

    db, client, headers, empresa_id = entorno
    base = _base(empresa_id)
    h_segundo = _unir(client, headers, empresa_id, SEGUNDO, "Clave-Segundo-1", rol="administrador")
    ids = {u["email"]: u["usuario_id"] for u in client.get(f"{base}/usuarios", headers=headers).json()["usuarios"]}

    resultados = {}
    barrera = threading.Barrier(2)

    def quitar(nombre, h, objetivo):
        propio = TestClient(main.app)
        barrera.wait()
        resultados[nombre] = propio.delete(f"{base}/usuarios/{objetivo}", headers=h).status_code

    hilos = [threading.Thread(target=quitar, args=("dueno", headers, ids[SEGUNDO])),
             threading.Thread(target=quitar, args=("segundo", h_segundo, ids[DUENO]))]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    assert sorted(resultados.values())[0] == 204
    assert sorted(resultados.values())[1] in (403, 409)
    admins = db.query_all("SELECT usuario_id FROM usuario_empresas WHERE empresa_id = %s AND rol = 'administrador'",
                          (empresa_id,))
    assert len(admins) == 1


def test_cambio_de_contrasena(entorno):
    _db, client, headers, _empresa_id = entorno
    url = "/api/v1/cuenta/contrasena"
    assert client.post(url, headers=headers, json={"actual": "incorrecta", "nueva": "Nueva-Clave-1"}).status_code == 400
    assert client.post(url, headers=headers, json={"actual": CLAVE, "nueva": "corta"}).status_code == 422
    assert client.post(url, headers=headers, json={"actual": CLAVE, "nueva": "Nueva-Clave-1"}).status_code == 204
    assert _login(client, DUENO, CLAVE).status_code == 401
    assert _login(client, DUENO, "Nueva-Clave-1").status_code == 200


def test_cuenta_con_el_mismo_correo_en_otras_mayusculas_no_toma_la_invitacion(entorno):
    """B1: usuarios.email distingue mayúsculas; con dos cuentas para el mismo correo en
    minúsculas nadie ve ni acepta la invitación hasta que se resuelva la duplicidad."""
    from backend.deps import hash_password

    db, client, headers, empresa_id = entorno
    assert _invitar(client, headers, empresa_id, EXISTENTE).status_code == 201
    db.execute("INSERT INTO usuarios (email, password_hash) VALUES (%s, %s)", (ATACANTE, hash_password("Clave-Atacante-1")))
    h_atacante = _headers(client, ATACANTE, "Clave-Atacante-1")
    h_victima = _headers(client, EXISTENTE, "Clave-Existente-1")

    assert client.get("/api/v1/cuenta/invitaciones", headers=h_atacante).json() == []
    assert client.get("/api/v1/cuenta/invitaciones", headers=h_victima).json() == []
    inv_id = db.query_one("SELECT id FROM invitaciones_empresa WHERE empresa_id = %s AND email = %s",
                          (empresa_id, EXISTENTE))["id"]
    assert client.post(f"/api/v1/cuenta/invitaciones/{inv_id}/aceptar", headers=h_atacante).status_code == 404
    assert client.get(f"/api/v1/empresas/{empresa_id}", headers=h_atacante).status_code == 403
    assert db.query_one("SELECT COUNT(*) AS n FROM auditoria WHERE accion = 'cuenta.correo_ambiguo'")["n"] >= 1


def test_invitacion_vencida_no_se_lista_ni_se_acepta(entorno):
    db, client, headers, empresa_id = entorno
    assert _invitar(client, headers, empresa_id, EXISTENTE).status_code == 201
    db.execute("UPDATE invitaciones_empresa SET expires_at = NOW() - INTERVAL '1 minute' WHERE email = %s", (EXISTENTE,))
    h = _headers(client, EXISTENTE, "Clave-Existente-1")
    assert client.get("/api/v1/cuenta/invitaciones", headers=h).json() == []
    inv_id = db.query_one("SELECT id FROM invitaciones_empresa WHERE email = %s", (EXISTENTE,))["id"]
    assert client.post(f"/api/v1/cuenta/invitaciones/{inv_id}/aceptar", headers=h).status_code == 404
    # Tampoco aparece como pendiente para la empresa, y re-invitar la renueva.
    assert client.get(f"{_base(empresa_id)}/usuarios", headers=headers).json()["invitaciones"] == []
    assert _invitar(client, headers, empresa_id, EXISTENTE).status_code == 201
    assert len(client.get("/api/v1/cuenta/invitaciones", headers=h).json()) == 1


def test_aceptacion_sin_aprobar_vence_a_los_7_dias(entorno):
    db, client, headers, empresa_id = entorno
    assert _invitar(client, headers, empresa_id, EXISTENTE).status_code == 201
    h = _headers(client, EXISTENTE, "Clave-Existente-1")
    inv_id = _aceptar(client, h)
    vence = db.query_one("SELECT expires_at - respondida_at AS plazo FROM invitaciones_empresa WHERE id = %s", (inv_id,))
    assert vence["plazo"].days == 7
    db.execute("UPDATE invitaciones_empresa SET expires_at = NOW() - INTERVAL '1 minute' WHERE id = %s", (inv_id,))
    assert client.get(f"{_base(empresa_id)}/usuarios", headers=headers).json()["por_aprobar"] == []
    assert client.post(f"{_base(empresa_id)}/invitaciones/{inv_id}/aprobar", headers=headers).status_code == 404
    assert client.get(f"/api/v1/empresas/{empresa_id}", headers=h).status_code == 403
    assert client.get("/api/v1/cuenta/invitaciones", headers=h).json() == []


def test_no_se_acepta_invitacion_de_empresa_inactiva(entorno):
    db, client, headers, empresa_id = entorno
    assert _invitar(client, headers, empresa_id, EXISTENTE).status_code == 201
    h = _headers(client, EXISTENTE, "Clave-Existente-1")
    inv_id = client.get("/api/v1/cuenta/invitaciones", headers=h).json()[0]["id"]
    db.execute("UPDATE empresas SET activo = FALSE WHERE id = %s", (empresa_id,))
    try:
        assert client.get("/api/v1/cuenta/invitaciones", headers=h).json() == []
        assert client.post(f"/api/v1/cuenta/invitaciones/{inv_id}/aceptar", headers=h).status_code == 404
    finally:
        db.execute("UPDATE empresas SET activo = TRUE WHERE id = %s", (empresa_id,))


def test_aprobar_o_promover_a_administrador_respeta_el_plan_de_la_persona(entorno):
    """M7.1: administrar la empresa suma un RFC al plan de la persona. Con el plan de
    prueba (1 RFC) ya usado en otra empresa, no se le aprueba ni se le promueve como
    administradora; como contadora, sí."""
    db, client, headers, empresa_id = entorno
    base = _base(empresa_id)
    segundo = db.query_one("SELECT id FROM usuarios WHERE email = %s", (SEGUNDO,))["id"]
    otra = db.execute("INSERT INTO empresas (rfc, razon_social) VALUES (%s, 'Propia') RETURNING id", (RFC_OTRA,),
                      returning=True)
    db.execute("INSERT INTO usuario_empresas (usuario_id, empresa_id, rol) VALUES (%s, %s, 'administrador')",
               (segundo, otra["id"]))

    assert _invitar(client, headers, empresa_id, SEGUNDO, "administrador").status_code == 201
    h = _headers(client, SEGUNDO, "Clave-Segundo-1")
    inv_id = _aceptar(client, h)
    r = client.post(f"{base}/invitaciones/{inv_id}/aprobar", headers=headers)
    assert r.status_code == 403 and "de esa persona" in r.json()["detail"], r.text
    assert client.get(f"/api/v1/empresas/{empresa_id}", headers=h).status_code == 403
    assert client.get(f"{base}/usuarios", headers=headers).json()["por_aprobar"][0]["id"] == inv_id

    # Se rechaza esa aceptación y se le invita como contadora: entra.
    assert client.post(f"{base}/invitaciones/{inv_id}/rechazar", headers=headers).status_code == 204
    _unir(client, headers, empresa_id, SEGUNDO, "Clave-Segundo-1", rol="contador")
    assert client.get(f"/api/v1/empresas/{empresa_id}", headers=h).status_code == 200
    r = client.patch(f"{base}/usuarios/{segundo}", headers=headers, json={"rol": "administrador"})
    assert r.status_code == 403 and "de esa persona" in r.json()["detail"], r.text
