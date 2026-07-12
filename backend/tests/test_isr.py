from decimal import Decimal

from backend.isr import isr_provisional

CU = Decimal("0.0850")
TASA = Decimal("0.30")
CERO = Decimal("0")


def test_caso_a_enero_sin_pagos_previos():
    # Caso A: ene 2026, nominal acum 1,000,000 -> utilidad 85,000 -> ISR 25,500 -> pago 25,500
    res = isr_provisional(
        ingresos_por_mes={1: Decimal("1000000")},
        mes=1, cu=CU, tasa=TASA, ptu=CERO, perdidas=CERO, retencion_mes=CERO,
    )
    assert res["ingreso_nominal_acum"] == Decimal("1000000.00")
    assert res["utilidad_estimada"] == Decimal("85000.00")
    assert res["base_gravable"] == Decimal("85000.00")
    assert res["isr_acumulado"] == Decimal("25500.00")
    assert res["pagos_previos"] == Decimal("0.00")
    assert res["pago_del_mes"] == Decimal("25500.00")


def test_caso_a_febrero_resta_pago_previo():
    # Caso A: feb 2026, nominal acum 2,200,000 -> ISR acum 56,100 -> pago 30,600 (resta ene 25,500)
    res = isr_provisional(
        ingresos_por_mes={1: Decimal("1000000"), 2: Decimal("2200000")},
        mes=2, cu=CU, tasa=TASA, ptu=CERO, perdidas=CERO, retencion_mes=CERO,
    )
    assert res["pagos_previos"] == Decimal("25500.00")
    assert res["pago_del_mes"] == Decimal("30600.00")


def test_caso_a_marzo_continuidad_del_acumulado():
    # Caso A: mar 2026, nominal acum 3,000,000 -> ISR acum 76,500 -> pago 20,400 (resta ene+feb)
    res = isr_provisional(
        ingresos_por_mes={1: Decimal("1000000"), 2: Decimal("2200000"), 3: Decimal("3000000")},
        mes=3, cu=CU, tasa=TASA, ptu=CERO, perdidas=CERO, retencion_mes=CERO,
    )
    assert res["pagos_previos"] == Decimal("56100.00")
    assert res["pago_del_mes"] == Decimal("20400.00")


def test_caso_b_retencion_de_isr_se_resta():
    # Caso B: enero con retencion 1,500 -> pago 25,500 - 1,500 = 24,000
    res = isr_provisional(
        ingresos_por_mes={1: Decimal("1000000")},
        mes=1, cu=CU, tasa=TASA, ptu=CERO, perdidas=CERO, retencion_mes=Decimal("1500"),
    )
    assert res["isr_retenido"] == Decimal("1500.00")
    assert res["pago_del_mes"] == Decimal("24000.00")


def test_caso_c_ptu_y_perdidas_disminuyen_la_base():
    # Caso C: utilidad estimada 85,000 - PTU 20,000 - perdidas 15,000 = base 50,000 -> ISR 15,000
    res = isr_provisional(
        ingresos_por_mes={1: Decimal("1000000")},
        mes=1, cu=CU, tasa=TASA, ptu=Decimal("20000"), perdidas=Decimal("15000"),
        retencion_mes=CERO,
    )
    assert res["base_gravable"] == Decimal("50000.00")
    assert res["isr_acumulado"] == Decimal("15000.00")
    assert res["pago_del_mes"] == Decimal("15000.00")


def test_base_negativa_se_trunca_a_cero():
    # PTU + perdidas > utilidad estimada -> base 0, ISR 0, pago 0
    res = isr_provisional(
        ingresos_por_mes={1: Decimal("1000000")},
        mes=1, cu=CU, tasa=TASA, ptu=Decimal("70000"), perdidas=Decimal("30000"),
        retencion_mes=CERO,
    )
    assert res["base_gravable"] == Decimal("0.00")
    assert res["pago_del_mes"] == Decimal("0.00")


def test_pago_negativo_se_trunca_a_cero():
    # Retencion mayor al ISR acumulado del mes -> pago no puede ser negativo
    res = isr_provisional(
        ingresos_por_mes={1: Decimal("1000000")},
        mes=1, cu=CU, tasa=TASA, ptu=CERO, perdidas=CERO,
        retencion_mes=Decimal("999999"),
    )
    assert res["pago_del_mes"] == Decimal("0.00")
