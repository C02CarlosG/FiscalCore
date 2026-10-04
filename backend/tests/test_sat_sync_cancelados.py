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
