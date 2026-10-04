"""marcar_cancelados: los CFDI que el SAT reporta cancelados dejan de contar como vigentes. Postgres real."""
import uuid as _uuid
from datetime import datetime

import pytest

from backend.sat_fiel import MetadataCFDI
from backend.tests.conftest import db_disponible

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


def _uuid_nuevo() -> str:
    return str(_uuid.uuid4()).upper()


def _meta(uuid, estatus="cancelado", fecha=datetime(2026, 9, 20, 9, 30), efecto="I"):
    return MetadataCFDI(uuid, "AAA010101AAA", "BBB020202BBB", efecto, estatus, fecha if estatus == "cancelado" else None)


def _crear_empresa(db, nombre):
    rfc = "CAN010101" + _uuid.uuid4().hex[:3].upper()
    return str(db.execute("INSERT INTO empresas (rfc, razon_social) VALUES (%s, %s) RETURNING id",
                          (rfc, nombre), returning=True)["id"]), rfc


def _cfdi(db, empresa_id, rfc, uuid, **kw):
    v = dict(
        uuid=uuid, tipo_comprobante="I", serie="A", folio="1", rfc_emisor=rfc, nombre_emisor="Emisora",
        rfc_receptor="XAXX010101000", nombre_receptor="CLIENTE", fecha_emision="2026-09-10", subtotal="100",
        descuento="0", iva_trasladado="16", iva_retenido="0", isr_retenido="0", total="116", estado="vigente",
        metodo_pago="PUE", forma_pago="03", uso_cfdi="G03", moneda="MXN", tipo_cambio="1", monto_cobrado="0",
        cfdi_relacionados="[]",
    )
    v.update(kw)
    db.execute(f"INSERT INTO cfdi (empresa_id, {', '.join(v)}) VALUES (%s, {', '.join(['%s'] * len(v))})",
               (empresa_id, *v.values()))


@pytest.fixture()
def empresa():
    from backend import db

    db.init_db()
    emp, rfc = _crear_empresa(db, "Cancelados")
    yield db, emp, rfc
    db.execute("DELETE FROM cfdi WHERE empresa_id=%s", (emp,))
    db.execute("DELETE FROM empresas WHERE id=%s", (emp,))


def _estado(db, emp, uuid):
    return db.query_one("SELECT estado, monto_cobrado, estado_pago FROM cfdi WHERE empresa_id=%s AND uuid=%s", (emp, uuid))


def _eventos(db, emp):
    return db.query_all("SELECT * FROM auditoria WHERE empresa_id=%s AND accion='cfdi_cancelado_posterior'", (emp,))


def test_un_vigente_que_viene_cancelado_pasa_a_cancelado_y_deja_evento(empresa):
    from backend import sat_sync

    db, emp, rfc = empresa
    u = _uuid_nuevo()
    _cfdi(db, emp, rfc, u, tipo_comprobante="E")

    n = sat_sync.marcar_cancelados(emp, [_meta(u, efecto="E")])

    assert n == 1
    assert _estado(db, emp, u)["estado"] == "cancelado"
    [evento] = _eventos(db, emp)
    assert evento["usuario_id"] is None and evento["entidad"] == "cfdi" and evento["entidad_id"] == u
    meta = evento["metadata"]
    assert meta["uuid"] == u and meta["tipo_comprobante"] == "E" and meta["periodo"] == "2026-09"
    assert meta["fecha_emision"] == "2026-09-10" and meta["fecha_cancelacion"] == "2026-09-20T09:30:00"
    assert meta["origen"] == "automatico"


def test_un_registro_vigente_no_cambia_nada(empresa):
    from backend import sat_sync

    db, emp, rfc = empresa
    u = _uuid_nuevo()
    _cfdi(db, emp, rfc, u)
    assert sat_sync.marcar_cancelados(emp, [_meta(u, "vigente")]) == 0
    assert _estado(db, emp, u)["estado"] == "vigente" and _eventos(db, emp) == []


def test_un_uuid_que_no_existe_no_crea_nada_ni_falla(empresa):
    from backend import sat_sync

    db, emp, rfc = empresa
    assert sat_sync.marcar_cancelados(emp, [_meta(_uuid_nuevo())]) == 0
    assert db.query_one("SELECT COUNT(*) AS n FROM cfdi WHERE empresa_id=%s", (emp,))["n"] == 0


def test_no_toca_el_cfdi_de_otra_empresa_con_el_mismo_uuid(empresa):
    from backend import sat_sync

    db, emp, rfc = empresa
    otra, rfc_otra = _crear_empresa(db, "Otra")
    u = _uuid_nuevo()
    _cfdi(db, emp, rfc, u)
    try:
        # el UUID es único global (decisión conocida, M4): se prueba con otro CFDI de la otra empresa
        u_ajeno = _uuid_nuevo()
        _cfdi(db, otra, rfc_otra, u_ajeno)
        assert sat_sync.marcar_cancelados(emp, [_meta(u_ajeno)]) == 0
        assert _estado(db, otra, u_ajeno)["estado"] == "vigente"
    finally:
        db.execute("DELETE FROM cfdi WHERE empresa_id=%s", (otra,))
        db.execute("DELETE FROM empresas WHERE id=%s", (otra,))


def test_aplicarlo_dos_veces_no_duplica_eventos(empresa):
    from backend import sat_sync

    db, emp, rfc = empresa
    u = _uuid_nuevo()
    _cfdi(db, emp, rfc, u)
    assert sat_sync.marcar_cancelados(emp, [_meta(u)]) == 1
    assert sat_sync.marcar_cancelados(emp, [_meta(u)]) == 0
    assert len(_eventos(db, emp)) == 1


def test_un_cfdi_sustituido_o_ya_cancelado_no_se_toca(empresa):
    from backend import sat_sync

    db, emp, rfc = empresa
    sust, canc = _uuid_nuevo(), _uuid_nuevo()
    _cfdi(db, emp, rfc, sust, estado="sustituido")
    _cfdi(db, emp, rfc, canc, estado="cancelado")
    assert sat_sync.marcar_cancelados(emp, [_meta(sust), _meta(canc)]) == 0
    assert _estado(db, emp, sust)["estado"] == "sustituido"
    assert _eventos(db, emp) == []


def test_un_cfdi_vigente_nunca_se_crea_ni_se_des_cancela(empresa):
    from backend import sat_sync

    db, emp, rfc = empresa
    canc = _uuid_nuevo()
    _cfdi(db, emp, rfc, canc, estado="cancelado")
    sat_sync.marcar_cancelados(emp, [_meta(canc, "vigente")])
    assert _estado(db, emp, canc)["estado"] == "cancelado"


def test_no_modifica_lo_cobrado_de_ninguna_factura(empresa):
    from backend import sat_sync

    db, emp, rfc = empresa
    factura, rep = _uuid_nuevo(), _uuid_nuevo()
    _cfdi(db, emp, rfc, factura, metodo_pago="PPD", monto_cobrado="116", estado_pago="pagado_total")
    _cfdi(db, emp, rfc, rep, tipo_comprobante="P", total="0", subtotal="0", iva_trasladado="0")

    sat_sync.marcar_cancelados(emp, [_meta(rep, efecto="P")])

    assert _estado(db, emp, rep)["estado"] == "cancelado"
    f = _estado(db, emp, factura)
    assert float(f["monto_cobrado"]) == 116.0 and f["estado_pago"] == "pagado_total"   # sin recálculo silencioso


def test_muchos_registros_no_hacen_una_lectura_por_fila(empresa, monkeypatch):
    from backend import db as dbm, sat_sync

    db, emp, rfc = empresa
    uuids = [_uuid_nuevo() for _ in range(300)]
    for u in uuids[:200]:
        _cfdi(db, emp, rfc, u)

    consultas = []
    original = dbm.query_all
    monkeypatch.setattr(dbm, "query_all", lambda *a, **k: consultas.append(a[0]) or original(*a, **k))
    n = sat_sync.marcar_cancelados(emp, [_meta(u) for u in uuids])

    assert n == 200
    assert len(_eventos(db, emp)) == 200
    assert len(consultas) <= 3                        # no una consulta por fila


def test_lista_vacia_no_hace_nada(empresa):
    from backend import sat_sync

    _db, emp, _rfc = empresa
    assert sat_sync.marcar_cancelados(emp, []) == 0


# ─── importar_paquetes_metadata ──────────────────────────────────────────────

ENCABEZADO = ("Uuid~RfcEmisor~NombreEmisor~RfcReceptor~NombreReceptor~RfcPac~FechaEmision~"
              "FechaCertificacionSat~Monto~EfectoComprobante~Estatus~FechaCancelacion")


def _txt(*uuids, estatus="0"):
    filas = [f"{u}~AAA010101AAA~E~BBB020202BBB~R~PAC010101AAA~2026-09-10T10:00:00~2026-09-10T10:01:00~116~I~{estatus}~2026-09-20T09:30:00"
             for u in uuids]
    return ("\n".join([ENCABEZADO, *filas]) + "\n").encode()


def _solicitud(db, emp):
    return str(db.execute(
        "INSERT INTO sat_solicitudes (empresa_id, tipo, periodo_inicio, periodo_fin, estado, origen, tipo_solicitud, "
        "estado_comprobante, fecha_inicio, fecha_fin, id_solicitud_sat, num_paquetes) "
        "VALUES (%s,'emitidos','2026-09','2026-09','terminado','cancelados','Metadata','Cancelado',"
        "'2026-09-01','2026-09-30','SAT-M', 2) RETURNING id", (emp,), returning=True)["id"])


def _fila(db, sol):
    return db.query_one("SELECT estado, error_msg, paquetes_descargados, cfdi_importados FROM sat_solicitudes WHERE id=%s", (sol,))


def _importar(emp, sol, paquetes, desde=0):
    from backend import sat_sync

    return sat_sync.importar_paquetes_metadata(
        object(), solicitud_id=sol, empresa_id=emp, periodo="2026-09", paquetes=paquetes, desde=desde)


def test_importa_los_paquetes_marca_los_cfdi_y_cuenta_los_cancelados(empresa, monkeypatch):
    from backend import sat_sync

    db, emp, rfc = empresa
    a, b, c = _uuid_nuevo(), _uuid_nuevo(), _uuid_nuevo()
    for u in (a, b, c):
        _cfdi(db, emp, rfc, u)
    paquetes = {"p1": [_txt(a, b)], "p2": [_txt(c)]}
    monkeypatch.setattr(sat_sync, "descargar_paquete", lambda creds, pid, extensiones=(".xml",): paquetes[pid])
    sol = _solicitud(db, emp)

    assert _importar(emp, sol, ["p1", "p2"]) == "descargado"

    assert _fila(db, sol) == {"estado": "descargado", "error_msg": None, "paquetes_descargados": 2, "cfdi_importados": 3}
    assert all(_estado(db, emp, u)["estado"] == "cancelado" for u in (a, b, c))


def test_retoma_desde_el_paquete_indicado(empresa, monkeypatch):
    from backend import sat_sync

    db, emp, rfc = empresa
    a, c = _uuid_nuevo(), _uuid_nuevo()
    _cfdi(db, emp, rfc, a)
    _cfdi(db, emp, rfc, c)
    bajados = []
    monkeypatch.setattr(sat_sync, "descargar_paquete",
                        lambda creds, pid, extensiones=(".xml",): bajados.append(pid) or [_txt(c)])
    sol = _solicitud(db, emp)

    _importar(emp, sol, ["p1", "p2"], desde=1)

    assert bajados == ["p2"]
    assert _estado(db, emp, a)["estado"] == "vigente" and _estado(db, emp, c)["estado"] == "cancelado"


def test_un_paquete_que_no_baja_deja_la_solicitud_para_reintentar(empresa, monkeypatch):
    from backend import sat_sync
    from backend.sat_fiel import FIELError

    db, emp, rfc = empresa

    def _falla(creds, pid, extensiones=(".xml",)):
        raise FIELError("tiempo agotado")
    monkeypatch.setattr(sat_sync, "descargar_paquete", _falla)
    sol = _solicitud(db, emp)

    assert _importar(emp, sol, ["p1"]) == "terminado"

    fila = _fila(db, sol)
    assert fila["estado"] == "terminado" and "intento 1 de 3" in fila["error_msg"] and "tiempo agotado" in fila["error_msg"]


def test_un_archivo_ilegible_deja_fallo_y_no_marca_nada_de_ese_paquete(empresa, monkeypatch):
    from backend import sat_sync

    db, emp, rfc = empresa
    a = _uuid_nuevo()
    _cfdi(db, emp, rfc, a)
    # el paquete trae un archivo válido y otro que no es de metadatos: no se marca ni el válido
    monkeypatch.setattr(sat_sync, "descargar_paquete",
                        lambda creds, pid, extensiones=(".xml",): [_txt(a), b"<html>error</html>"])
    sol = _solicitud(db, emp)

    assert _importar(emp, sol, ["p1"]) == "fallo"

    fila = _fila(db, sol)
    assert fila["estado"] == "fallo" and "Metadatos ilegibles en el paquete 1 de 1" in fila["error_msg"]
    assert _estado(db, emp, a)["estado"] == "vigente" and _eventos(db, emp) == []


def test_avanzar_solicitud_de_metadatos_usa_la_importacion_de_metadatos(empresa, monkeypatch):
    """Una solicitud Metadata nunca pasa por el parser de XML ni por el pipeline."""
    from backend import sat_sync

    db, emp, rfc = empresa
    a = _uuid_nuevo()
    _cfdi(db, emp, rfc, a)
    sol = str(db.execute(
        "INSERT INTO sat_solicitudes (empresa_id, tipo, periodo_inicio, periodo_fin, estado, origen, tipo_solicitud, "
        "estado_comprobante, fecha_inicio, fecha_fin, id_solicitud_sat) "
        "VALUES (%s,'emitidos','2026-09','2026-09','solicitado','cancelados','Metadata','Cancelado',"
        "'2026-09-01','2026-09-30','SAT-M') RETURNING id", (emp,), returning=True)["id"])
    monkeypatch.setattr(sat_sync, "verificar_solicitud",
                        lambda creds, id_sat: {"estado": 3, "num_cfdi": 1, "id_paquetes": ["p1"]})
    monkeypatch.setattr(sat_sync, "descargar_paquete", lambda creds, pid, extensiones=(".xml",): [_txt(a)])
    monkeypatch.setattr(sat_sync, "importar_paquetes", lambda **kw: pytest.fail("no debe usar la importación de XML"))

    fila = db.query_one("SELECT * FROM sat_solicitudes WHERE id=%s", (sol,))
    assert sat_sync.avanzar_solicitud(object(), fila) == "descargado"
    assert _estado(db, emp, a)["estado"] == "cancelado"
