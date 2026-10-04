"""Catálogos y reglas cruzadas de la DIOT (F6.1). Sin DB."""
import pytest

from backend import diot_catalogos as c


@pytest.mark.parametrize("rfc,esperado", [("PRO010101AAA", "04"), ("XEXX010101000", "05"), ("XAXX010101000", "15"), ("basura", None)])
def test_tipo_de_tercero_por_defecto(rfc, esperado):
    assert c.tipo_tercero_por_defecto(rfc) == esperado


@pytest.mark.parametrize("prov,ok", [
    ({"rfc": "PRO010101AAA", "tipo_tercero": "04", "tipo_operacion": "85"}, True),
    ({"rfc": "PRO010101AAA", "tipo_tercero": "99"}, False),
    ({"rfc": "PRO010101AAA", "tipo_operacion": "99"}, False),
    ({"rfc": "XEXX010101000", "tipo_tercero": "04"}, False),                                   # nacional con RFC genérico
    ({"rfc": "XEXX010101000", "tipo_tercero": "05"}, False),                                   # falta ID fiscal y país
    ({"rfc": "XEXX010101000", "tipo_tercero": "05", "id_fiscal": "1", "pais": "USA"}, True),
    ({"rfc": "XAXX010101000", "tipo_tercero": "15", "tipo_operacion": "87"}, True),
    ({"rfc": "PRO010101AAA", "tipo_tercero": "04", "tipo_operacion": "87"}, False),            # 87 solo con 15
    ({"rfc": "PRO010101AAA"}, True),                                                           # sin clasificar es válido
])
def test_validaciones_cruzadas(prov, ok):
    assert (c.validar(prov) == []) is ok


def test_pendiente_solo_para_extranjeros_incompletos():
    assert c.pendiente({"tipo_tercero": "05"}) is True
    assert c.pendiente({"tipo_tercero": "05", "pais": "USA", "id_fiscal": "1"}) is False
    assert c.pendiente({"tipo_tercero": "04"}) is False
