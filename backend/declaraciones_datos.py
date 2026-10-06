"""Declaraciones presentadas (M5): lectura y escritura. El cambio y su auditoría van en la misma transacción."""
from __future__ import annotations

from typing import Optional

import psycopg2.extras

from . import db

CAMPOS = ("tipo", "fecha_presentacion", "numero_operacion", "ingresos", "deducciones", "impuesto_trasladado",
          "impuesto_acreditable", "retenciones", "impuesto_a_cargo", "monto_pagado", "notas")


def _publica(fila: Optional[dict]) -> Optional[dict]:
    if fila is None:
        return None
    return {**{k: fila[k] for k in ("periodo", "impuesto", *CAMPOS)},
            "fecha_presentacion": fila["fecha_presentacion"].isoformat() if fila["fecha_presentacion"] else None,
            "updated_at": fila["updated_at"].isoformat()}


def obtener(empresa_id: str, periodo: str, impuesto: str) -> Optional[dict]:
    return _publica(db.query_one(
        "SELECT * FROM declaraciones WHERE empresa_id = %s AND periodo = %s AND impuesto = %s",
        (empresa_id, periodo, impuesto)))


def del_ejercicio(empresa_id: str, ejercicio: int) -> list[dict]:
    filas = db.query_all(
        "SELECT * FROM declaraciones WHERE empresa_id = %s AND periodo LIKE %s ORDER BY periodo, impuesto",
        (empresa_id, f"{ejercicio:04d}-%"))
    return [_publica(f) for f in filas]


def guardar(empresa_id: str, periodo: str, impuesto: str, datos: dict, usuario_id: str) -> None:
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            columnas = ", ".join(CAMPOS)
            marcas = ", ".join(["%s"] * len(CAMPOS))
            cur.execute(
                f"""INSERT INTO declaraciones (empresa_id, periodo, impuesto, {columnas}, usuario_id)
                    VALUES (%s, %s, %s, {marcas}, %s)
                    ON CONFLICT (empresa_id, periodo, impuesto) DO UPDATE SET
                    {", ".join(f"{c} = EXCLUDED.{c}" for c in CAMPOS)}, usuario_id = EXCLUDED.usuario_id, updated_at = NOW()""",
                (empresa_id, periodo, impuesto, *(datos.get(c) for c in CAMPOS), usuario_id))
            cur.execute(
                """INSERT INTO auditoria (usuario_id, empresa_id, accion, entidad, entidad_id, metadata)
                   VALUES (%s, %s, 'declaracion_guardada', 'empresa', %s, %s)""",
                (usuario_id, empresa_id, empresa_id, psycopg2.extras.Json(
                    {"periodo": periodo, "impuesto": impuesto, "tipo": datos.get("tipo"),
                     "impuesto_a_cargo": str(datos.get("impuesto_a_cargo")), "monto_pagado": str(datos.get("monto_pagado"))})))


def eliminar(empresa_id: str, periodo: str, impuesto: str, usuario_id: str) -> bool:
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM declaraciones WHERE empresa_id = %s AND periodo = %s AND impuesto = %s RETURNING 1",
                        (empresa_id, periodo, impuesto))
            if cur.fetchone() is None:
                return False
            cur.execute(
                """INSERT INTO auditoria (usuario_id, empresa_id, accion, entidad, entidad_id, metadata)
                   VALUES (%s, %s, 'declaracion_eliminada', 'empresa', %s, %s)""",
                (usuario_id, empresa_id, empresa_id, psycopg2.extras.Json({"periodo": periodo, "impuesto": impuesto})))
            return True
