from decimal import Decimal

from backend.iva import (
    aplicar_prorrateo,
    factor_prorrateo,
    iva_acreditable,
    iva_trasladado,
)

RFC = "COP010101AAA"
PROV = "PROV010101AAA"


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


# ── IVA acreditable (gastos recibidos y pagados) ──────────────────────────


def _gasto(**kw):
    """CFDI donde la empresa es la RECEPTORA (gasto)."""
    kw.setdefault("rfc_emisor", PROV)
    kw.setdefault("rfc_receptor", RFC)
    kw.setdefault("uuid", "G1")
    return _cfdi(**kw)


def test_pue_recibido_suma_acreditable():
    # Caso B (consultora): 6 gastos PUE, IVA total $736
    ivas = ["320", "80", "80", "96", "80", "80"]
    cfdis = [_gasto(uuid=f"G{i}", forma_pago="03", total=Decimal("1000"),
                    iva_trasladado=Decimal(v)) for i, v in enumerate(ivas)]
    res = iva_acreditable(cfdis, [], "2026-01", RFC)
    assert res["bruto"] == Decimal("736.00")


def test_caso_coplasur_acreditable():
    # Caso A: IVA acreditable $3,056,596
    cfdis = [_gasto(forma_pago="03", total=Decimal("22160324"),
                    iva_trasladado=Decimal("3056596"))]
    res = iva_acreditable(cfdis, [], "2026-01", RFC)
    assert res["bruto"] == Decimal("3056596.00")


def test_ppd_recibido_prorratea_iva():
    cfdis = [_gasto(uuid="GP1", metodo_pago="PPD", forma_pago="03",
                    total=Decimal("11600"), iva_trasladado=Decimal("1600"))]
    pagos = [_pago("GP1", "5800", "2026-01-20")]
    res = iva_acreditable(cfdis, pagos, "2026-01", RFC)
    assert res["ppd"]["iva"] == Decimal("800.00")
    assert res["bruto"] == Decimal("800.00")


def test_efectivo_mayor_2000_no_es_acreditable():
    # forma_pago '01' = efectivo, total > $2,000 -> no acreditable
    cfdis = [_gasto(forma_pago="01", total=Decimal("3000"), iva_trasladado=Decimal("400"))]
    res = iva_acreditable(cfdis, [], "2026-01", RFC)
    assert res["bruto"] == Decimal("0.00")
    assert res["excluido_efectivo"]["iva"] == Decimal("400.00")


def test_efectivo_menor_o_igual_2000_si_es_acreditable():
    cfdis = [_gasto(forma_pago="01", total=Decimal("1500"), iva_trasladado=Decimal("200"))]
    res = iva_acreditable(cfdis, [], "2026-01", RFC)
    assert res["bruto"] == Decimal("200.00")


def test_cfdi_emitido_no_es_acreditable():
    # La empresa es emisora -> es venta, no gasto
    cfdis = [_cfdi(forma_pago="03", iva_trasladado=Decimal("1600"))]
    res = iva_acreditable(cfdis, [], "2026-01", RFC)
    assert res["bruto"] == Decimal("0.00")


def test_gasto_cancelado_excluido():
    cfdis = [_gasto(estado="cancelado", forma_pago="03", iva_trasladado=Decimal("400"))]
    res = iva_acreditable(cfdis, [], "2026-01", RFC)
    assert res["bruto"] == Decimal("0.00")


def test_nota_de_credito_recibida_resta_acreditable():
    # Un proveedor emite factura (IVA $100) y luego una nota de crédito tipo E ($30)
    cfdis = [
        _gasto(uuid="G1", forma_pago="03", iva_trasladado=Decimal("100")),
        _gasto(uuid="E1", tipo_comprobante="E", forma_pago="03", iva_trasladado=Decimal("30")),
    ]
    res = iva_acreditable(cfdis, [], "2026-01", RFC)
    assert res["notas_credito"]["iva"] == Decimal("30.00")
    assert res["bruto"] == Decimal("70.00")


def test_anticipo_sat_recibido_se_excluye_de_acreditable():
    # Regresión: un anticipo SAT recibido no debe acreditarse (se acredita al
    # llegar la factura final que lo aplica). Antes del fix, este anticipo se
    # sumaba dos veces: una al recibirlo, otra al recibir la factura final.
    cfdis = [
        _gasto(uuid="A1", es_anticipo_sat=True, forma_pago="03", iva_trasladado=Decimal("1600")),
        _gasto(uuid="G1", forma_pago="03", total=Decimal("11600"), iva_trasladado=Decimal("1600")),
    ]
    res = iva_acreditable(cfdis, [], "2026-01", RFC)
    assert res["bruto"] == Decimal("1600.00")


# ── Prorrateo (Art. 5-V LIVA) ─────────────────────────────────────────────


def test_factor_prorrateo_gravados_exentos():
    assert factor_prorrateo(Decimal("800000"), Decimal("200000")) == Decimal("0.800000")


def test_factor_prorrateo_sin_actividad_devuelve_uno():
    assert factor_prorrateo(Decimal("0"), Decimal("0")) == Decimal("1.000000")


def test_aplicar_prorrateo_reduce_por_factor():
    assert aplicar_prorrateo(Decimal("1000"), Decimal("0.8")) == Decimal("800.00")


def test_aplicar_prorrateo_factor_uno_no_cambia():
    assert aplicar_prorrateo(Decimal("3056596"), Decimal("1")) == Decimal("3056596.00")
