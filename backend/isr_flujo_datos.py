"""ISR base flujo (F7.1) — lectura y escritura en la base para el motor ``isr_flujo``.

Carga los CFDI, los pagos de los REP y las nóminas del ejercicio hasta un periodo, los ajustes del contador y el
porcentaje de nómina exenta; el motor decide qué cuenta y cómo."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

import psycopg2.extras

from . import db, isr_flujo


def cargar_ajustes(empresa_id: str) -> dict:
    """Ajustes de la empresa por ``(UUID en mayúsculas, lado)``."""
    filas = db.query_all("SELECT cfdi_uuid, lado, motivo FROM isr_ajustes WHERE empresa_id = %s", (empresa_id,))
    return {(isr_flujo.llave(f["cfdi_uuid"]), f["lado"]): {"accion": "excluir", "motivo": f["motivo"]} for f in filas}


def porcentaje_nomina_exenta(empresa_id: str, ejercicio: int) -> Decimal:
    fila = db.query_one("SELECT pct_nomina_exenta FROM isr_config_flujo WHERE empresa_id = %s AND ejercicio = %s",
                        (empresa_id, ejercicio))
    return Decimal(str(fila["pct_nomina_exenta"])) if fila else isr_flujo.PORCENTAJE_NOMINA_EXENTA


def _siguiente_mes(periodo: str) -> str:
    anio, mes = int(periodo[:4]), int(periodo[5:])
    return f"{anio + (mes == 12):04d}-{mes % 12 + 1:02d}"


def cargar_eventos(empresa_id: str, rfc: str, periodo: str) -> list[dict]:
    """Eventos de ISR del 1 de enero del ejercicio al fin de ``periodo`` (el motor separa mes y acumulado)."""
    desde, hasta = f"{periodo[:4]}-01-01", f"{_siguiente_mes(periodo)}-01"
    docs = db.query_all(
        """
        SELECT c.uuid, c.tipo_comprobante, c.metodo_pago, c.forma_pago, c.uso_cfdi, c.estado, c.es_anticipo_sat,
               c.rfc_emisor, c.nombre_emisor, c.rfc_receptor, c.nombre_receptor, c.fecha_emision,
               c.subtotal, c.descuento, c.total, c.isr_retenido, c.moneda, c.tipo_cambio,
               COALESCE(rel.info, '[]'::json) AS relacionados_info
        FROM cfdi c
        LEFT JOIN LATERAL (
            -- CFDI que un Egreso relaciona: define si su aplicación ya está en un REP y si el original se dedujo
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
                (c.fecha_emision >= %s::date AND c.fecha_emision < %s::date)
             OR (c.metodo_pago = 'PPD' AND UPPER(c.uuid) IN (
                    SELECT UPPER(pr.cfdi_uuid) FROM pagos_relaciones pr JOIN pagos_cfdi pc ON pc.id = pr.pago_id
                    WHERE pc.empresa_id = %s AND pc.fecha_pago >= %s::date AND pc.fecha_pago < %s::date))
          )
        """,
        (empresa_id, rfc, rfc, desde, hasta, empresa_id, desde, hasta),
    )
    por_uuid = {isr_flujo.llave(d["uuid"]): d for d in docs}
    pagos = db.query_all(
        """
        SELECT pc.uuid_cfdi_pago AS uuid_pago, pc.fecha_pago, pc.version_pago, pc.moneda AS pago_moneda,
               pc.tipo_cambio AS pago_tipo_cambio, rep.estado AS pago_estado,
               pr.cfdi_uuid, pr.parcialidad, pr.importe_pagado, pr.moneda_dr, pr.equivalencia_dr
        FROM pagos_relaciones pr
        JOIN pagos_cfdi pc ON pc.id = pr.pago_id
        JOIN cfdi rep ON rep.id = pc.cfdi_id
        WHERE pc.empresa_id = %s AND pc.fecha_pago >= %s::date AND pc.fecha_pago < %s::date
        """,
        (empresa_id, desde, hasta),
    )
    eventos = [e for d in docs for e in isr_flujo.eventos_de_documento(d, rfc)]
    for p in pagos:
        doc: Optional[dict] = por_uuid.get(isr_flujo.llave(p["cfdi_uuid"]))
        if doc is not None:
            eventos.extend(isr_flujo.eventos_de_pago(p, doc, rfc))
    for n in _cargar_nominas(empresa_id, rfc, desde, hasta):
        ev = isr_flujo.evento_de_nomina(n)
        if ev:
            eventos.append(ev)
    return eventos


def _cargar_nominas(empresa_id: str, rfc: str, desde: str, hasta: str) -> list[dict]:
    """Nóminas (tipo N) emitidas por la empresa, con sus percepciones por tipo, en su fecha de pago."""
    return db.query_all(
        """
        SELECT c.uuid, c.estado, c.fecha_emision, c.rfc_emisor, c.nombre_emisor, c.rfc_receptor, c.nombre_receptor,
               nn.fecha_pago, nn.isr_retenido, COALESCE(p.percepciones, '[]'::json) AS percepciones
        FROM cfdi c
        JOIN LATERAL (
            SELECT COALESCE(MIN(n.fecha_pago), c.fecha_emision::date) AS fecha_pago,
                   COALESCE(SUM(n.total_impuestos_retenidos), 0) AS isr_retenido
            FROM cfdi_nominas n WHERE n.cfdi_id = c.id
        ) nn ON TRUE
        LEFT JOIN LATERAL (
            SELECT json_agg(json_build_object('tipo', k.tipo, 'gravado', k.importe_gravado::text, 'exento', k.importe_exento::text)) AS percepciones
            FROM cfdi_nominas n JOIN cfdi_nomina_conceptos k ON k.nomina_id = n.id AND k.categoria = 'percepcion'
            WHERE n.cfdi_id = c.id
        ) p ON TRUE
        WHERE c.empresa_id = %s AND c.estado = 'vigente' AND c.tipo_comprobante = 'N' AND c.rfc_emisor = %s
          AND nn.fecha_pago >= %s::date AND nn.fecha_pago < %s::date
        """,
        (empresa_id, rfc, desde, hasta),
    )


# ── escritura: el cambio y su auditoría van en la misma transacción ──────────

def _auditar(cur, usuario_id: str, accion: str, empresa_id: str, entidad: str, entidad_id: str, metadata: dict) -> None:
    cur.execute(
        """INSERT INTO auditoria (usuario_id, empresa_id, accion, entidad, entidad_id, metadata)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (usuario_id, empresa_id, accion, entidad, entidad_id, psycopg2.extras.Json(metadata)),
    )


def guardar_ajuste(empresa_id: str, uuid: str, lado: str, motivo: str, usuario_id: str) -> None:
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO isr_ajustes (empresa_id, cfdi_uuid, lado, motivo, usuario_id)
                   VALUES (%s, UPPER(%s), %s, %s, %s)
                   ON CONFLICT (empresa_id, cfdi_uuid, lado) DO UPDATE
                   SET motivo = EXCLUDED.motivo, usuario_id = EXCLUDED.usuario_id, updated_at = NOW()""",
                (empresa_id, uuid, lado, motivo, usuario_id),
            )
            _auditar(cur, usuario_id, "isr_ajuste", empresa_id, "cfdi", uuid.upper(), {"lado": lado, "accion": "excluir", "motivo": motivo})


def quitar_ajuste(empresa_id: str, uuid: str, lado: str, usuario_id: str) -> bool:
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM isr_ajustes WHERE empresa_id = %s AND cfdi_uuid = UPPER(%s) AND lado = %s RETURNING 1",
                        (empresa_id, uuid, lado))
            if cur.fetchone() is None:
                return False
            _auditar(cur, usuario_id, "isr_ajuste_retirado", empresa_id, "cfdi", uuid.upper(), {"lado": lado})
            return True


def guardar_porcentaje(empresa_id: str, ejercicio: int, porcentaje: Decimal, usuario_id: str) -> None:
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO isr_config_flujo (empresa_id, ejercicio, pct_nomina_exenta, usuario_id)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (empresa_id, ejercicio) DO UPDATE
                   SET pct_nomina_exenta = EXCLUDED.pct_nomina_exenta, usuario_id = EXCLUDED.usuario_id, updated_at = NOW()""",
                (empresa_id, ejercicio, porcentaje, usuario_id),
            )
            _auditar(cur, usuario_id, "isr_config_flujo", empresa_id, "empresa", empresa_id,
                     {"ejercicio": ejercicio, "pct_nomina_exenta": str(porcentaje)})
