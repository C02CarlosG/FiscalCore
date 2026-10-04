"""Detalle del CFDI: derivación de columnas de concepto y armado de la respuesta (sin DB)."""
from decimal import Decimal

from backend import cfdi_detalle as cd


def _imp(ambito, impuesto, tasa, base, importe, factor="Tasa"):
    return {"ambito": ambito, "impuesto": impuesto, "tipo_factor": factor,
            "tasa_o_cuota": tasa, "base": base, "importe": importe}


def _concepto(**kw):
    base = dict(linea=1, clave_prod_serv="84111506", no_identificacion=None, cantidad=Decimal("2"),
                clave_unidad="E48", unidad="Servicio", descripcion="Servicio", valor_unitario=Decimal("50"),
                importe=Decimal("100"), descuento=Decimal("0"), objeto_imp="02", cuenta_predial=None, impuestos=[])
    base.update(kw)
    return base


def test_concepto_con_iva_trasladado():
    c = cd.concepto_publico(_concepto(impuestos=[_imp("traslado", "002", "0.160000", "100.00", "16.00")]))

    assert (c["iva_traslado_base"], c["iva_traslado_tasa"], c["iva_traslado_importe"]) == (100.0, 0.16, 16.0)
    assert c["ieps_importe"] is None and c["isr_importe"] is None and c["iva_retencion_importe"] is None


def test_concepto_con_retenciones_e_ieps():
    c = cd.concepto_publico(_concepto(impuestos=[
        _imp("traslado", "002", "0.160000", "100", "16"),
        _imp("traslado", "003", "0.080000", "100", "8"),
        _imp("retencion", "002", "0.106667", "100", "10.67"),
        _imp("retencion", "001", "0.100000", "100", "10"),
    ]))

    assert (c["ieps_base"], c["ieps_tasa"], c["ieps_importe"]) == (100.0, 0.08, 8.0)
    assert (c["iva_retencion_tasa"], c["iva_retencion_importe"]) == (0.106667, 10.67)
    assert (c["isr_tasa"], c["isr_importe"]) == (0.1, 10.0)


def test_varias_tasas_del_mismo_impuesto_suman_y_no_inventan_tasa():
    c = cd.concepto_publico(_concepto(impuestos=[
        _imp("traslado", "002", "0.160000", "60", "9.6"),
        _imp("traslado", "002", "0.000000", "40", "0"),
    ]))

    assert (c["iva_traslado_base"], c["iva_traslado_importe"], c["iva_traslado_tasa"]) == (100.0, 9.6, None)


def test_exento_no_tiene_tasa_ni_importe():
    c = cd.concepto_publico(_concepto(impuestos=[_imp("traslado", "002", None, "100", "0", factor="Exento")]))

    assert (c["iva_traslado_base"], c["iva_traslado_tasa"], c["iva_traslado_importe"]) == (100.0, None, 0.0)


def test_importes_del_concepto_viajan_como_numero():
    c = cd.concepto_publico(_concepto())

    assert (c["cantidad"], c["valor_unitario"], c["importe"], c["descuento"]) == (2.0, 50.0, 100.0, 0.0)
    assert "impuestos" not in c


def test_relacionados_con_descripcion_del_tipo():
    rel = cd.relacionados([{"tipo_relacion": "04", "uuids": ["U1", "U2"]}, {"tipo_relacion": "99", "uuids": []}])

    assert rel[0] == {"tipo_relacion": "04", "descripcion": "04 - Sustitución de los CFDI previos", "uuids": ["U1", "U2"]}
    assert rel[1]["descripcion"] == "99"


def test_relacionados_tolera_nulo_y_basura():
    assert cd.relacionados(None) == []
    assert cd.relacionados([{"uuids": "x"}, "no"]) == []
