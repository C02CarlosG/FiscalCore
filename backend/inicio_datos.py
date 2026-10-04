"""Inicio (F4) — lectura de la base para la pantalla de entrada.

Las reglas de inclusión viven aquí, en SQL (vigente, sin anticipos SAT, dirección,
tipo y conversión a pesos); la composición del resultado está en ``inicio.py``.
"""
from __future__ import annotations

from decimal import Decimal

from . import db, iva, inicio


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


def cargar_iva_ejercicio(empresa_id: str, rfc: str, ejercicio: int) -> list[dict]:
    """IVA trasladado y acreditable de cada mes del ejercicio, calculados con las
    mismas funciones y los mismos insumos que la cédula de IVA de un mes, para que
    el Inicio nunca la contradiga."""
    desde, hasta = f"{ejercicio:04d}-01-01", f"{ejercicio + 1:04d}-01-01"
    cfdis = db.query_all(
        """
        SELECT uuid, tipo_comprobante, metodo_pago, estado, es_anticipo_sat,
               rfc_emisor, rfc_receptor, forma_pago, fecha_emision,
               subtotal, descuento, total, iva_trasladado
        FROM cfdi
        WHERE empresa_id = %s
          AND estado = 'vigente'
          AND (metodo_pago = 'PPD' OR (fecha_emision >= %s::date AND fecha_emision < %s::date))
        """,
        (empresa_id, desde, hasta),
    )
    pagos = db.query_all(
        """
        SELECT pr.cfdi_uuid, pr.importe_pagado, p.fecha_pago
        FROM pagos_cfdi p
        JOIN pagos_relaciones pr ON pr.pago_id = p.id
        WHERE p.empresa_id = %s AND p.fecha_pago >= %s::date AND p.fecha_pago < %s::date
        """,
        (empresa_id, desde, hasta),
    )
    meses = []
    for mes in inicio.meses_del_ejercicio(ejercicio):
        trasladado = iva.iva_trasladado(cfdis, pagos, mes, rfc)
        acreditable = iva.iva_acreditable(cfdis, pagos, mes, rfc)
        ajustado = iva.aplicar_prorrateo(acreditable["bruto"], Decimal("1"))
        # v1 igual que la cédula: sin retenciones y factor de prorrateo 1; llegan con F5.
        meses.append(inicio.aplanar_iva(mes, trasladado, acreditable, ajustado, Decimal("0.00")))
    return meses
