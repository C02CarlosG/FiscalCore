"""Comparativo contra lo declarado (M5). Sin DB."""
from decimal import Decimal as D

import pytest

from backend import declaraciones as d

IVA_CALC = {"impuesto_trasladado": D("1600.00"), "impuesto_acreditable": D("500.00"), "retenciones": D("0.00"),
            "retenciones_a_terceros": D("0.00"), "saldo_a_favor_aplicado": None, "impuesto_a_cargo": D("1100.00")}


def por_clave(r):
    return {x["clave"]: x for x in r["renglones"]}


def test_sin_declaracion_muestra_lo_calculado_y_el_estado():
    r = d.comparar("iva", [], IVA_CALC)

    assert r["estado"] == "sin_declaracion" and r["pendiente_de_pago"] is None and r["declaraciones"] == 0
    assert por_clave(r)["impuesto_trasladado"]["calculado"] == D("1600.00")
    assert por_clave(r)["impuesto_trasladado"]["estado"] == "sin_captura"


def test_hasta_un_peso_de_diferencia_cuadra_y_mas_es_diferencia():
    r = d.comparar("iva", [{"impuesto_trasladado": D("1601"), "impuesto_acreditable": D("498"), "impuesto_a_cargo": D("1100")}],
                   IVA_CALC)
    p = por_clave(r)

    assert p["impuesto_trasladado"]["estado"] == "cuadra" and p["impuesto_trasladado"]["diferencia"] == D("1.00")
    assert p["impuesto_acreditable"]["estado"] == "diferencia" and p["impuesto_acreditable"]["diferencia"] == D("-2.00")
    assert p["retenciones"]["estado"] == "sin_captura"
    assert r["estado"] == "con_diferencias"


def test_lo_calculado_se_redondea_a_peso_antes_de_comparar():
    calc = {**IVA_CALC, "impuesto_a_cargo": D("1100.50")}
    r = d.comparar("iva", [{"impuesto_a_cargo": D("1101")}], calc)

    assert por_clave(r)["impuesto_a_cargo"]["calculado"] == D("1101.00") and r["estado"] == "cuadra"


def test_saldo_a_favor_aplicado_resta_de_lo_calculado_a_cargo():
    calc = {**IVA_CALC, "impuesto_a_cargo": D("8000.00")}
    r = d.comparar("iva", [{"impuesto_a_cargo": D("5000"), "saldo_a_favor_aplicado": D("3000")}], calc)
    p = por_clave(r)

    assert p["impuesto_a_cargo"]["calculado"] == D("5000.00") and p["impuesto_a_cargo"]["estado"] == "cuadra"
    assert p["saldo_a_favor_aplicado"]["declarado"] == D("3000.00") and p["saldo_a_favor_aplicado"]["estado"] == "sin_calculo"
    assert r["estado"] == "cuadra"


def test_el_saldo_a_favor_se_aplica_sobre_el_a_cargo_calculado_nunca_negativo():
    calc = {**IVA_CALC, "impuesto_a_cargo": D("-500.00")}                    # el mes sale a favor
    r = d.comparar("iva", [{"impuesto_a_cargo": D("-3000"), "saldo_a_favor_aplicado": D("3000")}], calc)

    assert por_clave(r)["impuesto_a_cargo"]["calculado"] == D("-3000.00")     # max(0, −500) − 3,000


def test_iva_retenido_a_terceros_se_compara_contra_lo_que_se_debe_enterar():
    calc = {**IVA_CALC, "retenciones_a_terceros": D("320.00")}
    r = d.comparar("iva", [{"retenciones_a_terceros": D("200")}], calc)

    assert por_clave(r)["retenciones_a_terceros"]["estado"] == "diferencia" and r["estado"] == "con_diferencias"


def test_si_nada_se_pudo_comparar_el_estado_es_sin_comparar():
    calc = {"ingresos": D("1000.00"), "deducciones": D("400.00"), "retenciones": D("0.00"),
            "retenciones_a_terceros": D("0.00"), "impuesto_a_cargo": None}
    r = d.comparar("isr", [{"impuesto_a_cargo": D("90")}], calc)

    assert por_clave(r)["impuesto_a_cargo"]["estado"] == "sin_calculo"
    assert r["estado"] == "sin_comparar"
    assert d.comparar("isr", [{"ingresos": D("1000")}], calc)["estado"] == "cuadra"


def test_el_pago_provisional_no_se_calcula_y_solo_se_muestra_declarado():
    calc = {"ingresos": D("1000.00"), "deducciones": D("400.00"), "retenciones": D("0.00"),
            "retenciones_a_terceros": D("0.00"), "impuesto_a_cargo": None}
    r = d.comparar("isr", [{"ingresos": D("1000"), "impuesto_a_cargo": D("90")}], calc)

    assert por_clave(r)["impuesto_a_cargo"]["declarado"] == D("90.00") and r["estado"] == "cuadra"


def test_pendiente_de_pago_de_una_sola_declaracion():
    base = {"impuesto_a_cargo": D("1100")}
    assert d.comparar("iva", [{**base, "monto_pagado": D("1100")}], IVA_CALC)["pendiente_de_pago"] == D("0")
    assert d.comparar("iva", [{**base, "monto_pagado": D("1099.50")}], IVA_CALC)["pendiente_de_pago"] == D("0")   # redondeo
    assert d.comparar("iva", [{**base, "monto_pagado": D("600")}], IVA_CALC)["pendiente_de_pago"] == D("500.00")
    assert d.comparar("iva", [base], IVA_CALC)["pendiente_de_pago"] == D("1100.00")
    assert d.comparar("iva", [{"impuesto_a_cargo": D("-50")}], IVA_CALC)["pendiente_de_pago"] is None


def test_la_complementaria_suma_lo_pagado_de_toda_la_cadena():
    normal = {"impuesto_a_cargo": D("10000"), "monto_pagado": D("10000")}
    complementaria = {"impuesto_a_cargo": D("12000"), "monto_pagado": D("2000")}
    r = d.comparar("iva", [normal, complementaria], IVA_CALC)

    assert r["pendiente_de_pago"] == D("0") and r["declaraciones"] == 2 and r["declaracion"] is complementaria
    assert d.comparar("iva", [normal, {**complementaria, "monto_pagado": D("500")}], IVA_CALC)["pendiente_de_pago"] == D("1500.00")


def test_impuesto_invalido():
    with pytest.raises(ValueError):
        d.comparar("ieps", [], {})


def test_el_calculado_sale_de_los_resumenes_de_los_motores():
    from backend import isr_flujo, iva_flujo
    from backend.tests.test_isr_flujo import doc, todos
    from backend.tests.test_iva_flujo import doc as doc_iva

    iva = iva_flujo.resumen([e for e in iva_flujo.eventos_de_documento(doc_iva("U1"), "AAA010101AAA")], "2026-09", {}, D("1"))
    isr = isr_flujo.resumen(todos(doc("U1")), "2026-09", {}, isr_flujo.PORCENTAJE_NOMINA_EXENTA)

    assert d.calculado_de_iva(iva)["impuesto_trasladado"] == D("160.00")
    assert d.calculado_de_iva(iva)["retenciones_a_terceros"] == iva["retenciones_a_enterar"]
    assert d.calculado_de_isr(isr)["ingresos"] == D("1000.00") and d.calculado_de_isr(isr)["impuesto_a_cargo"] is None
    assert d.calculado_de_isr(isr)["retenciones_a_terceros"] == isr["mes"]["retenciones_a_cargo"]["total"]


def test_el_pago_provisional_calculado_alimenta_el_a_cargo_del_isr():
    from backend import isr_flujo
    from backend.tests.test_isr_flujo import doc, todos

    isr = isr_flujo.resumen(todos(doc("U1")), "2026-09", {}, isr_flujo.PORCENTAJE_NOMINA_EXENTA)
    calc = d.calculado_de_isr(isr, D("120.00"))
    r = d.comparar("isr", [{"impuesto_a_cargo": D("120")}], calc)

    assert calc["impuesto_a_cargo"] == D("120.00")
    assert por_clave(r)["impuesto_a_cargo"]["estado"] == "cuadra" and r["estado"] == "cuadra"
    diferente = d.comparar("isr", [{"impuesto_a_cargo": D("200")}], calc)
    assert por_clave(diferente)["impuesto_a_cargo"]["diferencia"] == D("80.00") and diferente["estado"] == "con_diferencias"
