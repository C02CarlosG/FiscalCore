from datetime import date
from decimal import Decimal

from backend.deducciones import deducciones_periodo

RFC = "COP010101AAA"       # empresa (receptora de las deducciones)
PROV = "PROV010101AAA"     # proveedor (emisor)

ENERO = (date(2026, 1, 1), date(2026, 2, 1))
ENE_FEB = (date(2026, 1, 1), date(2026, 3, 1))


def _cfdi(**kw):
    base = {
        "uuid": "U1",
        "tipo_comprobante": "I",
        "metodo_pago": "PUE",
        "estado": "vigente",
        "es_anticipo_sat": False,
        "uso_cfdi": "G03",
        "rfc_emisor": PROV,
        "rfc_receptor": RFC,           # por defecto la empresa es receptora (gasto)
        "forma_pago": "03",
        "fecha_emision": "2026-01-15",
        "subtotal": Decimal("0"),
        "total": Decimal("0"),
    }
    base.update(kw)
    return base


def _pago(cfdi_uuid, importe, fecha):
    return {"cfdi_uuid": cfdi_uuid, "importe_pagado": Decimal(importe), "fecha_pago": fecha}


def test_gasto_pue_se_deduce():
    cfdis = [_cfdi(subtotal=Decimal("20000"), total=Decimal("20000"))]
    res = deducciones_periodo(cfdis, [], RFC, *ENERO)
    assert res["gasto"] == Decimal("20000.00")
    assert res["total_deducible"] == Decimal("20000.00")


def test_costo_identificado_no_se_suma_al_deducible():
    cfdis = [_cfdi(uso_cfdi="G01", subtotal=Decimal("80000"), total=Decimal("80000"))]
    res = deducciones_periodo(cfdis, [], RFC, *ENERO)
    assert res["costo_identificado"] == Decimal("80000.00")
    assert res["total_deducible"] == Decimal("0.00")


def test_inversion_identificada_no_se_suma_al_deducible():
    cfdis = [_cfdi(uso_cfdi="I04", subtotal=Decimal("18000"), total=Decimal("18000"))]
    res = deducciones_periodo(cfdis, [], RFC, *ENERO)
    assert res["inversion_identificada"] == Decimal("18000.00")
    assert res["total_deducible"] == Decimal("0.00")


def test_nota_de_credito_resta_del_gasto():
    cfdis = [
        _cfdi(uuid="I1", subtotal=Decimal("20000"), total=Decimal("20000")),
        _cfdi(uuid="E1", tipo_comprobante="E", subtotal=Decimal("2000"), total=Decimal("2000")),
    ]
    res = deducciones_periodo(cfdis, [], RFC, *ENERO)
    assert res["gasto"] == Decimal("18000.00")


def test_efectivo_mayor_2000_se_excluye():
    cfdis = [_cfdi(forma_pago="01", subtotal=Decimal("3000"), total=Decimal("3000"))]
    res = deducciones_periodo(cfdis, [], RFC, *ENERO)
    assert res["excluido_efectivo"] == Decimal("3000.00")
    assert res["gasto"] == Decimal("0.00")


def test_ppd_pagado_en_periodo_se_deduce_proporcional():
    cfdis = [_cfdi(uuid="P1", metodo_pago="PPD", subtotal=Decimal("10000"), total=Decimal("11600"))]
    pagos = [_pago("P1", "5800", "2026-01-20")]
    res = deducciones_periodo(cfdis, pagos, RFC, *ENERO)
    assert res["gasto"] == Decimal("5000.00")


def test_ppd_sin_rep_no_cuenta():
    cfdis = [_cfdi(uuid="P1", metodo_pago="PPD", subtotal=Decimal("10000"), total=Decimal("11600"))]
    res = deducciones_periodo(cfdis, [], RFC, *ENERO)
    assert res["gasto"] == Decimal("0.00")


def test_cfdi_emitido_no_es_deduccion():
    cfdis = [_cfdi(rfc_emisor=RFC, rfc_receptor="XAXX010101000", subtotal=Decimal("20000"), total=Decimal("20000"))]
    res = deducciones_periodo(cfdis, [], RFC, *ENERO)
    assert res["gasto"] == Decimal("0.00")


def test_cfdi_cancelado_se_excluye():
    cfdis = [_cfdi(estado="cancelado", subtotal=Decimal("20000"), total=Decimal("20000"))]
    res = deducciones_periodo(cfdis, [], RFC, *ENERO)
    assert res["gasto"] == Decimal("0.00")


def test_anticipo_sat_se_excluye():
    cfdis = [_cfdi(es_anticipo_sat=True, subtotal=Decimal("20000"), total=Decimal("20000"))]
    res = deducciones_periodo(cfdis, [], RFC, *ENERO)
    assert res["gasto"] == Decimal("0.00")


def test_uso_cfdi_desconocido_cae_en_gasto():
    cfdis = [_cfdi(uso_cfdi=None, subtotal=Decimal("5000"), total=Decimal("5000"))]
    res = deducciones_periodo(cfdis, [], RFC, *ENERO)
    assert res["gasto"] == Decimal("5000.00")


def test_caso_a_ferreteria_enero():
    cfdis = [
        _cfdi(uuid="RENTA", subtotal=Decimal("20000"), total=Decimal("20000")),
        _cfdi(uuid="HON", metodo_pago="PPD", subtotal=Decimal("15000"), total=Decimal("15000")),
        _cfdi(uuid="NC-RENTA", tipo_comprobante="E", subtotal=Decimal("2000"), total=Decimal("2000")),
        _cfdi(uuid="PAPEL", forma_pago="01", subtotal=Decimal("3000"), total=Decimal("3000")),
        _cfdi(uuid="MERCANCIA", uso_cfdi="G01", subtotal=Decimal("80000"), total=Decimal("80000")),
        _cfdi(uuid="EQUIPO", uso_cfdi="I04", subtotal=Decimal("18000"), total=Decimal("18000")),
    ]
    pagos = [_pago("HON", "15000", "2026-01-20")]
    res = deducciones_periodo(cfdis, pagos, RFC, *ENERO)
    assert res["gasto"] == Decimal("33000.00")
    assert res["costo_identificado"] == Decimal("80000.00")
    assert res["inversion_identificada"] == Decimal("18000.00")
    assert res["excluido_efectivo"] == Decimal("3000.00")
    assert res["total_deducible"] == Decimal("33000.00")


def test_caso_b_acumulado_ejercicio():
    cfdis = [
        _cfdi(uuid="RENTA", subtotal=Decimal("20000"), total=Decimal("20000")),
        _cfdi(uuid="HON", metodo_pago="PPD", subtotal=Decimal("15000"), total=Decimal("15000")),
        _cfdi(uuid="NC-RENTA", tipo_comprobante="E", subtotal=Decimal("2000"), total=Decimal("2000")),
        _cfdi(uuid="MERCANCIA-ENE", uso_cfdi="G01", subtotal=Decimal("80000"), total=Decimal("80000")),
        _cfdi(uuid="MERCANCIA-FEB", uso_cfdi="G01", fecha_emision="2026-02-10",
              subtotal=Decimal("40000"), total=Decimal("40000")),
        _cfdi(uuid="SERVICIOS-FEB", fecha_emision="2026-02-10", subtotal=Decimal("10000"), total=Decimal("10000")),
    ]
    pagos = [_pago("HON", "15000", "2026-01-20")]
    res = deducciones_periodo(cfdis, pagos, RFC, *ENE_FEB)
    assert res["gasto"] == Decimal("43000.00")
    assert res["costo_identificado"] == Decimal("120000.00")
    assert res["total_deducible"] == Decimal("43000.00")
