"""Pago provisional de ISR por flujo de efectivo (F7.3), Art. 106 LISR: personas físicas con actividad empresarial (612).

Puro: sobre los resúmenes de ``isr_flujo`` y la tarifa del Anexo 8. Para cada mes ``k`` del ejercicio:

    utilidad_k      = máx(0, ingresos_acum_k − deducciones_acum_k − PTU pagada − pérdidas pendientes)
    causado_k       = cuota fija + (utilidad_k − límite inferior) × % de la tarifa acumulada del mes k
    pago_k          = máx(0, causado_k − Σ pagos de los meses anteriores − ISR retenido a favor acumulado hasta el mes k)

Las retenciones se acreditan **acumuladas** (Art. 106, último párrafo): los pagos anteriores ya salieron netos de la retención
de su mes, así que restar solo la del mes k dejaría sin acreditar las retenciones de los meses anteriores. La PTU resta solo
desde el mes en que se pagó (``ptu_mes_pago``). Si no se conocen los pagos realmente enterados se estiman con esta fórmula. No calcula Art. 116 (arrendamiento, 606), ni
estímulos, ni la deducción opcional del 35 %. Ver ``docs/superpowers/specs/2026-10-04-f7-isr-base-flujo-design.md``."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Callable, Optional

from . import tarifas_isr

CERO = Decimal("0")
CENTAVOS = Decimal("0.01")


def _q(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def _a_pesos(valor: Decimal) -> Decimal:
    """Monto a pesos enteros (medio hacia arriba), como se paga en la declaración."""
    return valor.quantize(Decimal("1"), rounding=ROUND_HALF_UP).quantize(CENTAVOS)


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
    ptu_mes_pago: Optional[int] = None,
) -> dict:
    """Pago provisional del ``periodo`` (YYYY-MM). ``resumen_de(periodo_k)`` devuelve ``isr_flujo.resumen`` de ese mes;
    ``pagos_reales`` = {mes: pago enterado} de los meses anteriores (si falta alguno, se estima). La PTU se resta desde
    ``ptu_mes_pago`` (sin mes de pago no se resta y se avisa)."""
    ejercicio, mes = int(periodo[:4]), int(periodo[5:7])
    if tarifas_isr.tarifa_art_106(ejercicio, mes) is None:
        return {"calculado": False, "motivo": "sin_tarifa", "ejercicio": ejercicio,
                "mensaje": f"No hay tarifa del Anexo 8 cargada para el ejercicio {ejercicio}: no se calcula el pago provisional."}
    pagos_reales = pagos_reales or {}
    estimados: list[int] = []
    reales: list[int] = []
    pagos_previos: dict[int, Decimal] = {}
    detalle_mes: dict = {}
    for k in range(1, mes + 1):
        bloque = resumen_de(f"{ejercicio:04d}-{k:02d}")
        acum, del_mes = bloque["acumulado"], bloque["mes"]
        utilidad_antes = acum["ingresos"]["total"] - acum["deducciones"]["total"]
        ptu_k = ptu_pagada if ptu_mes_pago is not None and k >= ptu_mes_pago else CERO
        utilidad = max(CERO, utilidad_antes - ptu_k - perdidas_pendientes)
        r = aplicar_tarifa(utilidad, tarifas_isr.tarifa_art_106(ejercicio, k))
        anteriores = sum((pagos_previos[m] for m in range(1, k)), CERO)
        retencion = acum["ingresos"]["retenciones_a_favor"]
        crudo = r["impuesto_causado"] - anteriores - retencion
        pago = max(CERO, crudo)
        detalle_mes = {
            "ingresos_acumulados": acum["ingresos"]["total"], "deducciones_acumuladas": acum["deducciones"]["total"],
            "utilidad_antes_de_ajustes": _q(utilidad_antes), "ptu_pagada": ptu_k, "perdidas_pendientes": perdidas_pendientes,
            "base_gravable": _q(utilidad), "tarifa": r, "impuesto_causado": r["impuesto_causado"],
            "pagos_provisionales_anteriores": _q(anteriores), "isr_retenido_acumulado": _q(retencion),
            "pago_del_mes": _q(pago), "pago_del_mes_a_pesos": _a_pesos(pago),
            "exceso_de_pagos_y_retenciones": _q(max(CERO, -crudo)),
        }
        if k < mes:
            if k in pagos_reales:
                pagos_previos[k] = Decimal(str(pagos_reales[k]))
                reales.append(k)
            else:
                pagos_previos[k] = pago
                estimados.append(k)
    avisos = ["Estimación del flujo: no sustituye la declaración. No aplica estímulos."]
    if perdidas_pendientes > CERO:
        avisos.append("Las pérdidas pendientes se restan tal como se capturaron: no se actualizan por inflación (Art. 57 LISR).")
    if ptu_pagada > CERO and ptu_mes_pago is None:
        avisos.append("Hay PTU pagada sin mes de pago: no se resta. Captura el mes en que se pagó.")
    if estimados:
        avisos.append("Los pagos provisionales de " + ", ".join(f"{m:02d}" for m in estimados) +
                      " se estiman con el mismo cálculo porque no se capturó lo realmente pagado.")
    return {"calculado": True, "ejercicio": ejercicio, "mes": mes, "fuente": tarifas_isr.fuente(ejercicio),
            **detalle_mes, "meses_con_pago_estimado": estimados, "meses_con_pago_real": reales, "avisos": avisos}


MESES_DE_PAGO_TRIMESTRAL = (3, 6, 9, 12)
PORCENTAJE_OPCIONAL = Decimal("0.35")


def pago_provisional_arrendamiento(
    periodo: str,
    resumen_de: Callable[[str], dict],
    periodicidad: str = "mensual",
    deduccion_opcional: bool = False,
    predial: Decimal = CERO,
) -> dict:
    """Pago provisional de arrendamiento (606), Art. 116 LISR. No es acumulado ni resta pagos anteriores:

        base    = ingresos del periodo − deducciones del periodo
        causado = tarifa mensual (o trimestral: 3 × límites y cuotas) del Anexo 8 sobre la base
        pago    = máx(0, causado − ISR retenido por personas morales en el periodo)   (Art. 116, párrafo 3)

    El periodo es el mes, o el trimestre cuando ``periodicidad = trimestral`` (solo en marzo, junio, septiembre y diciembre).
    Con ``deduccion_opcional`` (Art. 115, último párrafo) las deducciones son el 35 % de los ingresos, sin comprobantes, más
    el predial (que sí se suma); sustituyen a las deducciones reales. ``resumen_de(periodo_k)`` = ``isr_flujo.resumen``."""
    ejercicio, mes = int(periodo[:4]), int(periodo[5:7])
    tarifa = tarifas_isr.tarifa_art_116(ejercicio, periodicidad)
    if tarifa is None:
        return {"calculado": False, "motivo": "sin_tarifa", "ejercicio": ejercicio,
                "mensaje": f"No hay tarifa del Anexo 8 cargada para el ejercicio {ejercicio}: no se calcula el pago provisional."}
    if periodicidad == "trimestral":
        if mes not in MESES_DE_PAGO_TRIMESTRAL:
            return {"calculado": False, "motivo": "no_es_mes_de_pago", "ejercicio": ejercicio,
                    "mensaje": "Con pago trimestral el pago provisional se calcula en marzo, junio, septiembre o diciembre."}
        meses = range(mes - 2, mes + 1)
    else:
        meses = range(mes, mes + 1)
    ingresos = deducciones = retenciones = CERO
    for k in meses:
        mes_k = resumen_de(f"{ejercicio:04d}-{k:02d}")["mes"]
        ingresos += mes_k["ingresos"]["total"]
        deducciones += mes_k["deducciones"]["total"]
        retenciones += mes_k["ingresos"]["retenciones_a_favor"]
    if deduccion_opcional:
        deducciones_usadas = _q(ingresos * PORCENTAJE_OPCIONAL) + predial
    else:
        deducciones_usadas = deducciones
        predial = CERO
    base = max(CERO, ingresos - deducciones_usadas)
    r = aplicar_tarifa(base, tarifa)
    pago = max(CERO, r["impuesto_causado"] - retenciones)
    avisos = ["Estimación del flujo: no sustituye la declaración. No aplica estímulos."]
    if deduccion_opcional:
        avisos.append("Deducción opcional del 35 % (Art. 115): sustituye a las deducciones reales y no requiere comprobantes; el predial se suma.")
    return {"calculado": True, "ejercicio": ejercicio, "mes": mes, "periodicidad": periodicidad, "articulo": "116",
            "fuente": tarifas_isr.fuente(ejercicio), "ingresos_del_periodo": _q(ingresos),
            "deducciones_reales_del_periodo": _q(deducciones), "deduccion_opcional_35": deduccion_opcional,
            "deducciones_usadas": _q(deducciones_usadas), "predial": _q(predial), "base_gravable": _q(base),
            "tarifa": r, "impuesto_causado": r["impuesto_causado"], "isr_retenido_acreditado": _q(retenciones),
            "pago_del_periodo": _q(pago), "pago_del_periodo_a_pesos": _a_pesos(pago), "exceso_de_retenciones": _q(max(CERO, retenciones - r["impuesto_causado"])),
            "avisos": avisos}
