"""
Persistencia de CFDI parseados — punto único para la subida manual
(routers/ingesta.py) y la Descarga Masiva del SAT (routers/sat.py).

Antes cada ruta tenía su propio INSERT y solo la subida manual procesaba los
Complementos de Pago, así que los REP descargados por FIEL nunca registraban
pagos. Aquí viven el INSERT, el complemento de pago y el recálculo de lo
cobrado, para que ambas rutas se comporten igual.

``monto_cobrado`` / ``estado_pago`` de un CFDI se DERIVAN de ``pagos_relaciones``
(nunca se incrementan): re-ingerir el mismo REP no cambia el resultado, y el
orden en que llegan factura y REP no importa.
"""
from __future__ import annotations

import json

from . import db


def recalcular_cobrado(empresa_id: str, uuid: str) -> None:
    """Recalcula monto_cobrado y estado_pago de un CFDI a partir de los pagos
    registrados para él (suma de ``pagos_relaciones`` de la empresa)."""
    uuid = uuid.upper()
    db.execute(
        """
        UPDATE cfdi c
        SET monto_cobrado = LEAST(c.total, p.pagado),
            estado_pago = CASE
                WHEN p.pagado >= c.total THEN 'pagado_total'
                WHEN p.pagado > 0        THEN 'pagado_parcial'
                ELSE 'pendiente'
            END
        FROM (
            SELECT COALESCE(SUM(pr.importe_pagado), 0) AS pagado
            FROM pagos_relaciones pr
            JOIN pagos_cfdi pc ON pc.id = pr.pago_id
            WHERE pc.empresa_id = %s AND pr.cfdi_uuid = %s
        ) p
        WHERE c.empresa_id = %s AND c.uuid = %s
        """,
        (empresa_id, uuid, empresa_id, uuid),
    )


def persistir_complemento_pago(empresa_id: str, resultado) -> None:
    """
    Persiste los nodos pago20:Pago de un CFDI tipo P:
    - Inserta en pagos_cfdi y pagos_relaciones (idempotente: re-ingerir el
      mismo REP no duplica filas — ver migración 027).
    - Recalcula monto_cobrado y estado_pago de los CFDIs relacionados.
    """
    cfdi_row = db.query_one(
        "SELECT id FROM cfdi WHERE uuid = %s AND empresa_id = %s",
        (resultado.uuid, empresa_id),
    )
    if not cfdi_row:
        return
    cfdi_db_id = str(cfdi_row["id"])
    uuids_afectados: list[str] = []

    for pago in resultado.pagos:
        if not pago.fecha_pago or pago.monto <= 0:
            continue

        pago_row = db.execute(
            """
            INSERT INTO pagos_cfdi (empresa_id, cfdi_id, uuid_cfdi_pago, fecha_pago, monto, moneda, tipo_cambio)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (cfdi_id, fecha_pago, monto) DO NOTHING
            RETURNING id
            """,
            (
                empresa_id, cfdi_db_id, resultado.uuid,
                pago.fecha_pago, str(pago.monto),
                pago.moneda, str(pago.tipo_cambio),
            ),
            returning=True,
        )
        if not pago_row:
            # Ya existía (ON CONFLICT DO NOTHING) — recuperar id existente
            pago_row = db.query_one(
                "SELECT id FROM pagos_cfdi WHERE cfdi_id = %s AND fecha_pago = %s AND monto = %s",
                (cfdi_db_id, pago.fecha_pago, str(pago.monto)),
            )
        if not pago_row:
            continue
        pago_db_id = str(pago_row["id"])

        for docto in pago.doctos_relacionados:
            if not docto.uuid:
                continue
            docto_uuid = docto.uuid.upper()
            db.execute(
                """
                INSERT INTO pagos_relaciones (pago_id, cfdi_uuid, parcialidad, importe_pagado, saldo_anterior, saldo_restante)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (
                    pago_db_id, docto_uuid, docto.num_parcialidad,
                    str(docto.imp_pagado), str(docto.imp_saldo_ant), str(docto.imp_saldo_insoluto),
                ),
            )
            if docto_uuid not in uuids_afectados:
                uuids_afectados.append(docto_uuid)

    for uuid in uuids_afectados:
        recalcular_cobrado(empresa_id, uuid)


def insertar_cfdi(empresa_id: str, resultado, xml_bytes: bytes) -> None:
    """Inserta un CFDIParsed (ignora duplicados por UUID) y aplica sus efectos
    sobre pagos: un tipo P registra su complemento; un tipo I/E recoge los
    pagos de REPs que hayan llegado antes que él."""
    db.execute(
        """
        INSERT INTO cfdi (
            empresa_id, uuid, tipo_comprobante, serie, folio, version,
            rfc_emisor, nombre_emisor, rfc_receptor, nombre_receptor,
            fecha_emision, fecha_timbrado,
            subtotal, descuento, iva_trasladado, iva_retenido, isr_retenido, total,
            metodo_pago, forma_pago, uso_cfdi, moneda, tipo_cambio, xml_raw,
            exportacion, lugar_expedicion,
            domicilio_fiscal_receptor, regimen_fiscal_receptor,
            cfdi_relacionados, es_anticipo_sat
        ) VALUES (
            %s,%s,%s,%s,%s,%s,
            %s,%s,%s,%s,
            %s,%s,
            %s,%s,%s,%s,%s,%s,
            %s,%s,%s,%s,%s,%s,
            %s,%s,%s,%s,
            %s,%s
        )
        ON CONFLICT (uuid) DO NOTHING
        """,
        (
            empresa_id, resultado.uuid, resultado.tipo_comprobante,
            resultado.serie, resultado.folio, resultado.version,
            resultado.rfc_emisor, resultado.nombre_emisor,
            resultado.rfc_receptor, resultado.nombre_receptor,
            resultado.fecha_emision, resultado.fecha_timbrado,
            str(resultado.subtotal), str(resultado.descuento),
            str(resultado.iva_trasladado), str(resultado.iva_retenido),
            str(resultado.isr_retenido), str(resultado.total),
            resultado.metodo_pago, resultado.forma_pago,
            resultado.uso_cfdi, resultado.moneda,
            str(resultado.tipo_cambio),
            xml_bytes.decode("utf-8", errors="replace"),
            resultado.exportacion,
            resultado.lugar_expedicion,
            resultado.domicilio_fiscal_receptor,
            resultado.regimen_fiscal_receptor,
            json.dumps(resultado.cfdi_relacionados),
            resultado.es_anticipo_sat,
        ),
    )

    if resultado.tipo_comprobante == "P":
        if resultado.pagos:
            persistir_complemento_pago(empresa_id, resultado)
    elif resultado.tipo_comprobante in ("I", "E"):
        recalcular_cobrado(empresa_id, resultado.uuid)
