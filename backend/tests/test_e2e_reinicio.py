"""E2E de «Reiniciar datos» contra Postgres real: permisos, doble confirmación,
qué se borra y qué se conserva, otra empresa intacta y confirmaciones simultáneas."""
import threading
from datetime import timedelta

import pytest

from backend.tests.conftest import db_disponible

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]

RFC, RFC_OTRA = "RNI010101AB1", "RNO010101AB1"
ADMIN, CONTADOR = "reinicio-admin@test.local", "reinicio-contador@test.local"
CLAVE = "Clave-Reinicio-1"


def _limpiar(db):
    # Borrar la empresa arrastra sus CFDI, movimientos y conciliaciones en una sola sentencia.
    db.execute("DELETE FROM empresas WHERE rfc IN (%s, %s)", (RFC, RFC_OTRA))
    db.execute("DELETE FROM usuarios WHERE email IN (%s, %s)", (ADMIN, CONTADOR))


def _usuario(db, email):
    from backend.deps import crear_token, hash_password

    fila = db.execute("INSERT INTO usuarios (email, password_hash, nombre) VALUES (%s, %s, 'E2E') RETURNING id",
                      (email, hash_password(CLAVE)), returning=True)
    return str(fila["id"]), {"Authorization": f"Bearer {crear_token({'user_id': str(fila['id']), 'email': email})}"}


def _sembrar(db, empresa_id, prefijo):
    """Datos operativos y no operativos de una empresa."""
    cfdi = [db.execute(
        "INSERT INTO cfdi (empresa_id, uuid, tipo_comprobante, rfc_emisor, rfc_receptor, fecha_emision) "
        "VALUES (%s, %s, 'I', 'AAA010101AAA', 'BBB010101BBB', '2026-03-01') RETURNING id",
        (empresa_id, f"REINICIO-{prefijo}-{n}"), returning=True)["id"] for n in range(2)]
    db.execute("INSERT INTO cfdi_conceptos (cfdi_id, linea) VALUES (%s, 1)", (cfdi[0],))
    db.execute("INSERT INTO pagos_cfdi (empresa_id, cfdi_id, uuid_cfdi_pago, fecha_pago, monto) "
               "VALUES (%s, %s, %s, '2026-03-02', 10)", (empresa_id, cfdi[1], f"REINICIO-{prefijo}-P"))
    mov = db.execute("INSERT INTO movimientos_bancarios (empresa_id, banco, fecha, monto, tipo, cfdi_id) "
                     "VALUES (%s, 'BANCO', '2026-03-02', 10, 'deposito', %s) RETURNING id",
                     (empresa_id, cfdi[0]), returning=True)["id"]
    db.execute("INSERT INTO conciliaciones (empresa_id, tipo_match, cfdi_id, movimiento_id) VALUES (%s, 'exacto', %s, %s)",
               (empresa_id, cfdi[0], mov))
    for mes, estado in (("2026-01", "fallo"), ("2026-02", "descargado"), ("2026-03", "en_proceso")):
        db.execute("INSERT INTO sat_solicitudes (empresa_id, tipo, periodo_inicio, periodo_fin, estado) "
                   "VALUES (%s, 'emitidos', %s, %s, %s)", (empresa_id, mes, mes, estado))
    db.execute("INSERT INTO sat_sync_config (empresa_id, activa, estado) VALUES (%s, TRUE, 'al_dia') "
               "ON CONFLICT (empresa_id) DO UPDATE SET activa = TRUE, estado = 'al_dia'", (empresa_id,))
    db.execute("INSERT INTO declaraciones (empresa_id, periodo, impuesto) VALUES (%s, '2026-03', 'iva')", (empresa_id,))
    db.execute("INSERT INTO proveedores (empresa_id, rfc) VALUES (%s, 'CCC010101CCC')", (empresa_id,))


def _cuenta(db, tabla, empresa_id, extra=""):
    return db.query_one(f"SELECT COUNT(*) AS n FROM {tabla} WHERE empresa_id = %s{extra}", (empresa_id,))["n"]


@pytest.fixture
def entorno():
    from fastapi.testclient import TestClient

    import backend.main_api as main
    from backend import db
    from backend.deps import limiter

    db.init_db()
    _limpiar(db)
    limiter.reset()
    try:
        admin_id, h_admin = _usuario(db, ADMIN)
        contador_id, h_contador = _usuario(db, CONTADOR)
        empresas = []
        for rfc in (RFC, RFC_OTRA):
            eid = str(db.execute("INSERT INTO empresas (rfc, razon_social) VALUES (%s, 'Reinicio') RETURNING id",
                                 (rfc,), returning=True)["id"])
            db.execute("INSERT INTO usuario_empresas (usuario_id, empresa_id, rol, created_at) "
                       "VALUES (%s, %s, 'administrador', NOW() - INTERVAL '1 day')", (admin_id, eid))
            _sembrar(db, eid, rfc)
            empresas.append(eid)
        db.execute("INSERT INTO usuario_empresas (usuario_id, empresa_id, rol) VALUES (%s, %s, 'contador')",
                   (contador_id, empresas[0]))
        yield db, TestClient(main.app), h_admin, h_contador, empresas[0], empresas[1]
    finally:
        limiter.reset()
        _limpiar(db)


def _base(eid):
    return f"/api/v1/reinicio/empresas/{eid}"


def _previsualizar(client, h, eid):
    return client.post(f"{_base(eid)}/previsualizar", headers=h, json={"alcance": "todo"})


def _confirmar(client, h, eid, token, frase=f"REINICIAR {RFC}", contrasena=CLAVE):
    from backend.deps import limiter
    limiter.reset()
    return client.post(f"{_base(eid)}/confirmar", headers=h, json={"token": token, "frase": frase, "contrasena": contrasena})


def test_contador_no_reinicia(entorno):
    db, client, _h_admin, h_contador, eid, _otra = entorno
    assert _previsualizar(client, h_contador, eid).status_code == 403
    assert _confirmar(client, h_contador, eid, "x").status_code == 403
    assert _cuenta(db, "cfdi", eid) == 2


def test_previsualizar_cuenta_y_da_frase(entorno):
    db, client, h_admin, _h_contador, eid, _otra = entorno
    assert client.post(f"{_base(eid)}/previsualizar", headers=h_admin, json={"alcance": "2026"}).status_code == 422
    r = _previsualizar(client, h_admin, eid)
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["frase"] == f"REINICIAR {RFC}" and len(cuerpo["token"]) >= 40
    assert (cuerpo["total_cfdi"], cuerpo["conteos"]["sat_solicitudes"], cuerpo["conteos"]["conciliaciones"]) == (2, 2, 1)
    # Solo el hash del token queda guardado.
    guardado = db.query_one("SELECT token_sha256 FROM reinicios_empresa WHERE empresa_id = %s", (eid,))["token_sha256"]
    assert cuerpo["token"] not in guardado and len(guardado) == 64


def test_confirmaciones_invalidas_no_borran_nada(entorno):
    db, client, h_admin, h_contador, eid, otra = entorno
    token = _previsualizar(client, h_admin, eid).json()["token"]
    assert _confirmar(client, h_admin, eid, token, frase="REINICIAR").status_code == 400
    assert _confirmar(client, h_admin, eid, token, frase=f"REINICIAR {RFC_OTRA}").status_code == 400
    assert _confirmar(client, h_admin, eid, token, contrasena="incorrecta").status_code == 403
    assert _confirmar(client, h_admin, eid, "token-inventado").status_code == 400
    # El token de una empresa no sirve en la otra.
    assert _confirmar(client, h_admin, otra, token, frase=f"REINICIAR {RFC_OTRA}").status_code == 400
    # Vencido.
    db.execute("UPDATE reinicios_empresa SET expira_en = NOW() - INTERVAL '1 second' WHERE empresa_id = %s", (eid,))
    assert _confirmar(client, h_admin, eid, token).status_code == 400
    assert _cuenta(db, "cfdi", eid) == 2 and _cuenta(db, "conciliaciones", eid) == 1


def test_reinicio_borra_lo_operativo_y_conserva_lo_demas(entorno):
    db, client, h_admin, _h_contador, eid, otra = entorno
    token = _previsualizar(client, h_admin, eid).json()["token"]
    r = _confirmar(client, h_admin, eid, token)
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["sincronizacion_pausada"] is True
    assert (cuerpo["borrados"]["cfdi"], cuerpo["borrados"]["sat_solicitudes"]) == (2, 2)

    for tabla in ("cfdi", "pagos_cfdi", "movimientos_bancarios", "conciliaciones"):
        assert _cuenta(db, tabla, eid) == 0, tabla
    assert db.query_one("SELECT COUNT(*) AS n FROM cfdi_conceptos cc JOIN cfdi c ON c.id = cc.cfdi_id "
                        "WHERE c.empresa_id = %s", (eid,))["n"] == 0
    # Se conservan: la solicitud en curso, declaraciones, proveedores, la empresa y su configuración (pausada).
    assert _cuenta(db, "sat_solicitudes", eid, " AND estado = 'en_proceso'") == 1
    assert _cuenta(db, "declaraciones", eid) == 1 and _cuenta(db, "proveedores", eid) == 1
    config = db.query_one("SELECT activa, estado, motivo_pausa FROM sat_sync_config WHERE empresa_id = %s", (eid,))
    assert (config["activa"], config["estado"], config["motivo_pausa"]) == (False, "pausada", "Reinicio de datos")
    # La otra empresa no cambia.
    assert _cuenta(db, "cfdi", otra) == 2 and _cuenta(db, "sat_solicitudes", otra) == 3
    assert db.query_one("SELECT activa FROM sat_sync_config WHERE empresa_id = %s", (otra,))["activa"] is True
    # Auditoría e historial.
    acciones = [f["accion"] for f in db.query_all("SELECT accion FROM auditoria WHERE empresa_id = %s ORDER BY creado_en", (eid,))]
    assert acciones[-2:] == ["empresa.reiniciar_previsualizar", "empresa.reiniciar"]
    historial = db.query_one("SELECT usado_en, borrados FROM reinicios_empresa WHERE empresa_id = %s", (eid,))
    assert historial["usado_en"] is not None and historial["borrados"]["cfdi"] == 2
    # El token no se reutiliza.
    assert _confirmar(client, h_admin, eid, token).status_code == 409


def test_dos_confirmaciones_simultaneas(entorno):
    from fastapi.testclient import TestClient

    import backend.main_api as main
    from backend.deps import limiter

    db, client, h_admin, _h_contador, eid, _otra = entorno
    token = _previsualizar(client, h_admin, eid).json()["token"]
    limiter.reset()
    barrera, codigos = threading.Barrier(2), []

    def confirmar():
        propio = TestClient(main.app)
        barrera.wait()
        codigos.append(propio.post(f"{_base(eid)}/confirmar", headers=h_admin,
                                   json={"token": token, "frase": f"REINICIAR {RFC}", "contrasena": CLAVE}).status_code)

    hilos = [threading.Thread(target=confirmar) for _ in range(2)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert sorted(codigos) == [200, 409]
    assert _cuenta(db, "cfdi", eid) == 0


def test_empresa_demasiado_grande_responde_409(entorno, monkeypatch):
    from backend import reinicio_empresa

    db, client, h_admin, _h_contador, eid, _otra = entorno
    monkeypatch.setattr(reinicio_empresa, "MAX_CFDI", 1)
    r = _previsualizar(client, h_admin, eid)
    assert r.status_code == 409 and "segundo plano" in r.json()["detail"]
    assert db.query_one("SELECT COUNT(*) AS n FROM reinicios_empresa WHERE empresa_id = %s", (eid,))["n"] == 0
