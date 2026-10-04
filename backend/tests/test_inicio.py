"""Inicio (F4): composición de ingresos y gastos, ventana de 12 meses y IVA anual. Sin DB."""
from decimal import Decimal

import pytest

from backend import inicio

D = Decimal


def _fila(mes, lado, tipo, base, cuenta=1):
    return {"mes": mes, "lado": lado, "tipo": tipo, "base": D(str(base)), "cuenta": cuenta}


def test_ventana_de_12_meses_termina_en_el_periodo():
    v = inicio.ventana_12_meses("2026-09")

    assert len(v) == 12
    assert (v[0], v[-1]) == ("2025-10", "2026-09")


def test_ventana_cruza_de_ejercicio_y_en_enero():
    assert inicio.ventana_12_meses("2026-01")[0] == "2025-02"
    assert inicio.ventana_12_meses("2026-12") == [f"2026-{m:02d}" for m in range(1, 13)]


def test_meses_del_ejercicio():
    assert inicio.meses_del_ejercicio(2026) == [f"2026-{m:02d}" for m in range(1, 13)]


@pytest.mark.parametrize("valor", ["2026-13", "1999-01", "2026-9", "x", "", None, "2100-01"])
def test_periodo_invalido(valor):
    assert inicio.periodo_valido(valor) is False


def test_periodo_valido():
    assert inicio.periodo_valido("2026-09") is True


def test_rango_de_consulta_cubre_ejercicio_y_ventana():
    assert inicio.rango_consulta("2026-09") == ("2025-10", "2026-09")   # la ventana arranca antes que enero
    assert inicio.rango_consulta("2026-12") == ("2026-01", "2026-12")
    assert inicio.rango_consulta("2026-01") == ("2025-02", "2026-01")


def test_ingresos_facturado_menos_notas_de_credito():
    r = inicio.componer_resumen([
        _fila("2026-09", "emitido", "I", 1000, 3),
        _fila("2026-09", "emitido", "E", 200, 1),
    ], "2026-09")

    assert r["ingresos"]["periodo"] == {
        "facturado": D("1000.00"), "notas_credito": D("200.00"), "neto": D("800.00"), "cfdi": 4,
    }


def test_gastos_son_los_recibidos_y_la_nomina_va_aparte():
    r = inicio.componer_resumen([
        _fila("2026-09", "recibido", "I", 500, 2),
        _fila("2026-09", "recibido", "E", 50, 1),
        _fila("2026-09", "emitido", "N", 300, 5),
    ], "2026-09")

    g = r["gastos"]["periodo"]
    assert (g["facturado"], g["notas_credito"], g["neto"], g["cfdi"]) == (D("500.00"), D("50.00"), D("450.00"), 3)
    assert g["nomina"] == D("300.00")
    assert r["ingresos"]["periodo"]["neto"] == D("0.00")      # la nómina no es ingreso


def test_lo_que_no_es_ingreso_ni_gasto_se_ignora():
    r = inicio.componer_resumen([
        _fila("2026-09", "emitido", "T", 999),
        _fila("2026-09", "emitido", "P", 999),
        _fila("2026-09", "recibido", "N", 999),
        _fila("2026-09", "recibido", "P", 999),
    ], "2026-09")

    assert r["ingresos"]["periodo"]["neto"] == D("0.00")
    assert r["gastos"]["periodo"]["neto"] == D("0.00")
    assert r["gastos"]["periodo"]["nomina"] == D("0.00")


def test_acumulado_va_de_enero_al_periodo_y_no_incluye_meses_posteriores():
    filas = [_fila(f"2026-{m:02d}", "emitido", "I", 100 * m) for m in (1, 3, 9, 11)]
    r = inicio.componer_resumen(filas, "2026-09")

    assert r["ingresos"]["acumulado"]["neto"] == D("1300.00")     # 100 + 300 + 900; noviembre no cuenta
    assert r["ingresos"]["acumulado"]["cfdi"] == 3
    assert r["ingresos"]["periodo"]["neto"] == D("900.00")


def test_acumulado_de_enero_es_el_periodo():
    r = inicio.componer_resumen([_fila("2026-01", "emitido", "I", 700), _fila("2025-12", "emitido", "I", 5)], "2026-01")

    assert r["ingresos"]["acumulado"] == r["ingresos"]["periodo"]
    assert r["ingresos"]["acumulado"]["neto"] == D("700.00")      # diciembre del ejercicio anterior no entra


def test_serie_de_12_meses_incluye_meses_vacios_y_cruza_de_ejercicio():
    r = inicio.componer_resumen([
        _fila("2025-11", "emitido", "I", 400),
        _fila("2026-09", "emitido", "I", 900),
        _fila("2026-09", "recibido", "I", 250),
    ], "2026-09")

    meses = r["meses"]
    assert [m["periodo"] for m in meses][0] == "2025-10" and len(meses) == 12
    por = {m["periodo"]: m for m in meses}
    assert por["2025-10"]["ingresos"]["neto"] == D("0.00")
    assert por["2025-11"]["ingresos"]["neto"] == D("400.00")
    assert por["2026-09"]["gastos"]["neto"] == D("250.00")
    assert r["ejercicio"] == 2026
    # 2025-11 está en la serie pero no en el acumulado del ejercicio 2026
    assert r["ingresos"]["acumulado"]["neto"] == D("900.00")


def test_sin_datos_todo_es_cero():
    r = inicio.componer_resumen([], "2026-09")

    cero = {"facturado": D("0.00"), "notas_credito": D("0.00"), "neto": D("0.00"), "cfdi": 0}
    assert r["ingresos"]["periodo"] == cero and r["ingresos"]["acumulado"] == cero
    assert len(r["meses"]) == 12


def test_los_importes_se_redondean_a_centavos_al_final():
    r = inicio.componer_resumen([
        _fila("2026-09", "emitido", "I", "0.004"),
        _fila("2026-09", "emitido", "I", "0.004"),
        _fila("2026-09", "emitido", "I", "0.004"),
    ], "2026-09")

    assert r["ingresos"]["periodo"]["facturado"] == D("0.01")    # 0.012 → 0.01, no 3 × 0.00


# ── IVA anual ────────────────────────────────────────────────────────────────

def _mes_iva(periodo, traslado, acred, retenido="0"):
    t = {"pue": D(str(traslado)), "ppd": D("0"), "notas_credito": D("0"), "total": D(str(traslado))}
    a = {"pue": D(str(acred)), "ppd": D("0"), "notas_credito": D("0"), "excluido_efectivo": D("0"),
         "bruto": D(str(acred)), "ajustado": D(str(acred))}
    return {"periodo": periodo, "trasladado": t, "acreditable": a, "iva_retenido": D(str(retenido))}


def test_iva_anual_resultado_a_cargo_y_a_favor_son_excluyentes():
    r = inicio.componer_iva_anual(2026, [_mes_iva("2026-01", 160, 100), _mes_iva("2026-02", 50, 80)], None)

    enero, febrero = r["meses"][0]["resultado"], r["meses"][1]["resultado"]
    assert (enero["iva_por_pagar"], enero["saldo_a_cargo"], enero["saldo_a_favor"]) == (D("60.00"), D("60.00"), D("0.00"))
    assert (febrero["iva_por_pagar"], febrero["saldo_a_cargo"], febrero["saldo_a_favor"]) == (D("-30.00"), D("0.00"), D("30.00"))


def test_iva_anual_descuenta_la_retencion():
    r = inicio.componer_iva_anual(2026, [_mes_iva("2026-01", 160, 100, retenido="10")], None)

    assert r["meses"][0]["resultado"]["iva_por_pagar"] == D("50.00")


def test_iva_anual_siempre_trae_12_meses_y_los_faltantes_van_en_cero():
    r = inicio.componer_iva_anual(2026, [_mes_iva("2026-03", 160, 100)], None)

    assert [m["periodo"] for m in r["meses"]] == inicio.meses_del_ejercicio(2026)
    assert r["meses"][0]["trasladado"]["total"] == D("0.00")
    assert r["meses"][2]["trasladado"]["total"] == D("160.00")


def test_iva_anual_deja_vacios_los_meses_posteriores_al_periodo():
    r = inicio.componer_iva_anual(2026, [_mes_iva("2026-01", 160, 100), _mes_iva("2026-06", 999, 1)], "2026-03")

    assert r["meses"][0]["trasladado"]["total"] == D("160.00")
    assert r["meses"][5]["trasladado"]["total"] == D("0.00")      # junio es posterior a marzo


def test_iva_anual_totales_suman_los_meses():
    r = inicio.componer_iva_anual(2026, [_mes_iva("2026-01", 160, 100), _mes_iva("2026-02", 50, 80, retenido="5")], None)

    assert r["totales"] == {
        "trasladado": D("210.00"), "acreditable": D("180.00"), "iva_retenido": D("5.00"), "iva_por_pagar": D("25.00"),
    }
    assert r["iva_retenido_incluido"] is False and r["factor_prorrateo"] == D("1")


# ── Forma de lo que devuelve iva.py ──────────────────────────────────────────

def test_aplanar_iva_toma_el_iva_de_cada_renglon_de_la_cedula():
    traslado = {"pue": {"base": D("1000"), "iva": D("160")}, "ppd": {"cobrado": D("580"), "iva": D("80")},
                "notas_credito": {"base": D("300"), "iva": D("48")}, "total": D("192")}
    acreditable = {"pue": {"base": D("400"), "iva": D("64")}, "ppd": {"pagado": D("0"), "iva": D("0")},
                   "notas_credito": {"base": D("50"), "iva": D("8")}, "excluido_efectivo": {"iva": D("5")},
                   "bruto": D("56")}

    r = inicio.aplanar_iva("2026-09", traslado, acreditable, D("56"), D("0"))

    assert r["periodo"] == "2026-09"
    assert r["trasladado"] == {"pue": D("160"), "ppd": D("80"), "notas_credito": D("48"), "total": D("192")}
    assert r["acreditable"] == {"pue": D("64"), "ppd": D("0"), "notas_credito": D("8"),
                                "excluido_efectivo": D("5"), "bruto": D("56"), "ajustado": D("56")}
    assert r["iva_retenido"] == D("0")


def test_el_resultado_del_aplanado_se_compone_sin_error():
    traslado = {"pue": {"base": D("1000"), "iva": D("160")}, "ppd": {"cobrado": D("0"), "iva": D("0")},
                "notas_credito": {"base": D("0"), "iva": D("0")}, "total": D("160")}
    acreditable = {"pue": {"base": D("0"), "iva": D("0")}, "ppd": {"pagado": D("0"), "iva": D("0")},
                   "notas_credito": {"base": D("0"), "iva": D("0")}, "excluido_efectivo": {"iva": D("0")}, "bruto": D("0")}

    r = inicio.componer_iva_anual(2026, [inicio.aplanar_iva("2026-01", traslado, acreditable, D("0"), D("0"))], None)

    assert r["meses"][0]["resultado"]["iva_por_pagar"] == D("160.00")
