"""Catálogos del SAT usados para describir códigos del CFDI."""
from backend import catalogos_sat as cat


def test_descripcion_une_codigo_y_texto():
    assert cat.descripcion(cat.FORMA_PAGO, "99") == "99 - Por definir"
    assert cat.descripcion(cat.METODO_PAGO, "PPD") == "PPD - Pago en parcialidades o diferido"
    assert cat.descripcion(cat.USO_CFDI, "G01") == "G01 - Adquisición de mercancías"
    assert cat.descripcion(cat.REGIMEN_FISCAL, "601") == "601 - General de Ley Personas Morales"
    assert cat.descripcion(cat.TIPO_RELACION, "07") == "07 - CFDI por aplicación de anticipo"


def test_codigo_fuera_de_catalogo_se_devuelve_tal_cual():
    assert cat.descripcion(cat.FORMA_PAGO, "ZZ") == "ZZ"


def test_codigo_vacio_no_tiene_descripcion():
    assert cat.descripcion(cat.FORMA_PAGO, None) is None
    assert cat.descripcion(cat.FORMA_PAGO, "") is None
