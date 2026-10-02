"""Listado de CFDI: valida la consulta contra el catálogo de columnas y arma el
SQL. Todo valor que viene del usuario viaja como parámetro; los nombres de
columna, el orden y los operadores salen únicamente del catálogo.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Optional

from . import catalogos_sat, db
from .cfdi_columnas import A_PESOS, DESCRIPCIONES, LATERALES, Columna, columnas

DIRECCIONES = ("emitidos", "recibidos")
TIPOS = ("I", "E", "T", "N", "P")
ESTADOS = ("vigente", "cancelado", "todos")
METODOS = ("PUE", "PPD", "todos")
PAGOS = ("pendientes", "pagadas", "todos")
POR_PAGINA = (30, 50, 100)
MAX_FILTROS = 10
MAX_TEXTO = 200
MAX_BUSQUEDA = 100
CENTAVOS = Decimal("0.01")

_PERIODO_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_COMPARACION = {"igual": "=", "mayor": ">", "menor": "<"}
_NUMERICOS = ("igual", "mayor", "menor", "entre")
OPERADORES = {
    "texto": ("contiene", "igual", "empieza"),
    "numero": _NUMERICOS,
    "moneda": _NUMERICOS,
    "fecha": _NUMERICOS,
    "fecha_hora": _NUMERICOS,
    "booleano": ("igual",),
    "catalogo": ("igual", "en"),
}


class FiltroInvalido(ValueError):
    """La consulta pide algo fuera del catálogo o con un valor mal formado."""


@dataclass
class Consulta:
    direccion: str
    periodo: str
    tipo: str = "I"
    estado: str = "vigente"
    metodo: str = "todos"
    pago: str = "todos"
    q: Optional[str] = None
    filtros: list[dict] = field(default_factory=list)
    orden: str = "fecha_emision"
    dir: str = "asc"
    pagina: int = 1
    por_pagina: int = 30


def _uno_de(nombre: str, valor: Any, opciones: tuple) -> None:
    if valor not in opciones:
        raise FiltroInvalido(f"{nombre} inválido; valores permitidos: {', '.join(str(o) for o in opciones)}")


def _escapar_like(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _valor(col: Columna, valor: Any) -> Any:
    """Convierte y valida un valor de filtro según el tipo de dato de la columna."""
    if isinstance(valor, (dict, list)) or valor is None:
        raise FiltroInvalido(f"Valor inválido para {col.clave}")
    if col.tipo_dato == "booleano":
        if not isinstance(valor, bool):
            raise FiltroInvalido(f"{col.clave} espera verdadero o falso")
        return valor
    if col.tipo_dato in ("numero", "moneda"):
        try:
            numero = Decimal(str(valor))
        except Exception:
            raise FiltroInvalido(f"{col.clave} espera un número")
        if not numero.is_finite():
            raise FiltroInvalido(f"{col.clave} espera un número")
        return numero
    if col.tipo_dato in ("fecha", "fecha_hora"):
        try:
            return date.fromisoformat(str(valor))
        except ValueError:
            raise FiltroInvalido(f"{col.clave} espera una fecha AAAA-MM-DD")
    texto = str(valor)
    if len(texto) > MAX_TEXTO:
        raise FiltroInvalido(f"Valor demasiado largo para {col.clave}")
    if col.tipo_dato == "catalogo" and col.opciones and texto not in col.opciones:
        raise FiltroInvalido(f"{col.clave} no admite el valor {texto!r}")
    return texto


def _validar_filtros(crudo: Any, por_clave: dict[str, Columna]) -> list[dict]:
    if crudo in (None, "", []):
        return []
    if isinstance(crudo, str):
        try:
            crudo = json.loads(crudo)
        except ValueError:
            raise FiltroInvalido("filtros debe ser JSON válido")
    if not isinstance(crudo, list):
        raise FiltroInvalido("filtros debe ser una lista")
    if len(crudo) > MAX_FILTROS:
        raise FiltroInvalido(f"Máximo {MAX_FILTROS} filtros")

    limpios = []
    for f in crudo:
        if not isinstance(f, dict) or "valor" not in f:
            raise FiltroInvalido("Cada filtro lleva campo, op y valor")
        col = por_clave.get(f.get("campo"))
        if col is None or not col.filtrable:
            raise FiltroInvalido(f"No se puede filtrar por {f.get('campo')!r}")
        op = f.get("op")
        if op not in OPERADORES.get(col.tipo_dato, ()):
            raise FiltroInvalido(f"Operador {op!r} no aplica a {col.clave}")
        valor = f["valor"]
        if op in ("entre", "en"):
            if not isinstance(valor, list) or not valor or (op == "entre" and len(valor) != 2) or len(valor) > 50:
                raise FiltroInvalido(f"{op} espera una lista de valores para {col.clave}")
            valor = [_valor(col, v) for v in valor]
        else:
            valor = _valor(col, valor)
        limpios.append({"campo": col.clave, "op": op, "valor": valor})
    return limpios


def validar(
    direccion: str,
    periodo: str,
    tipo: str = "I",
    estado: str = "vigente",
    metodo: str = "todos",
    pago: str = "todos",
    q: Optional[str] = None,
    filtros: Any = None,
    orden: str = "fecha_emision",
    dir: str = "asc",
    pagina: int = 1,
    por_pagina: int = 30,
) -> Consulta:
    """Valida todos los parámetros contra el catálogo. Lanza ``FiltroInvalido``."""
    _uno_de("direccion", direccion, DIRECCIONES)
    if not isinstance(periodo, str) or not _PERIODO_RE.match(periodo):
        raise FiltroInvalido("periodo inválido; formato esperado YYYY-MM")
    _uno_de("tipo", tipo, TIPOS)
    _uno_de("estado", estado, ESTADOS)
    _uno_de("metodo", metodo, METODOS)
    _uno_de("pago", pago, PAGOS)
    _uno_de("dir", dir, ("asc", "desc"))
    _uno_de("por_pagina", por_pagina, POR_PAGINA)
    if not isinstance(pagina, int) or pagina < 1:
        raise FiltroInvalido("pagina debe ser un entero mayor o igual a 1")
    q = (q or "").strip() or None
    if q and len(q) > MAX_BUSQUEDA:
        raise FiltroInvalido(f"La búsqueda admite hasta {MAX_BUSQUEDA} caracteres")

    por_clave = {c.clave: c for c in columnas(direccion, tipo)}
    col_orden = por_clave.get(orden)
    if col_orden is None or not col_orden.ordenable:
        raise FiltroInvalido(f"No se puede ordenar por {orden!r}")

    return Consulta(
        direccion=direccion, periodo=periodo, tipo=tipo, estado=estado, metodo=metodo, pago=pago,
        q=q, filtros=_validar_filtros(filtros, por_clave), orden=orden, dir=dir,
        pagina=pagina, por_pagina=por_pagina,
    )


def rango(periodo: str) -> tuple[date, date]:
    """Primer día del mes y primer día del mes siguiente."""
    anio, mes = int(periodo[:4]), int(periodo[5:7])
    return date(anio, mes, 1), (date(anio + 1, 1, 1) if mes == 12 else date(anio, mes + 1, 1))


def _filtro_sql(col: Columna, op: str, valor: Any) -> tuple[str, list]:
    expr = col.sql
    if col.tipo_dato == "texto":
        if op == "igual":
            return f"UPPER({expr}) = UPPER(%s)", [valor]
        patron = _escapar_like(valor) + "%"
        return f"{expr} ILIKE %s ESCAPE '\\'", [("%" if op == "contiene" else "") + patron]
    if col.tipo_dato in ("fecha", "fecha_hora"):
        expr = f"({expr})::date"
    if op == "entre":
        return f"{expr} BETWEEN %s AND %s", list(valor)
    if op == "en":
        return f"{expr} = ANY(%s)", [list(valor)]
    return f"{expr} {_COMPARACION[op]} %s", [valor]


def condiciones(
    c: Consulta, empresa_id: str, rfc: str, *, desde: date, hasta: date, con_tipo: bool = True
) -> tuple[str, list]:
    """Fragmento WHERE (sin la palabra) y sus parámetros, en el mismo orden."""
    por_clave = {col.clave: col for col in columnas(c.direccion, c.tipo)}
    col_rfc = "c.rfc_emisor" if c.direccion == "emitidos" else "c.rfc_receptor"
    sql = ["c.empresa_id = %s", f"{col_rfc} = %s", "c.fecha_emision >= %s", "c.fecha_emision < %s"]
    params: list = [empresa_id, rfc, desde, hasta]

    if con_tipo:
        sql.append("c.tipo_comprobante = %s")
        params.append(c.tipo)
    if c.estado != "todos":
        sql.append("c.estado = %s")
        params.append(c.estado)
    if c.metodo != "todos":
        sql.append("c.metodo_pago = %s")
        params.append(c.metodo)
        if c.metodo == "PPD" and c.pago != "todos":
            comparador = "<" if c.pago == "pendientes" else ">="
            sql.append(f"COALESCE(c.monto_cobrado, 0) {comparador} c.total")
    if c.q:
        patron = f"%{_escapar_like(c.q)}%"
        campos = ["c.uuid", por_clave["rfc_contraparte"].sql, por_clave["contraparte"].sql,
                  "(COALESCE(c.serie, '') || COALESCE(c.folio, ''))"]
        sql.append("(" + " OR ".join(f"{campo} ILIKE %s ESCAPE '\\'" for campo in campos) + ")")
        params += [patron] * len(campos)
    for f in c.filtros:
        fragmento, valores = _filtro_sql(por_clave[f["campo"]], f["op"], f["valor"])
        sql.append(fragmento)
        params += valores

    return " AND ".join(sql), params


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------

# Importes del encabezado que se suman en los totales (clave → expresión).
_SUMAS = {
    "retencion_iva": "COALESCE(c.iva_retenido, 0)",
    "retencion_isr": "COALESCE(c.isr_retenido, 0)",
    "traslado_iva": "COALESCE(c.iva_trasladado, 0)",
    "subtotal": "c.subtotal",
    "descuento": "COALESCE(c.descuento, 0)",
    "total": "c.total",
}
# Impuestos que solo viven en cfdi_impuestos (clave → (ámbito, impuesto)).
_SUMAS_IMPUESTOS = {
    "traslado_ieps": ("traslado", "003"),
    "retencion_ieps": ("retencion", "003"),
    "traslado_isr": ("traslado", "001"),
}
_ORDEN_TOTALES = (
    "conteo", "retencion_iva", "retencion_ieps", "retencion_isr", "traslado_iva", "traslado_ieps",
    "traslado_isr", "total_retenciones", "subtotal", "descuento", "neto", "total",
)


def _json(valor: Any) -> Any:
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    return valor


def _item(fila: dict) -> dict:
    item = {clave: _json(valor) for clave, valor in fila.items()}
    for derivada, (origen, catalogo) in DESCRIPCIONES.items():
        item[derivada] = catalogos_sat.descripcion(catalogo, fila.get(origen))
    return item


def listar(empresa_id: str, rfc: str, c: Consulta) -> dict:
    """Una página del listado. Primero se recorta la página (orden + límite) y
    solo sobre esas filas se calculan las columnas que dependen de subconsultas."""
    cols = columnas(c.direccion, c.tipo)
    desde, hasta = rango(c.periodo)
    where, params = condiciones(c, empresa_id, rfc, desde=desde, hasta=hasta)

    total = db.query_one(f"SELECT COUNT(*) AS n FROM cfdi c WHERE {where}", tuple(params))["n"]
    orden = next(col.sql for col in cols if col.clave == c.orden)
    direccion = "DESC" if c.dir == "desc" else "ASC"
    seleccion = ", ".join(f'{col.sql} AS "{col.clave}"' for col in cols if col.sql)

    filas = db.query_all(
        f"""
        WITH pagina AS (
            SELECT c.id, ROW_NUMBER() OVER (ORDER BY {orden} {direccion} NULLS LAST, c.id) AS n
            FROM cfdi c
            WHERE {where}
            ORDER BY n
            LIMIT %s OFFSET %s
        )
        SELECT {seleccion}
        FROM pagina p
        JOIN cfdi c ON c.id = p.id
        {LATERALES}
        ORDER BY p.n
        """,
        (*params, c.por_pagina, (c.pagina - 1) * c.por_pagina),
    )
    return {
        "items": [_item(f) for f in filas],
        "total": int(total),
        "pagina": c.pagina,
        "por_pagina": c.por_pagina,
    }


def _bloque(prefijo: str, encabezado: dict, impuestos: dict) -> dict:
    conteo = int(encabezado[f"{prefijo}_conteo"] or 0)
    if conteo == 0:
        return {clave: (0 if clave == "conteo" else None) for clave in _ORDEN_TOTALES}

    def pesos(fila: dict, clave: str) -> Decimal:
        return Decimal(str(fila.get(f"{prefijo}_{clave}") or 0))

    t = {clave: pesos(encabezado, clave) for clave in _SUMAS}
    t.update({clave: pesos(impuestos, clave) for clave in _SUMAS_IMPUESTOS})
    t["neto"] = t["subtotal"] - t["descuento"]
    t["total_retenciones"] = t["retencion_iva"] + t["retencion_isr"] + t["retencion_ieps"]
    bloque = {clave: float(t[clave].quantize(CENTAVOS, rounding=ROUND_HALF_UP)) for clave in _ORDEN_TOTALES[1:]}
    return {"conteo": conteo, **{clave: bloque[clave] for clave in _ORDEN_TOTALES[1:]}}


def _advertencias(empresa_id: str, rfc: str, desde: date, hasta: date) -> list[dict]:
    """Facturas que aplican un anticipo (TipoRelacion 07) sin su CFDI de egreso
    con forma de pago 30 en el periodo."""
    filas = db.query_all(
        """
        SELECT f.uuid
        FROM cfdi f
        WHERE f.empresa_id = %s AND f.rfc_emisor = %s AND f.tipo_comprobante = 'I'
          AND f.fecha_emision >= %s AND f.fecha_emision < %s
          AND COALESCE(f.cfdi_relacionados, '[]'::jsonb) @> '[{"tipo_relacion": "07"}]'::jsonb
          AND NOT EXISTS (
              SELECT 1
              FROM cfdi e, jsonb_array_elements(COALESCE(e.cfdi_relacionados, '[]'::jsonb)) r
              WHERE e.empresa_id = f.empresa_id AND e.rfc_emisor = f.rfc_emisor
                AND e.tipo_comprobante = 'E' AND e.forma_pago = '30'
                AND e.fecha_emision >= %s AND e.fecha_emision < %s
                AND r->'uuids' @> to_jsonb(UPPER(f.uuid))
          )
        ORDER BY f.fecha_emision
        """,
        (empresa_id, rfc, desde, hasta, desde, hasta),
    )
    return [
        {
            "tipo": "sin_egreso_anticipo",
            "uuid_factura": f["uuid"],
            "mensaje": f"La factura {f['uuid'][:8]}... aplica anticipo (TipoRel=07) pero no se encontró "
                       "CFDI Egreso con FormaPago=30 en el periodo",
        }
        for f in filas
    ]


def resumen(empresa_id: str, rfc: str, c: Consulta) -> dict:
    """Conteos por tipo (para las pestañas) y totales en pesos del tipo activo:
    del periodo y del acumulado del ejercicio (enero al mes del periodo)."""
    desde, hasta = rango(c.periodo)
    enero = date(desde.year, 1, 1)

    where, params = condiciones(c, empresa_id, rfc, desde=desde, hasta=hasta, con_tipo=False)
    conteos = {t: 0 for t in TIPOS}
    for fila in db.query_all(
        f"SELECT c.tipo_comprobante AS tipo, COUNT(*) AS n FROM cfdi c WHERE {where} GROUP BY c.tipo_comprobante",
        tuple(params),
    ):
        if fila["tipo"] in conteos:
            conteos[fila["tipo"]] = int(fila["n"])

    where, params = condiciones(c, empresa_id, rfc, desde=enero, hasta=hasta)
    base = f"""
        WITH base AS (
            SELECT c.id, (c.fecha_emision >= %s) AS en_periodo, {A_PESOS} AS tc,
                   {", ".join(f"{expr} AS {clave}" for clave, expr in _SUMAS.items())}
            FROM cfdi c
            WHERE {where}
        )
    """
    sumas = ", ".join(
        f"SUM({clave} * tc) FILTER (WHERE en_periodo) AS p_{clave}, SUM({clave} * tc) AS a_{clave}"
        for clave in _SUMAS
    )
    encabezado = db.query_one(
        f"{base} SELECT COUNT(*) FILTER (WHERE en_periodo) AS p_conteo, COUNT(*) AS a_conteo, {sumas} FROM base",
        (desde, *params),
    )
    sumas = ", ".join(
        f"SUM(i.importe * b.tc) FILTER (WHERE b.en_periodo AND i.ambito = '{ambito}' AND i.impuesto = '{impuesto}')"
        f" AS p_{clave}, "
        f"SUM(i.importe * b.tc) FILTER (WHERE i.ambito = '{ambito}' AND i.impuesto = '{impuesto}') AS a_{clave}"
        for clave, (ambito, impuesto) in _SUMAS_IMPUESTOS.items()
    )
    impuestos = db.query_one(
        f"{base} SELECT {sumas} FROM base b JOIN cfdi_impuestos i ON i.cfdi_id = b.id AND i.impuesto <> '002'",
        (desde, *params),
    )

    return {
        "conteos": conteos,
        "totales": {
            "periodo": _bloque("p", encabezado, impuestos),
            "acumulado": _bloque("a", encabezado, impuestos),
        },
        "advertencias": _advertencias(empresa_id, rfc, desde, hasta) if c.direccion == "emitidos" else [],
    }
