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
