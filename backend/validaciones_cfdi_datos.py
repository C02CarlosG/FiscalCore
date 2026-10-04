"""
validaciones_cfdi_datos.py
Consultas de V1: conteos por validación, lista de CFDI de una tarjeta y
configuración por empresa. Las reglas viven en `validaciones_cfdi.py`.
"""
from __future__ import annotations

import psycopg2.extras

from . import db
from . import validaciones_cfdi as v

MAX_FILAS = 500

_COLUMNA_EMPRESA = {"emitidos": "c.rfc_emisor", "recibidos": "c.rfc_receptor"}
_CONTRAPARTE = {
    "emitidos": ("c.rfc_receptor", "c.nombre_receptor"),
    "recibidos": ("c.rfc_emisor", "c.nombre_emisor"),
}


def _base(empresa_id: str, rfc: str, direccion: str, desde, hasta) -> tuple[str, list]:
    """CFDI vigentes de la empresa en la dirección y el rango de fechas."""
    return (
        f"c.empresa_id = %s AND c.estado = 'vigente' AND {_COLUMNA_EMPRESA[direccion]} = %s "
        "AND c.fecha_emision >= %s AND c.fecha_emision < %s",
        [empresa_id, rfc, desde, hasta],
    )


def leer_configuracion(empresa_id: str) -> v.Configuracion:
    fila = db.query_one("SELECT config FROM validaciones_cfdi_config WHERE empresa_id = %s", (empresa_id,))
    return v.Configuracion.desde_json((fila or {}).get("config"))


def guardar_configuracion(empresa_id: str, config: v.Configuracion, usuario_id: str) -> None:
    db.execute(
        """
        INSERT INTO validaciones_cfdi_config (empresa_id, config, usuario_id, updated_at)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (empresa_id)
        DO UPDATE SET config = EXCLUDED.config, usuario_id = EXCLUDED.usuario_id, updated_at = NOW()
        """,
        (empresa_id, psycopg2.extras.Json(config.a_json()), usuario_id),
    )


def contar(empresa_id: str, rfc: str, direccion: str, periodo: str, config: v.Configuracion) -> dict:
    """``{clave: (periodo, acumulado)}`` de las validaciones activas de la dirección."""
    inicio_mes, siguiente, inicio_ejercicio = v.rangos(periodo)
    activas = [x for x in v.de_direccion(direccion) if config.activa(x.clave)]
    if not activas:
        return {}
    columnas, params = [], []
    for x in activas:
        cond, cparams = v.condicion(x.clave, config)
        columnas.append(f"COUNT(*) FILTER (WHERE c.fecha_emision >= %s AND {cond}) AS p_{x.clave}")
        params += [inicio_mes, *cparams]
        columnas.append(f"COUNT(*) FILTER (WHERE {cond}) AS a_{x.clave}")
        params += cparams
    where, wparams = _base(empresa_id, rfc, direccion, inicio_ejercicio, siguiente)
    fila = db.query_one(f"SELECT {', '.join(columnas)} FROM cfdi c WHERE {where}", tuple(params + wparams))
    return {x.clave: (int(fila[f"p_{x.clave}"]), int(fila[f"a_{x.clave}"])) for x in activas}


def listar(empresa_id: str, rfc: str, direccion: str, clave: str, alcance: str, periodo: str,
           config: v.Configuracion) -> dict:
    """Hasta ``MAX_FILAS`` CFDI de la tarjeta, por fecha de emisión."""
    if not config.activa(clave):
        return {"cfdis": [], "total_filas": 0}
    inicio_mes, siguiente, inicio_ejercicio = v.rangos(periodo)
    desde = inicio_mes if alcance == "periodo" else inicio_ejercicio
    where, params = _base(empresa_id, rfc, direccion, desde, siguiente)
    cond, cparams = v.condicion(clave, config)
    where = f"{where} AND {cond}"
    params += cparams
    total = db.query_one(f"SELECT COUNT(*) AS n FROM cfdi c WHERE {where}", tuple(params))["n"]
    rfc_col, nombre_col = _CONTRAPARTE[direccion]
    filas = db.query_all(
        f"""
        SELECT c.uuid, c.fecha_emision, c.serie, c.folio, {rfc_col} AS rfc, {nombre_col} AS nombre,
               c.total, c.moneda, c.forma_pago, c.metodo_pago, c.tipo_comprobante
        FROM cfdi c WHERE {where}
        ORDER BY c.fecha_emision, c.uuid
        LIMIT {MAX_FILAS}
        """,
        tuple(params),
    )
    return {"cfdis": filas, "total_filas": int(total)}
