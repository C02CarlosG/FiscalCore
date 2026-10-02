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
import logging

from . import db

_log = logging.getLogger(__name__)

# Versión del extractor de detalle. Subirla cuando el parser extraiga algo nuevo
# hace que reproceso.reprocesar_detalle vuelva a tomar los CFDI ya guardados.
DETALLE_VERSION = 1


def _tasa(valor):
    """Decimal opcional a texto para la base (None se conserva como NULL)."""
    return None if valor is None else str(valor)


def _en_transaccion(sentencias: list[tuple[str, tuple]]) -> None:
    """Ejecuta varias sentencias en una sola transacción: todas o ninguna."""
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            for sql, params in sentencias:
                cur.execute(sql, params)


def _sentencias_impuestos(tabla: str, columna_fk: str, fk_id: str, impuestos) -> list[tuple[str, tuple]]:
    """Borrar e insertar los impuestos de un CFDI o de una relación de pago.
    ``tabla`` y ``columna_fk`` son constantes internas, nunca entrada externa."""
    sentencias: list[tuple[str, tuple]] = [(f"DELETE FROM {tabla} WHERE {columna_fk} = %s", (fk_id,))]
    if not impuestos:
        return sentencias
    params: list = []
    for i in impuestos:
        params += [fk_id, i.ambito, i.impuesto, i.tipo_factor, _tasa(i.tasa_o_cuota), str(i.base), str(i.importe)]
    sentencias.append((
        f"INSERT INTO {tabla} ({columna_fk}, ambito, impuesto, tipo_factor, tasa_o_cuota, base, importe) VALUES "
        + ",".join(["(%s,%s,%s,%s,%s,%s,%s)"] * len(impuestos)),
        tuple(params),
    ))
    return sentencias


def _sentencias_conceptos(cfdi_id: str, conceptos) -> list[tuple[str, tuple]]:
    sentencias: list[tuple[str, tuple]] = [("DELETE FROM cfdi_conceptos WHERE cfdi_id = %s", (cfdi_id,))]
    if not conceptos:
        return sentencias
    params: list = []
    for c in conceptos:
        impuestos = [
            {"ambito": i.ambito, "impuesto": i.impuesto, "tipo_factor": i.tipo_factor,
             "tasa_o_cuota": _tasa(i.tasa_o_cuota), "base": str(i.base), "importe": str(i.importe)}
            for i in c.impuestos
        ]
        params += [
            cfdi_id, c.linea, c.clave_prod_serv, c.no_identificacion, str(c.cantidad),
            c.clave_unidad, c.unidad, c.descripcion, str(c.valor_unitario), str(c.importe),
            str(c.descuento), c.objeto_imp, c.cuenta_predial, json.dumps(impuestos),
        ]
    sentencias.append((
        """INSERT INTO cfdi_conceptos (
               cfdi_id, linea, clave_prod_serv, no_identificacion, cantidad,
               clave_unidad, unidad, descripcion, valor_unitario, importe,
               descuento, objeto_imp, cuenta_predial, impuestos
           ) VALUES """
        + ",".join(["(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"] * len(conceptos)),
        tuple(params),
    ))
    return sentencias


def guardar_detalle(empresa_id: str, resultado) -> bool:
    """Guarda encabezados adicionales, impuestos por tasa y conceptos de un CFDI
    ya insertado, y lo marca con ``DETALLE_VERSION``. Todo en una transacción:
    o queda completo o queda como estaba (un fallo no borra lo ya guardado ni
    marca como completo un detalle a medias). Devuelve False si el CFDI no
    existe en esa empresa."""
    fila = db.query_one(
        "SELECT id FROM cfdi WHERE uuid = %s AND empresa_id = %s", (resultado.uuid, empresa_id)
    )
    if not fila:
        return False
    cfdi_id = str(fila["id"])
    n = resultado.nomina

    def _nomina(campo: str):
        return str(getattr(n, campo)) if n is not None else None

    _en_transaccion([
        (
            """
            UPDATE cfdi SET
                regimen_emisor = %s, condiciones_pago = %s, no_certificado = %s,
                periodicidad = %s, meses = %s, anio_global = %s,
                nomina_percepciones = %s, nomina_deducciones = %s, nomina_otros_pagos = %s,
                nomina_gravado = %s, nomina_exento = %s, nomina_isr_retenido = %s,
                detalle_version = %s
            WHERE id = %s
            """,
            (
                resultado.regimen_emisor, resultado.condiciones_pago, resultado.no_certificado,
                resultado.periodicidad, resultado.meses, resultado.anio_global,
                _nomina("total_percepciones"), _nomina("total_deducciones"), _nomina("total_otros_pagos"),
                _nomina("total_gravado"), _nomina("total_exento"), _nomina("isr_retenido"),
                DETALLE_VERSION, cfdi_id,
            ),
        ),
        *_sentencias_impuestos("cfdi_impuestos", "cfdi_id", cfdi_id, resultado.resumen_impuestos),
        *_sentencias_conceptos(cfdi_id, resultado.conceptos),
    ])
    return True


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
        db.execute("UPDATE pagos_cfdi SET version_pago = %s WHERE id = %s", (pago.version, pago_db_id))

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
            relacion = db.query_one(
                """SELECT id FROM pagos_relaciones
                   WHERE pago_id = %s AND cfdi_uuid = %s
                     AND COALESCE(parcialidad, 0) = COALESCE(%s, 0)""",
                (pago_db_id, docto_uuid, docto.num_parcialidad),
            )
            if relacion:
                relacion_id = str(relacion["id"])
                _en_transaccion([
                    (
                        "UPDATE pagos_relaciones SET moneda_dr = %s, equivalencia_dr = %s WHERE id = %s",
                        (docto.moneda_dr, _tasa(docto.equivalencia_dr), relacion_id),
                    ),
                    *_sentencias_impuestos(
                        "pagos_relaciones_impuestos", "relacion_id", relacion_id, docto.impuestos),
                ])
            if docto_uuid not in uuids_afectados:
                uuids_afectados.append(docto_uuid)

    for uuid in uuids_afectados:
        recalcular_cobrado(empresa_id, uuid)


def insertar_cfdi(empresa_id: str, resultado, xml_bytes: bytes) -> None:
    """Inserta un CFDIParsed (ignora duplicados por UUID) y aplica sus efectos
    sobre pagos: un tipo P registra su complemento; un tipo I/E recoge los
    pagos de REPs que hayan llegado antes que él.

    El detalle fiscal se guarda al final y solo para un CFDI recién insertado:
    si falla, lo cobrado ya quedó aplicado y el CFDI queda con
    ``detalle_version = 0`` para ``reproceso.reprocesar_detalle``. Un UUID que
    ya existía conserva su registro y su detalle (salen del primer XML)."""
    insertado = db.execute(
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
        RETURNING id
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
        returning=True,
    ) is not None

    if resultado.tipo_comprobante == "P":
        if resultado.pagos:
            persistir_complemento_pago(empresa_id, resultado)
    elif resultado.tipo_comprobante in ("I", "E"):
        recalcular_cobrado(empresa_id, resultado.uuid)

    if insertado:
        try:
            guardar_detalle(empresa_id, resultado)
        except Exception:
            _log.exception(
                "cfdi_store: no se pudo guardar el detalle de %s; queda para reproceso", resultado.uuid)
