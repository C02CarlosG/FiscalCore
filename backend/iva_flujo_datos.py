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


def _siguiente_mes(periodo: str) -> str:
    anio, mes = int(periodo[:4]), int(periodo[5:])
    return f"{anio + (mes == 12):04d}-{mes % 12 + 1:02d}"


def cargar_eventos(empresa_id: str, rfc: str, periodo: str, ajustes: dict) -> list[dict]:
    """Eventos de IVA que pueden caer en ``periodo`` (un mes)."""
    reasignados = sorted({u for (u, _), a in ajustes.items() if a["periodo_destino"] == periodo})
    return _cargar(empresa_id, rfc, f"{periodo}-01", f"{_siguiente_mes(periodo)}-01", reasignados)


def cargar_eventos_ejercicio(empresa_id: str, rfc: str, ejercicio: int, ajustes: dict) -> list[dict]:
    """Eventos de IVA que pueden caer en cualquier mes del ejercicio, en una sola lectura. Con ellos se
    resume mes por mes (``iva_flujo.resumen``) sin volver a consultar la base."""
    reasignados = sorted({u for (u, _), a in ajustes.items()
                          if a["periodo_destino"] and a["periodo_destino"].startswith(f"{ejercicio:04d}-")})
    return _cargar(empresa_id, rfc, f"{ejercicio:04d}-01-01", f"{ejercicio + 1:04d}-01-01", reasignados)


def _cargar(empresa_id: str, rfc: str, desde: str, hasta: str, reasignados: list[str]) -> list[dict]:
    """Eventos cuyo efecto natural cae en ``[desde, hasta)``, más los de los CFDI reasignados a ese rango."""
    docs = db.query_all(
        f"""
        SELECT c.uuid, c.tipo_comprobante, c.metodo_pago, c.forma_pago, c.uso_cfdi, c.estado, c.es_anticipo_sat,
               c.rfc_emisor, c.nombre_emisor, c.rfc_receptor, c.nombre_receptor, c.fecha_emision,
               c.subtotal, c.descuento, c.total, c.iva_trasladado, c.iva_retenido, c.moneda, c.tipo_cambio,
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
                (c.fecha_emision >= %s::date AND c.fecha_emision < %s::date)
             OR (c.metodo_pago = 'PPD' AND UPPER(c.uuid) IN (
                    SELECT UPPER(pr.cfdi_uuid) FROM pagos_relaciones pr JOIN pagos_cfdi pc ON pc.id = pr.pago_id
                    WHERE pc.empresa_id = %s AND pc.fecha_pago >= %s::date AND pc.fecha_pago < %s::date))
             OR UPPER(c.uuid) = ANY(%s)
          )
        """,
        (empresa_id, rfc, rfc, desde, hasta, empresa_id, desde, hasta, reasignados),
    )
    por_uuid = {iva_flujo.llave(d["uuid"]): d for d in docs}

    pagos = db.query_all(
        f"""
        SELECT pc.id AS pago_id, pc.uuid_cfdi_pago AS uuid_pago, pc.fecha_pago, pc.version_pago, pc.monto AS pago_monto,
               agg.suma_equivalente, agg.n_relaciones, np.n_pagos_rep,
               pc.moneda AS pago_moneda, pc.tipo_cambio AS pago_tipo_cambio, pc.forma_pago AS forma_pago_p, rep.estado AS pago_estado,
               pr.cfdi_uuid, pr.parcialidad, pr.importe_pagado, pr.moneda_dr, pr.equivalencia_dr, pr.objeto_imp_dr,
               COALESCE(ri.impuestos, '[]'::json) AS impuestos_dr,
               COALESCE(ip.impuestos, '[]'::json) AS impuestos_p,
               CASE WHEN tot.cfdi_id IS NULL THEN NULL ELSE jsonb_build_object(
                   'total_traslados_iva16', tot.total_traslados_iva16::text,
                   'total_traslados_iva8', tot.total_traslados_iva8::text) END AS totales
        FROM pagos_relaciones pr
        JOIN pagos_cfdi pc ON pc.id = pr.pago_id
        JOIN cfdi rep ON rep.id = pc.cfdi_id
        LEFT JOIN cfdi_pagos_totales tot ON tot.cfdi_id = pc.cfdi_id
        CROSS JOIN LATERAL (
            SELECT SUM(x.importe_pagado / COALESCE(NULLIF(x.equivalencia_dr, 0), 1))::text AS suma_equivalente,
                   COUNT(*) AS n_relaciones
            FROM pagos_relaciones x WHERE x.pago_id = pc.id
        ) agg
        CROSS JOIN LATERAL (SELECT COUNT(*) AS n_pagos_rep FROM pagos_cfdi y WHERE y.cfdi_id = pc.cfdi_id) np
        LEFT JOIN LATERAL (
            SELECT {_FILAS_IMPUESTOS} AS impuestos FROM pagos_impuestos WHERE pago_id = pc.id AND impuesto = '002'
        ) ip ON TRUE
        LEFT JOIN LATERAL (
            SELECT {_FILAS_IMPUESTOS} AS impuestos FROM pagos_relaciones_impuestos WHERE relacion_id = pr.id AND impuesto = '002'
        ) ri ON TRUE
        WHERE pc.empresa_id = %s
          AND ((pc.fecha_pago >= %s::date AND pc.fecha_pago < %s::date) OR UPPER(pr.cfdi_uuid) = ANY(%s))
        """,
        (empresa_id, desde, hasta, reasignados),
    )

    eventos = [e for d in docs for e in iva_flujo.eventos_de_documento(d, rfc)]
    por_pago: dict = {}
    for p in pagos:
        doc: Optional[dict] = por_uuid.get(iva_flujo.llave(p["cfdi_uuid"]))
        if doc is None:
            continue
        nuevos = iva_flujo.eventos_de_pago(p, doc, rfc)
        eventos.extend(nuevos)
        if nuevos:
            grupo = por_pago.setdefault(p["pago_id"], {"pago": p, "filas": 0, "eventos": []})
            grupo["filas"] += 1
            grupo["eventos"].extend(nuevos)
    _marcar_descuadres_de_rep(por_pago)
    return eventos


def _marcar_descuadres_de_rep(por_pago: dict) -> None:
    """Compara, por pago, el IVA a 16 % y 8 % de todos sus documentos con lo que el REP declara. Solo cuando se
    cargaron todos los documentos del pago (con uno reasignado a otro periodo la suma sería parcial) y ninguno quedó
    fuera por una regla automática (su IVA sí está en lo declarado y la comparación saldría falsa); se marcan solo
    los eventos que sí se suman."""
    for grupo in por_pago.values():
        pago = grupo["pago"]
        if grupo["filas"] != int(pago.get("n_relaciones") or 0):
            continue
        for direccion in iva_flujo.DIRECCIONES:
            evs = [e for e in grupo["eventos"] if e["direccion"] == direccion]
            if not evs or any(iva_flujo.motivo_exclusion(e) for e in evs):
                continue
            calculado = sum((e["iva"]["16"] + e["iva"]["8"] for e in evs), iva_flujo.CERO)
            if not iva_flujo.cuadre_rep(pago, calculado):
                for e in evs:
                    e["marcas"].add("descuadre_rep")


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
