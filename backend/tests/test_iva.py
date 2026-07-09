from decimal import Decimal

from backend.iva import iva_trasladado

RFC = "COP010101AAA"


def _cfdi(**kw):
    base = {
        "uuid": "U1",
        "tipo_comprobante": "I",
        "metodo_pago": "PUE",
        "estado": "vigente",
        "es_anticipo_sat": False,
        "rfc_emisor": RFC,          # por defecto la empresa es emisora (venta)
        "rfc_receptor": "XAXX010101000",
        "fecha_emision": "2026-01-15",
        "subtotal": Decimal("0"),
        "total": Decimal("0"),
        "iva_trasladado": Decimal("0"),
    }
    base.update(kw)
    return base


def _pago(cfdi_uuid, importe, fecha):
    return {"cfdi_uuid": cfdi_uuid, "importe_pagado": Decimal(importe), "fecha_pago": fecha}


def test_pue_ingreso_suma_iva_trasladado():
    # Caso B (consultora): un ingreso PUE de $10,000 base, IVA $1,600
    cfdis = [_cfdi(subtotal=Decimal("10000"), total=Decimal("11600"), iva_trasladado=Decimal("1600"))]
    res = iva_trasladado(cfdis, [], "2026-01", RFC)
    assert res["pue"]["iva"] == Decimal("1600.00")
    assert res["total"] == Decimal("1600.00")


def test_caso_coplasur_traslado():
    # Caso A (Copla Sur, ene-2026): base $25,553,202, IVA $4,088,513
    cfdis = [_cfdi(subtotal=Decimal("25553202"), total=Decimal("29641715"),
                   iva_trasladado=Decimal("4088513"))]
    res = iva_trasladado(cfdis, [], "2026-01", RFC)
    assert res["total"] == Decimal("4088513.00")


def test_ppd_con_rep_en_periodo_prorratea_iva():
    # PPD total $11,600 (IVA $1,600); se cobra $5,800 (mitad) en el periodo -> IVA $800
    cfdis = [_cfdi(uuid="P1", metodo_pago="PPD", subtotal=Decimal("10000"),
                   total=Decimal("11600"), iva_trasladado=Decimal("1600"))]
    pagos = [_pago("P1", "5800", "2026-01-20")]
    res = iva_trasladado(cfdis, pagos, "2026-01", RFC)
    assert res["ppd"]["iva"] == Decimal("800.00")
    assert res["total"] == Decimal("800.00")


def test_ppd_con_rep_fuera_de_periodo_no_cuenta():
    cfdis = [_cfdi(uuid="P1", metodo_pago="PPD", total=Decimal("11600"),
                   iva_trasladado=Decimal("1600"))]
    pagos = [_pago("P1", "5800", "2026-02-05")]  # pago en febrero
    res = iva_trasladado(cfdis, pagos, "2026-01", RFC)
    assert res["total"] == Decimal("0.00")


def test_cfdi_cancelado_se_excluye():
    cfdis = [_cfdi(estado="cancelado", iva_trasladado=Decimal("1600"))]
    res = iva_trasladado(cfdis, [], "2026-01", RFC)
    assert res["total"] == Decimal("0.00")


def test_nota_de_credito_resta():
    cfdis = [
        _cfdi(uuid="I1", iva_trasladado=Decimal("1600")),
        _cfdi(uuid="E1", tipo_comprobante="E", iva_trasladado=Decimal("160")),
    ]
    res = iva_trasladado(cfdis, [], "2026-01", RFC)
    assert res["notas_credito"]["iva"] == Decimal("160.00")
    assert res["total"] == Decimal("1440.00")


def test_anticipo_sat_se_excluye():
    cfdis = [_cfdi(es_anticipo_sat=True, iva_trasladado=Decimal("1600"))]
    res = iva_trasladado(cfdis, [], "2026-01", RFC)
    assert res["total"] == Decimal("0.00")


def test_cfdi_recibido_no_es_traslado():
    # La empresa es receptora -> es un gasto, no una venta; no cuenta como trasladado
    cfdis = [_cfdi(rfc_emisor="PROV010101AAA", rfc_receptor=RFC, iva_trasladado=Decimal("1600"))]
    res = iva_trasladado(cfdis, [], "2026-01", RFC)
    assert res["total"] == Decimal("0.00")


def test_pue_fuera_de_periodo_no_cuenta():
    cfdis = [_cfdi(fecha_emision="2026-02-15", iva_trasladado=Decimal("1600"))]
    res = iva_trasladado(cfdis, [], "2026-01", RFC)
    assert res["total"] == Decimal("0.00")
