"""Comparativo contra lo declarado (M5). Sin DB."""
from decimal import Decimal as D

import pytest

from backend import declaraciones as d

IVA_CALC = {"impuesto_trasladado": D("1600.00"), "impuesto_acreditable": D("500.00"), "retenciones": D("0.00"),
            "impuesto_a_cargo": D("1100.00")}


def por_clave(r):
    return {x["clave"]: x for x in r["renglones"]}


def test_sin_declaracion_muestra_lo_calculado_y_el_estado():
    r = d.comparar("iva", None, IVA_CALC)

    assert r["estado"] == "sin_declaracion" and r["pendiente_de_pago"] is None
    assert por_clave(r)["impuesto_trasladado"]["calculado"] == D("1600.00")
    assert por_clave(r)["impuesto_trasladado"]["estado"] == "sin_captura"


def test_hasta_un_peso_de_diferencia_cuadra_y_mas_es_diferencia():
    r = d.comparar("iva", {"impuesto_trasladado": D("1601"), "impuesto_acreditable": D("498"), "impuesto_a_cargo": D("1100")},
                   IVA_CALC)
    p = por_clave(r)

    assert p["impuesto_trasladado"]["estado"] == "cuadra" and p["impuesto_trasladado"]["diferencia"] == D("1.00")
    assert p["impuesto_acreditable"]["estado"] == "diferencia" and p["impuesto_acreditable"]["diferencia"] == D("-2.00")
    assert p["retenciones"]["estado"] == "sin_captura"
    assert r["estado"] == "con_diferencias"


def test_todo_lo_capturado_cuadra():
    r = d.comparar("iva", {"impuesto_trasladado": D("1600"), "impuesto_a_cargo": D("1100")}, IVA_CALC)

    assert r["estado"] == "cuadra"


def test_el_pago_provisional_no_se_calcula_y_solo_se_muestra_declarado():
    calc = {"ingresos": D("1000.00"), "deducciones": D("400.00"), "retenciones": D("0.00"), "impuesto_a_cargo": None}
    r = d.comparar("isr", {"ingresos": D("1000"), "impuesto_a_cargo": D("90")}, calc)
    p = por_clave(r)

    assert p["impuesto_a_cargo"]["estado"] == "sin_calculo" and p["impuesto_a_cargo"]["declarado"] == D("90.00")
    assert r["estado"] == "cuadra"


def test_pendiente_de_pago():
    base = {"impuesto_a_cargo": D("1100")}
    assert d.comparar("iva", {**base, "monto_pagado": D("1100")}, IVA_CALC)["pendiente_de_pago"] == D("0")
    assert d.comparar("iva", {**base, "monto_pagado": D("1099.50")}, IVA_CALC)["pendiente_de_pago"] == D("0")   # redondeo
    assert d.comparar("iva", {**base, "monto_pagado": D("600")}, IVA_CALC)["pendiente_de_pago"] == D("500.00")
    assert d.comparar("iva", base, IVA_CALC)["pendiente_de_pago"] == D("1100.00")
    assert d.comparar("iva", {"impuesto_a_cargo": D("-50")}, IVA_CALC)["pendiente_de_pago"] is None


def test_impuesto_invalido():
    with pytest.raises(ValueError):
        d.comparar("ieps", None, {})


def test_el_calculado_sale_de_los_resumenes_de_los_motores():
    from backend import isr_flujo, iva_flujo
    from backend.tests.test_isr_flujo import doc, todos
    from backend.tests.test_iva_flujo import doc as doc_iva

    iva = iva_flujo.resumen([e for e in iva_flujo.eventos_de_documento(doc_iva("U1"), "AAA010101AAA")], "2026-09", {}, D("1"))
    isr = isr_flujo.resumen(todos(doc("U1")), "2026-09", {}, isr_flujo.PORCENTAJE_NOMINA_EXENTA)

    assert d.calculado_de_iva(iva)["impuesto_trasladado"] == D("160.00")
    assert d.calculado_de_isr(isr)["ingresos"] == D("1000.00") and d.calculado_de_isr(isr)["impuesto_a_cargo"] is None
