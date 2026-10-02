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
