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
from .cfdi_columnas import A_PESOS, DESCRIPCIONES, Columna, columnas, laterales

DIRECCIONES = ("emitidos", "recibidos")
TIPOS = ("I", "E", "T", "N", "P")
ESTADOS = ("vigente", "cancelado", "todos")
METODOS = ("PUE", "PPD", "todos")
PAGOS = ("pendientes", "pagadas", "todos")
POR_PAGINA = (30, 50, 100)
MAX_FILTROS = 10
MAX_TEXTO = 200
MAX_BUSQUEDA = 100
MAX_PAGINA = 100_000
MAX_NUMERO = Decimal("1e15")   # holgado para cualquier importe; evita desbordar NUMERIC
CENTAVOS = Decimal("0.01")

# Años 2000-2099: fuera de eso date() o Postgres fallan, y no hay CFDI.
_PERIODO_RE = re.compile(r"20[0-9]{2}-(0[1-9]|1[0-2])")
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


MAX_FILAS_EXPORTACION = 50_000


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


def _texto_seguro(texto: str, nombre: str) -> str:
    """Rechaza texto que Postgres no puede recibir (NUL) o que no es UTF-8 válido."""
    try:
        texto.encode("utf-8")
    except UnicodeEncodeError:
        raise FiltroInvalido(f"Texto inválido en {nombre}")
    if "\x00" in texto:
        raise FiltroInvalido(f"Texto inválido en {nombre}")
    return texto


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
        if not numero.is_finite() or abs(numero) >= MAX_NUMERO or numero.as_tuple().exponent < -6:
            raise FiltroInvalido(f"{col.clave} espera un número de hasta 15 enteros y 6 decimales")
        return numero
    if col.tipo_dato in ("fecha", "fecha_hora"):
        try:
            return date.fromisoformat(str(valor))
        except ValueError:
            raise FiltroInvalido(f"{col.clave} espera una fecha AAAA-MM-DD")
    texto = _texto_seguro(str(valor), col.clave)
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
        except (ValueError, RecursionError):
            raise FiltroInvalido("filtros debe ser JSON válido")
    if not isinstance(crudo, list):
        raise FiltroInvalido("filtros debe ser una lista")
    if len(crudo) > MAX_FILTROS:
        raise FiltroInvalido(f"Máximo {MAX_FILTROS} filtros")

    limpios = []
    for f in crudo:
        if not isinstance(f, dict) or "valor" not in f:
            raise FiltroInvalido("Cada filtro lleva campo, op y valor")
        campo, op = f.get("campo"), f.get("op")
        col = por_clave.get(campo) if isinstance(campo, str) else None
        if col is None or not col.filtrable:
            raise FiltroInvalido(f"No se puede filtrar por {campo!r}")
        if not isinstance(op, str) or op not in OPERADORES.get(col.tipo_dato, ()):
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
    if not isinstance(periodo, str) or not _PERIODO_RE.fullmatch(periodo):
        raise FiltroInvalido("periodo inválido; formato esperado YYYY-MM")
    _uno_de("tipo", tipo, TIPOS)
    _uno_de("estado", estado, ESTADOS)
    _uno_de("metodo", metodo, METODOS)
    _uno_de("pago", pago, PAGOS)
    _uno_de("dir", dir, ("asc", "desc"))
    _uno_de("por_pagina", por_pagina, POR_PAGINA)
    if not isinstance(pagina, int) or not 1 <= pagina <= MAX_PAGINA:
        raise FiltroInvalido(f"pagina debe ser un entero entre 1 y {MAX_PAGINA}")
    q = _texto_seguro(q or "", "la búsqueda").strip() or None
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


# Cifras que muestra la tabla de totales de cada tipo: (clave, etiqueta, formato). El conteo va
# siempre primero. La pantalla las lee de la respuesta, así que Nómina y Pago no necesitan
# código propio en el cliente.
_CIFRAS_COMPROBANTE = (
    ("conteo", "CFDI", "entero"), ("retencion_iva", "Ret. IVA", "moneda"), ("retencion_ieps", "Ret. IEPS", "moneda"),
    ("retencion_isr", "Ret. ISR", "moneda"), ("traslado_iva", "Tras. IVA", "moneda"),
    ("traslado_ieps", "Tras. IEPS", "moneda"), ("traslado_isr", "Tras. ISR", "moneda"),
    ("total_retenciones", "Total ret.", "moneda"), ("subtotal", "Subtotal", "moneda"),
    ("descuento", "Descuento", "moneda"), ("neto", "Neto", "moneda"), ("total", "Total", "moneda"),
)

# Nómina y Pago: (clave, etiqueta, formato, expresión SQL, agregado). Las expresiones usan los
# alias de ``_UNIONES_TOTALES`` (subconsultas agrupadas por CFDI, no por página).
_CIFRAS_SIMPLES = {
    "N": (
        ("conteo", "CFDI", "entero", None, "conteo"),
        ("empleados", "Empleados", "entero", "{contraparte}", "distintos"),
        ("sueldos", "Sueldos", "moneda", "nom.sueldos", "suma"),
        ("otras_percepciones", "Otras percepciones", "moneda", "nom.otras_percepciones", "suma"),
        ("gravado", "Gravado", "moneda", "c.nomina_gravado", "suma"),
        ("exento", "Exento", "moneda", "c.nomina_exento", "suma"),
        ("isr_retenido", "ISR retenido", "moneda", "c.nomina_isr_retenido", "suma"),
        ("otras_deducciones", "Otras deducciones", "moneda", "(c.nomina_deducciones - c.nomina_isr_retenido)", "suma"),
        ("subsidio_causado", "Subsidio causado", "moneda", "sub.subsidio", "suma"),
        ("neto_pagar", "Neto a pagar", "moneda", "c.total", "suma"),
    ),
    "P": (
        ("conteo", "CFDI", "entero", None, "conteo"),
        ("base_iva_16", "Base IVA 16 %", "moneda", "ptot.total_traslados_base_iva16", "suma"),
        ("base_iva_8", "Base IVA 8 %", "moneda", "ptot.total_traslados_base_iva8", "suma"),
        ("base_iva_0", "Base IVA 0 %", "moneda", "ptot.total_traslados_base_iva0", "suma"),
        ("base_iva_exento", "Base IVA exento", "moneda", "ptot.total_traslados_base_exento", "suma"),
        ("traslado_iva", "Traslado IVA", "moneda",
         "(COALESCE(ptot.total_traslados_iva16, 0) + COALESCE(ptot.total_traslados_iva8, 0)"
         " + COALESCE(ptot.total_traslados_iva0, 0))", "suma"),
        ("retencion_iva", "Retención IVA", "moneda", "ptot.total_retenciones_iva", "suma"),
        ("total", "Total", "moneda", "ptot.monto_total_pagos", "suma"),
        ("pagos_relacionados", "Documentos relacionados", "entero", "rel.n", "suma"),
    ),
}

# Uniones agrupadas por CFDI para los totales de Nómina y Pago (en el listado se calculan por
# página con LATERAL; aquí son sobre todo el periodo).
_UNIONES_TOTALES = {
    "N": """
        LEFT JOIN (
            SELECT n.cfdi_id, SUM(n.total_sueldos) AS sueldos,
                   SUM(COALESCE(n.total_percepciones, 0) - COALESCE(n.total_sueldos, 0)) AS otras_percepciones
            FROM cfdi_nominas n GROUP BY n.cfdi_id
        ) nom ON nom.cfdi_id = c.id
        LEFT JOIN (
            SELECT n.cfdi_id, SUM(k.subsidio_causado) AS subsidio
            FROM cfdi_nominas n JOIN cfdi_nomina_conceptos k ON k.nomina_id = n.id GROUP BY n.cfdi_id
        ) sub ON sub.cfdi_id = c.id
    """,
    "P": """
        LEFT JOIN cfdi_pagos_totales ptot ON ptot.cfdi_id = c.id
        LEFT JOIN (
            SELECT p.cfdi_id, COUNT(pr.id) AS n
            FROM pagos_cfdi p JOIN pagos_relaciones pr ON pr.pago_id = p.id GROUP BY p.cfdi_id
        ) rel ON rel.cfdi_id = c.id
    """,
}


def _json(valor: Any) -> Any:
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, datetime):
        # La fecha del CFDI es hora local del emisor y se guardó sin convertir:
        # se devuelve tal cual, sin zona, para que el navegador no la desplace.
        return valor.replace(tzinfo=None).isoformat()
    if isinstance(valor, date):
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
        {laterales(c.tipo)}
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


def exportar(empresa_id: str, rfc: str, c: Consulta, claves: Optional[list[str]]) -> dict:
    """Todas las filas que cumplen los filtros (sin paginar), con las columnas pedidas
    en el orden pedido. Responde ``FiltroInvalido`` si hay más de 50,000 filas o si
    alguna clave no es una columna del catálogo."""
    por_clave = {col.clave: col for col in columnas(c.direccion, c.tipo)}
    if claves:
        desconocidas = [k for k in claves if k not in por_clave]
        if desconocidas or len(set(claves)) != len(claves):
            raise FiltroInvalido(f"Columnas inválidas: {', '.join(desconocidas) or 'repetidas'}")
        cols = [por_clave[k] for k in claves]
    else:
        cols = [col for col in por_clave.values() if col.visible]

    desde, hasta = rango(c.periodo)
    where, params = condiciones(c, empresa_id, rfc, desde=desde, hasta=hasta)
    total = db.query_one(f"SELECT COUNT(*) AS n FROM cfdi c WHERE {where}", tuple(params))["n"]
    if total > MAX_FILAS_EXPORTACION:
        raise FiltroInvalido(
            f"El resultado tiene {int(total):,} CFDI y el máximo a exportar es "
            f"{MAX_FILAS_EXPORTACION:,}; acota el periodo o los filtros")

    orden = por_clave[c.orden].sql
    direccion = "DESC" if c.dir == "desc" else "ASC"
    # Las columnas derivadas (descripciones de catálogo) se calculan en Python a partir
    # de su origen: se piden todas las del catálogo y se recorta al final.
    seleccion = ", ".join(f'{col.sql} AS "{col.clave}"' for col in por_clave.values() if col.sql)
    filas = db.query_all(
        f"""
        WITH pagina AS (
            SELECT c.id, ROW_NUMBER() OVER (ORDER BY {orden} {direccion} NULLS LAST, c.id) AS n
            FROM cfdi c
            WHERE {where}
        )
        SELECT {seleccion}
        FROM pagina p
        JOIN cfdi c ON c.id = p.id
        {laterales(c.tipo)}
        ORDER BY p.n
        """,
        tuple(params),
    )
    return {"columnas": cols, "items": [_item(f) for f in filas], "total": int(total)}


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


def _totales_nomina_o_pago(
    empresa_id: str, rfc: str, c: Consulta, desde: date, hasta: date, enero: date
) -> tuple[list[dict], dict]:
    """Totales de Nómina o Pago del periodo y del acumulado. Todo viene ya en pesos (el
    complemento de nómina y pago20:Totales son MXN), así que no se multiplica por tipo de
    cambio. Una cifra cuya fuente no está (CFDI sin extracción v2, REP de Pagos 1.0) no suma
    nada: si ningún CFDI la trae, va en null y la pantalla muestra un guion."""
    contraparte = "c.rfc_receptor" if c.direccion == "emitidos" else "c.rfc_emisor"
    definiciones = tuple(
        (clave, etq, fmt, expr.replace("{contraparte}", contraparte) if expr else expr, agregado)
        for clave, etq, fmt, expr, agregado in _CIFRAS_SIMPLES[c.tipo]
    )
    where, params = condiciones(c, empresa_id, rfc, desde=enero, hasta=hasta)

    columnas_sql = ["COUNT(*) FILTER (WHERE c.fecha_emision >= %s) AS p_conteo", "COUNT(*) AS a_conteo"]
    for clave, _etq, _fmt, expr, agregado in definiciones:
        if agregado == "conteo":
            continue
        if agregado == "distintos":
            columnas_sql.append(f"COUNT(DISTINCT {expr}) FILTER (WHERE c.fecha_emision >= %s) AS p_{clave}")
            columnas_sql.append(f"COUNT(DISTINCT {expr}) AS a_{clave}")
        else:
            columnas_sql.append(f"SUM({expr}) FILTER (WHERE c.fecha_emision >= %s) AS p_{clave}")
            columnas_sql.append(f"SUM({expr}) AS a_{clave}")
    desde_params = tuple(desde for _ in range(sum(col.count("%s") for col in columnas_sql)))

    fila = db.query_one(
        f"SELECT {', '.join(columnas_sql)} FROM cfdi c {_UNIONES_TOTALES[c.tipo]} WHERE {where}",
        (*desde_params, *params),
    )

    def bloque(prefijo: str) -> dict:
        conteo = int(fila[f"{prefijo}_conteo"] or 0)
        if conteo == 0:
            return {clave: (0 if clave == "conteo" else None) for clave, *_ in definiciones}
        resultado: dict = {"conteo": conteo}
        for clave, _etq, formato, _expr, agregado in definiciones:
            if agregado == "conteo":
                continue
            valor = fila[f"{prefijo}_{clave}"]
            if valor is None:
                resultado[clave] = None
            elif formato == "entero":
                resultado[clave] = int(valor)
            else:
                resultado[clave] = float(Decimal(str(valor)).quantize(CENTAVOS, rounding=ROUND_HALF_UP))
        return resultado

    cifras = [{"clave": k, "etiqueta": e, "formato": f} for k, e, f, *_ in definiciones]
    return cifras, {"periodo": bloque("p"), "acumulado": bloque("a")}


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

    if c.tipo in _CIFRAS_SIMPLES:
        cifras, totales = _totales_nomina_o_pago(empresa_id, rfc, c, desde, hasta, enero)
        return {
            "conteos": conteos,
            "cifras": cifras,
            "totales": totales,
            "advertencias": _advertencias(empresa_id, rfc, desde, hasta) if c.direccion == "emitidos" else [],
        }

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
        "cifras": [{"clave": k, "etiqueta": e, "formato": f} for k, e, f in _CIFRAS_COMPROBANTE],
        "totales": {
            "periodo": _bloque("p", encabezado, impuestos),
            "acumulado": _bloque("a", encabezado, impuestos),
        },
        "advertencias": _advertencias(empresa_id, rfc, desde, hasta) if c.direccion == "emitidos" else [],
    }
