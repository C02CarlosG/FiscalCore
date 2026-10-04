"""La cédula de IVA y la tabla del Inicio salen del mismo motor (``iva_flujo``): misma cifra en las tres pantallas."""
from datetime import date
from decimal import Decimal

from backend import cedula_iva
from backend import inicio
from backend import iva_flujo as f
from backend.tests.test_iva_flujo import D, RFC, _construir, doc, imp, pago, recibido, tras


def _resumen(docs, pagos=(), periodo="2026-09", factor=D("1"), ajustes=None):
    return f.resumen(_construir(docs, pagos), periodo, ajustes or {}, factor)


# ── forma de la cédula ───────────────────────────────────────────────────────

def test_cedula_conserva_la_forma_de_siempre():
    docs = [
        doc("U1", impuestos=[tras("0.16", 1000, 160), tras("0.08", 500, 40)], iva_trasladado=D("200"), subtotal=D("1500")),
        doc("P1", metodo_pago="PPD", total=D("1160")),
        doc("N1", tipo_comprobante="E", impuestos=[tras("0.16", 300, 48)], iva_trasladado=D("48")),
        recibido("R1", impuestos=[tras("0.16", 250, 40)], iva_trasladado=D("40")),
        recibido("R2", forma_pago="01", total=D("5000"), impuestos=[tras("0.16", 100, 16)], iva_trasladado=D("16")),
    ]
    c = cedula_iva.desde_motor(_resumen(docs, [pago("P1")]), D("40"))

    assert c["trasladado"]["pue"] == {"base": D("1500.00"), "iva": D("200.00")}
    assert c["trasladado"]["ppd"] == {"cobrado": D("580.00"), "iva": D("80.00")}
    assert c["trasladado"]["notas_credito"] == {"base": D("300.00"), "iva": D("48.00")}
    assert c["trasladado"]["total"] == D("232.00")
    assert c["acreditable"]["pue"] == {"base": D("250.00"), "iva": D("40.00")}
    assert c["acreditable"]["excluido_efectivo"] == {"iva": D("16.00")}
    assert c["acreditable"]["bruto"] == D("40.00") and c["acreditable"]["ajustado"] == D("40.00")
    assert c["acreditable"]["factor_prorrateo"] == D("1")
    assert c["resultado"] == {"iva_por_pagar": D("192.00"), "saldo_a_cargo": D("192.00"), "saldo_a_favor": D("0.00")}
    assert c["comparativo_sat"] == {"diot_iva_pagado": D("40"), "diferencia": D("0.00")}


def test_cedula_ahora_si_descuenta_la_retencion_que_le_hacen_a_la_empresa():
    d = doc("U1", impuestos=[tras("0.16", 1000, 160), imp("retencion", "002", "Tasa", "0.106667", 1000, "106.67")], iva_retenido=D("106.67"))
    c = cedula_iva.desde_motor(_resumen([d]), D("0"))

    assert c["iva_retenido"] == D("106.67")
    assert c["resultado"]["iva_por_pagar"] == D("53.33")


def test_cedula_trae_las_advertencias_y_las_retenciones_a_enterar():
    d = doc("U1", metodo_pago="PPD", total=D("1160"))
    c = cedula_iva.desde_motor(_resumen([d], [pago("U1", version_pago="1.0", impuestos_dr=[])]), D("0"))

    assert {a["codigo"] for a in c["advertencias"]} == {"pago_v1"}
    assert c["retenciones_a_enterar"] == D("0.00")


def test_cedula_con_factor_de_prorrateo():
    c = cedula_iva.desde_motor(_resumen([recibido("R1", impuestos=[tras("0.16", 250, 40)], iva_trasladado=D("40"))], factor=D("0.5")), D("0"))

    assert c["acreditable"]["bruto"] == D("40.00") and c["acreditable"]["ajustado"] == D("20.00")
    assert c["acreditable"]["factor_prorrateo"] == D("0.5")


def test_cedula_de_un_mes_sin_movimiento_es_ceros():
    c = cedula_iva.desde_motor(_resumen([]), D("0"))

    assert c["resultado"]["iva_por_pagar"] == D("0.00") and c["trasladado"]["total"] == D("0.00")


# ── una sola cifra en la cédula, el Inicio y la pantalla de IVA ──────────────

def test_el_inicio_toma_cada_mes_del_mismo_resumen():
    docs = [
        doc("U1", fecha_emision=date(2026, 3, 5), impuestos=[tras("0.16", 1000, 160)], iva_trasladado=D("160")),
        doc("U2", fecha_emision=date(2026, 9, 5), impuestos=[tras("0.16", 500, 80)], iva_trasladado=D("80")),
        recibido("R1", fecha_emision=date(2026, 9, 6), impuestos=[tras("0.16", 250, 40)], iva_trasladado=D("40")),
        recibido("R2", fecha_emision=date(2026, 9, 7), forma_pago="01", total=D("5000"),
                 impuestos=[tras("0.16", 100, 16)], iva_trasladado=D("16")),
    ]
    eventos = _construir(docs)

    meses = [inicio.iva_mes_desde_motor(f.resumen(eventos, m, {})) for m in inicio.meses_del_ejercicio(2026)]
    anual = inicio.componer_iva_anual(2026, meses, None)

    marzo, septiembre = anual["meses"][2], anual["meses"][8]
    assert marzo["trasladado"]["total"] == D("160.00") and septiembre["trasladado"]["total"] == D("80.00")
    assert septiembre["acreditable"]["excluido_efectivo"] == D("16.00")
    # la misma cifra que da la cédula del mes
    c = cedula_iva.desde_motor(f.resumen(eventos, "2026-09", {}), D("0"))
    assert septiembre["trasladado"]["total"] == c["trasladado"]["total"]
    assert septiembre["acreditable"]["bruto"] == c["acreditable"]["bruto"]
    assert septiembre["resultado"]["iva_por_pagar"] == c["resultado"]["iva_por_pagar"]


def test_el_inicio_incluye_las_retenciones_en_el_resultado_del_mes():
    d = doc("U1", impuestos=[tras("0.16", 1000, 160), imp("retencion", "002", "Tasa", "0.106667", 1000, "106.67")], iva_retenido=D("106.67"))
    mes = inicio.iva_mes_desde_motor(f.resumen(_construir([d]), "2026-09", {}))

    assert mes["iva_retenido"] == D("106.67")
    assert inicio.componer_iva_anual(2026, [mes], None)["meses"][8]["resultado"]["iva_por_pagar"] == D("53.33")


def test_advertencias_del_ano_suman_las_de_cada_mes_y_conservan_el_prorrateo():
    d1 = doc("U1", metodo_pago="PPD", total=D("1160"), fecha_emision=date(2026, 1, 5))
    eventos = _construir([d1], [pago("U1", version_pago="1.0", impuestos_dr=[], fecha=date(2026, 3, 5)),
                                pago("U1", version_pago="1.0", impuestos_dr=[], fecha=date(2026, 4, 5), uuid_pago="REP2")])
    resumenes = [f.resumen(eventos, m, {}) for m in inicio.meses_del_ejercicio(2026)]

    avisos = {a["codigo"]: a["cfdi"] for a in inicio.advertencias_desde_motor(resumenes)}

    assert avisos["pago_v1"] == 2                       # un CFDI con pagos en dos meses cuenta en cada mes
    assert avisos["prorrateo"] is None
    assert "retenciones" not in avisos


def test_el_anual_marca_que_ya_incluye_las_retenciones():
    anual = inicio.componer_iva_anual(2026, [], None)

    assert anual["iva_retenido_incluido"] is True
