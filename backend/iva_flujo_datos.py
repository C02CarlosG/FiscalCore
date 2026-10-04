"""IVA base flujo (F5.1) — lectura de la base de datos para el motor ``iva_flujo``.

Carga los CFDI y los pagos que pueden afectar a un periodo (los PUE y notas de crédito
emitidos en él, los PPD con un pago en él y los reasignados a él) y los ajustes de la
empresa; el motor decide qué cuenta y cómo. Los importes salen como texto para no perder
precisión al pasar por JSON.
"""
from __future__ import annotations

from typing import Optional

import psycopg2.extras

from . import db, iva_flujo

_FILAS_IMPUESTOS = """
    json_agg(json_build_object(
        'ambito', ambito, 'impuesto', impuesto, 'tipo_factor', tipo_factor,
        'tasa_o_cuota', tasa_o_cuota::text, 'base', base::text, 'importe', importe::text))
"""

_MES = "(%s || '-01')::date"


def cargar_ajustes(empresa_id: str) -> dict:
    """Ajustes de la empresa por ``(UUID en mayúsculas, dirección)``."""
    filas = db.query_all(
        "SELECT cfdi_uuid, direccion, accion, periodo_destino, motivo FROM iva_ajustes WHERE empresa_id = %s",
        (empresa_id,),
    )
    return {
        (iva_flujo.llave(f["cfdi_uuid"]), f["direccion"]): {
            "accion": f["accion"],
            "periodo_destino": f["periodo_destino"],
            "motivo": f["motivo"],
        }
        for f in filas
    }


def cargar_eventos(empresa_id: str, rfc: str, periodo: str, ajustes: dict) -> list[dict]:
    """Eventos de IVA que pueden caer en ``periodo``."""
    reasignados = sorted({u for (u, _), a in ajustes.items() if a["periodo_destino"] == periodo})

    docs = db.query_all(
        f"""
        SELECT c.uuid, c.tipo_comprobante, c.metodo_pago, c.forma_pago, c.uso_cfdi, c.estado, c.es_anticipo_sat,
               c.rfc_emisor, c.nombre_emisor, c.rfc_receptor, c.nombre_receptor, c.fecha_emision,
               c.subtotal, c.descuento, c.total, c.iva_trasladado, c.moneda, c.tipo_cambio,
               COALESCE(i.impuestos, '[]'::json) AS impuestos,
               COALESCE(n.base, 0) AS no_objeto,
               COALESCE(rel.info, '[]'::json) AS relacionados_info
        FROM cfdi c
        LEFT JOIN LATERAL (
            SELECT {_FILAS_IMPUESTOS} AS impuestos FROM cfdi_impuestos WHERE cfdi_id = c.id AND impuesto = '002'
        ) i ON TRUE
        LEFT JOIN LATERAL (
            SELECT SUM(importe - descuento) AS base FROM cfdi_conceptos WHERE cfdi_id = c.id AND objeto_imp = '01'
        ) n ON TRUE
        LEFT JOIN LATERAL (
            -- CFDI que un Egreso relaciona: define si su aplicación ya está en un REP y si el original se acreditó
            SELECT json_agg(json_build_object(
                       'metodo_pago', o.metodo_pago, 'forma_pago', o.forma_pago, 'uso_cfdi', o.uso_cfdi,
                       'total', o.total::text, 'moneda', o.moneda, 'tipo_cambio', o.tipo_cambio::text)) AS info
            FROM jsonb_array_elements(COALESCE(c.cfdi_relacionados, '[]'::jsonb)) r,
                 jsonb_array_elements_text(COALESCE(r->'uuids', '[]'::jsonb)) u
            JOIN cfdi o ON o.empresa_id = c.empresa_id AND UPPER(o.uuid) = UPPER(u)
            WHERE c.tipo_comprobante = 'E'
        ) rel ON TRUE
        WHERE c.empresa_id = %s
          AND c.estado = 'vigente'
          AND c.tipo_comprobante IN ('I', 'E')
          AND (c.rfc_emisor = %s OR c.rfc_receptor = %s)
          AND (
                (c.fecha_emision >= {_MES} AND c.fecha_emision < {_MES} + INTERVAL '1 month')
             OR (c.metodo_pago = 'PPD' AND UPPER(c.uuid) IN (
                    SELECT UPPER(pr.cfdi_uuid) FROM pagos_relaciones pr JOIN pagos_cfdi pc ON pc.id = pr.pago_id
                    WHERE pc.empresa_id = %s AND pc.fecha_pago >= {_MES} AND pc.fecha_pago < {_MES} + INTERVAL '1 month'))
             OR UPPER(c.uuid) = ANY(%s)
          )
        """,
        (empresa_id, rfc, rfc, periodo, periodo, empresa_id, periodo, periodo, reasignados),
    )
    por_uuid = {iva_flujo.llave(d["uuid"]): d for d in docs}

    pagos = db.query_all(
        f"""
        SELECT pc.uuid_cfdi_pago AS uuid_pago, pc.fecha_pago, pc.version_pago, pc.moneda AS pago_moneda,
               pc.tipo_cambio AS pago_tipo_cambio, rep.estado AS pago_estado,
               pr.cfdi_uuid, pr.parcialidad, pr.importe_pagado, pr.moneda_dr, pr.equivalencia_dr,
               COALESCE(ri.impuestos, '[]'::json) AS impuestos_dr
        FROM pagos_relaciones pr
        JOIN pagos_cfdi pc ON pc.id = pr.pago_id
        JOIN cfdi rep ON rep.id = pc.cfdi_id
        LEFT JOIN LATERAL (
            SELECT {_FILAS_IMPUESTOS} AS impuestos FROM pagos_relaciones_impuestos WHERE relacion_id = pr.id AND impuesto = '002'
        ) ri ON TRUE
        WHERE pc.empresa_id = %s
          AND ((pc.fecha_pago >= {_MES} AND pc.fecha_pago < {_MES} + INTERVAL '1 month') OR UPPER(pr.cfdi_uuid) = ANY(%s))
        """,
        (empresa_id, periodo, periodo, reasignados),
    )

    eventos = [e for d in docs for e in iva_flujo.eventos_de_documento(d, rfc)]
    for p in pagos:
        doc: Optional[dict] = por_uuid.get(iva_flujo.llave(p["cfdi_uuid"]))
        if doc is None:
            continue
        eventos.extend(iva_flujo.eventos_de_pago(p, doc, rfc))
    return eventos


# ── Ajustes: el cambio y su auditoría van en la misma transacción ─────────────

def _auditar(cur, usuario_id: str, accion: str, empresa_id: str, uuid: str, metadata: dict) -> None:
    """Inserta en ``auditoria`` con el cursor de la transacción en curso. A diferencia de
    ``auditoria.registrar_evento`` (que nunca falla), aquí un error sí deshace el ajuste:
    el plan exige que excluir y reasignar queden siempre auditados."""
    cur.execute(
        """INSERT INTO auditoria (usuario_id, empresa_id, accion, entidad, entidad_id, metadata)
           VALUES (%s, %s, %s, 'cfdi', %s, %s)""",
        (usuario_id, empresa_id, accion, uuid, psycopg2.extras.Json(metadata)),
    )


def guardar_ajuste(empresa_id: str, uuid: str, direccion: str, accion: str,
                   periodo_destino: Optional[str], motivo: str, usuario_id: str) -> None:
    """Crea o reemplaza el ajuste de un CFDI y lo audita, todo o nada."""
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO iva_ajustes (empresa_id, cfdi_uuid, direccion, accion, periodo_destino, motivo, usuario_id)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (empresa_id, cfdi_uuid, direccion) DO UPDATE
                   SET accion = EXCLUDED.accion, periodo_destino = EXCLUDED.periodo_destino, motivo = EXCLUDED.motivo,
                       usuario_id = EXCLUDED.usuario_id, updated_at = NOW()""",
                (empresa_id, uuid, direccion, accion, periodo_destino, motivo, usuario_id),
            )
            _auditar(cur, usuario_id, "iva_ajuste", empresa_id, uuid,
                     {"direccion": direccion, "accion": accion, "periodo_destino": periodo_destino, "motivo": motivo})


def quitar_ajuste(empresa_id: str, uuid: str, direccion: str, usuario_id: str) -> Optional[dict]:
    """Retira un ajuste y lo audita, todo o nada. Devuelve el ajuste retirado o ``None`` si no existía."""
    with db.get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """DELETE FROM iva_ajustes WHERE empresa_id = %s AND cfdi_uuid = UPPER(%s) AND direccion = %s
                   RETURNING accion, periodo_destino""",
                (empresa_id, uuid, direccion),
            )
            fila = cur.fetchone()
            if fila is None:
                return None
            _auditar(cur, usuario_id, "iva_ajuste_retirado", empresa_id, uuid.upper(),
                     {"direccion": direccion, "accion": fila["accion"], "periodo_destino": fila["periodo_destino"]})
            return dict(fila)
