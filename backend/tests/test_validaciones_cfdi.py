"""Reglas puras de V1: catálogo, periodos, configuración y condiciones SQL."""
from datetime import date
from decimal import Decimal

import pytest

from backend import validaciones_cfdi as v


def test_catalogo_con_cuatro_validaciones_y_sus_direcciones():
    assert [x.clave for x in v.CATALOGO] == ["pue_forma_99", "pue_con_rep", "egreso_sin_relacion", "no_bancarizado"]
    assert v.POR_CLAVE["no_bancarizado"].direcciones == ("recibidos",)
    assert v.POR_CLAVE["pue_forma_99"].direcciones == ("emitidos", "recibidos")
    assert [x.clave for x in v.de_direccion("emitidos")] == ["pue_forma_99", "pue_con_rep", "egreso_sin_relacion"]


@pytest.mark.parametrize("periodo,esperado", [
    ("2026-03", (date(2026, 3, 1), date(2026, 4, 1), date(2026, 1, 1))),
    ("2026-12", (date(2026, 12, 1), date(2027, 1, 1), date(2026, 1, 1))),
    ("2026-01", (date(2026, 1, 1), date(2026, 2, 1), date(2026, 1, 1))),
])
def test_rangos_del_periodo_y_acumulado(periodo, esperado):
    assert v.rangos(periodo) == esperado


@pytest.mark.parametrize("periodo", ["2026-13", "2026-3", "26-03", "", None, "2026-00"])
def test_periodo_invalido(periodo):
    with pytest.raises(v.ValidacionInvalida):
        v.rangos(periodo)


def test_configuracion_por_defecto():
    c = v.Configuracion.desde_json(None)
    assert c.inactivas == frozenset()
    assert c.umbral_efectivo == Decimal("2000.00")
    assert c.activa("pue_con_rep") is True
    assert c.a_json() == {"inactivas": [], "umbral_efectivo": "2000.00"}


def test_configuracion_ignora_claves_desconocidas_al_leer():
    c = v.Configuracion.desde_json({"inactivas": ["pue_con_rep", "vieja"], "umbral_efectivo": "3000", "otra": 1})
    assert c.inactivas == frozenset({"pue_con_rep"})
    assert c.umbral_efectivo == Decimal("3000.00")
    assert c.activa("pue_con_rep") is False


def test_configuracion_con_umbral_corrupto_usa_el_defecto():
    assert v.Configuracion.desde_json({"umbral_efectivo": "abc"}).umbral_efectivo == Decimal("2000.00")


def test_validar_cambio():
    c = v.validar_cambio({"inactivas": ["no_bancarizado"], "umbral_efectivo": "2500.5"})
    assert c.inactivas == frozenset({"no_bancarizado"})
    assert c.umbral_efectivo == Decimal("2500.50")


@pytest.mark.parametrize("cuerpo", [
    {"inactivas": ["desconocida"]},
    {"umbral_efectivo": "-1"},
    {"umbral_efectivo": "NaN"},
    {"umbral_efectivo": "1e12"},
    {"inactivas": "pue_con_rep"},
])
def test_validar_cambio_rechaza(cuerpo):
    with pytest.raises(v.ValidacionInvalida):
        v.validar_cambio(cuerpo)


def test_condicion_no_bancarizado_lleva_el_umbral_como_parametro():
    sql, params = v.condicion("no_bancarizado", v.Configuracion.desde_json({"umbral_efectivo": "3000"}))
    assert "%s" in sql and "3000" not in sql
    assert params == [Decimal("3000.00")]


def test_condiciones_sin_parametros():
    c = v.Configuracion.desde_json(None)
    for clave in ("pue_forma_99", "pue_con_rep", "egreso_sin_relacion"):
        sql, params = v.condicion(clave, c)
        assert sql and params == []


def test_direccion_y_alcance():
    assert v.validar_direccion("emitidos") == "emitidos"
    with pytest.raises(v.ValidacionInvalida):
        v.validar_direccion("todos")
    with pytest.raises(v.ValidacionInvalida):
        v.validar_validacion("no_bancarizado", "emitidos")
    assert v.validar_validacion("no_bancarizado", "recibidos").clave == "no_bancarizado"
    with pytest.raises(v.ValidacionInvalida):
        v.validar_alcance("anual")
