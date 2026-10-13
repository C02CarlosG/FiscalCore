"""E2E del criterio de efectivo contra Postgres real: caso COPLASUR de octubre de 2026 (9 compras en
efectivo menores a $2,000 y una por transferencia). La diferencia entre criterios es exactamente el IVA
de las 9 compras: $1,572.66."""
from decimal import Decimal

import pytest

from backend.tests.conftest import db_disponible

RFC = "CEF010101E2E"
PROV = "PRO010101AAA"

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]

# (IVA, total) de las 9 compras en efectivo observadas en la plataforma de referencia (todas < $2,000).
EFECTIVO = [("224.13", "1655.00"), ("135.42", "1000.00"), ("203.19", "1500.39"), ("158.02", "1145.65"),
            ("240.03", "1740.20"), ("56.43", "409.14"), ("255.86", "1855.00"), ("204.76", "1484.50"),
            ("94.82", "700.00")]


def _uuid(n: int) -> str:
    return f"CEF0{n:04d}-0000-4000-8000-000000000000"


def _compra(db, empresa_id, n, iva, total, forma_pago):
    base = Decimal(total) - Decimal(iva)
    fila = db.execute(
        "INSERT INTO cfdi (empresa_id, uuid, tipo_comprobante, serie, folio, rfc_emisor, nombre_emisor, rfc_receptor,"
        " nombre_receptor, fecha_emision, subtotal, descuento, iva_trasladado, iva_retenido, isr_retenido, total, estado,"
        " metodo_pago, forma_pago, uso_cfdi, moneda, tipo_cambio, monto_cobrado, cfdi_relacionados, es_anticipo_sat)"
        " VALUES (%s, %s, 'I', 'A', %s, %s, 'PROVEEDOR', %s, 'Empresa CEF', '2026-10-02 10:00:00', %s, 0, %s, 0, 0, %s,"
        " 'vigente', 'PUE', %s, 'G03', 'MXN', 1, 0, '[]', FALSE) RETURNING id",
        (empresa_id, _uuid(n), str(n), PROV, RFC, str(base), iva, total, forma_pago), returning=True)
    db.execute("INSERT INTO cfdi_impuestos (cfdi_id, ambito, impuesto, tipo_factor, tasa_o_cuota, base, importe)"
               " VALUES (%s, 'traslado', '002', 'Tasa', 0.16, %s, %s)", (str(fila["id"]), str(base), iva))


@pytest.fixture
def empresa():
    from backend import db

    db.init_db()
    db.execute("DELETE FROM cfdi WHERE uuid LIKE 'CEF0%%'")
    db.execute("DELETE FROM empresas WHERE rfc = %s", (RFC,))
    e = str(db.execute("INSERT INTO empresas (rfc, razon_social) VALUES (%s, 'Empresa CEF') RETURNING id", (RFC,),
                       returning=True)["id"])
    for i, (iva, total) in enumerate(EFECTIVO, start=1):
        _compra(db, e, i, iva, total, "01")
    _compra(db, e, 20, "93.84", "680.34", "03")            # transferencia: siempre se acredita
    yield e
    db.execute("DELETE FROM cfdi WHERE uuid LIKE 'CEF0%%'")
    db.execute("DELETE FROM empresas WHERE id = %s", (e,))


def _acreditable(e):
    from backend import iva_flujo, iva_flujo_datos

    eventos = iva_flujo_datos.cargar_eventos(e, RFC, "2026-10", {})
    return iva_flujo.resumen(eventos, "2026-10", {})["acreditable"]["total"]["iva"]["total"]


def test_coplasur_octubre_diferencia_entre_criterios_es_1572_66(empresa):
    from backend import db

    legal = _acreditable(empresa)
    db.execute("UPDATE empresas SET criterio_efectivo = 'estricto' WHERE id = %s", (empresa,))
    estricto = _acreditable(empresa)
    assert estricto == Decimal("93.84")
    assert legal == Decimal("1666.50")
    assert legal - estricto == Decimal("1572.66")


def test_isr_deducciones_en_efectivo_siguen_el_criterio(empresa):
    from backend import db, isr_flujo, isr_flujo_datos

    def excluidos():
        evs = isr_flujo_datos.cargar_eventos(empresa, RFC, "2026-10")
        return [e for e in evs if e["lado"] == "deduccion" and isr_flujo.motivo_exclusion(e) == "efectivo"]

    assert excluidos() == []
    db.execute("UPDATE empresas SET criterio_efectivo = 'estricto' WHERE id = %s", (empresa,))
    assert len(excluidos()) == 9
