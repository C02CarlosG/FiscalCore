"""Pago provisional de ISR por flujo de efectivo (F7.3), Art. 106 LISR: personas físicas con actividad empresarial (612).

Puro: sobre los resúmenes de ``isr_flujo`` y la tarifa del Anexo 8. Para cada mes ``k`` del ejercicio:

    utilidad_k      = máx(0, ingresos_acum_k − deducciones_acum_k − PTU pagada − pérdidas pendientes)
    causado_k       = cuota fija + (utilidad_k − límite inferior) × % de la tarifa acumulada del mes k
    pago_k          = máx(0, causado_k − Σ pagos de los meses anteriores − ISR retenido a favor del mes k)

Los pagos anteriores restan ya netos de su propia retención (como en el Art. 14, ``isr.py``). Si no se conocen los pagos
realmente enterados se estiman con esta misma fórmula y se avisa. No calcula Art. 116 (arrendamiento, 606), ni
estímulos, ni la deducción opcional del 35 %. Ver ``docs/superpowers/specs/2026-10-04-f7-isr-base-flujo-design.md``."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Callable, Optional

from . import tarifas_isr

CERO = Decimal("0")
CENTAVOS = Decimal("0.01")


def _q(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def aplicar_tarifa(utilidad: Decimal, tarifa: list) -> dict:
    """Renglón de la tarifa que le toca a ``utilidad`` y el impuesto causado. Utilidad ≤ 0 → sin impuesto."""
    if utilidad <= CERO:
        return {"limite_inferior": CERO, "limite_superior": None, "cuota_fija": CERO, "porcentaje": CERO,
                "excedente": CERO, "impuesto_marginal": CERO, "impuesto_causado": CERO}
    for inferior, superior, cuota, porcentaje in tarifa:
        if utilidad >= inferior and (superior is None or utilidad <= superior):
            excedente = utilidad - inferior
            marginal = excedente * porcentaje / Decimal("100")
            return {"limite_inferior": inferior, "limite_superior": superior, "cuota_fija": cuota, "porcentaje": porcentaje,
                    "excedente": _q(excedente), "impuesto_marginal": _q(marginal), "impuesto_causado": _q(cuota + marginal)}
    # utilidad entre 0 y 0.01: por debajo del primer renglón de la tarifa
    return aplicar_tarifa(CERO, tarifa)


def pago_provisional_flujo(
    periodo: str,
    resumen_de: Callable[[str], dict],
    ptu_pagada: Decimal = CERO,
    perdidas_pendientes: Decimal = CERO,
    pagos_reales: Optional[dict[int, Decimal]] = None,
) -> dict:
    """Pago provisional del ``periodo`` (YYYY-MM). ``resumen_de(periodo_k)`` devuelve ``isr_flujo.resumen`` de ese mes;
    ``pagos_reales`` = {mes: pago enterado} de los meses anteriores (si falta alguno, se estima)."""
    ejercicio, mes = int(periodo[:4]), int(periodo[5:7])
    if tarifas_isr.tarifa_art_106(ejercicio, mes) is None:
        return {"calculado": False, "motivo": "sin_tarifa", "ejercicio": ejercicio,
                "mensaje": f"No hay tarifa del Anexo 8 cargada para el ejercicio {ejercicio}: no se calcula el pago provisional."}
    pagos_reales = pagos_reales or {}
    estimados: list[int] = []
    pagos_previos: dict[int, Decimal] = {}
    detalle_mes: dict = {}
    for k in range(1, mes + 1):
        bloque = resumen_de(f"{ejercicio:04d}-{k:02d}")
        acum, del_mes = bloque["acumulado"], bloque["mes"]
        utilidad_antes = acum["ingresos"]["total"] - acum["deducciones"]["total"]
        utilidad = max(CERO, utilidad_antes - ptu_pagada - perdidas_pendientes)
        r = aplicar_tarifa(utilidad, tarifas_isr.tarifa_art_106(ejercicio, k))
        anteriores = sum((pagos_previos[m] for m in range(1, k)), CERO)
        retencion = del_mes["ingresos"]["retenciones_a_favor"]
        crudo = r["impuesto_causado"] - anteriores - retencion
        pago = max(CERO, crudo)
        detalle_mes = {
            "ingresos_acumulados": acum["ingresos"]["total"], "deducciones_acumuladas": acum["deducciones"]["total"],
            "utilidad_antes_de_ajustes": _q(utilidad_antes), "ptu_pagada": ptu_pagada, "perdidas_pendientes": perdidas_pendientes,
            "base_gravable": _q(utilidad), "tarifa": r, "impuesto_causado": r["impuesto_causado"],
            "pagos_provisionales_anteriores": _q(anteriores), "isr_retenido_del_mes": retencion,
            "pago_del_mes": _q(pago), "exceso_de_pagos_y_retenciones": _q(max(CERO, -crudo)),
        }
        if k < mes:
            if k in pagos_reales:
                pagos_previos[k] = Decimal(str(pagos_reales[k]))
            else:
                pagos_previos[k] = pago
                estimados.append(k)
    avisos = ["Estimación del flujo: no sustituye la declaración. No aplica estímulos ni la deducción opcional del 35 %."]
    if estimados:
        avisos.append("Los pagos provisionales de " + ", ".join(f"{m:02d}" for m in estimados) +
                      " se estiman con el mismo cálculo porque no se capturó lo realmente pagado.")
    return {"calculado": True, "ejercicio": ejercicio, "mes": mes, "fuente": tarifas_isr.fuente(ejercicio),
            **detalle_mes, "meses_con_pago_estimado": estimados, "avisos": avisos}
