"""Catálogo de columnas del listado de CFDI."""
import pytest

from backend import cfdi_columnas as cc

VISIBLES = [
    "fecha_emision", "serie", "folio", "rfc_contraparte", "contraparte", "total", "saldo",
    "pagos_relacionados", "subtotal", "descuento", "neto", "traslado_iva", "uuid_sustituye",
    "uso_cfdi", "metodo_pago", "forma_pago", "categoria", "estado",
]


@pytest.mark.parametrize("direccion", ["emitidos", "recibidos"])
def test_claves_unicas_y_tipos_de_dato_validos(direccion):
    cols = cc.columnas(direccion, "I")
    claves = [c.clave for c in cols]

    assert len(claves) == len(set(claves))
    assert {c.tipo_dato for c in cols} <= set(cc.TIPOS_DATO)


def test_columnas_visibles_por_defecto_en_su_orden():
    assert [c.clave for c in cc.columnas("emitidos", "I") if c.visible] == VISIBLES


def test_la_contraparte_depende_de_la_direccion():
    emitidos = {c.clave: c for c in cc.columnas("emitidos", "I")}
    recibidos = {c.clave: c for c in cc.columnas("recibidos", "I")}

    assert (emitidos["rfc_contraparte"].etiqueta, emitidos["rfc_contraparte"].sql) == ("RFC receptor", "c.rfc_receptor")
    assert (emitidos["contraparte"].etiqueta, emitidos["contraparte"].sql) == ("Receptor", "c.nombre_receptor")
    assert (recibidos["rfc_contraparte"].etiqueta, recibidos["rfc_contraparte"].sql) == ("RFC emisor", "c.rfc_emisor")
    assert (recibidos["contraparte"].etiqueta, recibidos["contraparte"].sql) == ("Emisor", "c.nombre_emisor")


def test_columnas_calculadas_fuera_del_cfdi_no_se_ordenan_ni_filtran():
    cols = {c.clave: c for c in cc.columnas("emitidos", "I")}

    for clave in ("traslado_ieps", "retencion_ieps", "pagos_relacionados", "uuid_relacionado", "forma_pago_desc"):
        assert (cols[clave].ordenable, cols[clave].filtrable) == (False, False), clave
    assert (cols["total"].ordenable, cols["total"].filtrable) == (True, True)


def test_los_filtros_de_la_barra_no_se_repiten_en_el_filtro_avanzado():
    cols = {c.clave: c for c in cc.columnas("emitidos", "I")}

    for clave in ("tipo_comprobante", "estado", "metodo_pago"):
        assert cols[clave].ordenable is True
        assert cols[clave].filtrable is False


def test_la_version_publica_no_expone_el_sql():
    publica = cc.columnas("emitidos", "I")[0].publica()

    assert publica == {
        "clave": "fecha_emision", "etiqueta": "Fecha expedición", "tipo_dato": "fecha",
        "grupo": "encabezado", "visible_por_defecto": True, "ordenable": True, "filtrable": True,
        "opciones": [],
    }


def test_cada_descripcion_apunta_a_una_columna_de_codigo_existente():
    claves = {c.clave for c in cc.columnas("emitidos", "I")}

    for derivada, (origen, catalogo) in cc.DESCRIPCIONES.items():
        assert derivada in claves and origen in claves
        assert isinstance(catalogo, dict) and catalogo


def test_columnas_de_concepto():
    cols = cc.columnas_concepto()

    assert {c.grupo for c in cols} == {"concepto"}
    assert [c.clave for c in cols if c.visible] == [
        "clave_prod_serv", "cantidad", "clave_unidad", "descripcion", "valor_unitario",
        "importe", "descuento", "iva_traslado_base", "iva_traslado_importe",
    ]


# ─── Nómina y Pago tienen su propio juego de columnas (F3.5b) ─────────────────

import re

from backend.cfdi_columnas import columnas, laterales

_TIPOS = ("I", "E", "T", "N", "P")
_ALIAS_DE_LATERALES = {"I": {"imp", "pag"}, "E": {"imp", "pag"}, "T": {"imp", "pag"},
                       "N": {"nom", "sub"}, "P": {"ptot", "pgo", "rel"}}


@pytest.mark.parametrize("direccion", ["emitidos", "recibidos"])
@pytest.mark.parametrize("tipo", _TIPOS)
def test_cada_tipo_tiene_claves_unicas_y_columnas_visibles(direccion, tipo):
    claves = [c.clave for c in columnas(direccion, tipo)]
    assert len(claves) == len(set(claves))
    assert any(c.visible for c in columnas(direccion, tipo))
    assert {"fecha_emision", "rfc_contraparte", "contraparte", "estado", "uuid"} <= set(claves)


@pytest.mark.parametrize("tipo", _TIPOS)
def test_las_columnas_solo_usan_los_alias_que_su_tipo_define(tipo):
    """Una columna que apunta a un alias que el tipo no une rompería la consulta del listado."""
    permitidos = {"c"} | _ALIAS_DE_LATERALES[tipo]
    for col in columnas("emitidos", tipo):
        if col.sql is None:
            continue
        usados = set(re.findall(r"\b([a-z]{1,4})\.[a-z_]+", col.sql))
        usados -= {"r", "u", "i", "n", "k", "p", "pr", "e"}   # alias internos de subconsultas propias
        assert usados <= permitidos, (tipo, col.clave, usados)


@pytest.mark.parametrize("tipo", _TIPOS)
def test_las_columnas_ordenables_y_filtrables_solo_dependen_de_la_tabla_cfdi(tipo):
    """Orden y filtro corren sobre toda la tabla, antes de recortar la página: no pueden usar
    las subconsultas LATERAL (que solo se calculan sobre la página)."""
    for col in columnas("emitidos", tipo):
        if col.ordenable:
            assert not re.search(r"\b(nom|sub|ptot|pgo|rel|imp|pag)\.", col.sql), (tipo, col.clave)


def test_laterales_por_tipo():
    assert "cfdi_nominas" in laterales("N") and "cfdi_pagos_totales" not in laterales("N")
    assert "cfdi_pagos_totales" in laterales("P") and "cfdi_nominas" not in laterales("P")
    assert laterales("I") == laterales("E") == laterales("T")
    assert "pagos_relaciones" in laterales("I")


def test_nomina_y_pago_no_publican_las_columnas_de_comprobante():
    nomina = {c.clave for c in columnas("emitidos", "N")}
    pago = {c.clave for c in columnas("emitidos", "P")}
    assert not ({"subtotal", "saldo", "metodo_pago", "categoria", "pagos_relacionados"} & nomina)
    assert not ({"subtotal", "saldo", "metodo_pago", "categoria"} & pago)
    assert "ajuste_isr_retenido" not in nomina


def test_la_contraparte_de_nomina_y_pago_sigue_la_direccion():
    assert {c.clave: c.sql for c in columnas("emitidos", "N")}["rfc_contraparte"] == "c.rfc_receptor"
    assert {c.clave: c.sql for c in columnas("recibidos", "P")}["rfc_contraparte"] == "c.rfc_emisor"
