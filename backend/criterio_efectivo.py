"""Criterio de efectivo por empresa (spec 2026-10-13-criterio-efectivo-design).

``legal``: el pago en efectivo (forma de pago 01) no se acredita ni se deduce solo si supera $2,000
(LIVA 5-III, LISR 27-III). ``estricto``: ningún pago en efectivo se acredita ni se deduce (criterio de la
plataforma de referencia). El resto del cálculo no cambia: el umbral 0 hace que la comparación existente
«efectivo y monto mayor al umbral» excluya cualquier efectivo mayor a cero.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

import psycopg2.extras

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


def guardar(empresa_id: str, nuevo: str, usuario_id: str) -> dict:
    """Cambia el criterio y lo audita, todo o nada. Devuelve el valor nuevo y el anterior."""
    nuevo = validar(nuevo)
    with db.get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT criterio_efectivo FROM empresas WHERE id = %s FOR UPDATE", (empresa_id,))
            fila = cur.fetchone()
            if fila is None:
                raise LookupError("Empresa no encontrada")
            anterior = fila["criterio_efectivo"]
            cur.execute("UPDATE empresas SET criterio_efectivo = %s WHERE id = %s", (nuevo, empresa_id))
            cur.execute(
                """INSERT INTO auditoria (usuario_id, empresa_id, accion, entidad, entidad_id, metadata)
                   VALUES (%s, %s, 'criterio_efectivo', 'empresa', %s, %s)""",
                (usuario_id, empresa_id, empresa_id, psycopg2.extras.Json({"anterior": anterior, "nuevo": nuevo})),
            )
    return {"criterio_efectivo": nuevo, "anterior": anterior}
