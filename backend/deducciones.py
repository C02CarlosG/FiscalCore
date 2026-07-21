"""Módulo 4 — Deducciones autorizadas (MVP), Art. 27 LISR.

Función pura sobre registros de CFDI (dicts como los devuelve ``db.query_all``
con ``RealDictCursor``). No toca la base de datos. Independiente del ISR
provisional: las deducciones aplican a la declaración anual, no al pago
provisional mensual. Ver ``docs/modulo-cogs-deducciones-spec.md``.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from .iva import UMBRAL_EFECTIVO

CENTAVOS = Decimal("0.01")
USOS_INVERSION = {f"I0{n}" for n in range(1, 9)}  # I01..I08 (catálogo SAT c_UsoCFDI)
USO_COSTO = "G01"  # Adquisición de mercancías


def _dec(valor: Any) -> Decimal:
    """Convierte a Decimal de forma segura (None -> 0)."""
    if valor is None:
        return Decimal("0")
    if isinstance(valor, Decimal):
        return valor
    return Decimal(str(valor))


def _fecha(valor: Any) -> date:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return date.fromisoformat(str(valor)[:10])


def _en_rango(valor: Any, desde: date, hasta: date) -> bool:
    """``desde`` inclusive, ``hasta`` exclusivo (igual que las queries SQL del proyecto)."""
    f = _fecha(valor)
    return desde <= f < hasta


def _cubeta(uso_cfdi: Any) -> str:
    if uso_cfdi == USO_COSTO:
        return "costo"
    if uso_cfdi in USOS_INVERSION:
        return "inversion"
    return "gasto"  # default conservador: incluye uso_cfdi nulo/desconocido


def deducciones_periodo(
    cfdis: list[dict],
    pagos: list[dict],
    rfc_empresa: str,
    desde: date,
    hasta: date,
) -> dict:
    """Deducciones autorizadas por CFDIs recibidos y efectivamente pagados en
    ``[desde, hasta)`` (Art. 27 LISR, flujo de efectivo — simétrico a
    :func:`backend.iva.iva_acreditable`).

    - PUE (tipo I): deducible en ``fecha_emision`` dentro del rango.
    - PPD (tipo I): deducible cuando hay un pago (REP) con ``fecha_pago`` en el
      rango; proporcional al importe pagado.
    - Notas de crédito (tipo E) recibidas restan de su cubeta.
    - Efectivo (``forma_pago == '01'``) por más de ``UMBRAL_EFECTIVO`` no es
      deducible (Art. 27-III LISR).
    - Se excluyen: CFDIs no vigentes, ``es_anticipo_sat`` y CFDIs donde la
      empresa no es la receptora (esos son ventas, no gastos).
    - Clasificación por ``uso_cfdi``: G01 -> costo, I01-I08 -> inversión, resto
      -> gasto. Solo "gasto" se deduce en el MVP (``total_deducible``);
      inversión/costo se identifican pero no se suman (sin depreciación ni
      costeo absorbente todavía).
    """
    buckets = {"gasto": Decimal("0"), "costo": Decimal("0"), "inversion": Decimal("0")}
    excluido = Decimal("0")

    pagos_por_uuid: dict[str, list[dict]] = {}
    for p in pagos:
        pagos_por_uuid.setdefault(p["cfdi_uuid"], []).append(p)

    for c in cfdis:
        if c.get("rfc_receptor") != rfc_empresa:
            continue  # la empresa no es receptora -> no es gasto
        if c.get("estado") != "vigente":
            continue
        if c.get("es_anticipo_sat"):
            continue

        tipo = c.get("tipo_comprobante")
        cubeta = _cubeta(c.get("uso_cfdi"))

        if tipo == "E":  # nota de crédito recibida -> resta de su cubeta
            if _en_rango(c.get("fecha_emision"), desde, hasta):
                buckets[cubeta] -= _dec(c.get("subtotal"))
            continue

        if tipo != "I":
            continue

        total = _dec(c.get("total"))
        subtotal = _dec(c.get("subtotal"))
        es_efectivo_no_deducible = c.get("forma_pago") == "01" and total > UMBRAL_EFECTIVO

        if c.get("metodo_pago") == "PUE":
            if _en_rango(c.get("fecha_emision"), desde, hasta):
                if es_efectivo_no_deducible:
                    excluido += subtotal
                else:
                    buckets[cubeta] += subtotal
        elif c.get("metodo_pago") == "PPD":
            for p in pagos_por_uuid.get(c.get("uuid"), []):
                if not _en_rango(p.get("fecha_pago"), desde, hasta):
                    continue
                importe = _dec(p.get("importe_pagado"))
                monto = subtotal * (importe / total) if total > 0 else Decimal("0")
                if es_efectivo_no_deducible:
                    excluido += monto
                else:
                    buckets[cubeta] += monto

    q = lambda d: d.quantize(CENTAVOS)
    return {
        "gasto": q(buckets["gasto"]),
        "inversion_identificada": q(buckets["inversion"]),
        "costo_identificado": q(buckets["costo"]),
        "excluido_efectivo": q(excluido),
        "total_deducible": q(buckets["gasto"]),
    }
