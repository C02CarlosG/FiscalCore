"""Reproceso del detalle fiscal de CFDI ya guardados.

Los CFDI anteriores a la migración 028 solo tienen totales. Aquí se vuelve a
parsear su ``xml_raw`` para llenar impuestos por tasa, conceptos, encabezados y
los impuestos de cada pago, sin volver a descargar nada del SAT.

Por lotes: cada llamada toma hasta ``limite`` CFDI con ``detalle_version``
menor a la actual. Un CFDI que no se puede reprocesar (XML ilegible, dato que
la base rechaza) se marca con -1 para que no se reintente en cada lote; un
error transitorio de la base no marca nada y corta el lote.
"""
from __future__ import annotations

import logging
from typing import Optional

import psycopg2

from . import cfdi_store, db
from .cfdi_parser import CFDIParser

_log = logging.getLogger(__name__)

_PENDIENTE = "detalle_version >= 0 AND detalle_version < %s AND xml_raw IS NOT NULL"


def _descartar(uuid: str, empresa_id: str, exc: Exception, errores: list[dict]) -> None:
    """Marca con -1 un CFDI que no se puede reprocesar (XML ilegible o dato que
    la base rechaza) para que no vuelva a entrar en cada lote."""
    _log.warning("reproceso: CFDI %s no se pudo reprocesar: %s", uuid, exc)
    errores.append({"uuid": uuid, "error": str(exc)[:300]})
    db.execute(
        "UPDATE cfdi SET detalle_version = -1 WHERE uuid = %s AND empresa_id = %s", (uuid, empresa_id)
    )


def reprocesar_detalle(limite: int = 500, empresa_id: Optional[str] = None) -> dict:
    """Reprocesa hasta ``limite`` CFDI pendientes (de una empresa o de todas).

    Devuelve ``{"procesados": int, "errores": [{"uuid", "error"}], "pendientes": int}``.
    """
    filtro_empresa = " AND empresa_id = %s" if empresa_id else ""
    params_empresa = (empresa_id,) if empresa_id else ()

    filas = db.query_all(
        f"SELECT empresa_id, uuid, xml_raw FROM cfdi WHERE {_PENDIENTE}{filtro_empresa} "
        "ORDER BY created_at LIMIT %s",
        (cfdi_store.DETALLE_VERSION, *params_empresa, limite),
    )

    parser = CFDIParser()
    procesados = 0
    errores: list[dict] = []
    for fila in filas:
        empresa = str(fila["empresa_id"])
        try:
            resultado = parser.parse_xml(fila["xml_raw"])
            if resultado.uuid != fila["uuid"]:
                raise ValueError("el UUID del XML no coincide con el del registro")
        except Exception as exc:
            _descartar(fila["uuid"], empresa, exc, errores)
            continue

        try:
            # El complemento va antes que el detalle: guardar_detalle es quien
            # marca el CFDI como completo, y un REP no lo está sin sus pagos.
            if resultado.tipo_comprobante == "P" and resultado.pagos:
                cfdi_store.persistir_complemento_pago(empresa, resultado)
            cfdi_store.guardar_detalle(empresa, resultado)
            procesados += 1
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as exc:
            # Falla de la base, no del CFDI: se deja pendiente y se corta el lote.
            _log.warning("reproceso: error transitorio de base en %s: %s", fila["uuid"], exc)
            errores.append({"uuid": fila["uuid"], "error": f"transitorio: {str(exc)[:280]}"})
            break
        except Exception as exc:
            _descartar(fila["uuid"], empresa, exc, errores)

    pendientes = db.query_one(
        f"SELECT COUNT(*) AS n FROM cfdi WHERE {_PENDIENTE}{filtro_empresa}",
        (cfdi_store.DETALLE_VERSION, *params_empresa),
    )["n"]
    return {"procesados": procesados, "errores": errores, "pendientes": int(pendientes)}
