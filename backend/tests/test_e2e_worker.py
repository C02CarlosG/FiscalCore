"""Worker de descarga automática de punta a punta: reinicio, candado e idempotencia.

Postgres real y XML reales que pasan por el parser y `cfdi_store`; solo el SAT y la e.firma
están simulados.
"""
import threading
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from backend.tests.conftest import db_disponible

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


ENCABEZADO_METADATA = ("Uuid~RfcEmisor~NombreEmisor~RfcReceptor~NombreReceptor~RfcPac~FechaEmision~"
                       "FechaCertificacionSat~Monto~EfectoComprobante~Estatus~FechaCancelacion")


def _xml_ingreso(uuid_cfdi: str, rfc_emisor: str) -> bytes:
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
    Version="4.0" Fecha="2026-10-02T10:00:00" TipoDeComprobante="I" SubTotal="1000.00" Total="1160.00"
    Moneda="MXN" MetodoPago="PUE" FormaPago="03" Exportacion="01" LugarExpedicion="01000">
  <cfdi:Emisor Rfc="{rfc_emisor}" Nombre="Emisora worker" RegimenFiscal="601"/>
  <cfdi:Receptor Rfc="XAXX010101000" Nombre="Cliente" UsoCFDI="G03" DomicilioFiscalReceptor="01000" RegimenFiscalReceptor="616"/>
  <cfdi:Impuestos TotalImpuestosTrasladados="160.00"><cfdi:Traslados>
    <cfdi:Traslado Base="1000.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="160.00"/>
  </cfdi:Traslados></cfdi:Impuestos>
  <cfdi:Complemento><tfd:TimbreFiscalDigital UUID="{uuid_cfdi}" FechaTimbrado="2026-10-02T10:01:00"/></cfdi:Complemento>
</cfdi:Comprobante>'''.encode()


@pytest.fixture()
def worker(monkeypatch):
    """Empresa con carga inicial hecha (corrida diaria chica) y un SAT que entrega 2 paquetes por solicitud."""
    import backend.routers.ingesta as ingesta
    from backend import db, fiel_store, sat_sync

    db.init_db()
    rfc = "WRK010101" + uuid.uuid4().hex[:3].upper()          # RFC de persona moral con formato válido
    empresa = str(db.execute(
        "INSERT INTO empresas (rfc, razon_social) VALUES (%s, 'Empresa e2e worker') RETURNING id",
        (rfc,), returning=True)["id"])
    ahora = datetime.now(timezone.utc)
    db.execute(
        "INSERT INTO sat_sync_config (empresa_id, activa, estado, carga_inicial_ok, ultima_exitosa, proxima_corrida) "
        "VALUES (%s, TRUE, 'al_dia', TRUE, %s, %s)", (empresa, ahora - timedelta(days=1), ahora - timedelta(minutes=1)))

    class _Sat:
        def __init__(self):
            self.solicitudes = 0
            self.descargas = []                  # id de paquete en cada descarga
            self.falla_en = {}                   # id de paquete -> excepción (una sola vez)
            self.cancelar = set()                # UUID que los paquetes de metadatos reportan cancelados
            self.antes_de_solicitar = None       # gancho para simular lentitud / concurrencia
            self.pipeline = []
            self.lock = threading.Lock()

    sat = _Sat()

    def _solicitar(creds, rfc_, tipo, inicio, fin, **kw):
        if sat.antes_de_solicitar:
            sat.antes_de_solicitar()
        with sat.lock:
            sat.solicitudes += 1
            return f"{empresa}-SAT-{sat.solicitudes}"

    def _verificar(creds, id_sat):
        return {"estado": 3, "num_cfdi": 2, "id_paquetes": [f"{id_sat}-p1", f"{id_sat}-p2"]}

    def _descargar(creds, id_paquete, extensiones=(".xml",)):
        with sat.lock:
            sat.descargas.append(id_paquete)
        if id_paquete in sat.falla_en:
            raise sat.falla_en.pop(id_paquete)
        if ".txt" in extensiones:                        # paquete de metadatos
            filas = [f"{u}~AAA010101AAA~Emisora~XAXX010101000~Cliente~PAC010101AAA~2026-10-02T10:00:00~"
                     f"2026-10-02T10:01:00~1160.00~I~0~2026-10-03T08:00:00" for u in sorted(sat.cancelar)]
            return [("\n".join([ENCABEZADO_METADATA, *filas]) + "\n").encode()]
        # un CFDI distinto por paquete, estable entre descargas del mismo paquete
        uuid_cfdi = str(uuid.uuid5(uuid.NAMESPACE_URL, id_paquete)).upper()
        return [_xml_ingreso(uuid_cfdi, rfc)]

    monkeypatch.setattr(sat_sync, "solicitar_descarga", _solicitar)
    monkeypatch.setattr(sat_sync, "verificar_solicitud", _verificar)
    monkeypatch.setattr(sat_sync, "descargar_paquete", _descargar)
    monkeypatch.setattr(sat_sync, "ESPERA_VERIFICACION_SEG", 0)
    monkeypatch.setattr(fiel_store, "estado_fiel", lambda db_, eid: {"tiene_fiel": True, "vencida": False})
    monkeypatch.setattr(fiel_store, "obtener_signer", lambda db_, eid: object())
    monkeypatch.setattr(ingesta, "_correr_pipeline", lambda e, p, r: sat.pipeline.append((e, p)))

    yield db, empresa, sat, ahora
    db.execute("DELETE FROM cfdi WHERE empresa_id=%s", (empresa,))
    db.execute("DELETE FROM empresas WHERE id=%s", (empresa,))


def _num_cfdi(db, empresa):
    return db.query_one("SELECT COUNT(*) AS n FROM cfdi WHERE empresa_id=%s", (empresa,))["n"]


def _correr(empresa, ahora, tope=30):
    from backend import sat_sync

    for _ in range(tope):
        r = sat_sync.procesar_empresa(empresa, ahora=ahora)
        if r != "sincronizando":
            return r
    raise AssertionError("la corrida no terminó")


def test_corrida_completa_importa_los_cfdi_y_corre_el_pipeline_una_vez_por_periodo(worker):
    db, empresa, sat, ahora = worker

    assert _correr(empresa, ahora) == "al_dia"

    solicitudes = db.query_all("SELECT estado, cfdi_importados, tipo_solicitud FROM sat_solicitudes WHERE empresa_id=%s", (empresa,))
    assert {s["estado"] for s in solicitudes} == {"descargado"}
    assert _num_cfdi(db, empresa) == 2 * sum(1 for s in solicitudes if s["tipo_solicitud"] == "CFDI")
    periodos = {p for _, p in sat.pipeline}
    assert len(sat.pipeline) == len(periodos)             # nunca dos veces el mismo periodo
    assert {(e) for e, _ in sat.pipeline} == {empresa}


def test_un_reinicio_a_mitad_de_la_importacion_retoma_sin_duplicar(worker):
    db, empresa, sat, ahora = worker
    from backend import sat_sync

    # el proceso "muere" al bajar el segundo paquete de la primera solicitud
    sat.falla_en[f"{empresa}-SAT-1-p2"] = RuntimeError("el proceso murió")
    with pytest.raises(RuntimeError):
        sat_sync.procesar_empresa(empresa, ahora=ahora)

    parcial = db.query_one(
        "SELECT estado, paquetes_descargados, cfdi_importados FROM sat_solicitudes "
        "WHERE empresa_id=%s AND id_solicitud_sat=%s", (empresa, f"{empresa}-SAT-1"))
    assert parcial == {"estado": "terminado", "paquetes_descargados": 1, "cfdi_importados": 1}
    assert _num_cfdi(db, empresa) == 1
    assert _correr_no_cerrada(db, empresa)

    # el worker arranca de nuevo; la solicitud interrumpida se retoma pasados 10 min sin actividad
    db.execute("UPDATE sat_solicitudes SET updated_at = NOW() - INTERVAL '11 minutes' "
               "WHERE empresa_id=%s AND estado='terminado'", (empresa,))
    assert _correr(empresa, ahora) == "al_dia"

    solicitudes = db.query_all("SELECT estado, tipo_solicitud FROM sat_solicitudes WHERE empresa_id=%s", (empresa,))
    assert {s["estado"] for s in solicitudes} == {"descargado"}
    assert _num_cfdi(db, empresa) == 2 * sum(1 for s in solicitudes if s["tipo_solicitud"] == "CFDI")   # sin duplicados
    assert sat.descargas.count(f"{empresa}-SAT-1-p1") == 1                   # el paquete 1 no se bajó otra vez


def _correr_no_cerrada(db, empresa):
    cfg = db.query_one("SELECT corrida_inicio, estado FROM sat_sync_config WHERE empresa_id=%s", (empresa,))
    return cfg["corrida_inicio"] is not None and cfg["estado"] == "sincronizando"


def test_dos_workers_a_la_vez_sobre_la_misma_empresa_no_se_pisan(worker):
    db, empresa, sat, ahora = worker
    from backend import sat_sync

    dentro = threading.Event()
    soltar = threading.Event()

    def _lento():
        dentro.set()
        assert soltar.wait(timeout=10)
    sat.antes_de_solicitar = _lento

    resultados = {}
    hilo = threading.Thread(target=lambda: resultados.setdefault("primero", sat_sync.procesar_empresa(empresa, ahora=ahora)))
    hilo.start()
    assert dentro.wait(timeout=10)                 # el primero ya tiene el candado y está pidiendo al SAT

    resultados["segundo"] = sat_sync.procesar_empresa(empresa, ahora=ahora)

    soltar.set()
    hilo.join(timeout=30)
    assert resultados["segundo"] == "omitida"
    sat.antes_de_solicitar = None
    if resultados["primero"] == "sincronizando":
        resultados["primero"] = _correr(empresa, ahora)
    assert resultados["primero"] == "al_dia"

    solicitudes = db.query_one("SELECT COUNT(*) AS n FROM sat_solicitudes WHERE empresa_id=%s", (empresa,))["n"]
    de_xml = db.query_one("SELECT COUNT(*) AS n FROM sat_solicitudes WHERE empresa_id=%s AND tipo_solicitud='CFDI'",
                          (empresa,))["n"]
    assert len(sat.descargas) == len(set(sat.descargas)) == 2 * solicitudes   # cada paquete, una sola vez
    assert _num_cfdi(db, empresa) == 2 * de_xml


def test_repetir_la_corrida_con_los_mismos_paquetes_no_duplica(worker):
    db, empresa, sat, ahora = worker

    assert _correr(empresa, ahora) == "al_dia"
    primera = _num_cfdi(db, empresa)

    # otra corrida: el SAT vuelve a entregar exactamente los mismos XML
    sat.solicitudes = 0                                         # mismos ids de solicitud y de paquete
    db.execute("UPDATE sat_sync_config SET proxima_corrida = NOW() - INTERVAL '1 minute' WHERE empresa_id=%s", (empresa,))
    db.execute("DELETE FROM sat_solicitudes WHERE empresa_id=%s", (empresa,))
    assert _correr(empresa, ahora) == "al_dia"

    assert _num_cfdi(db, empresa) == primera
    assert db.query_one(
        "SELECT COUNT(*) AS n, COUNT(DISTINCT uuid) AS u FROM cfdi WHERE empresa_id=%s", (empresa,)) == {"n": primera, "u": primera}


def test_un_cfdi_cancelado_despues_de_descargarse_queda_cancelado_en_la_siguiente_corrida(worker):
    db, empresa, sat, ahora = worker

    assert _correr(empresa, ahora) == "al_dia"
    uuid_cfdi = db.query_one("SELECT uuid FROM cfdi WHERE empresa_id=%s ORDER BY uuid LIMIT 1", (empresa,))["uuid"]
    assert db.query_one("SELECT estado FROM cfdi WHERE uuid=%s", (uuid_cfdi,))["estado"] == "vigente"
    pipeline_antes = len(sat.pipeline)

    # al día siguiente el SAT reporta ese CFDI como cancelado
    sat.cancelar = {uuid_cfdi}
    db.execute("UPDATE sat_sync_config SET proxima_corrida = NOW() - INTERVAL '1 minute' WHERE empresa_id=%s", (empresa,))
    db.execute("DELETE FROM sat_solicitudes WHERE empresa_id=%s", (empresa,))
    sat.solicitudes = 0

    assert _correr(empresa, ahora) == "al_dia"

    assert db.query_one("SELECT estado FROM cfdi WHERE uuid=%s", (uuid_cfdi,))["estado"] == "cancelado"
    evento = db.query_all("SELECT * FROM auditoria WHERE empresa_id=%s AND accion='cfdi_cancelado_posterior'", (empresa,))
    assert [e["entidad_id"] for e in evento] == [uuid_cfdi]
    fin = db.query_all("SELECT metadata FROM auditoria WHERE empresa_id=%s AND accion='sync_corrida_fin' "
                       "ORDER BY creado_en DESC LIMIT 1", (empresa,))[0]["metadata"]
    assert fin["cancelados_marcados"] == 1 and fin["cancelados_fallidas"] == 0
    assert len(sat.pipeline) == pipeline_antes + len({p for _, p in sat.pipeline[pipeline_antes:]})  # sin pipeline por cancelar
    assert db.query_one("SELECT COUNT(*) AS n FROM cfdi WHERE empresa_id=%s AND estado='vigente'",
                        (empresa,))["n"] == _num_cfdi(db, empresa) - 1


def test_una_falla_en_los_metadatos_de_cancelados_no_frena_la_descarga(worker, monkeypatch):
    from backend import sat_sync

    db, empresa, sat, ahora = worker
    original = sat_sync.descargar_paquete

    def _metadatos_ilegibles(creds, id_paquete, extensiones=(".xml",)):
        if ".txt" in extensiones:
            return [b"esto no es un archivo de metadatos del SAT"]
        return original(creds, id_paquete, extensiones)
    monkeypatch.setattr(sat_sync, "descargar_paquete", _metadatos_ilegibles)

    assert _correr(empresa, ahora) == "al_dia"

    cfg = db.query_one("SELECT estado, ultima_exitosa FROM sat_sync_config WHERE empresa_id=%s", (empresa,))
    assert cfg["estado"] == "al_dia" and cfg["ultima_exitosa"] is not None
    fallos = db.query_all("SELECT error_msg FROM sat_solicitudes WHERE empresa_id=%s AND estado='fallo'", (empresa,))
    assert fallos and all("Metadatos ilegibles" in f["error_msg"] for f in fallos)
    assert _num_cfdi(db, empresa) > 0                                       # los XML sí se importaron
    fin = db.query_one("SELECT metadata FROM auditoria WHERE empresa_id=%s AND accion='sync_corrida_fin' "
                       "ORDER BY creado_en DESC LIMIT 1", (empresa,))["metadata"]
    assert fin["cancelados_fallidas"] == len(fallos) and fin["fallidas"] == 0
