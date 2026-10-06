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
    con = p.pago_provisional_flujo("2026-01", resumen_falso(por_mes), ptu_pagada=D("10000"), perdidas_pendientes=D("5000"))
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
