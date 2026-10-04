"""Catálogo de proveedores (F6.1) — alimentado de los CFDI recibidos y editable.

Aquí vive la lectura/escritura en la base; las reglas de validación están en el router. Todo cambio
hecho por el contador se audita en la misma transacción (como los ajustes de IVA)."""
from __future__ import annotations

from typing import Optional

import psycopg2.extras

from . import db

CAMPOS_EDITABLES = ("nombre", "tipo_tercero", "tipo_operacion", "pais", "id_fiscal")


def rfc_normalizado(rfc: str) -> str:
    return (rfc or "").strip().upper()


def sincronizar(empresa_id: str, rfc_empresa: str) -> int:
    """Agrega al catálogo los emisores de los CFDI recibidos vigentes que aún no están y actualiza el nombre de
    los que el contador no editó. Idempotente. Devuelve cuántos proveedores se agregaron."""
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH recibidos AS (
                    SELECT DISTINCT ON (UPPER(rfc_emisor)) UPPER(rfc_emisor) AS rfc, COALESCE(nombre_emisor, '') AS nombre
                    FROM cfdi
                    WHERE empresa_id = %s AND estado = 'vigente' AND tipo_comprobante IN ('I', 'E')
                      AND rfc_receptor = %s AND rfc_emisor <> %s
                    ORDER BY UPPER(rfc_emisor), fecha_emision DESC
                )
                INSERT INTO proveedores (empresa_id, rfc, nombre, origen)
                SELECT %s, rfc, nombre, 'cfdi' FROM recibidos
                ON CONFLICT (empresa_id, rfc) DO UPDATE
                   SET nombre = EXCLUDED.nombre, updated_at = NOW()
                   WHERE proveedores.nombre_editado = FALSE AND proveedores.origen = 'cfdi'
                     AND proveedores.nombre IS DISTINCT FROM EXCLUDED.nombre
                RETURNING (xmax = 0) AS nuevo
                """,
                (empresa_id, rfc_empresa, rfc_empresa, empresa_id),
            )
            return sum(1 for f in cur.fetchall() if f[0])


def listar(empresa_id: str, q: Optional[str] = None) -> list[dict]:
    filtro, params = "", [empresa_id]
    if q:
        filtro = " AND (rfc ILIKE %s OR nombre ILIKE %s)"
        params += [f"%{q}%", f"%{q}%"]
    return db.query_all(
        f"""SELECT rfc, nombre, nombre_editado, tipo_tercero, tipo_operacion, pais, id_fiscal, origen,
                   created_at, updated_at
            FROM proveedores WHERE empresa_id = %s{filtro} ORDER BY nombre, rfc""",
        tuple(params),
    )


def obtener(empresa_id: str, rfc: str) -> Optional[dict]:
    return db.query_one(
        """SELECT rfc, nombre, nombre_editado, tipo_tercero, tipo_operacion, pais, id_fiscal, origen,
                  created_at, updated_at FROM proveedores WHERE empresa_id = %s AND rfc = %s""",
        (empresa_id, rfc_normalizado(rfc)),
    )


def _auditar(cur, usuario_id: str, accion: str, empresa_id: str, rfc: str, metadata: dict) -> None:
    cur.execute(
        """INSERT INTO auditoria (usuario_id, empresa_id, accion, entidad, entidad_id, metadata)
           VALUES (%s, %s, %s, 'proveedor', %s, %s)""",
        (usuario_id, empresa_id, accion, rfc, psycopg2.extras.Json(metadata)),
    )


def crear(empresa_id: str, rfc: str, datos: dict, usuario_id: str) -> Optional[dict]:
    """Alta manual. Devuelve ``None`` si el RFC ya está en el catálogo."""
    rfc = rfc_normalizado(rfc)
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO proveedores (empresa_id, rfc, nombre, nombre_editado, tipo_tercero, tipo_operacion,
                                            pais, id_fiscal, origen)
                   VALUES (%s, %s, %s, TRUE, %s, %s, %s, %s, 'manual')
                   ON CONFLICT (empresa_id, rfc) DO NOTHING RETURNING id""",
                (empresa_id, rfc, datos.get("nombre") or "", datos.get("tipo_tercero"), datos.get("tipo_operacion"),
                 datos.get("pais"), datos.get("id_fiscal")),
            )
            if cur.fetchone() is None:
                return None
            _auditar(cur, usuario_id, "proveedor_creado", empresa_id, rfc, datos)
    return obtener(empresa_id, rfc)


def actualizar(empresa_id: str, rfc: str, cambios: dict, usuario_id: str) -> Optional[dict]:
    """Cambia campos del proveedor y lo audita, todo o nada. ``None`` si no existe."""
    rfc = rfc_normalizado(rfc)
    cambios = {k: v for k, v in cambios.items() if k in CAMPOS_EDITABLES}
    if not cambios:
        return obtener(empresa_id, rfc)
    asignaciones = [f"{k} = %s" for k in cambios]
    if "nombre" in cambios:
        asignaciones.append("nombre_editado = TRUE")
    with db.get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT " + ", ".join(cambios) + " FROM proveedores WHERE empresa_id = %s AND rfc = %s FOR UPDATE",
                        (empresa_id, rfc))
            antes = cur.fetchone()
            if antes is None:
                return None
            cur.execute(
                f"UPDATE proveedores SET {', '.join(asignaciones)}, updated_at = NOW() WHERE empresa_id = %s AND rfc = %s",
                (*cambios.values(), empresa_id, rfc),
            )
            _auditar(cur, usuario_id, "proveedor_editado", empresa_id, rfc,
                     {"antes": dict(antes), "despues": cambios})
    return obtener(empresa_id, rfc)
