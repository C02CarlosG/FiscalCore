"""Lista 69-B del SAT: importación atómica, estado y consulta por RFC (spec 2026-10-13-efos-69b-design)."""
from __future__ import annotations

import hashlib
from datetime import date
from typing import Iterable, Optional

import psycopg2.extras

from . import db, efos

DIAS_DESACTUALIZADA = 45

_COLUMNAS_FECHA = ("presunto_sat", "presunto_dof", "desvirtuado_sat", "desvirtuado_dof",
                   "definitivo_sat", "definitivo_dof", "sentencia_sat", "sentencia_dof")


def _registrar(origen: str, usuario_id: Optional[str], estado: str, mensaje: Optional[str], sha: Optional[str] = None,
               fecha_archivo: Optional[date] = None, filas: int = 0, rfc_unicos: int = 0) -> None:
    db.execute(
        """INSERT INTO efos_importaciones (origen, usuario_id, fecha_archivo, sha256, filas, rfc_unicos, estado, mensaje)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (origen, usuario_id, fecha_archivo, sha, filas, rfc_unicos, estado, mensaje))


def importar(contenido: bytes, origen: str, usuario_id: Optional[str] = None) -> dict:
    """Importa el CSV. Todo o nada: ante cualquier falla la lista anterior queda intacta y el intento queda
    registrado como ``fallida``. Un archivo idéntico al de la última importación correcta no cambia nada."""
    sha = hashlib.sha256(contenido).hexdigest()
    try:
        ultima = db.query_one(
            "SELECT sha256, filas, rfc_unicos, fecha_archivo FROM efos_importaciones "
            "WHERE estado = 'correcta' ORDER BY creado_en DESC, id DESC LIMIT 1")
        if ultima and ultima["sha256"] == sha:
            _registrar(origen, usuario_id, "sin_cambios", "Archivo idéntico al de la última importación", sha,
                       ultima["fecha_archivo"], ultima["filas"], ultima["rfc_unicos"])
            return {"estado": "sin_cambios", "filas": ultima["filas"], "rfc_unicos": ultima["rfc_unicos"],
                    "fecha_archivo": ultima["fecha_archivo"].isoformat() if ultima["fecha_archivo"] else None,
                    "descartadas": 0, "genericas": 0}
        resultado = efos.parsear(contenido)
        efos.validar_contra_anterior(len(resultado.filas), ultima["filas"] if ultima else None)
    except efos.ErrorImportacion as exc:
        _registrar(origen, usuario_id, "fallida", str(exc), sha)
        raise
    rfc_unicos = len({f.rfc for f in resultado.filas})
    try:
        with db.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO efos_importaciones (origen, usuario_id, fecha_archivo, sha256, filas, rfc_unicos, estado)
                       VALUES (%s, %s, %s, %s, %s, %s, 'correcta') RETURNING id""",
                    (origen, usuario_id, resultado.fecha_archivo, sha, len(resultado.filas), rfc_unicos))
                importacion_id = cur.fetchone()[0]
                cur.execute("DELETE FROM efos_lista")
                valores = [
                    (importacion_id, f.no_sat, f.rfc, f.nombre, f.situacion, *(f.fechas[k] for k in _COLUMNAS_FECHA),
                     psycopg2.extras.Json(f.oficios))
                    for f in resultado.filas
                ]
                psycopg2.extras.execute_values(
                    cur,
                    "INSERT INTO efos_lista (importacion_id, no_sat, rfc, nombre, situacion, "
                    + ", ".join(f"fecha_{k}" for k in _COLUMNAS_FECHA) + ", oficios) VALUES %s",
                    valores, page_size=2000)
    except Exception as exc:
        _registrar(origen, usuario_id, "fallida", f"Error al guardar la lista: {exc}", sha)
        raise
    return {"estado": "correcta", "filas": len(resultado.filas), "rfc_unicos": rfc_unicos,
            "fecha_archivo": resultado.fecha_archivo.isoformat() if resultado.fecha_archivo else None,
            "descartadas": resultado.descartadas, "genericas": resultado.genericas}


def estado(hoy: Optional[date] = None) -> dict:
    """Estado de la lista vigente y del último intento de importación."""
    hoy = hoy or date.today()
    ultimo = db.query_one(
        "SELECT estado, mensaje, creado_en FROM efos_importaciones ORDER BY creado_en DESC, id DESC LIMIT 1")
    intento = {"estado": ultimo["estado"], "mensaje": ultimo["mensaje"], "creado_en": ultimo["creado_en"].isoformat()} if ultimo else None
    fila = db.query_one(
        "SELECT fecha_archivo, creado_en, filas, rfc_unicos FROM efos_importaciones "
        "WHERE estado = 'correcta' ORDER BY creado_en DESC, id DESC LIMIT 1")
    if not fila:
        return {"hay_lista": False, "fecha_archivo": None, "importada_en": None, "filas": 0, "rfc_unicos": 0,
                "dias_de_antiguedad": None, "desactualizada": True, "ultimo_intento": intento}
    referencia = fila["fecha_archivo"] or fila["creado_en"].date()
    dias = (hoy - referencia).days
    return {"hay_lista": True,
            "fecha_archivo": fila["fecha_archivo"].isoformat() if fila["fecha_archivo"] else None,
            "importada_en": fila["creado_en"].isoformat(), "filas": fila["filas"], "rfc_unicos": fila["rfc_unicos"],
            "dias_de_antiguedad": dias, "desactualizada": dias > DIAS_DESACTUALIZADA, "ultimo_intento": intento}


def situaciones_de(rfcs: Iterable[str]) -> dict:
    """Situación vigente, riesgo y fecha de publicación de la etapa, para los RFC que están en la lista."""
    lista = sorted({r.strip().upper() for r in rfcs if r})
    if not lista:
        return {}
    filas = db.query_all(
        "SELECT rfc, situacion, " + ", ".join(f"fecha_{k}" for k in _COLUMNAS_FECHA)
        + " FROM efos_vigente WHERE rfc = ANY(%s)", (lista,))
    resultado = {}
    for f in filas:
        fechas = {k: f[f"fecha_{k}"] for k in _COLUMNAS_FECHA}
        fecha = efos.fecha_de_etapa(f["situacion"], fechas)
        resultado[f["rfc"]] = {"situacion": f["situacion"], "riesgo": efos.RIESGO[f["situacion"]],
                               "fecha_publicacion": fecha.isoformat() if fecha else None}
    return resultado
