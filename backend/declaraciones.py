"""Comparativo contra lo declarado (M5): lo que el contador capturó de cada declaración frente a lo que calculan los motores
de flujo (IVA e ISR). Puro: sin base de datos. Ver ``docs/superpowers/specs/2026-10-06-m5-comparativo-declarado-design.md``."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Optional

CERO = Decimal("0")
CENTAVOS = Decimal("0.01")
# Las declaraciones se presentan en pesos enteros: hasta un peso de diferencia es redondeo, no error.
TOLERANCIA = Decimal("1.00")

IMPUESTOS = ("iva", "isr")

# (clave del renglón, etiqueta) en el orden en que se muestran
RENGLONES = {
    "iva": (
        ("impuesto_trasladado", "IVA trasladado cobrado"),
        ("impuesto_acreditable", "IVA acreditable"),
        ("retenciones", "Retenciones de IVA a favor"),
        ("retenciones_a_terceros", "IVA retenido a terceros por enterar"),
        ("saldo_a_favor_aplicado", "Saldo a favor de periodos anteriores aplicado"),
        ("impuesto_a_cargo", "IVA a cargo (+) o a favor (−), después del saldo a favor aplicado"),
    ),
    "isr": (
        ("ingresos", "Ingresos acumulables"),
        ("deducciones", "Deducciones autorizadas"),
        ("retenciones", "ISR retenido a favor"),
        ("retenciones_a_terceros", "ISR retenido a terceros por enterar"),
        ("impuesto_a_cargo", "Pago provisional a cargo (+) o a favor (−)"),
    ),
}


PESO = Decimal("1")


def _q(valor: Any) -> Decimal:
    return Decimal(str(valor)).quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def _a_peso(valor: Any) -> Decimal:
    """Lo calculado a peso entero, como se presenta la declaración (medio hacia arriba)."""
    return Decimal(str(valor)).quantize(PESO, rounding=ROUND_HALF_UP).quantize(CENTAVOS)


def calculado_de_iva(resumen: dict) -> dict:
    """Los renglones del IVA que calcula ``iva_flujo.resumen``. El resultado es a cargo (+) o a favor (−)."""
    r = resumen["resultado"]
    return {
        "impuesto_trasladado": r["trasladado"], "impuesto_acreditable": r["acreditable"],
        "retenciones": r["retenciones_a_favor"], "retenciones_a_terceros": resumen["retenciones_a_enterar"],
        "saldo_a_favor_aplicado": None, "impuesto_a_cargo": r["iva_por_pagar"],
    }


def calculado_de_isr(resumen: dict) -> dict:
    """Los renglones del ISR del mes que calcula ``isr_flujo.resumen``. El pago provisional no se calcula (F7.3)."""
    mes = resumen["mes"]
    return {
        "ingresos": mes["ingresos"]["total"], "deducciones": mes["deducciones"]["total"],
        "retenciones": mes["ingresos"]["retenciones_a_favor"],
        "retenciones_a_terceros": mes["retenciones_a_cargo"]["total"], "impuesto_a_cargo": None,
    }


def _renglon(clave: str, etiqueta: str, declarado: Any, calculado: Any) -> dict:
    d = None if declarado is None else _q(declarado)
    c = None if calculado is None else _a_peso(calculado)
    if d is None:
        estado, dif = "sin_captura", None
    elif c is None:
        estado, dif = "sin_calculo", None
    else:
        dif = d - c
        estado = "cuadra" if abs(dif) <= TOLERANCIA else "diferencia"
    return {"clave": clave, "etiqueta": etiqueta, "declarado": d, "calculado": c, "diferencia": dif, "estado": estado}


def comparar(impuesto: str, cadena: list[dict], calculado: dict) -> dict:
    """Compara la declaración vigente (la última de ``cadena``: normal y complementarias en orden) con lo calculado.

    En IVA el saldo a favor de periodos anteriores aplicado resta de máx(0, lo calculado a cargo); lo calculado se redondea a
    peso. El pendiente de pago usa el a cargo de la vigente y suma lo pagado de toda la cadena."""
    if impuesto not in IMPUESTOS:
        raise ValueError("impuesto inválido")
    vigente = cadena[-1] if cadena else None
    calc = dict(calculado)
    if impuesto == "iva" and vigente is not None and calc.get("impuesto_a_cargo") is not None:
        # el saldo a favor se aplica contra el impuesto a cargo (nunca contra un saldo a favor del mes)
        a_cargo = max(CERO, Decimal(str(calc["impuesto_a_cargo"])))
        calc["impuesto_a_cargo"] = a_cargo - Decimal(str(vigente.get("saldo_a_favor_aplicado") or 0))
    renglones = [_renglon(k, e, (vigente or {}).get(k), calc.get(k)) for k, e in RENGLONES[impuesto]]
    if vigente is None:
        return {"impuesto": impuesto, "estado": "sin_declaracion", "declaracion": None, "declaraciones": 0,
                "renglones": renglones, "pendiente_de_pago": None}
    comparados = [r for r in renglones if r["estado"] in ("cuadra", "diferencia")]
    if not comparados:
        estado = "sin_comparar"          # nada capturado contra nada calculado: no se puede decir que cuadra
    else:
        estado = "con_diferencias" if any(r["estado"] == "diferencia" for r in comparados) else "cuadra"
    a_cargo = vigente.get("impuesto_a_cargo")
    pendiente = None
    if a_cargo is not None and _q(a_cargo) > 0:
        pagado = sum((_q(d.get("monto_pagado") or 0) for d in cadena), CERO)
        pendiente = max(CERO, _q(a_cargo) - pagado)
        if pendiente <= TOLERANCIA:
            pendiente = CERO
    return {"impuesto": impuesto, "estado": estado, "declaracion": vigente, "declaraciones": len(cadena),
            "renglones": renglones, "pendiente_de_pago": pendiente}
