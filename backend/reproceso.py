"""Reproceso del detalle fiscal de CFDI ya guardados.

Los CFDI anteriores a la migración 028 solo tienen totales. Aquí se vuelve a
parsear su ``xml_raw`` para llenar impuestos por tasa, conceptos, encabezados y
los impuestos de cada pago, sin volver a descargar nada del SAT.

Por lotes: cada llamada toma hasta ``limite`` CFDI con ``detalle_version``
menor a la actual. Un XML que no se puede leer se marca con -1 para que no
se reintente en cada lote.
"""
from __future__ import annotations

import logging
from typing import Optional

from . import cfdi_store, db
from .cfdi_parser import CFDIParser

_log = logging.getLogger(__name__)

_PENDIENTE = "detalle_version >= 0 AND detalle_version < %s AND xml_raw IS NOT NULL"


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
            cfdi_store.guardar_detalle(empresa, resultado)
            if resultado.tipo_comprobante == "P" and resultado.pagos:
                cfdi_store.persistir_complemento_pago(empresa, resultado)
            procesados += 1
        except Exception as exc:
            _log.warning("reproceso: CFDI %s no se pudo reprocesar: %s", fila["uuid"], exc)
            errores.append({"uuid": fila["uuid"], "error": str(exc)[:300]})
            db.execute(
                "UPDATE cfdi SET detalle_version = -1 WHERE uuid = %s AND empresa_id = %s",
                (fila["uuid"], empresa),
            )

    pendientes = db.query_one(
        f"SELECT COUNT(*) AS n FROM cfdi WHERE {_PENDIENTE}{filtro_empresa}",
        (cfdi_store.DETALLE_VERSION, *params_empresa),
    )["n"]
    return {"procesados": procesados, "errores": errores, "pendientes": int(pendientes)}
