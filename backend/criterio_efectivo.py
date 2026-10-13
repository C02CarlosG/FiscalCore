"""Criterio de efectivo por empresa (spec 2026-10-13-criterio-efectivo-design).

``legal``: el pago en efectivo (forma de pago 01) no se acredita ni se deduce solo si supera $2,000
(LIVA 5-III, LISR 27-III). ``estricto``: ningún pago en efectivo se acredita ni se deduce (criterio de la
plataforma de referencia). El resto del cálculo no cambia: el umbral 0 hace que la comparación existente
«efectivo y monto mayor al umbral» excluya cualquier efectivo mayor a cero.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from . import db

CRITERIOS = ("legal", "estricto")
CRITERIO_POR_DEFECTO = "legal"
UMBRAL_LEGAL = Decimal("2000")
UMBRAL_ESTRICTO = Decimal("0")


class CriterioInvalido(ValueError):
    """El valor no es uno de ``CRITERIOS``."""


def validar(valor: Any) -> str:
    if not isinstance(valor, str) or valor not in CRITERIOS:
        raise CriterioInvalido(f"criterio de efectivo inválido; valores permitidos: {', '.join(CRITERIOS)}")
    return valor


def umbral(criterio: Any) -> Decimal:
    """Monto en efectivo por encima del cual un pago no se acredita ni se deduce."""
    return UMBRAL_ESTRICTO if validar(criterio) == "estricto" else UMBRAL_LEGAL


def leer(empresa_id: str) -> str:
    """Criterio vigente de la empresa; ``legal`` si la empresa no existe."""
    fila = db.query_one("SELECT criterio_efectivo FROM empresas WHERE id = %s", (empresa_id,))
    return fila["criterio_efectivo"] if fila else CRITERIO_POR_DEFECTO
