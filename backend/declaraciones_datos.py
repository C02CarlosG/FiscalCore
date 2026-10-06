"""Declaraciones presentadas (M5): lectura y escritura. El cambio y su auditoría van en la misma transacción.

Historial por (empresa, periodo, impuesto): ``secuencia`` 1 es la normal y 2, 3… las complementarias; la vigente es la
última. Una complementaria se agrega, nunca pisa a la anterior."""
from __future__ import annotations

from typing import Optional

import psycopg2.extras

from . import db

CAMPOS = ("fecha_presentacion", "numero_operacion", "ingresos", "deducciones", "impuesto_trasladado", "impuesto_acreditable",
          "retenciones", "retenciones_a_terceros", "saldo_a_favor_aplicado", "impuesto_a_cargo", "monto_pagado", "notas")


class ConflictoDeclaracion(Exception):
    """La captura contradice el historial (normal sobre una complementaria, o complementaria sin normal)."""


def _publica(fila: Optional[dict]) -> Optional[dict]:
    if fila is None:
        return None
    return {**{k: fila[k] for k in ("periodo", "impuesto", "secuencia", "tipo", *CAMPOS)},
            "fecha_presentacion": fila["fecha_presentacion"].isoformat() if fila["fecha_presentacion"] else None,
            "updated_at": fila["updated_at"].isoformat()}


def cadena(empresa_id: str, periodo: str, impuesto: str) -> list[dict]:
    """Normal y complementarias del periodo, en orden; la vigente es la última."""
    filas = db.query_all(
        "SELECT * FROM declaraciones WHERE empresa_id = %s AND periodo = %s AND impuesto = %s ORDER BY secuencia",
        (empresa_id, periodo, impuesto))
    return [_publica(f) for f in filas]


def del_ejercicio(empresa_id: str, ejercicio: int) -> list[dict]:
    """La declaración vigente de cada periodo e impuesto del ejercicio, con cuántas lleva el historial."""
    filas = db.query_all(
        """SELECT DISTINCT ON (periodo, impuesto) d.*, n.total
           FROM declaraciones d
           JOIN (SELECT periodo, impuesto, COUNT(*) AS total FROM declaraciones
                 WHERE empresa_id = %s AND periodo LIKE %s GROUP BY periodo, impuesto) n USING (periodo, impuesto)
           WHERE d.empresa_id = %s AND d.periodo LIKE %s
           ORDER BY periodo, impuesto, secuencia DESC""",
        (empresa_id, f"{ejercicio:04d}-%", empresa_id, f"{ejercicio:04d}-%"))
    return [{**_publica(f), "declaraciones": f["total"]} for f in filas]


def _auditar(cur, usuario_id: str, accion: str, empresa_id: str, metadata: dict) -> None:
    cur.execute(
        """INSERT INTO auditoria (usuario_id, empresa_id, accion, entidad, entidad_id, metadata)
           VALUES (%s, %s, %s, 'empresa', %s, %s)""",
        (usuario_id, empresa_id, accion, empresa_id, psycopg2.extras.Json(metadata, dumps=_dumps)))


def _dumps(valor) -> str:
    import json
    return json.dumps(valor, default=str)


def guardar(empresa_id: str, periodo: str, impuesto: str, tipo: str, datos: dict, usuario_id: str) -> int:
    """Captura la normal (o corrige la normal mientras no haya complementarias) o agrega una complementaria.
    Devuelve la secuencia guardada. Lanza ``ConflictoDeclaracion`` si contradice el historial."""
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            # candado por (empresa, periodo, impuesto): dos capturas simultáneas no repiten secuencia
            cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"declaracion:{empresa_id}:{periodo}:{impuesto}",))
            cur.execute("SELECT COALESCE(MAX(secuencia), 0) FROM declaraciones WHERE empresa_id = %s AND periodo = %s AND impuesto = %s",
                        (empresa_id, periodo, impuesto))
            maxima = cur.fetchone()[0]
            columnas = ", ".join(CAMPOS)
            marcas = ", ".join(["%s"] * len(CAMPOS))
            valores = [datos.get(c) for c in CAMPOS]
            if tipo == "normal":
                if maxima > 1:
                    raise ConflictoDeclaracion("Ya hay una complementaria: la normal no se puede volver a capturar")
                secuencia = 1
                cur.execute(
                    f"""INSERT INTO declaraciones (empresa_id, periodo, impuesto, secuencia, tipo, {columnas}, usuario_id)
                        VALUES (%s, %s, %s, 1, 'normal', {marcas}, %s)
                        ON CONFLICT (empresa_id, periodo, impuesto, secuencia) DO UPDATE SET
                        {", ".join(f"{c} = EXCLUDED.{c}" for c in CAMPOS)}, usuario_id = EXCLUDED.usuario_id, updated_at = NOW()""",
                    (empresa_id, periodo, impuesto, *valores, usuario_id))
            else:
                if maxima == 0:
                    raise ConflictoDeclaracion("No hay una declaración normal a la que complementar")
                secuencia = maxima + 1
                cur.execute(
                    f"""INSERT INTO declaraciones (empresa_id, periodo, impuesto, secuencia, tipo, {columnas}, usuario_id)
                        VALUES (%s, %s, %s, %s, 'complementaria', {marcas}, %s)""",
                    (empresa_id, periodo, impuesto, secuencia, *valores, usuario_id))
            _auditar(cur, usuario_id, "declaracion_guardada", empresa_id,
                     {"periodo": periodo, "impuesto": impuesto, "tipo": tipo, "secuencia": secuencia,
                      **{c: datos.get(c) for c in CAMPOS}})
            return secuencia


def eliminar_ultima(empresa_id: str, periodo: str, impuesto: str, usuario_id: str) -> bool:
    """Borra la declaración vigente (la última del historial); la anterior vuelve a ser la vigente."""
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"declaracion:{empresa_id}:{periodo}:{impuesto}",))
            cur.execute(
                f"""DELETE FROM declaraciones WHERE id = (
                       SELECT id FROM declaraciones WHERE empresa_id = %s AND periodo = %s AND impuesto = %s
                       ORDER BY secuencia DESC LIMIT 1) RETURNING secuencia, tipo, {", ".join(CAMPOS)}""",
                (empresa_id, periodo, impuesto))
            fila = cur.fetchone()
            if fila is None:
                return False
            # la auditoría conserva lo que se borró: importes y datos de la presentación
            _auditar(cur, usuario_id, "declaracion_eliminada", empresa_id,
                     {"periodo": periodo, "impuesto": impuesto, "secuencia": fila[0], "tipo": fila[1],
                      **dict(zip(CAMPOS, fila[2:]))})
            return True
