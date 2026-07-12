"""Módulo 5 — Pagos provisionales de ISR, persona moral régimen general (Art. 14 LISR).

Función pura sobre montos ya agregados (ingreso nominal acumulado por mes). No toca
la base de datos: el caller carga los ingresos y los parámetros de ``config_isr_empresa``.
Base DEVENGADO (fecha_emision), motor separado del de IVA. Ver ``docs/modulo-isr-provisional-spec.md``.
"""

from __future__ import annotations

from decimal import Decimal

CENTAVOS = Decimal("0.01")


def _isr_acumulado(nominal_acum: Decimal, cu: Decimal, tasa: Decimal, ptu: Decimal, perdidas: Decimal) -> Decimal:
    """ISR acumulado del ejercicio a un corte dado (utilidad estimada × tasa, base nunca negativa)."""
    utilidad_estimada = nominal_acum * cu
    base_gravable = max(utilidad_estimada - ptu - perdidas, Decimal("0"))
    return base_gravable * tasa


def _pago_sin_quantizar(
    ingresos_por_mes: dict[int, Decimal],
    mes: int,
    cu: Decimal,
    tasa: Decimal,
    ptu: Decimal,
    perdidas: Decimal,
    retencion_mes: Decimal,
) -> Decimal:
    """Pago del mes dado, sin redondear (recursión sobre meses anteriores)."""
    isr_acumulado = _isr_acumulado(ingresos_por_mes[mes], cu, tasa, ptu, perdidas)
    pagos_previos = sum(
        (_pago_sin_quantizar(ingresos_por_mes, m, cu, tasa, ptu, perdidas, Decimal("0")) for m in range(1, mes)),
        Decimal("0"),
    )
    return max(isr_acumulado - pagos_previos - retencion_mes, Decimal("0"))


def isr_provisional(
    ingresos_por_mes: dict[int, Decimal],
    mes: int,
    cu: Decimal,
    tasa: Decimal,
    ptu: Decimal,
    perdidas: Decimal,
    retencion_mes: Decimal,
) -> dict:
    """Pago provisional de ISR del ``mes`` dado, acumulado del ejercicio (Art. 14 LISR).

    ``ingresos_por_mes`` mapea mes -> ingreso nominal acumulado del ejercicio a ese
    corte (enero..mes). La retención solo aplica al mes declarado.
    """
    q = lambda d: d.quantize(CENTAVOS)

    nominal_acum = ingresos_por_mes[mes]
    utilidad_estimada = nominal_acum * cu
    base_gravable = max(utilidad_estimada - ptu - perdidas, Decimal("0"))
    isr_acumulado = base_gravable * tasa

    pagos_previos = sum(
        (_pago_sin_quantizar(ingresos_por_mes, m, cu, tasa, ptu, perdidas, Decimal("0")) for m in range(1, mes)),
        Decimal("0"),
    )
    pago_del_mes = max(isr_acumulado - pagos_previos - retencion_mes, Decimal("0"))

    return {
        "ingreso_nominal_acum": q(nominal_acum),
        "utilidad_estimada": q(utilidad_estimada),
        "base_gravable": q(base_gravable),
        "isr_acumulado": q(isr_acumulado),
        "pagos_previos": q(pagos_previos),
        "isr_retenido": q(retencion_mes),
        "pago_del_mes": q(pago_del_mes),
    }
