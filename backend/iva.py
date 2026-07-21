"""Módulo 3 — Cédula de IVA (cálculo por flujo de efectivo, Art. 1-B LIVA).

Funciones puras sobre registros de CFDI (dicts como los devuelve ``db.query_all``
con ``RealDictCursor``). No tocan la base de datos: reciben los datos ya cargados
para poder probarse en aislamiento. Ver ``docs/modulo-iva-spec.md``.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

CENTAVOS = Decimal("0.01")
SEIS_DECIMALES = Decimal("0.000001")
UMBRAL_EFECTIVO = Decimal("2000")  # Art. 27-III LISR / 5 LIVA: efectivo > $2,000 no deducible


def _dec(valor: Any) -> Decimal:
    """Convierte a Decimal de forma segura (None -> 0)."""
    if valor is None:
        return Decimal("0")
    if isinstance(valor, Decimal):
        return valor
    return Decimal(str(valor))


def _mes(fecha: Any) -> str:
    """Devuelve 'YYYY-MM' de una fecha date/datetime o string ISO."""
    if isinstance(fecha, (date, datetime)):
        return fecha.strftime("%Y-%m")
    return str(fecha)[:7]


def _en_periodo(fecha: Any, periodo: str) -> bool:
    return _mes(fecha) == periodo


def iva_trasladado(
    cfdis: list[dict],
    pagos: list[dict],
    periodo: str,
    rfc_empresa: str,
) -> dict:
    """IVA trasladado (ventas) causado en el periodo, por flujo de efectivo.

    - PUE (tipo I): causa en ``fecha_emision`` dentro del periodo, IVA completo.
    - PPD (tipo I): causa cuando hay un pago (REP) con ``fecha_pago`` en el periodo;
      el IVA de la parcialidad se aproxima proporcionalmente
      (``iva_trasladado * importe_pagado / total``).
    - Notas de crédito (tipo E) emitidas restan del total.
    - Se excluyen: CFDIs no vigentes, anticipos SAT y CFDIs donde la empresa no es
      la emisora (esos son gastos, no ventas).
    """
    pue_base = pue_iva = Decimal("0")
    ppd_cobrado = ppd_iva = Decimal("0")
    nc_base = nc_iva = Decimal("0")

    # Índice de pagos por UUID de CFDI
    pagos_por_uuid: dict[str, list[dict]] = {}
    for p in pagos:
        pagos_por_uuid.setdefault(p["cfdi_uuid"], []).append(p)

    for c in cfdis:
        if c.get("rfc_emisor") != rfc_empresa:
            continue  # la empresa no es emisora -> no es venta
        if c.get("estado") != "vigente":
            continue
        if c.get("es_anticipo_sat"):
            continue

        tipo = c.get("tipo_comprobante")
        metodo = c.get("metodo_pago")

        if tipo == "E":  # nota de crédito emitida (PUE, en el periodo)
            if _en_periodo(c.get("fecha_emision"), periodo):
                nc_base += _dec(c.get("subtotal"))
                nc_iva += _dec(c.get("iva_trasladado"))
            continue

        if tipo != "I":
            continue  # tipo P/T/N no son ingreso

        if metodo == "PUE":
            if _en_periodo(c.get("fecha_emision"), periodo):
                pue_base += _dec(c.get("subtotal"))
                pue_iva += _dec(c.get("iva_trasladado"))
        elif metodo == "PPD":
            total = _dec(c.get("total"))
            iva_cfdi = _dec(c.get("iva_trasladado"))
            for p in pagos_por_uuid.get(c.get("uuid"), []):
                if not _en_periodo(p.get("fecha_pago"), periodo):
                    continue
                importe = _dec(p.get("importe_pagado"))
                ppd_cobrado += importe
                if total > 0:
                    ppd_iva += iva_cfdi * (importe / total)

    total = pue_iva + ppd_iva - nc_iva
    q = lambda d: d.quantize(CENTAVOS)
    return {
        "pue": {"base": q(pue_base), "iva": q(pue_iva)},
        "ppd": {"cobrado": q(ppd_cobrado), "iva": q(ppd_iva)},
        "notas_credito": {"base": q(nc_base), "iva": q(nc_iva)},
        "total": q(total),
    }


def iva_acreditable(
    cfdis: list[dict],
    pagos: list[dict],
    periodo: str,
    rfc_empresa: str,
) -> dict:
    """IVA acreditable (gastos/compras) pagado en el periodo, por flujo de efectivo.

    Simétrico a :func:`iva_trasladado` pero sobre CFDIs donde la empresa es la
    RECEPTORA. Se excluyen los anticipos SAT recibidos (se acreditan cuando llega
    la factura final que los aplica, no al recibir el anticipo, evitando doble
    conteo). Regla de bancarización de v1: pagos en efectivo
    (``forma_pago == '01'``) por más de $2,000 no son acreditables (van a un
    balde ``excluido_efectivo``). El resultado es el IVA **bruto**; el ajuste por
    prorrateo se aplica aparte con :func:`aplicar_prorrateo`.
    """
    pue_base = pue_iva = Decimal("0")
    ppd_pagado = ppd_iva = Decimal("0")
    nc_base = nc_iva = Decimal("0")
    exc_iva = Decimal("0")

    pagos_por_uuid: dict[str, list[dict]] = {}
    for p in pagos:
        pagos_por_uuid.setdefault(p["cfdi_uuid"], []).append(p)

    for c in cfdis:
        if c.get("rfc_receptor") != rfc_empresa:
            continue  # la empresa no es receptora -> no es gasto
        if c.get("estado") != "vigente":
            continue
        if c.get("es_anticipo_sat"):
            continue  # se acredita cuando llega la factura final que lo aplica

        tipo = c.get("tipo_comprobante")
        if tipo == "E":  # nota de crédito recibida -> reduce el IVA acreditable
            if _en_periodo(c.get("fecha_emision"), periodo):
                nc_base += _dec(c.get("subtotal"))
                nc_iva += _dec(c.get("iva_trasladado"))
            continue
        if tipo != "I":
            continue

        total = _dec(c.get("total"))
        iva_cfdi = _dec(c.get("iva_trasladado"))
        es_efectivo_no_deducible = c.get("forma_pago") == "01" and total > UMBRAL_EFECTIVO

        if c.get("metodo_pago") == "PUE":
            if _en_periodo(c.get("fecha_emision"), periodo):
                if es_efectivo_no_deducible:
                    exc_iva += iva_cfdi
                else:
                    pue_base += _dec(c.get("subtotal"))
                    pue_iva += iva_cfdi
        elif c.get("metodo_pago") == "PPD":
            for p in pagos_por_uuid.get(c.get("uuid"), []):
                if not _en_periodo(p.get("fecha_pago"), periodo):
                    continue
                importe = _dec(p.get("importe_pagado"))
                iva_parcial = iva_cfdi * (importe / total) if total > 0 else Decimal("0")
                if es_efectivo_no_deducible:
                    exc_iva += iva_parcial
                else:
                    ppd_pagado += importe
                    ppd_iva += iva_parcial

    bruto = pue_iva + ppd_iva - nc_iva
    q = lambda d: d.quantize(CENTAVOS)
    return {
        "pue": {"base": q(pue_base), "iva": q(pue_iva)},
        "ppd": {"pagado": q(ppd_pagado), "iva": q(ppd_iva)},
        "notas_credito": {"base": q(nc_base), "iva": q(nc_iva)},
        "excluido_efectivo": {"iva": q(exc_iva)},
        "bruto": q(bruto),
    }


def factor_prorrateo(gravados: Any, exentos: Any) -> Decimal:
    """Factor de acreditamiento para actividades mixtas (Art. 5-V LIVA).

    ``gravados / (gravados + exentos)``. Sin actividad (total 0) devuelve 1.0
    (100% acreditable, caso de una empresa 100% gravada).
    """
    g = _dec(gravados)
    e = _dec(exentos)
    total = g + e
    if total == 0:
        return Decimal("1").quantize(SEIS_DECIMALES)
    return (g / total).quantize(SEIS_DECIMALES)


def aplicar_prorrateo(bruto: Any, factor: Any) -> Decimal:
    """Aplica el factor de prorrateo al IVA acreditable bruto."""
    return (_dec(bruto) * _dec(factor)).quantize(CENTAVOS)
