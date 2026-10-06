"""procesar_empresa: una vuelta del worker sobre una empresa. Postgres real; SAT y e.firma simulados."""
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from backend.tests.conftest import db_disponible

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


@pytest.fixture()
def entorno(monkeypatch):
    """Empresa con config activa lista para una corrida, y un SAT simulado que acepta todo."""
    from backend import db, fiel_store, sat_sync

    db.init_db()
    rfc = ("P" + uuid.uuid4().hex[:11]).upper()
    empresa = str(db.execute(
        "INSERT INTO empresas (rfc, razon_social) VALUES (%s, 'Empresa worker') RETURNING id",
        (rfc,), returning=True)["id"])
    db.execute("INSERT INTO sat_sync_config (empresa_id, activa, estado) VALUES (%s, TRUE, 'sincronizando')", (empresa,))

    class _Sat:
        def __init__(self):
            self.pedidas = []            # (tipo, inicio, fin)
            self.parametros = []         # kwargs de cada solicitud (tipo_solicitud, estado_comprobante)
            self.en_vuelo_al_pedir = []  # solicitudes activas de la empresa en cada llamada
            self.rechazos = {}           # (tipo, inicio) -> excepción a lanzar
            self.verificaciones = {}     # id_sat -> resultado de verificar_solicitud
            self.tope_dias = None        # el SAT rechaza (5003) ventanas de más de tantos días
            self.respuesta_defecto = {"estado": 3, "num_cfdi": 0, "id_paquetes": []}  # terminada, sin CFDI
            self.n = 0

    sat = _Sat()

    def _solicitar(creds, rfc_, tipo, inicio, fin, **kw):
        sat.pedidas.append((tipo, inicio, fin))
        sat.parametros.append(kw)
        sat.en_vuelo_al_pedir.append(db.query_one(
            "SELECT COUNT(*) AS n FROM sat_solicitudes WHERE empresa_id=%s AND estado IN "
            "('solicitado','en_proceso','terminado')", (empresa,))["n"])
        if (tipo, inicio) in sat.rechazos:
            raise sat.rechazos[(tipo, inicio)]
        if sat.tope_dias and (fin - inicio).days + 1 > sat.tope_dias:
            from backend.sat_fiel import SolicitudRechazada
            raise SolicitudRechazada("tope", codigo="5003")
        sat.n += 1
        return f"SAT-{sat.n}"

    def _verificar(creds, id_sat):
        return sat.verificaciones.get(id_sat, sat.respuesta_defecto)

    monkeypatch.setattr(sat_sync, "solicitar_descarga", _solicitar)
    monkeypatch.setattr(sat_sync, "verificar_solicitud", _verificar)
    monkeypatch.setattr(sat_sync, "ESPERA_VERIFICACION_SEG", 0)
    # paquetes de metadatos vacíos (sin cancelaciones): lo de cancelados se prueba en test_sat_sync_cancelados
    monkeypatch.setattr(sat_sync, "descargar_paquete", lambda creds, id_paq, extensiones=(".xml",): [])
    monkeypatch.setattr(fiel_store, "estado_fiel", lambda db_, eid: {"tiene_fiel": True, "vencida": False})
    monkeypatch.setattr(fiel_store, "obtener_signer", lambda db_, eid: object())
    monkeypatch.setenv("SAT_SYNC_MAX_EN_VUELO", "3")

    yield db, empresa, sat
    db.execute("DELETE FROM empresas WHERE id=%s", (empresa,))


def _cfg(db, empresa):
    return db.query_one("SELECT * FROM sat_sync_config WHERE empresa_id=%s", (empresa,))


def _correr_hasta_terminar(empresa, ahora=None, tope=40):
    from backend import sat_sync

    resultado = None
    for _ in range(tope):
        resultado = sat_sync.procesar_empresa(empresa, ahora=ahora)
        if resultado != "sincronizando":
            return resultado
    raise AssertionError("la corrida no terminó")


def _eventos(db, empresa, accion):
    return db.query_all("SELECT * FROM auditoria WHERE empresa_id=%s AND accion=%s", (empresa, accion))


# ─── omitir ──────────────────────────────────────────────────────────────────

def test_empresa_inactiva_se_omite_sin_tocar_la_efirma_ni_el_sat(entorno, monkeypatch):
    from backend import fiel_store, sat_sync

    db, empresa, sat = entorno
    db.execute("UPDATE sat_sync_config SET activa=FALSE WHERE empresa_id=%s", (empresa,))

    def _no_debe_llamarse(*a, **k):
        raise AssertionError("no debe tocar la e.firma de una empresa inactiva")
    monkeypatch.setattr(fiel_store, "estado_fiel", _no_debe_llamarse)
    monkeypatch.setattr(fiel_store, "obtener_signer", _no_debe_llamarse)

    assert sat_sync.procesar_empresa(empresa) == "omitida"
    assert sat.pedidas == []


def test_empresa_sin_config_se_omite(entorno):
    from backend import sat_sync

    db, empresa, sat = entorno
    db.execute("DELETE FROM sat_sync_config WHERE empresa_id=%s", (empresa,))
    assert sat_sync.procesar_empresa(empresa) == "omitida"


def test_sin_corrida_vencida_ni_pendientes_se_omite(entorno):
    from backend import sat_sync

    db, empresa, sat = entorno
    db.execute("UPDATE sat_sync_config SET estado='al_dia', proxima_corrida=NOW() + INTERVAL '5 hours' "
               "WHERE empresa_id=%s", (empresa,))
    assert sat_sync.procesar_empresa(empresa) == "omitida"
    assert sat.pedidas == []


def test_candado_ocupado_se_omite_sin_tocar_nada(entorno):
    from backend import sat_sync

    db, empresa, sat = entorno
    with sat_sync.candado_empresa(empresa) as obtenido:
        assert obtenido is True
        assert sat_sync.procesar_empresa(empresa) == "omitida"
    assert sat.pedidas == []
    assert _cfg(db, empresa)["corrida_inicio"] is None


# ─── pausa por e.firma ───────────────────────────────────────────────────────

def test_efirma_vencida_pausa_sin_llamar_al_sat_y_audita_una_sola_vez(entorno, monkeypatch):
    from backend import fiel_store, sat_sync

    db, empresa, sat = entorno
    monkeypatch.setattr(fiel_store, "estado_fiel", lambda db_, eid: {"tiene_fiel": True, "vencida": True})

    assert sat_sync.procesar_empresa(empresa) == "pausada"
    assert sat_sync.procesar_empresa(empresa) == "pausada"

    cfg = _cfg(db, empresa)
    assert (cfg["estado"], cfg["motivo_pausa"]) == ("pausada", "e.firma vencida")
    assert sat.pedidas == []
    assert len(_eventos(db, empresa, "sync_pausada")) == 1
    assert _eventos(db, empresa, "sync_pausada")[0]["usuario_id"] is None


def test_sin_efirma_guardada_pausa(entorno, monkeypatch):
    from backend import fiel_store, sat_sync

    db, empresa, sat = entorno
    monkeypatch.setattr(fiel_store, "estado_fiel", lambda db_, eid: None)
    assert sat_sync.procesar_empresa(empresa) == "pausada"
    assert _cfg(db, empresa)["motivo_pausa"] == "Sin e.firma guardada"


def test_efirma_ilegible_pausa_con_el_motivo(entorno, monkeypatch):
    from backend import fiel_store, sat_sync

    db, empresa, sat = entorno

    def _falla(db_, eid):
        raise ValueError("Error al cargar FIEL guardada: contraseña incorrecta")
    monkeypatch.setattr(fiel_store, "obtener_signer", _falla)

    assert sat_sync.procesar_empresa(empresa) == "pausada"
    assert "contraseña incorrecta" in _cfg(db, empresa)["motivo_pausa"]


def test_se_reanuda_sola_al_guardar_una_efirma_valida(entorno, monkeypatch):
    from backend import fiel_store, sat_sync

    db, empresa, sat = entorno
    monkeypatch.setattr(fiel_store, "estado_fiel", lambda db_, eid: {"tiene_fiel": True, "vencida": True})
    assert sat_sync.procesar_empresa(empresa) == "pausada"

    monkeypatch.setattr(fiel_store, "estado_fiel", lambda db_, eid: {"tiene_fiel": True, "vencida": False})
    assert _correr_hasta_terminar(empresa) == "al_dia"
    assert _cfg(db, empresa)["motivo_pausa"] is None


# ─── carga inicial ───────────────────────────────────────────────────────────

def test_carga_inicial_pide_todo_respetando_el_maximo_en_vuelo_y_queda_al_dia(entorno):
    from backend import sat_sync

    db, empresa, sat = entorno
    ahora = datetime.now(timezone.utc)

    assert _correr_hasta_terminar(empresa, ahora) == "al_dia"

    hoy = ahora.astimezone(sat_sync._ZONA_CORRIDA).date()
    meses = (hoy.year - (hoy.year - 1)) * 12 + hoy.month          # enero del año anterior .. mes en curso
    assert len(sat.pedidas) == 2 * meses
    assert max(sat.en_vuelo_al_pedir) <= 3
    filas = db.query_all("SELECT origen, estado FROM sat_solicitudes WHERE empresa_id=%s", (empresa,))
    assert {f["origen"] for f in filas} == {"inicial"} and {f["estado"] for f in filas} == {"descargado"}

    cfg = _cfg(db, empresa)
    assert cfg["estado"] == "al_dia" and cfg["carga_inicial_ok"] is True
    assert cfg["corrida_inicio"] is None
    assert abs((cfg["ultima_exitosa"] - ahora).total_seconds()) < 1
    assert cfg["proxima_corrida"] == sat_sync.proxima_corrida(ahora, "03:00")
    assert len(_eventos(db, empresa, "sync_corrida_inicio")) == 1
    fin = _eventos(db, empresa, "sync_corrida_fin")
    assert len(fin) == 1 and fin[0]["metadata"]["resultado"] == "al_dia"


def test_una_vuelta_no_pasa_del_maximo_y_deja_la_corrida_abierta(entorno):
    from backend import sat_sync

    db, empresa, sat = entorno
    # el SAT deja las solicitudes en proceso: nada se cierra y no se pueden pedir más de 3
    sat.respuesta_defecto = {"estado": 2, "num_cfdi": 0, "id_paquetes": []}

    assert sat_sync.procesar_empresa(empresa) == "sincronizando"
    assert len(sat.pedidas) == 3
    assert _cfg(db, empresa)["corrida_inicio"] is not None
    assert sat_sync.procesar_empresa(empresa) == "sincronizando"
    assert len(sat.pedidas) == 3                    # sigue en 3: no hay lugar


# ─── corrida diaria ──────────────────────────────────────────────────────────

def test_corrida_diaria_pide_desde_ultima_exitosa_menos_traslape(entorno):
    from backend import sat_sync

    db, empresa, sat = entorno
    ahora = datetime.now(timezone.utc)
    hoy = ahora.astimezone(sat_sync._ZONA_CORRIDA).date()
    db.execute(
        "UPDATE sat_sync_config SET carga_inicial_ok=TRUE, ultima_exitosa=%s, proxima_corrida=%s, estado='al_dia' "
        "WHERE empresa_id=%s", (ahora - timedelta(days=2), ahora - timedelta(minutes=1), empresa))

    assert _correr_hasta_terminar(empresa, ahora) == "al_dia"

    desde = hoy - timedelta(days=2) - timedelta(days=7)
    xml = [p for p, kw in zip(sat.pedidas, sat.parametros) if kw["tipo_solicitud"] == "CFDI"]
    assert min(i for _, i, _ in xml) >= desde
    assert {t for t, _, _ in xml} == {"emitidos", "recibidos"}
    por_origen = {(o["origen"], o["tipo_solicitud"]) for o in db.query_all(
        "SELECT origen, tipo_solicitud FROM sat_solicitudes WHERE empresa_id=%s", (empresa,))}
    assert por_origen == {("diaria", "CFDI"), ("cancelados", "Metadata")}
    assert _cfg(db, empresa)["ultima_exitosa"] > ahora - timedelta(seconds=1)


# ─── pipeline y fallas ───────────────────────────────────────────────────────

def test_pipeline_corre_una_vez_por_periodo_y_no_por_solicitud(entorno, monkeypatch):
    import backend.routers.ingesta as ingesta
    from backend import sat_sync

    db, empresa, sat = entorno
    ahora = datetime.now(timezone.utc)
    db.execute(
        "UPDATE sat_sync_config SET carga_inicial_ok=TRUE, ultima_exitosa=%s, proxima_corrida=%s WHERE empresa_id=%s",
        (ahora - timedelta(days=40), ahora - timedelta(minutes=1), empresa))   # abarca varios meses
    sat.respuesta_defecto = {"estado": 3, "num_cfdi": 5, "id_paquetes": ["p1"]}

    def _importar(creds, solicitud_id, empresa_id, periodo, paquetes, desde=0, correr_pipeline=True):
        assert correr_pipeline is False          # el worker lo pospone
        db.execute("UPDATE sat_solicitudes SET estado='descargado', cfdi_importados=5 WHERE id=%s", (solicitud_id,))
        return "descargado"
    monkeypatch.setattr(sat_sync, "importar_paquetes", _importar)
    monkeypatch.setattr(sat_sync, "importar_paquetes_metadata", _importar)
    llamadas = []
    monkeypatch.setattr(ingesta, "_correr_pipeline", lambda e, p, r: llamadas.append(p))

    assert _correr_hasta_terminar(empresa, ahora) == "al_dia"

    periodos = {f["periodo_inicio"] for f in db.query_all(
        "SELECT periodo_inicio FROM sat_solicitudes WHERE empresa_id=%s AND tipo_solicitud='CFDI'", (empresa,))}
    assert len(periodos) >= 2
    assert sorted(llamadas) == sorted(periodos)          # una vez por periodo, no por solicitud (hay 2 tipos)


def test_una_solicitud_rechazada_deja_la_corrida_en_error_sin_avanzar_ultima_exitosa(entorno):
    from backend.sat_fiel import SolicitudRechazada

    db, empresa, sat = entorno
    ahora = datetime.now(timezone.utc)
    sat.rechazos[("emitidos", date(2025, 3, 1))] = SolicitudRechazada("rechazo 5005", codigo="5005")

    assert _correr_hasta_terminar(empresa, ahora) == "error"

    cfg = _cfg(db, empresa)
    assert cfg["estado"] == "error" and cfg["ultima_exitosa"] is None and cfg["carga_inicial_ok"] is False
    assert cfg["corrida_inicio"] is None and cfg["proxima_corrida"] > ahora
    fallo = db.query_all("SELECT * FROM sat_solicitudes WHERE empresa_id=%s AND estado='fallo'", (empresa,))
    assert len(fallo) == 1 and "5005" in fallo[0]["error_msg"]


def test_replanear_tras_un_error_no_repide_los_meses_ya_descargados(entorno):
    from backend import sat_sync
    from backend.sat_fiel import SolicitudRechazada

    db, empresa, sat = entorno
    ahora = datetime.now(timezone.utc)
    sat.rechazos[("emitidos", date(2025, 3, 1))] = SolicitudRechazada("rechazo 5005", codigo="5005")
    assert _correr_hasta_terminar(empresa, ahora) == "error"
    pedidas_primera = len(sat.pedidas)

    del sat.rechazos[("emitidos", date(2025, 3, 1))]
    db.execute("UPDATE sat_sync_config SET proxima_corrida=NULL WHERE empresa_id=%s", (empresa,))
    assert _correr_hasta_terminar(empresa, ahora) == "al_dia"

    segunda = sat.pedidas[pedidas_primera:]
    cerradas = [p for p in segunda if p[2] < ahora.astimezone(sat_sync._ZONA_CORRIDA).date()]
    assert cerradas == [("emitidos", date(2025, 3, 1), date(2025, 3, 31))]   # solo la que falló
    assert _cfg(db, empresa)["carga_inicial_ok"] is True


def test_ventana_partida_por_volumen_no_cuenta_como_falla(entorno):
    from backend import sat_sync

    db, empresa, sat = entorno
    ahora = datetime.now(timezone.utc)
    sat.tope_dias = 20     # los meses de 28 a 31 días se parten en mitades

    assert _correr_hasta_terminar(empresa, ahora) == "al_dia"

    partes = db.query_all(
        "SELECT estado, error_msg FROM sat_solicitudes WHERE empresa_id=%s AND tipo='recibidos' "
        "AND fecha_inicio >= DATE '2025-01-01' AND fecha_fin <= DATE '2025-01-31'", (empresa,))
    assert sorted(p["estado"] for p in partes) == ["descargado", "descargado", "fallo"]
    assert any(sat_sync.MARCA_PARTIDA in (p["error_msg"] or "") for p in partes)


# ─── pendientes por error transitorio ────────────────────────────────────────

def test_pendiente_sin_id_se_reenvia_cuando_vence_su_proximo_intento(entorno):
    from backend import sat_sync

    db, empresa, sat = entorno
    db.execute("UPDATE sat_sync_config SET estado='al_dia', proxima_corrida=NOW() + INTERVAL '5 hours' WHERE empresa_id=%s",
               (empresa,))
    fila = db.execute(
        """INSERT INTO sat_solicitudes (empresa_id, tipo, periodo_inicio, periodo_fin, estado, origen,
                                         fecha_inicio, fecha_fin, intentos, proximo_intento)
           VALUES (%s, 'emitidos', '2026-09', '2026-09', 'pendiente', 'diaria', '2026-09-01', '2026-09-30', 1,
                   NOW() - INTERVAL '1 minute') RETURNING id""", (empresa,), returning=True)

    sat_sync.procesar_empresa(empresa)

    assert sat.pedidas == [("emitidos", date(2026, 9, 1), date(2026, 9, 30))]
    assert db.query_one("SELECT estado FROM sat_solicitudes WHERE id=%s", (str(fila["id"]),))["estado"] == "descargado"


def test_pendiente_con_proximo_intento_futuro_no_se_reenvia(entorno):
    from backend import sat_sync

    db, empresa, sat = entorno
    db.execute("UPDATE sat_sync_config SET estado='al_dia', proxima_corrida=NOW() + INTERVAL '5 hours' WHERE empresa_id=%s",
               (empresa,))
    db.execute(
        """INSERT INTO sat_solicitudes (empresa_id, tipo, periodo_inicio, periodo_fin, estado, origen,
                                         fecha_inicio, fecha_fin, intentos, proximo_intento)
           VALUES (%s, 'emitidos', '2026-09', '2026-09', 'pendiente', 'diaria', '2026-09-01', '2026-09-30', 1,
                   NOW() + INTERVAL '1 hour')""", (empresa,))

    sat_sync.procesar_empresa(empresa)
    assert sat.pedidas == []


def test_una_excepcion_inesperada_deja_la_config_consistente(entorno, monkeypatch):
    from backend import sat_sync

    db, empresa, sat = entorno

    def _revienta(*a, **k):
        raise RuntimeError("falla inesperada")
    monkeypatch.setattr(sat_sync, "solicitar_descarga", _revienta)

    with pytest.raises(RuntimeError):
        sat_sync.procesar_empresa(empresa)

    cfg = _cfg(db, empresa)
    assert cfg["estado"] == "sincronizando" and cfg["corrida_inicio"] is not None
    # el candado quedó libre: se puede volver a intentar
    with sat_sync.candado_empresa(empresa) as obtenido:
        assert obtenido is True


# ─── cancelados: qué ventanas de metadatos pide la corrida diaria ────────────

def _diaria_lista(db, empresa, ahora):
    db.execute(
        "UPDATE sat_sync_config SET carga_inicial_ok=TRUE, ultima_exitosa=%s, proxima_corrida=%s, estado='al_dia', "
        "corrida_inicio=NULL WHERE empresa_id=%s", (ahora - timedelta(days=1), ahora - timedelta(minutes=1), empresa))


def _ventanas_de_metadatos(sat, desde=0):
    return [p for p, kw in list(zip(sat.pedidas, sat.parametros))[desde:] if kw["tipo_solicitud"] == "Metadata"]


def test_la_primera_corrida_diaria_hace_el_barrido_de_cancelados_y_las_siguientes_la_ventana_reciente(entorno):
    from backend import sat_sync

    db, empresa, sat = entorno
    ahora = datetime.now(timezone.utc)
    hoy = ahora.astimezone(sat_sync._ZONA_CORRIDA).date()
    _diaria_lista(db, empresa, ahora)

    assert _correr_hasta_terminar(empresa, ahora) == "al_dia"

    # primera vez: barrido desde enero del ejercicio anterior hasta hoy, una ventana por tipo
    assert _ventanas_de_metadatos(sat) == [("emitidos", date(hoy.year - 1, 1, 1), hoy),
                                           ("recibidos", date(hoy.year - 1, 1, 1), hoy)]

    # el día siguiente: ya hubo un barrido hace menos de 7 días, así que solo el mes en curso y los 3 anteriores
    manana = ahora + timedelta(days=1)
    hoy2 = manana.astimezone(sat_sync._ZONA_CORRIDA).date()
    previas = len(sat.pedidas)
    _diaria_lista(db, empresa, manana)
    assert _correr_hasta_terminar(empresa, manana) == "al_dia"
    reciente = sat_sync._restar_meses(hoy2.replace(day=1), 3)
    assert _ventanas_de_metadatos(sat, previas) == [("emitidos", reciente, hoy2), ("recibidos", reciente, hoy2)]


def test_dos_corridas_el_mismo_dia_no_repiten_los_metadatos(entorno):
    db, empresa, sat = entorno
    ahora = datetime.now(timezone.utc)
    _diaria_lista(db, empresa, ahora)
    assert _correr_hasta_terminar(empresa, ahora) == "al_dia"
    primeras = len(_ventanas_de_metadatos(sat))
    assert primeras == 2

    _diaria_lista(db, empresa, ahora)                    # "Actualizar ahora" el mismo día
    assert _correr_hasta_terminar(empresa, ahora) == "al_dia"

    assert len(_ventanas_de_metadatos(sat)) == primeras  # no se gastó otra solicitud idéntica


def test_el_barrido_se_repite_pasados_los_dias_configurados(entorno):
    from backend import sat_sync

    db, empresa, sat = entorno
    ahora = datetime.now(timezone.utc)
    _diaria_lista(db, empresa, ahora)
    assert _correr_hasta_terminar(empresa, ahora) == "al_dia"

    db.execute("UPDATE sat_solicitudes SET created_at = NOW() - INTERVAL '8 days' WHERE empresa_id=%s", (empresa,))
    en_8_dias = ahora + timedelta(days=8)
    hoy8 = en_8_dias.astimezone(sat_sync._ZONA_CORRIDA).date()
    previas = len(sat.pedidas)
    _diaria_lista(db, empresa, en_8_dias)
    assert _correr_hasta_terminar(empresa, en_8_dias) == "al_dia"

    assert _ventanas_de_metadatos(sat, previas) == [("emitidos", date(hoy8.year - 1, 1, 1), hoy8),
                                                    ("recibidos", date(hoy8.year - 1, 1, 1), hoy8)]


def test_la_carga_inicial_no_pide_metadatos(entorno):
    db, empresa, sat = entorno
    assert _correr_hasta_terminar(empresa, datetime.now(timezone.utc)) == "al_dia"
    assert _ventanas_de_metadatos(sat) == []


def _metadato(db, empresa, tipo, inicio, fin, estado, creada="NOW()"):
    db.execute(
        "INSERT INTO sat_solicitudes (empresa_id, tipo, periodo_inicio, periodo_fin, estado, origen, tipo_solicitud, "
        f"estado_comprobante, fecha_inicio, fecha_fin, created_at) VALUES (%s,%s,'2026-01','2026-10',%s,'cancelados','Metadata',"
        f"'Cancelado',%s,%s,{creada})",
        (empresa, tipo, estado, inicio, fin))


def test_el_barrido_es_por_tipo_y_un_fallo_de_hoy_cuenta_como_pedido(entorno):
    """Si el barrido de un tipo falló, no se da por hecho el del otro; y repetir hoy los mismos
    parámetros gastaría el límite 5002, así que una solicitud fallida de hoy también cuenta."""
    from backend import sat_sync

    db, empresa, _sat = entorno
    hoy = date(2026, 10, 10)
    enero = date(hoy.year - 1, 1, 1)
    _metadato(db, empresa, "emitidos", enero, hoy - timedelta(days=2), "descargado")     # barrido bueno de emitidos
    _metadato(db, empresa, "recibidos", enero, hoy - timedelta(days=2), "fallo")         # el de recibidos falló
    _metadato(db, empresa, "recibidos", enero, hoy, "fallo")                              # y hoy ya se intentó

    barrido, de_hoy = sat_sync._estado_de_cancelados(empresa, hoy, sat_sync.ConfigSync())

    assert barrido == frozenset({"recibidos"})
    assert de_hoy == frozenset({"recibidos"})
