"""DIOT por flujo (F6.2) — lectura y escritura en la base: clasificación por periodo y por CFDI.

Todo cambio y su auditoría van en la misma transacción."""
from __future__ import annotations

from typing import Optional

import psycopg2.extras

from . import db, iva_flujo


def cargar_overrides(empresa_id: str, periodo: str) -> dict:
    """Clasificación del periodo por ``proveedor_id`` (como texto)."""
    filas = db.query_all(
        "SELECT proveedor_id, tipo_tercero, tipo_operacion FROM diot_terceros_periodo WHERE empresa_id = %s AND periodo = %s",
        (empresa_id, periodo),
    )
    return {str(f["proveedor_id"]): {"tipo_tercero": f["tipo_tercero"], "tipo_operacion": f["tipo_operacion"]} for f in filas}


def cargar_operaciones_cfdi(empresa_id: str, periodo: str) -> dict:
    """Tipo de operación asignado a cada CFDI en el periodo, por UUID en mayúsculas."""
    filas = db.query_all("SELECT cfdi_uuid, tipo_operacion FROM diot_operaciones_cfdi WHERE empresa_id = %s AND periodo = %s",
                         (empresa_id, periodo))
    return {iva_flujo.llave(f["cfdi_uuid"]): f["tipo_operacion"] for f in filas}


def _auditar(cur, usuario_id: str, accion: str, empresa_id: str, entidad: str, entidad_id: str, metadata: dict) -> None:
    cur.execute(
        """INSERT INTO auditoria (usuario_id, empresa_id, accion, entidad, entidad_id, metadata)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (usuario_id, empresa_id, accion, entidad, entidad_id, psycopg2.extras.Json(metadata)),
    )


def guardar_tercero_periodo(empresa_id: str, periodo: str, proveedor_id: str, tipo_tercero: Optional[str],
                            tipo_operacion: Optional[str], usuario_id: str) -> None:
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO diot_terceros_periodo (empresa_id, periodo, proveedor_id, tipo_tercero, tipo_operacion, usuario_id)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (empresa_id, periodo, proveedor_id) DO UPDATE
                   SET tipo_tercero = EXCLUDED.tipo_tercero, tipo_operacion = EXCLUDED.tipo_operacion,
                       usuario_id = EXCLUDED.usuario_id, updated_at = NOW()""",
                (empresa_id, periodo, proveedor_id, tipo_tercero, tipo_operacion, usuario_id),
            )
            _auditar(cur, usuario_id, "diot_tercero_periodo", empresa_id, "proveedor", proveedor_id,
                     {"periodo": periodo, "tipo_tercero": tipo_tercero, "tipo_operacion": tipo_operacion})


def quitar_tercero_periodo(empresa_id: str, periodo: str, proveedor_id: str, usuario_id: str) -> bool:
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM diot_terceros_periodo WHERE empresa_id = %s AND periodo = %s AND proveedor_id = %s RETURNING 1",
                        (empresa_id, periodo, proveedor_id))
            if cur.fetchone() is None:
                return False
            _auditar(cur, usuario_id, "diot_tercero_periodo_retirado", empresa_id, "proveedor", proveedor_id, {"periodo": periodo})
            return True


def guardar_operacion_cfdi(empresa_id: str, periodo: str, uuid: str, tipo_operacion: str, usuario_id: str) -> None:
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO diot_operaciones_cfdi (empresa_id, periodo, cfdi_uuid, tipo_operacion, usuario_id)
                   VALUES (%s, %s, UPPER(%s), %s, %s)
                   ON CONFLICT (empresa_id, periodo, cfdi_uuid) DO UPDATE
                   SET tipo_operacion = EXCLUDED.tipo_operacion, usuario_id = EXCLUDED.usuario_id, updated_at = NOW()""",
                (empresa_id, periodo, uuid, tipo_operacion, usuario_id),
            )
            _auditar(cur, usuario_id, "diot_operacion_cfdi", empresa_id, "cfdi", uuid.upper(),
                     {"periodo": periodo, "tipo_operacion": tipo_operacion})


def quitar_operacion_cfdi(empresa_id: str, periodo: str, uuid: str, usuario_id: str) -> bool:
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM diot_operaciones_cfdi WHERE empresa_id = %s AND periodo = %s AND cfdi_uuid = UPPER(%s) RETURNING 1",
                        (empresa_id, periodo, uuid))
            if cur.fetchone() is None:
                return False
            _auditar(cur, usuario_id, "diot_operacion_cfdi_retirada", empresa_id, "cfdi", uuid.upper(), {"periodo": periodo})
            return True
