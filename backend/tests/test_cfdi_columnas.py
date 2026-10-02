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
