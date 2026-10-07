"""Endpoints de la descarga automática (sync/estado, sync/config, sync/ahora) contra Postgres real."""
from datetime import datetime, timedelta, timezone

import pytest

from backend.tests.conftest import db_disponible, headers_usuario_e2e

RFC = "SYN010101E2E"
EMAIL = "e2e-sync-endpoints@test.local"
EMAIL_AJENO = "e2e-sync-ajeno@test.local"

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


def _limpiar(db):
    db.execute("DELETE FROM empresas WHERE rfc = %s", (RFC,))
    db.execute("DELETE FROM usuarios WHERE email IN (%s, %s)", (EMAIL, EMAIL_AJENO))


@pytest.fixture(scope="module")
def entorno():
    from fastapi.testclient import TestClient

    import backend.main_api as main
    from backend import db

    db.init_db()
    _limpiar(db)
    client = TestClient(main.app)
    try:
        headers = headers_usuario_e2e(db, EMAIL)
        r = client.post("/api/v1/mis-empresas", headers=headers, json={"rfc": RFC, "razon_social": "Sync E2E"})
        assert r.status_code == 201, r.text
        yield db, client, headers, r.json()["empresa_id"]
    finally:
        _limpiar(db)


@pytest.fixture(autouse=True)
def _estado_limpio(entorno, monkeypatch):
    """Cada prueba parte sin configuración, solicitudes ni auditoría, con e.firma vigente y sin límite de tasa."""
    from backend import fiel_store
    from backend.deps import limiter

    db, _client, _headers, empresa = entorno
    for tabla in ("sat_sync_config", "sat_solicitudes", "auditoria"):
        db.execute(f"DELETE FROM {tabla} WHERE empresa_id = %s", (empresa,))
    limiter.reset()
    monkeypatch.setattr(fiel_store, "estado_fiel", lambda db_, eid: {"tiene_fiel": True, "vencida": False})


def _url(empresa, ruta):
    return f"/api/v1/sat/empresas/{empresa}/sync/{ruta}"


def _estado(entorno):
    _db, client, headers, empresa = entorno
    r = client.get(_url(empresa, "estado"), headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _activar(entorno, **cuerpo):
    _db, client, headers, empresa = entorno
    return client.put(_url(empresa, "config"), headers=headers, json={"activa": True, "consentimiento": True, **cuerpo})


def _config(db, empresa):
    return db.query_one("SELECT * FROM sat_sync_config WHERE empresa_id=%s", (empresa,))


def _auditoria(db, empresa, accion):
    return db.query_all("SELECT * FROM auditoria WHERE empresa_id=%s AND accion=%s", (empresa, accion))


def _usuario_id(db):
    return str(db.query_one("SELECT id FROM usuarios WHERE email=%s", (EMAIL,))["id"])


# ─── GET sync/estado ─────────────────────────────────────────────────────────

def test_estado_sin_configuracion_devuelve_los_valores_por_defecto(entorno):
    assert _estado(entorno) == {
        "activa": False, "estado": "inactiva", "motivo_pausa": None, "ultima_exitosa": None,
        "proxima_corrida": None, "carga_inicial_ok": False, "consentimiento_por": None,
        "consentimiento_el": None, "progreso": {"total": 0, "terminadas": 0, "fallidas": 0},
        "cancelados_fallidas": 0,
    }


def test_estado_con_corrida_en_curso_cuenta_el_progreso(entorno):
    from backend import sat_sync

    db, _c, _h, empresa = entorno
    ahora = datetime.now(timezone.utc)
    db.execute("INSERT INTO sat_sync_config (empresa_id, activa, estado, corrida_inicio, proxima_corrida) "
               "VALUES (%s, TRUE, 'sincronizando', NOW() - INTERVAL '1 minute', %s)", (empresa, ahora))

    def _sol(estado, tipo="emitidos", mes="2026-01", error=None, fi="2026-01-01", ff="2026-01-31"):
        db.execute(
            "INSERT INTO sat_solicitudes (empresa_id, tipo, periodo_inicio, periodo_fin, estado, error_msg, "
            "fecha_inicio, fecha_fin, origen) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'inicial')",
            (empresa, tipo, mes, mes, estado, error, fi, ff))
    _sol("descargado", mes="2026-01")
    _sol("descargado", mes="2026-02", fi="2026-02-01", ff="2026-02-28")
    _sol("solicitado", mes="2026-03", fi="2026-03-01", ff="2026-03-31")
    _sol("fallo", mes="2026-04", error="El SAT rechazó", fi="2026-04-01", ff="2026-04-30")
    _sol("fallo", tipo="recibidos", mes="2026-05", fi="2026-05-01", ff="2026-05-31",
         error=f"El SAT rechazó 2026-05-01 a 2026-05-31 por volumen (código 5003); {sat_sync.MARCA_PARTIDA}.")

    progreso = _estado(entorno)["progreso"]

    assert progreso["terminadas"] == 2
    assert progreso["fallidas"] == 1                       # la ventana partida no es una falla
    assert progreso["total"] > 2 + 1 + 1                   # incluye las ventanas planeadas que aún no se crean


def test_estado_sin_corrida_en_curso_tiene_progreso_en_cero(entorno):
    db, _c, _h, empresa = entorno
    db.execute("INSERT INTO sat_sync_config (empresa_id, activa, estado, ultima_exitosa, carga_inicial_ok) "
               "VALUES (%s, TRUE, 'al_dia', NOW(), TRUE)", (empresa,))
    e = _estado(entorno)
    assert e["progreso"] == {"total": 0, "terminadas": 0, "fallidas": 0}
    assert e["estado"] == "al_dia" and e["carga_inicial_ok"] is True and e["ultima_exitosa"] is not None


def test_estado_no_expone_credenciales(entorno):
    texto = str(_estado(entorno)).lower()
    for prohibido in ("cer", "key", "password", "pwd", "cifrado"):
        assert prohibido not in texto.replace("carga_inicial", "")


# ─── PUT sync/config ─────────────────────────────────────────────────────────

def test_activar_sin_consentimiento_da_422_y_no_escribe(entorno):
    db, client, headers, empresa = entorno

    r = client.put(_url(empresa, "config"), headers=headers, json={"activa": True, "consentimiento": False})

    assert r.status_code == 422
    assert "consentimiento" in r.json()["detail"].lower()
    assert _config(db, empresa) is None and _auditoria(db, empresa, "sync_activada") == []


def test_activar_sin_efirma_o_con_efirma_vencida_da_422_y_no_escribe(entorno, monkeypatch):
    from backend import fiel_store

    db, _c, _h, empresa = entorno
    monkeypatch.setattr(fiel_store, "estado_fiel", lambda db_, eid: None)
    r = _activar(entorno)
    assert r.status_code == 422 and "e.firma" in r.json()["detail"]

    monkeypatch.setattr(fiel_store, "estado_fiel", lambda db_, eid: {"tiene_fiel": True, "vencida": True})
    r = _activar(entorno)
    assert r.status_code == 422 and "vencida" in r.json()["detail"]
    assert _config(db, empresa) is None


def test_activar_guarda_el_consentimiento_deja_la_empresa_lista_y_audita(entorno):
    db, _c, _h, empresa = entorno

    r = _activar(entorno)

    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["activa"] is True and cuerpo["estado"] == "sincronizando"
    assert cuerpo["consentimiento_por"] == _usuario_id(db) and cuerpo["consentimiento_el"]
    cfg = _config(db, empresa)
    assert cfg["activa"] is True and cfg["motivo_pausa"] is None
    assert cfg["proxima_corrida"] <= datetime.now(timezone.utc)          # el worker la toma en su siguiente ciclo
    evento = _auditoria(db, empresa, "sync_activada")
    assert len(evento) == 1 and str(evento[0]["usuario_id"]) == _usuario_id(db)


def test_la_empresa_activada_es_elegible_para_el_worker(entorno):
    from backend import worker

    _db, _c, _h, empresa = entorno
    assert _activar(entorno).status_code == 200
    assert empresa in worker.empresas_elegibles(datetime.now(timezone.utc))


def test_activar_dos_veces_no_reinicia_la_corrida_ni_duplica_la_auditoria(entorno):
    db, _c, _h, empresa = entorno
    assert _activar(entorno).status_code == 200
    db.execute("UPDATE sat_sync_config SET corrida_inicio=NOW(), estado='sincronizando' WHERE empresa_id=%s", (empresa,))
    antes = _config(db, empresa)

    r = _activar(entorno)

    assert r.status_code == 200
    despues = _config(db, empresa)
    assert despues["corrida_inicio"] == antes["corrida_inicio"] and despues["proxima_corrida"] == antes["proxima_corrida"]
    assert len(_auditoria(db, empresa, "sync_activada")) == 1


def test_reactivar_una_empresa_pausada_limpia_el_motivo(entorno):
    db, _c, _h, empresa = entorno
    db.execute("INSERT INTO sat_sync_config (empresa_id, activa, estado, motivo_pausa) "
               "VALUES (%s, TRUE, 'pausada', 'e.firma vencida')", (empresa,))
    assert _activar(entorno).status_code == 200
    cfg = _config(db, empresa)
    assert cfg["motivo_pausa"] is None and cfg["estado"] == "sincronizando"


def test_desactivar_pausa_de_inmediato_y_audita(entorno):
    from backend import worker

    db, client, headers, empresa = entorno
    assert _activar(entorno).status_code == 200

    r = client.put(_url(empresa, "config"), headers=headers, json={"activa": False})

    assert r.status_code == 200 and r.json()["activa"] is False and r.json()["estado"] == "inactiva"
    cfg = _config(db, empresa)
    assert cfg["activa"] is False and cfg["corrida_inicio"] is None
    assert len(_auditoria(db, empresa, "sync_desactivada")) == 1
    assert empresa not in worker.empresas_elegibles(datetime.now(timezone.utc))


def test_desactivar_sin_configuracion_previa_no_hace_nada(entorno):
    db, client, headers, empresa = entorno
    r = client.put(_url(empresa, "config"), headers=headers, json={"activa": False})
    assert r.status_code == 200 and r.json()["estado"] == "inactiva"
    assert _config(db, empresa) is None and _auditoria(db, empresa, "sync_desactivada") == []


def test_config_con_cuerpo_invalido_da_422(entorno):
    _db, client, headers, empresa = entorno
    assert client.put(_url(empresa, "config"), headers=headers, json={"activa": "quizá"}).status_code == 422
    assert client.put(_url(empresa, "config"), headers=headers, json={}).status_code == 422


# ─── POST sync/ahora ─────────────────────────────────────────────────────────

def test_ahora_con_la_automatizacion_apagada_da_422(entorno):
    _db, client, headers, empresa = entorno
    r = client.post(_url(empresa, "ahora"), headers=headers)
    assert r.status_code == 422 and "activa" in r.json()["detail"].lower()


def test_ahora_sin_efirma_vigente_da_422(entorno, monkeypatch):
    from backend import fiel_store

    db, client, headers, empresa = entorno
    db.execute("INSERT INTO sat_sync_config (empresa_id, activa, estado, proxima_corrida) "
               "VALUES (%s, TRUE, 'al_dia', NOW() + INTERVAL '5 hours')", (empresa,))
    monkeypatch.setattr(fiel_store, "estado_fiel", lambda db_, eid: {"tiene_fiel": True, "vencida": True})
    r = client.post(_url(empresa, "ahora"), headers=headers)
    assert r.status_code == 422 and "vencida" in r.json()["detail"]


def test_ahora_con_una_corrida_en_curso_da_409(entorno):
    db, client, headers, empresa = entorno
    db.execute("INSERT INTO sat_sync_config (empresa_id, activa, estado, corrida_inicio) "
               "VALUES (%s, TRUE, 'sincronizando', NOW())", (empresa,))
    r = client.post(_url(empresa, "ahora"), headers=headers)
    assert r.status_code == 409 and "en curso" in r.json()["detail"]


def test_ahora_adelanta_la_corrida_y_audita(entorno):
    from backend import worker

    db, client, headers, empresa = entorno
    db.execute("INSERT INTO sat_sync_config (empresa_id, activa, estado, proxima_corrida, carga_inicial_ok, ultima_exitosa) "
               "VALUES (%s, TRUE, 'al_dia', NOW() + INTERVAL '8 hours', TRUE, NOW())", (empresa,))

    r = client.post(_url(empresa, "ahora"), headers=headers)

    assert r.status_code == 200, r.text
    assert _config(db, empresa)["proxima_corrida"] <= datetime.now(timezone.utc) + timedelta(seconds=1)
    assert empresa in worker.empresas_elegibles(datetime.now(timezone.utc))
    evento = _auditoria(db, empresa, "sync_ahora")
    assert len(evento) == 1 and str(evento[0]["usuario_id"]) == _usuario_id(db)


def test_ahora_esta_limitado_a_cinco_por_minuto(entorno):
    db, client, headers, empresa = entorno
    codigos = [client.post(_url(empresa, "ahora"), headers=headers).status_code for _ in range(7)]
    assert 429 in codigos


# ─── borrar la e.firma ───────────────────────────────────────────────────────

def test_borrar_la_efirma_desactiva_la_automatizacion_y_audita(entorno, monkeypatch):
    from backend import fiel_store

    db, client, headers, empresa = entorno
    assert _activar(entorno).status_code == 200
    monkeypatch.setattr(fiel_store, "eliminar_fiel", lambda db_, eid: True)

    r = client.delete(f"/api/v1/sat/empresas/{empresa}/fiel", headers=headers)

    assert r.status_code == 200 and r.json() == {"eliminada": True}
    cfg = _config(db, empresa)
    assert cfg["activa"] is False and cfg["estado"] == "inactiva"
    evento = _auditoria(db, empresa, "sync_desactivada")
    assert len(evento) == 1 and evento[0]["metadata"]["motivo"] == "e.firma eliminada"


def test_borrar_la_efirma_sin_automatizacion_no_falla(entorno, monkeypatch):
    from backend import fiel_store

    db, client, headers, empresa = entorno
    monkeypatch.setattr(fiel_store, "eliminar_fiel", lambda db_, eid: False)
    r = client.delete(f"/api/v1/sat/empresas/{empresa}/fiel", headers=headers)
    assert r.status_code == 200 and r.json() == {"eliminada": False}
    assert _auditoria(db, empresa, "sync_desactivada") == []


# ─── acceso ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("metodo,ruta,cuerpo", [
    ("get", "estado", None),
    ("put", "config", {"activa": True, "consentimiento": True}),
    ("post", "ahora", None),
])
def test_un_usuario_sin_acceso_a_la_empresa_recibe_403(entorno, metodo, ruta, cuerpo):
    db, client, _h, empresa = entorno
    db.execute("DELETE FROM usuarios WHERE email = %s", (EMAIL_AJENO,))
    ajeno = headers_usuario_e2e(db, EMAIL_AJENO)

    r = client.request(metodo, _url(empresa, ruta), headers=ajeno, **({"json": cuerpo} if cuerpo else {}))

    assert r.status_code == 403
    assert _config(db, empresa) is None


@pytest.mark.parametrize("metodo,ruta", [("get", "estado"), ("put", "config"), ("post", "ahora")])
def test_sin_sesion_recibe_401(entorno, metodo, ruta):
    _db, client, _h, empresa = entorno
    assert client.request(metodo, _url(empresa, ruta)).status_code == 401


def test_estado_informa_las_ventanas_de_cancelados_que_fallaron_en_la_ultima_corrida(entorno):
    from backend import sat_sync

    db, _client, _headers, empresa = entorno
    assert _activar(entorno).status_code == 200
    assert _estado(entorno)["cancelados_fallidas"] == 0
    sat_sync._auditar(empresa, "sync_corrida_fin", resultado="al_dia", cancelados_fallidas=2)
    assert _estado(entorno)["cancelados_fallidas"] == 2
    sat_sync._auditar(empresa, "sync_corrida_fin", resultado="al_dia", cancelados_fallidas=0)
    assert _estado(entorno)["cancelados_fallidas"] == 0          # manda la última corrida
