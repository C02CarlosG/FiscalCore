"""Pago provisional del ISR por flujo (F7.3, Art. 106). Sin DB. Las cifras se verificaron a mano contra el Anexo 8."""
from decimal import Decimal as D

import pytest

from backend import isr_pago_provisional as p
from backend import tarifas_isr as t


def resumen_falso(por_mes):
    """``por_mes[k] = (ingresos_acum, deducciones_acum, retencion_del_mes)``."""
    def _resumen(periodo):
        ing, ded, ret = por_mes[int(periodo[5:7])]
        bloque = {"ingresos": {"total": D(ing), "retenciones_a_favor": D(ret)}, "deducciones": {"total": D(ded)}}
        return {"mes": bloque, "acumulado": bloque}
    return _resumen


def test_la_tarifa_2026_trae_las_trece_tablas_de_once_renglones():
    for mes in range(1, 13):
        filas = t.tarifa_art_106(2026, mes)
        assert len(filas) == 11 and filas[0][0] == D("0.01") and filas[-1][1] is None and filas[-1][3] == D("35.00")
    assert t.tarifa_art_106(2027, 1) is None and t.tarifa_art_106(2026, 13) is None


def test_renglon_y_causado_de_enero():
    # 50,000 cae en 35,362.84–55,736.68: 5,665.16 + 14,637.16 × 23.52 % = 9,107.82
    r = p.aplicar_tarifa(D("50000"), t.tarifa_art_106(2026, 1))

    assert r["limite_inferior"] == D("35362.84") and r["excedente"] == D("14637.16")
    assert r["impuesto_marginal"] == D("3442.66") and r["impuesto_causado"] == D("9107.82")


def test_utilidad_cero_o_negativa_no_causa():
    assert p.aplicar_tarifa(D("-5"), t.tarifa_art_106(2026, 1))["impuesto_causado"] == D("0")
    assert p.aplicar_tarifa(D("0"), t.tarifa_art_106(2026, 1))["impuesto_causado"] == D("0")


def test_los_limites_de_un_renglon_pertenecen_a_su_renglon():
    tarifa = t.tarifa_art_106(2026, 1)
    assert p.aplicar_tarifa(D("844.59"), tarifa)["porcentaje"] == D("1.92")
    assert p.aplicar_tarifa(D("844.60"), tarifa)["cuota_fija"] == D("16.22")
    assert p.aplicar_tarifa(D("999999999"), tarifa)["porcentaje"] == D("35.00")


def test_enero_sin_pagos_anteriores():
    r = p.pago_provisional_flujo("2026-01", resumen_falso({1: ("100000", "50000", "0")}))

    assert r["calculado"] and r["impuesto_causado"] == D("9107.82") and r["pago_del_mes"] == D("9107.82")
    assert r["pagos_provisionales_anteriores"] == D("0.00") and r["meses_con_pago_estimado"] == []


def test_febrero_resta_el_pago_de_enero_estimado_y_la_retencion_del_mes():
    por_mes = {1: ("100000", "50000", "0"), 2: ("200000", "100000", "1000")}
    r = p.pago_provisional_flujo("2026-02", resumen_falso(por_mes))

    # febrero: utilidad acumulada 100,000 → 18,215.64 − 9,107.82 (enero) − 1,000 de retención = 8,107.82
    assert r["impuesto_causado"] == D("18215.64") and r["pagos_provisionales_anteriores"] == D("9107.82")
    assert r["pago_del_mes"] == D("8107.82") and r["meses_con_pago_estimado"] == [1]
    assert any("estiman" in a for a in r["avisos"])


def test_los_pagos_reales_reemplazan_a_la_estimacion():
    por_mes = {1: ("100000", "50000", "0"), 2: ("200000", "100000", "0")}
    r = p.pago_provisional_flujo("2026-02", resumen_falso(por_mes), pagos_reales={1: D("9000")})

    assert r["pagos_provisionales_anteriores"] == D("9000.00") and r["pago_del_mes"] == D("9215.64")
    assert r["meses_con_pago_estimado"] == []


def test_ptu_y_perdidas_bajan_la_base_y_el_pago_nunca_es_negativo():
    por_mes = {1: ("100000", "50000", "0")}
    con = p.pago_provisional_flujo("2026-01", resumen_falso(por_mes), ptu_pagada=D("10000"), perdidas_pendientes=D("5000"), ptu_mes_pago=1)
    assert con["base_gravable"] == D("35000.00")                     # 100,000 − 50,000 − 10,000 − 5,000
    exceso = p.pago_provisional_flujo("2026-01", resumen_falso({1: ("100000", "50000", "99999")}))
    assert exceso["pago_del_mes"] == D("0.00") and exceso["exceso_de_pagos_y_retenciones"] == D("90891.18")


def test_un_ejercicio_sin_tarifa_no_se_calcula():
    r = p.pago_provisional_flujo("2027-03", resumen_falso({}))

    assert r["calculado"] is False and r["motivo"] == "sin_tarifa"


def test_el_json_incluido_coincide_con_la_referencia_documentada():
    import json
    from pathlib import Path
    raiz = Path(__file__).parents[2]
    ref = json.loads((raiz / "docs" / "referencias" / "anexo-8-rmf-2026-tarifas.json").read_text())
    usado = json.loads((raiz / "backend" / "datos" / "anexo8_rmf_2026.json").read_text())["art_106"]
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    for i, m in enumerate(meses, 1):
        assert ref["art_106_" + m] == usado[str(i)]


# ── arrendamiento (606, Art. 116) ────────────────────────────────────────────

def arrend(por_mes, **kw):
    return p.pago_provisional_arrendamiento(kw.pop("periodo", "2026-09"), resumen_falso_mes(por_mes), **kw)


def resumen_falso_mes(por_mes):
    """``por_mes[k] = (ingresos_del_mes, deducciones_del_mes, retencion_del_mes)``; el resto de meses vale cero."""
    def _resumen(periodo):
        ing, ded, ret = por_mes.get(int(periodo[5:7]), (0, 0, 0))
        return {"mes": {"ingresos": {"total": D(ing), "retenciones_a_favor": D(ret)}, "deducciones": {"total": D(ded)}}}
    return _resumen


def test_la_tarifa_116_mensual_es_la_del_art_96_y_la_trimestral_son_tres_veces():
    mensual, trimestral = t.tarifa_art_116(2026, "mensual"), t.tarifa_art_116(2026, "trimestral")

    assert mensual == t.tarifa_art_116(2026, "mensual") and len(mensual) == len(trimestral) == 11
    assert trimestral[0][1] == D("2533.77") == D("844.59") * 3 and trimestral[1][2] == D("48.66") == D("16.22") * 3
    assert t.tarifa_art_116(2027, "mensual") is None and t.tarifa_art_116(2026, "anual") is None


def test_arrendamiento_mensual_sin_acumular_ni_restar_pagos_anteriores():
    # 100,000 − 40,000 = 60,000 → 10,457.09 + 4,263.31 × 30 % = 11,736.08; sin retención
    r = arrend({8: (500000, 0, 0), 9: (100000, 40000, 0)})

    assert r["base_gravable"] == D("60000.00") and r["impuesto_causado"] == D("11736.08") and r["pago_del_periodo"] == D("11736.08")
    assert r["ingresos_del_periodo"] == D("100000.00")             # agosto no entra: no es acumulado


def test_arrendamiento_acredita_la_retencion_del_10_por_ciento():
    r = arrend({9: (100000, 40000, 10000)})

    assert r["isr_retenido_acreditado"] == D("10000.00") and r["pago_del_periodo"] == D("1736.08")
    assert arrend({9: (100000, 40000, 20000)})["pago_del_periodo"] == D("0.00")
    assert arrend({9: (100000, 40000, 20000)})["exceso_de_retenciones"] == D("8263.92")


def test_arrendamiento_con_la_deduccion_opcional_del_35_por_ciento_sustituye_a_las_reales():
    # 35 % de 100,000 = 35,000 (no 40,000): base 65,000 → 10,457.09 + 9,263.31 × 30 % = 13,236.08
    r = arrend({9: (100000, 40000, 0)}, deduccion_opcional=True)

    assert r["deducciones_usadas"] == D("35000.00") and r["base_gravable"] == D("65000.00") and r["impuesto_causado"] == D("13236.08")
    assert r["deducciones_reales_del_periodo"] == D("40000.00") and any("35 %" in a for a in r["avisos"])


def test_el_predial_se_suma_a_la_deduccion_opcional_y_no_a_las_reales():
    con = arrend({9: (100000, 40000, 0)}, deduccion_opcional=True, predial=D("1000"))
    sin_opcion = arrend({9: (100000, 40000, 0)}, deduccion_opcional=False, predial=D("1000"))

    assert con["deducciones_usadas"] == D("36000.00") and con["impuesto_causado"] == D("12936.08")
    assert sin_opcion["deducciones_usadas"] == D("40000.00") and sin_opcion["predial"] == D("0.00")


def test_arrendamiento_trimestral_suma_los_tres_meses_con_la_tarifa_trimestral():
    por_mes = {7: (20000, 5000, 0), 8: (30000, 10000, 1000), 9: (50000, 25000, 2000)}
    r = arrend(por_mes, periodicidad="trimestral")

    # 100,000 − 40,000 = 60,000 → 5,570.52 + 7,399.07 × 21.36 % = 7,150.96; retenciones 3,000
    assert r["base_gravable"] == D("60000.00") and r["impuesto_causado"] == D("7150.96")
    assert r["isr_retenido_acreditado"] == D("3000.00") and r["pago_del_periodo"] == D("4150.96")


def test_arrendamiento_trimestral_solo_se_calcula_en_mes_de_pago():
    r = arrend({8: (1, 0, 0)}, periodo="2026-08", periodicidad="trimestral")

    assert r["calculado"] is False and r["motivo"] == "no_es_mes_de_pago"


def test_arrendamiento_sin_tarifa_o_base_negativa():
    assert arrend({}, periodo="2027-03")["motivo"] == "sin_tarifa"
    r = arrend({9: (1000, 5000, 0)})
    assert r["base_gravable"] == D("0.00") and r["pago_del_periodo"] == D("0.00")


# ── retenciones acumuladas, PTU por mes de pago, avisos y pesos ──────────────

def test_las_retenciones_se_acreditan_acumuladas_no_solo_las_del_mes():
    # enero: 9,107.82 − 1,000 de retención = 8,107.82 de pago. Febrero: 18,215.64 − 8,107.82 − (1,000 + 1,000) acumuladas = 8,107.82
    def resumen(periodo):
        k = int(periodo[5:7])
        ing, ded = {1: (100000, 50000), 2: (200000, 100000)}[k]
        acumulado = {"ingresos": {"total": D(ing), "retenciones_a_favor": D(1000 * k)}, "deducciones": {"total": D(ded)}}
        return {"mes": {"ingresos": {"total": D(ing), "retenciones_a_favor": D(1000)}}, "acumulado": acumulado}

    r = p.pago_provisional_flujo("2026-02", resumen)

    assert r["pagos_provisionales_anteriores"] == D("8107.82") and r["isr_retenido_acumulado"] == D("2000.00")
    assert r["pago_del_mes"] == D("8107.82")


def test_la_ptu_solo_resta_desde_el_mes_en_que_se_pago():
    por_mes = {k: (str(100000 * k), str(50000 * k), "0") for k in range(1, 7)}
    antes = p.pago_provisional_flujo("2026-04", resumen_falso(por_mes), ptu_pagada=D("10000"), ptu_mes_pago=5)
    desde = p.pago_provisional_flujo("2026-06", resumen_falso(por_mes), ptu_pagada=D("10000"), ptu_mes_pago=5)
    sin_mes = p.pago_provisional_flujo("2026-06", resumen_falso(por_mes), ptu_pagada=D("10000"))

    assert antes["ptu_pagada"] == D("0") and antes["base_gravable"] == D("200000.00")     # abril: la PTU aún no se paga
    assert desde["ptu_pagada"] == D("10000") and desde["base_gravable"] == D("290000.00")  # junio: ya resta
    assert sin_mes["ptu_pagada"] == D("0") and any("sin mes de pago" in a for a in sin_mes["avisos"])


def test_las_perdidas_avisan_que_no_se_actualizan_y_el_pago_se_expone_a_pesos():
    # base 100,000 − 50,000 − 1,000 = 49,000 → 5,665.16 + 13,637.16 × 23.52 % = 8,872.62 → $8,873
    r = p.pago_provisional_flujo("2026-01", resumen_falso({1: ("100000", "50000", "0")}), perdidas_pendientes=D("1000"))

    assert any("Art. 57" in a for a in r["avisos"])
    assert r["pago_del_mes"] == D("8872.62") and r["pago_del_mes_a_pesos"] == D("8873.00")
