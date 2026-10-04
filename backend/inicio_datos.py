"""Inicio (F4) — lectura de la base para la pantalla de entrada.

Las reglas de inclusión viven aquí, en SQL (vigente, sin anticipos SAT, dirección,
tipo y conversión a pesos); la composición del resultado está en ``inicio.py``.
"""
from __future__ import annotations

from decimal import Decimal

from . import db, inicio, iva_flujo, iva_flujo_datos


def _siguiente_mes(periodo: str) -> str:
    anio, mes = int(periodo[:4]), int(periodo[5:])
    return f"{anio + (mes == 12):04d}-{mes % 12 + 1:02d}"


def cargar_agregados(empresa_id: str, rfc: str, periodo: str) -> list[dict]:
    """Importes por mes, lado (emitido/recibido) y tipo de comprobante para todo lo
    que necesita la pantalla del periodo: el ejercicio completo hasta el periodo y
    la ventana de 12 meses. Un solo recorrido con ``GROUP BY``."""
    primero, ultimo = inicio.rango_consulta(periodo)
    return db.query_all(
        """
        SELECT to_char(c.fecha_emision, 'YYYY-MM') AS mes,
               CASE WHEN c.rfc_emisor = %s THEN 'emitido' ELSE 'recibido' END AS lado,
               c.tipo_comprobante AS tipo,
               SUM(
                   CASE WHEN c.tipo_comprobante = 'N'
                        THEN c.subtotal                              -- percepciones: el descuento son deducciones del trabajador
                        ELSE c.subtotal - COALESCE(c.descuento, 0)
                   END * COALESCE(NULLIF(c.tipo_cambio, 0), 1)
               ) AS base,
               COUNT(*) AS cuenta
        FROM cfdi c
        WHERE c.empresa_id = %s
          AND c.estado = 'vigente'
          AND NOT COALESCE(c.es_anticipo_sat, FALSE)
          AND c.tipo_comprobante IN ('I', 'E', 'N')
          -- El egreso que aplica un anticipo (forma de pago 30) no es una devolución: el
          -- anticipo ya se excluyó y la factura final trae el importe completo.
          AND NOT (c.tipo_comprobante = 'E' AND c.forma_pago = '30')
          AND (c.rfc_emisor = %s OR c.rfc_receptor = %s)
          AND c.fecha_emision >= (%s || '-01')::date
          AND c.fecha_emision <  (%s || '-01')::date
        GROUP BY 1, 2, 3
        """,
        (rfc, empresa_id, rfc, rfc, primero, _siguiente_mes(ultimo)),
    )


def cargar_iva_ejercicio(empresa_id: str, rfc: str, ejercicio: int, periodo: str | None = None) -> tuple[list[dict], list[dict]]:
    """IVA trasladado y acreditable de cada mes del ejercicio, calculados con el mismo motor
    (``iva_flujo``) y los mismos ajustes que la cédula y la pantalla de IVA, para que el Inicio nunca
    las contradiga. Lee los eventos del año una sola vez. Devuelve los meses y las advertencias."""
    ajustes = iva_flujo_datos.cargar_ajustes(empresa_id)
    eventos = iva_flujo_datos.cargar_eventos_ejercicio(empresa_id, rfc, ejercicio, ajustes)
    resumenes = [iva_flujo.resumen(eventos, mes, ajustes, Decimal("1")) for mes in inicio.meses_del_ejercicio(ejercicio)]
    return [inicio.iva_mes_desde_motor(r) for r in resumenes], inicio.advertencias_desde_motor(resumenes, periodo)
