"""Cédula de IVA (módulo 3) sobre el motor del IVA por flujo (F5.3).

La forma de la respuesta de ``/cedula-iva/{periodo}`` no cambia; lo que cambia es de dónde salen
las cifras: del mismo resumen que alimenta la pantalla de IVA base flujo y la tabla del Inicio, de
modo que las tres pantallas dan siempre la misma cifra. Funciones puras, sin base de datos.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

CENTAVOS = Decimal("0.01")
_CERO = Decimal("0.00")


def _suma_bases(bloque: dict) -> Decimal:
    return sum(bloque["bases"].values(), Decimal("0")).quantize(CENTAVOS)


def _desde_bloque(origenes: dict) -> tuple[dict, dict, dict]:
    contado, credito, notas = origenes["contado"], origenes["credito"], origenes["notas_credito"]
    return (
        {"base": _suma_bases(contado), "iva": contado["iva"]["total"]},
        credito,
        {"base": _suma_bases(notas), "iva": notas["iva"]["total"]},
    )


def desde_motor(resumen: dict, diot_iva: Any) -> dict:
    """Arma la cédula (trasladado, acreditable, retenciones, resultado y comparativo con la DIOT)
    a partir de ``iva_flujo.resumen``."""
    t, a = resumen["trasladado"], resumen["acreditable"]
    pue_t, credito_t, nc_t = _desde_bloque(t["origenes"])
    pue_a, credito_a, nc_a = _desde_bloque(a["origenes"])
    efectivo = a["no_considerados"].get("por_motivo", {}).get("efectivo", {"iva": _CERO})
    diot = Decimal(str(diot_iva))
    res = resumen["resultado"]

    return {
        "trasladado": {
            "pue": pue_t,
            "ppd": {"cobrado": credito_t["importe_pagado"], "iva": credito_t["iva"]["total"]},
            "notas_credito": nc_t,
            "total": t["total"]["total"],
            "no_considerados": t["no_considerados"],
            "reasignados": t["reasignados"],
        },
        "acreditable": {
            "pue": pue_a,
            "ppd": {"pagado": credito_a["importe_pagado"], "iva": credito_a["iva"]["total"]},
            "notas_credito": nc_a,
            "excluido_efectivo": {"iva": efectivo["iva"]},
            "no_considerados": a["no_considerados"],
            "reasignados": a["reasignados"],
            "bruto": a["total"]["total"],
            "factor_prorrateo": resumen["factor_prorrateo"],
            "ajustado": a["ajustado"],
        },
        "iva_retenido": res["retenciones_a_favor"],
        "retenciones_a_enterar": resumen["retenciones_a_enterar"],
        "resultado": {
            "iva_por_pagar": res["iva_por_pagar"],
            "saldo_a_cargo": res["saldo_a_cargo"],
            "saldo_a_favor": res["saldo_a_favor"],
        },
        "comparativo_sat": {
            "diot_iva_pagado": diot,
            "diferencia": (a["ajustado"] - diot).quantize(CENTAVOS),
        },
        "advertencias": resumen["advertencias"],
    }
