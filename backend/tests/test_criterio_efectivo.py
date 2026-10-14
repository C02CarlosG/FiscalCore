"""Criterio de efectivo por empresa (spec 2026-10-13): validación y umbral. Sin DB."""
from decimal import Decimal

import pytest

from backend import criterio_efectivo as c


def test_umbral_legal_es_2000():
    assert c.umbral("legal") == Decimal("2000")


def test_umbral_estricto_es_cero():
    assert c.umbral("estricto") == Decimal("0")


@pytest.mark.parametrize("valor", [None, "", "Legal", "ESTRICTO", "otro", 3, ["legal"], {"c": "legal"}])
def test_validar_rechaza_valores_fuera_del_catalogo(valor):
    with pytest.raises(c.CriterioInvalido):
        c.validar(valor)


def test_umbral_no_asume_legal_con_valor_desconocido():
    with pytest.raises(c.CriterioInvalido):
        c.umbral("laxo")


def test_por_defecto_es_legal():
    assert c.CRITERIO_POR_DEFECTO == "legal"
