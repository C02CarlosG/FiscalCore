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
        ("impuesto_a_cargo", "IVA a cargo (+) o a favor (−)"),
    ),
    "isr": (
        ("ingresos", "Ingresos acumulables"),
        ("deducciones", "Deducciones autorizadas"),
        ("retenciones", "ISR retenido a favor"),
        ("impuesto_a_cargo", "Pago provisional a cargo (+) o a favor (−)"),
    ),
}


def _q(valor: Any) -> Decimal:
    return Decimal(str(valor)).quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def calculado_de_iva(resumen: dict) -> dict:
    """Los renglones del IVA que calcula ``iva_flujo.resumen``. El resultado es a cargo (+) o a favor (−)."""
    r = resumen["resultado"]
    return {
        "impuesto_trasladado": r["trasladado"], "impuesto_acreditable": r["acreditable"],
        "retenciones": r["retenciones_a_favor"], "impuesto_a_cargo": r["iva_por_pagar"],
    }


def calculado_de_isr(resumen: dict) -> dict:
    """Los renglones del ISR del mes que calcula ``isr_flujo.resumen``. El pago provisional no se calcula (F7.3)."""
    mes = resumen["mes"]
    return {
        "ingresos": mes["ingresos"]["total"], "deducciones": mes["deducciones"]["total"],
        "retenciones": mes["ingresos"]["retenciones_a_favor"], "impuesto_a_cargo": None,
    }


def _renglon(clave: str, etiqueta: str, declarado: Any, calculado: Any) -> dict:
    d = None if declarado is None else _q(declarado)
    c = None if calculado is None else _q(calculado)
    if d is None:
        estado, dif = "sin_captura", None
    elif c is None:
        estado, dif = "sin_calculo", None
    else:
        dif = d - c
        estado = "cuadra" if abs(dif) <= TOLERANCIA else "diferencia"
    return {"clave": clave, "etiqueta": etiqueta, "declarado": d, "calculado": c, "diferencia": dif, "estado": estado}


def comparar(impuesto: str, declaracion: Optional[dict], calculado: dict) -> dict:
    """Compara una declaración (o ``None``) con lo calculado del mismo impuesto y periodo."""
    if impuesto not in IMPUESTOS:
        raise ValueError("impuesto inválido")
    if declaracion is None:
        return {"impuesto": impuesto, "estado": "sin_declaracion", "declaracion": None, "renglones": [
            _renglon(k, e, None, calculado.get(k)) for k, e in RENGLONES[impuesto]], "pendiente_de_pago": None}
    renglones = [_renglon(k, e, declaracion.get(k), calculado.get(k)) for k, e in RENGLONES[impuesto]]
    capturados = [r for r in renglones if r["estado"] in ("cuadra", "diferencia")]
    estado = "con_diferencias" if any(r["estado"] == "diferencia" for r in renglones) else "cuadra"
    if not capturados and not any(r["estado"] == "sin_calculo" for r in renglones):
        estado = "sin_captura"
    a_cargo, pagado = declaracion.get("impuesto_a_cargo"), declaracion.get("monto_pagado")
    pendiente = None
    if a_cargo is not None and _q(a_cargo) > 0:
        pendiente = max(CERO, _q(a_cargo) - _q(pagado or 0))
        if pendiente <= TOLERANCIA:
            pendiente = CERO
    return {"impuesto": impuesto, "estado": estado, "declaracion": declaracion, "renglones": renglones,
            "pendiente_de_pago": pendiente}
