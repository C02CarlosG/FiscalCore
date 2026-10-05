"""Router de cuenta (U1) con la base mockeada: validaciones, permisos y auditoría sin
contraseñas."""
from datetime import datetime

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import backend.main_api as main
from backend import db
from backend.deps import get_current_user, limiter
from backend.routers import cuenta

client = TestClient(main.app)
EMPRESA = "11111111-1111-1111-1111-111111111111"
YO = "22222222-2222-2222-2222-222222222222"
OTRO = "33333333-3333-3333-3333-333333333333"
BASE = f"/api/v1/cuenta/empresas/{EMPRESA}/usuarios"


def _miembro(uid, rol, dia):
    return {"usuario_id": uid, "rol": rol, "created_at": datetime(2026, 1, dia), "email": f"{uid[:4]}@x.mx", "nombre": "N"}


@pytest.fixture(autouse=True)
def sesion(monkeypatch):
    main.app.dependency_overrides[get_current_user] = lambda: {"user_id": YO}
    monkeypatch.setattr(cuenta, "validar_acceso_empresa", lambda *a, **k: None)
    limiter.reset()
    yield
    limiter.reset()
    main.app.dependency_overrides.clear()


def _base_falsa(monkeypatch, miembros, rol_plataforma="contador", aceptada=None):
    """`aceptada`: la invitación por aprobar que devuelve el SELECT … FOR UPDATE, o None."""
    ejecutado = []

    def _one(sql, params=()):
        if "SELECT rol FROM usuarios" in sql:
            return {"rol": rol_plataforma}
        if "FROM empresas" in sql:
            return {"id": EMPRESA}
        if "FROM usuario_empresas" in sql:
            return None
        if "SELECT email FROM usuarios" in sql:
            return {"email": "yo@x.mx"}
        raise AssertionError(sql)

    monkeypatch.setattr(db, "query_one", _one)
    monkeypatch.setattr(db, "query_all", lambda sql, params=(): [] if "invitaciones_empresa" in sql else miembros)
    monkeypatch.setattr(db, "execute", lambda sql, params=(), returning=False: ejecutado.append((sql, params)))

    from contextlib import contextmanager
    from backend import usuarios_empresa as ue

    class _Cursor:
        ultimo = ""

        def execute(self, sql, params=()):
            self.ultimo = sql
            ejecutado.append((sql, params))

        def fetchone(self):
            if "INSERT INTO invitaciones_empresa" in self.ultimo:
                from datetime import datetime
                return {"id": "inv-1", "email": "c@d.mx", "rol": "contador", "estado": "pendiente",
                        "created_at": datetime(2026, 10, 4)}
            if "estado = 'aceptada_pendiente'" in self.ultimo:
                return aceptada
            return None

    @contextmanager
    def _bloqueados(eid):
        yield _Cursor(), miembros, ue.roles_efectivos(miembros)

    monkeypatch.setattr(cuenta, "_miembros_bloqueados", _bloqueados)
    return ejecutado


def test_sin_sesion_responde_401():
    main.app.dependency_overrides.clear()
    assert client.get(BASE).status_code == 401
    assert client.post("/api/v1/cuenta/contrasena", json={"actual": "a", "nueva": "b"}).status_code == 401


def test_sin_acceso_responde_403(monkeypatch):
    def _negar(*a, **k):
        raise HTTPException(status_code=403, detail="Sin acceso a esta empresa")

    monkeypatch.setattr(cuenta, "validar_acceso_empresa", _negar)
    _base_falsa(monkeypatch, [])
    assert client.get(BASE).status_code == 403


def test_admin_de_plataforma_entra_sin_ser_miembro(monkeypatch):
    monkeypatch.setattr(cuenta, "validar_acceso_empresa", lambda *a, **k: pytest.fail("no debe exigir membresía"))
    _base_falsa(monkeypatch, [_miembro(OTRO, "administrador", 1)], rol_plataforma="admin")
    r = client.get(BASE)
    assert r.status_code == 200
    assert r.json()["puede_administrar"] is True
    assert r.json()["mi_rol"] is None


def test_lista_marca_al_primer_vinculado_como_administrador(monkeypatch):
    _base_falsa(monkeypatch, [_miembro(YO, "contador", 1), _miembro(OTRO, "contador", 2)])
    cuerpo = client.get(BASE).json()
    assert (cuerpo["mi_rol"], cuerpo["puede_administrar"]) == ("administrador", True)
    assert [(u["rol"], u["soy_yo"]) for u in cuerpo["usuarios"]] == [("administrador", True), ("contador", False)]


def test_contador_no_puede_invitar(monkeypatch):
    ejecutado = _base_falsa(monkeypatch, [_miembro(OTRO, "administrador", 1), _miembro(YO, "contador", 2)])
    r = client.post(f"/api/v1/cuenta/empresas/{EMPRESA}/invitaciones", json={"email": "a@b.mx", "rol": "contador"})
    assert r.status_code == 403
    assert ejecutado == []


@pytest.mark.parametrize("cuerpo,detalle", [
    ({"email": "no-es-correo", "rol": "contador"}, "Correo"),
    ({"email": "a@b.mx", "rol": "dueño"}, "rol"),
])
def test_invitacion_invalida_responde_422_sin_escribir(monkeypatch, cuerpo, detalle):
    ejecutado = _base_falsa(monkeypatch, [_miembro(YO, "administrador", 1)])
    r = client.post(f"/api/v1/cuenta/empresas/{EMPRESA}/invitaciones", json=cuerpo)
    assert r.status_code == 422
    assert detalle in r.json()["detail"]
    assert ejecutado == []


def test_invitar_limitado_a_20_por_hora(monkeypatch):
    _base_falsa(monkeypatch, [_miembro(YO, "contador", 1), _miembro(OTRO, "administrador", 2)])
    codigos = [client.post(f"/api/v1/cuenta/empresas/{EMPRESA}/invitaciones",
                           json={"email": "a@b.mx", "rol": "contador"}).status_code for _ in range(21)]
    assert codigos[:20] == [403] * 20
    assert codigos[20] == 429


def test_cambio_de_contrasena_audita_sin_contrasenas(monkeypatch):
    from backend.deps import hash_password

    auditado = []
    monkeypatch.setattr(db, "query_one", lambda sql, params=(): {"password_hash": hash_password("Actual-123")})
    monkeypatch.setattr(db, "execute", lambda *a, **k: None)
    monkeypatch.setattr(cuenta, "registrar_evento", lambda *a, **k: auditado.append((a, k)))
    r = client.post("/api/v1/cuenta/contrasena", json={"actual": "Actual-123", "nueva": "Nueva-123"})
    assert r.status_code == 204
    assert auditado and "Nueva-123" not in repr(auditado) and "Actual-123" not in repr(auditado)


def test_contrasena_nueva_igual_a_la_actual(monkeypatch):
    from backend.deps import hash_password

    monkeypatch.setattr(db, "query_one", lambda sql, params=(): {"password_hash": hash_password("Actual-123")})
    r = client.post("/api/v1/cuenta/contrasena", json={"actual": "Actual-123", "nueva": "Actual-123"})
    assert r.status_code == 422


def test_contrasena_de_mas_de_128_caracteres_responde_422(monkeypatch):
    monkeypatch.setattr(db, "query_one", lambda *a, **k: pytest.fail("no debe consultar"))
    r = client.post("/api/v1/cuenta/contrasena", json={"actual": "x" * 129, "nueva": "y" * 8})
    assert r.status_code == 422


def test_cambio_de_contrasena_limitado_a_5_por_minuto(monkeypatch):
    monkeypatch.setattr(db, "query_one", lambda sql, params=(): None)
    codigos = [client.post("/api/v1/cuenta/contrasena", json={"actual": "x", "nueva": "y" * 8}).status_code
               for _ in range(6)]
    assert codigos == [400] * 5 + [429]


def test_el_limite_de_invitar_es_por_usuario_y_no_por_ip(monkeypatch):
    from backend.deps import crear_token

    main.app.dependency_overrides.clear()  # usar el token real de cada usuario
    _base_falsa(monkeypatch, [_miembro(YO, "contador", 1), _miembro(OTRO, "administrador", 2)])
    monkeypatch.setattr(cuenta, "validar_acceso_empresa", lambda *a, **k: None)
    url = f"/api/v1/cuenta/empresas/{EMPRESA}/invitaciones"
    h_a = {"Authorization": f"Bearer {crear_token({'user_id': YO})}"}
    h_b = {"Authorization": f"Bearer {crear_token({'user_id': OTRO})}"}
    codigos_a = [client.post(url, headers=h_a, json={"email": "a@b.mx", "rol": "contador"}).status_code for _ in range(21)]
    assert codigos_a[-1] == 429
    # Misma IP (el TestClient), otro usuario: tiene su propio cupo.
    monkeypatch.setattr(cuenta, "registrar_evento", lambda *a, **k: None)
    assert client.post(url, headers=h_b, json={"email": "c@d.mx", "rol": "contador"}).status_code == 201


PENDIENTE = {"id": "inv-1", "rol": "administrador", "respondida_por": OTRO}
APROBAR = f"/api/v1/cuenta/empresas/{EMPRESA}/invitaciones/{PENDIENTE['id'].replace('inv-1', '44444444-4444-4444-4444-444444444444')}"


def _escrituras(ejecutado):
    return [sql for sql, _ in ejecutado if sql.lstrip().startswith(("INSERT", "UPDATE", "DELETE"))
            and "auditoria" not in sql]


@pytest.mark.parametrize("accion", ["aprobar", "rechazar"])
def test_contador_no_puede_resolver_una_aceptacion(monkeypatch, accion):
    ejecutado = _base_falsa(monkeypatch, [_miembro(OTRO, "administrador", 1), _miembro(YO, "contador", 2)],
                            aceptada=PENDIENTE)
    assert client.post(f"{APROBAR}/{accion}").status_code == 403
    assert _escrituras(ejecutado) == []


@pytest.mark.parametrize("accion", ["aprobar", "rechazar"])
def test_resolver_sin_aceptacion_pendiente_responde_404(monkeypatch, accion):
    ejecutado = _base_falsa(monkeypatch, [_miembro(YO, "administrador", 1)], aceptada=None)
    assert client.post(f"{APROBAR}/{accion}").status_code == 404
    assert _escrituras(ejecutado) == []


def test_aprobar_vincula_con_el_rol_invitado_y_audita(monkeypatch):
    ejecutado = _base_falsa(monkeypatch, [_miembro(YO, "administrador", 1)], aceptada=PENDIENTE)
    assert client.post(f"{APROBAR}/aprobar").status_code == 204
    alta = [p for sql, p in ejecutado if "INSERT INTO usuario_empresas" in sql]
    assert alta == [(OTRO, EMPRESA, "administrador")]
    estado = [p for sql, p in ejecutado if "UPDATE invitaciones_empresa" in sql]
    assert estado and estado[0][0] == "aprobada"
    assert any("auditoria" in sql and "cuenta.aprobar_invitacion" in str(p) for sql, p in ejecutado)


def test_rechazar_no_vincula_y_audita(monkeypatch):
    ejecutado = _base_falsa(monkeypatch, [_miembro(YO, "administrador", 1)], aceptada=PENDIENTE)
    assert client.post(f"{APROBAR}/rechazar").status_code == 204
    assert not any("INSERT INTO usuario_empresas" in sql for sql, _ in ejecutado)
    assert [p[0] for sql, p in ejecutado if "UPDATE invitaciones_empresa" in sql] == ["rechazada_admin"]
    assert any("auditoria" in sql and "cuenta.rechazar_aceptacion" in str(p) for sql, p in ejecutado)
