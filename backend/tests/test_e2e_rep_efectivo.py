"""E2E: un REP pagado en efectivo por más de $2,000 (FormaDePagoP = 01) deja la compra fuera del IVA acreditable y de las
deducciones del ISR, y ya no avisa que la forma de pago del REP se desconoce. Postgres real."""
import pytest

from backend.tests.conftest import db_disponible, headers_usuario_e2e

RFC = "REP010101E2E"
PROV = "PRO010101AAA"
EMAIL = "e2e-rep-efectivo@test.local"

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


def _uuid(n):
    return f"7E0F{n:04d}-0000-4000-8000-000000000000"


def _cfdi(db, e, n, **kw):
    v = dict(uuid=_uuid(n), tipo_comprobante="I", serie="A", folio=str(n), rfc_emisor=PROV, nombre_emisor="PROVEEDOR",
             rfc_receptor=RFC, nombre_receptor="Empresa REP", fecha_emision="2026-08-10 10:00:00", subtotal="5000",
             descuento="0", iva_trasladado="800", iva_retenido="0", isr_retenido="0", total="5800", estado="vigente",
             metodo_pago="PPD", forma_pago="99", uso_cfdi="G03", moneda="MXN", tipo_cambio="1", monto_cobrado="0",
             cfdi_relacionados="[]", es_anticipo_sat=False)
    v.update(kw)
    fila = db.execute(f"INSERT INTO cfdi (empresa_id, {', '.join(v)}) VALUES (%s, {', '.join(['%s'] * len(v))}) RETURNING id",
                      (e, *v.values()), returning=True)
    cid = str(fila["id"])
    if v["tipo_comprobante"] == "I":
        db.execute("INSERT INTO cfdi_impuestos (cfdi_id, ambito, impuesto, tipo_factor, tasa_o_cuota, base, importe)"
                   " VALUES (%s, 'traslado', '002', 'Tasa', '0.16', 5000, 800)", (cid,))
    return cid


def _rep(db, e, n, uuid_docto, forma):
    rep = _cfdi(db, e, n, tipo_comprobante="P", subtotal="0", iva_trasladado="0", total="0", metodo_pago=None,
                forma_pago=None, uso_cfdi="CP01", moneda="XXX")
    pago = db.execute(
        "INSERT INTO pagos_cfdi (empresa_id, cfdi_id, uuid_cfdi_pago, fecha_pago, monto, moneda, tipo_cambio, version_pago, forma_pago)"
        " VALUES (%s, %s, %s, '2026-09-20 12:00:00', 5800, 'MXN', 1, '2.0', %s) RETURNING id", (e, rep, _uuid(n), forma),
        returning=True)
    db.execute("INSERT INTO pagos_relaciones (pago_id, cfdi_uuid, parcialidad, importe_pagado, saldo_anterior, saldo_restante,"
               " moneda_dr, equivalencia_dr, objeto_imp_dr) VALUES (%s, %s, 1, 5800, 5800, 0, 'MXN', 1, '02')",
               (str(pago["id"]), uuid_docto))


def _limpiar(db):
    db.execute("DELETE FROM empresas WHERE rfc = %s", (RFC,))
    db.execute("DELETE FROM cfdi WHERE uuid LIKE '7E0F%%'")
    db.execute("DELETE FROM usuarios WHERE email = %s", (EMAIL,))


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
        r = client.post("/api/v1/mis-empresas", headers=headers,
                        json={"rfc": RFC, "razon_social": "Empresa REP", "regimen_fiscal": "612"})
        assert r.status_code == 201, r.text
        e = r.json()["empresa_id"]
        _cfdi(db, e, 1)                                  # compra a crédito 5,000 + IVA 800, pagada en efectivo
        _rep(db, e, 2, _uuid(1), "01")
        _cfdi(db, e, 3, uuid=_uuid(3))                    # misma compra, pagada por transferencia
        _rep(db, e, 4, _uuid(3), "03")
        yield client, headers, e
    finally:
        _limpiar(db)


def test_el_efectivo_del_rep_excluye_la_compra_del_iva_y_del_isr(entorno):
    client, headers, e = entorno

    iva = client.get(f"/api/v1/empresas/{e}/iva-flujo/2026-09", headers=headers).json()
    isr = client.get(f"/api/v1/empresas/{e}/isr-flujo/2026-09", headers=headers).json()

    # solo la pagada por transferencia cuenta: 800 de IVA y 5,000 de base
    assert iva["acreditable"]["total"]["iva"]["total"] == 800.0
    assert iva["acreditable"]["no_considerados"]["cfdi"] == 1
    assert isr["mes"]["deducciones"]["credito"] == 5000.0
    assert isr["mes"]["deducciones"]["no_considerados"]["por_motivo"]["efectivo"]["cfdi"] == 1
    assert "forma_pago_rep" not in [a["codigo"] for a in iva["advertencias"] + isr["advertencias"]]
