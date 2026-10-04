"""Catálogo de proveedores (F6.1) — alimentado de los CFDI recibidos y editable.

Aquí vive la lectura/escritura en la base; las reglas de validación están en ``diot_catalogos`` y el router. Todo cambio
hecho por el contador, y la alimentación que agrega proveedores, se audita en la misma transacción."""
from __future__ import annotations

from typing import Optional

import psycopg2.extras

from . import db, diot_catalogos

CAMPOS_EDITABLES = ("nombre", "nombre_editado", "tipo_tercero", "tipo_operacion", "pais", "jurisdiccion_detalle",
                    "id_fiscal", "efectos_fiscales")
_COLUMNAS = ("id, rfc, nombre, nombre_editado, tipo_tercero, tipo_operacion, pais, jurisdiccion_detalle, id_fiscal, "
             "efectos_fiscales, origen, created_at, updated_at")


def rfc_normalizado(rfc: str) -> str:
    return (rfc or "").strip().upper()


def _publico(fila: Optional[dict]) -> Optional[dict]:
    if fila is None:
        return None
    return {**fila, "id": str(fila["id"]), "pendiente": diot_catalogos.pendiente(fila)}


def sincronizar(empresa_id: str, rfc_empresa: str, usuario_id: Optional[str] = None) -> dict:
    """Agrega al catálogo los emisores de los CFDI recibidos vigentes que aún no están y actualiza el nombre de los que el
    contador no editó. Idempotente. Un RFC genérico (extranjero o público en general) entra una vez por nombre; un RFC con
    formato inválido no entra (se cuenta en ``omitidos``). Escribe: si agrega algo, deja el evento
    ``proveedores_sincronizados`` en la auditoría. Devuelve ``{agregados, omitidos}``."""
    rfc_empresa = rfc_normalizado(rfc_empresa)
    with db.get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT DISTINCT ON (UPPER(TRIM(rfc_emisor)), CASE WHEN UPPER(TRIM(rfc_emisor)) IN %s THEN COALESCE(nombre_emisor, '') END)
                       UPPER(TRIM(rfc_emisor)) AS rfc, COALESCE(nombre_emisor, '') AS nombre
                FROM cfdi
                WHERE empresa_id = %s AND estado = 'vigente' AND tipo_comprobante IN ('I', 'E')
                  AND UPPER(TRIM(rfc_receptor)) = %s AND UPPER(TRIM(rfc_emisor)) <> %s
                ORDER BY UPPER(TRIM(rfc_emisor)), CASE WHEN UPPER(TRIM(rfc_emisor)) IN %s THEN COALESCE(nombre_emisor, '') END,
                         fecha_emision DESC
                """,
                (tuple(diot_catalogos.RFC_GENERICOS), empresa_id, rfc_empresa, rfc_empresa, tuple(diot_catalogos.RFC_GENERICOS)),
            )
            emisores = cur.fetchall()
            agregados = omitidos = 0
            for e in emisores:
                rfc, nombre = e["rfc"], e["nombre"]
                if not diot_catalogos.es_rfc_valido(rfc):
                    omitidos += 1
                    continue
                if rfc in diot_catalogos.RFC_GENERICOS:
                    cur.execute(
                        """INSERT INTO proveedores (empresa_id, rfc, nombre, tipo_tercero, tipo_operacion, origen)
                           VALUES (%s, %s, %s, %s, %s, 'cfdi')
                           ON CONFLICT (empresa_id, rfc, nombre) WHERE rfc IN ('XEXX010101000', 'XAXX010101000') AND origen = 'cfdi'
                           DO NOTHING RETURNING 1""",
                        (empresa_id, rfc, nombre, diot_catalogos.tipo_tercero_por_defecto(rfc), diot_catalogos.OPERACION_POR_DEFECTO),
                    )
                else:
                    cur.execute(
                        """INSERT INTO proveedores (empresa_id, rfc, nombre, tipo_tercero, tipo_operacion, origen)
                           VALUES (%s, %s, %s, %s, %s, 'cfdi')
                           ON CONFLICT (empresa_id, rfc) WHERE rfc NOT IN ('XEXX010101000', 'XAXX010101000') DO UPDATE
                              SET nombre = EXCLUDED.nombre, updated_at = NOW()
                              WHERE proveedores.nombre_editado = FALSE AND proveedores.origen = 'cfdi'
                                AND proveedores.nombre IS DISTINCT FROM EXCLUDED.nombre
                           RETURNING (xmax = 0) AS nuevo""",
                        (empresa_id, rfc, nombre, diot_catalogos.tipo_tercero_por_defecto(rfc), diot_catalogos.OPERACION_POR_DEFECTO),
                    )
                fila = cur.fetchone()
                if fila and (fila.get("nuevo", True) if isinstance(fila, dict) else True):
                    agregados += 1
            if agregados:
                _auditar(cur, usuario_id, "proveedores_sincronizados", empresa_id, empresa_id,
                         {"agregados": agregados, "omitidos": omitidos})
    return {"agregados": agregados, "omitidos": omitidos}


def listar(empresa_id: str, q: Optional[str] = None) -> list[dict]:
    filtro, params = "", [empresa_id]
    if q:
        filtro = " AND (rfc ILIKE %s OR nombre ILIKE %s OR id_fiscal ILIKE %s)"
        params += [f"%{q}%"] * 3
    filas = db.query_all(f"SELECT {_COLUMNAS} FROM proveedores WHERE empresa_id = %s{filtro} ORDER BY nombre, rfc", tuple(params))
    return [_publico(f) for f in filas]


def obtener(empresa_id: str, proveedor_id: str) -> Optional[dict]:
    return _publico(db.query_one(f"SELECT {_COLUMNAS} FROM proveedores WHERE empresa_id = %s AND id = %s",
                                 (empresa_id, proveedor_id)))


def _auditar(cur, usuario_id: Optional[str], accion: str, empresa_id: str, entidad_id: str, metadata: dict) -> None:
    cur.execute(
        """INSERT INTO auditoria (usuario_id, empresa_id, accion, entidad, entidad_id, metadata)
           VALUES (%s, %s, %s, 'proveedor', %s, %s)""",
        (usuario_id, empresa_id, accion, entidad_id, psycopg2.extras.Json(metadata)),
    )


class Duplicado(Exception):
    """El RFC (o el ID fiscal del extranjero) ya está en el catálogo."""


def crear(empresa_id: str, rfc: str, datos: dict, usuario_id: str) -> dict:
    """Alta manual. ``Duplicado`` si el RFC (no genérico) o el ID fiscal del extranjero ya existen."""
    rfc = rfc_normalizado(rfc)
    try:
        with db.get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """INSERT INTO proveedores (empresa_id, rfc, nombre, nombre_editado, tipo_tercero, tipo_operacion,
                                                pais, jurisdiccion_detalle, id_fiscal, efectos_fiscales, origen)
                       VALUES (%s, %s, %s, TRUE, %s, %s, %s, %s, %s, %s, 'manual') RETURNING id""",
                    (empresa_id, rfc, datos.get("nombre") or "", datos.get("tipo_tercero"), datos.get("tipo_operacion"),
                     datos.get("pais"), datos.get("jurisdiccion_detalle"), datos.get("id_fiscal"), datos.get("efectos_fiscales")),
                )
                nuevo = str(cur.fetchone()["id"])
                _auditar(cur, usuario_id, "proveedor_creado", empresa_id, nuevo, {"rfc": rfc, **datos})
    except psycopg2.errors.UniqueViolation as exc:
        raise Duplicado() from exc
    return obtener(empresa_id, nuevo)


def actualizar(empresa_id: str, proveedor_id: str, cambios: dict, usuario_id: str) -> Optional[dict]:
    """Cambia campos del proveedor y lo audita, todo o nada. ``None`` si no existe; ``Duplicado`` si el nuevo ID fiscal
    choca con otro extranjero. Editar el nombre lo protege de la alimentación; ``nombre_editado=False`` la reactiva."""
    cambios = {k: v for k, v in cambios.items() if k in CAMPOS_EDITABLES}
    if "nombre" in cambios and "nombre_editado" not in cambios:
        cambios["nombre_editado"] = True
    if not cambios:
        return obtener(empresa_id, proveedor_id)
    try:
        with db.get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT " + ", ".join(cambios) + " FROM proveedores WHERE empresa_id = %s AND id = %s FOR UPDATE",
                            (empresa_id, proveedor_id))
                antes = cur.fetchone()
                if antes is None:
                    return None
                cur.execute(
                    f"UPDATE proveedores SET {', '.join(f'{k} = %s' for k in cambios)}, updated_at = NOW() "
                    "WHERE empresa_id = %s AND id = %s",
                    (*cambios.values(), empresa_id, proveedor_id),
                )
                _auditar(cur, usuario_id, "proveedor_editado", empresa_id, proveedor_id,
                         {"antes": dict(antes), "despues": cambios})
    except psycopg2.errors.UniqueViolation as exc:
        raise Duplicado() from exc
    return obtener(empresa_id, proveedor_id)


def estado_para_validar(empresa_id: str, proveedor_id: str, cambios: dict) -> Optional[dict]:
    """El proveedor tal como quedaría después de aplicar ``cambios`` (para validar reglas cruzadas); ``None`` si no existe."""
    actual = obtener(empresa_id, proveedor_id)
    return None if actual is None else {**actual, **cambios}
