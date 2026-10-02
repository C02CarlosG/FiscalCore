"""Validación de la consulta del listado de CFDI y armado del SQL (sin DB)."""
import json
from datetime import date
from decimal import Decimal

import pytest

from backend import cfdi_listado as cl


def _condiciones(**kw):
    c = cl.validar("emitidos", "2026-09", **kw)
    return cl.condiciones(c, "emp-1", "AAA010101AAA", desde=date(2026, 9, 1), hasta=date(2026, 10, 1))


def test_valores_por_defecto():
    c = cl.validar("emitidos", "2026-09")

    assert (c.tipo, c.estado, c.metodo, c.pago, c.q, c.filtros) == ("I", "vigente", "todos", "todos", None, [])
    assert (c.orden, c.dir, c.pagina, c.por_pagina) == ("fecha_emision", "asc", 1, 30)


def test_rango_del_periodo():
    assert cl.rango("2026-09") == (date(2026, 9, 1), date(2026, 10, 1))
    assert cl.rango("2026-12") == (date(2026, 12, 1), date(2027, 1, 1))


@pytest.mark.parametrize("kw", [
    {"direccion": "ambos"},
    {"periodo": "2026-13"},
    {"periodo": "septiembre"},
    {"tipo": "X"},
    {"estado": "borrado"},
    {"metodo": "CONTADO"},
    {"pago": "algo"},
    {"dir": "arriba"},
    {"pagina": 0},
    {"por_pagina": 31},
    {"orden": "columna_inexistente"},
    {"orden": "fecha_emision; DROP TABLE cfdi"},
    {"orden": "pagos_relacionados"},          # existe, pero no es ordenable
    {"q": "x" * 101},
])
def test_parametros_fuera_de_catalogo_se_rechazan(kw):
    base = {"direccion": "emitidos", "periodo": "2026-09"}
    base.update(kw)

    with pytest.raises(cl.FiltroInvalido):
        cl.validar(**base)


@pytest.mark.parametrize("filtros", [
    "esto no es json",
    '{"campo": "total"}',                                               # no es lista
    '[{"campo": "inexistente", "op": "igual", "valor": 1}]',
    '[{"campo": "pagos_relacionados", "op": "igual", "valor": "x"}]',   # no filtrable
    '[{"campo": "estado", "op": "igual", "valor": "vigente"}]',         # filtro de barra
    '[{"campo": "total", "op": "contiene", "valor": 1}]',               # operador de otro tipo
    '[{"campo": "total", "op": "mayor", "valor": "mucho"}]',
    '[{"campo": "total", "op": "mayor; DROP TABLE cfdi", "valor": 1}]',
    '[{"campo": "total", "op": "entre", "valor": [1]}]',
    '[{"campo": "fecha_emision", "op": "igual", "valor": "ayer"}]',
    '[{"campo": "categoria", "op": "igual", "valor": "inventada"}]',
    '[{"campo": "serie", "op": "igual", "valor": {"a": 1}}]',
    '[{"campo": "serie", "op": "igual"}]',
    json.dumps([{"campo": "serie", "op": "igual", "valor": "A"}] * 11),
    json.dumps([{"campo": "serie", "op": "igual", "valor": "x" * 201}]),
])
def test_filtros_avanzados_invalidos_se_rechazan(filtros):
    with pytest.raises(cl.FiltroInvalido):
        cl.validar("emitidos", "2026-09", filtros=filtros)


def test_condiciones_base_de_emitidos_y_recibidos():
    sql, params = _condiciones()
    assert sql.startswith("c.empresa_id = %s AND c.rfc_emisor = %s AND c.fecha_emision >= %s AND c.fecha_emision < %s")
    assert params[:4] == ["emp-1", "AAA010101AAA", date(2026, 9, 1), date(2026, 10, 1)]
    assert params[4:] == ["I", "vigente"]

    recibidos = cl.validar("recibidos", "2026-09", estado="todos")
    sql, params = cl.condiciones(recibidos, "emp-1", "AAA010101AAA", desde=date(2026, 9, 1), hasta=date(2026, 10, 1))
    assert "c.rfc_receptor = %s" in sql and "c.estado" not in sql
    assert params == ["emp-1", "AAA010101AAA", date(2026, 9, 1), date(2026, 10, 1), "I"]


def test_sin_tipo_para_los_conteos_por_pestana():
    c = cl.validar("emitidos", "2026-09")
    sql, params = cl.condiciones(c, "e", "R", desde=date(2026, 9, 1), hasta=date(2026, 10, 1), con_tipo=False)

    assert "c.tipo_comprobante" not in sql
    assert params == ["e", "R", date(2026, 9, 1), date(2026, 10, 1), "vigente"]


def test_el_filtro_de_pago_solo_aplica_con_ppd():
    sql, _ = _condiciones(metodo="todos", pago="pendientes")
    assert "monto_cobrado" not in sql

    sql, params = _condiciones(metodo="PPD", pago="pendientes")
    assert "COALESCE(c.monto_cobrado, 0) < c.total" in sql and "PPD" in params

    sql, _ = _condiciones(metodo="PPD", pago="pagadas")
    assert "COALESCE(c.monto_cobrado, 0) >= c.total" in sql


def test_la_busqueda_escapa_los_comodines_y_va_como_parametro():
    sql, params = _condiciones(q="50%_DESC")

    assert "50%" not in sql and "DESC" not in sql
    assert params[-4:] == ["%50\\%\\_DESC%"] * 4
    assert sql.count("ILIKE %s ESCAPE") == 4


def test_filtros_avanzados_generan_sql_parametrizado():
    filtros = json.dumps([
        {"campo": "total", "op": "mayor", "valor": "4000.50"},
        {"campo": "serie", "op": "contiene", "valor": "A%"},
        {"campo": "fecha_emision", "op": "entre", "valor": ["2026-09-01", "2026-09-15"]},
        {"campo": "categoria", "op": "en", "valor": ["venta", "anticipo"]},
        {"campo": "uuid", "op": "igual", "valor": "abc"},
    ])
    sql, params = _condiciones(filtros=filtros)

    assert "c.total > %s" in sql
    assert "c.serie ILIKE %s ESCAPE" in sql
    assert "(c.fecha_emision)::date BETWEEN %s AND %s" in sql
    assert "= ANY(%s)" in sql
    assert "UPPER(c.uuid) = UPPER(%s)" in sql
    assert params[6:] == [
        Decimal("4000.50"), "%A\\%%", date(2026, 9, 1), date(2026, 9, 15), ["venta", "anticipo"], "abc",
    ]


def test_ningun_valor_del_usuario_llega_al_texto_del_sql():
    filtros = json.dumps([{"campo": "serie", "op": "igual", "valor": "'; DROP TABLE cfdi; --"}])
    sql, params = _condiciones(q="'; DROP TABLE cfdi; --", filtros=filtros)

    assert "DROP" not in sql
    assert "'; DROP TABLE cfdi; --" in params
