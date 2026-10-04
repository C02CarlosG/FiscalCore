"""Migración 040: extracción v2 del XML. Requiere Postgres real."""
import pytest

from backend.tests.conftest import db_disponible

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


def _columnas(db, tabla):
    filas = db.query_all(
        "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s",
        (tabla,),
    )
    return {f["column_name"] for f in filas}


def test_040_crea_tablas_y_columnas_y_se_puede_repetir():
    from backend import db

    db.init_db()
    db.init_db()  # idempotente

    assert {"rfc_a_cuenta_terceros", "nombre_a_cuenta_terceros", "regimen_a_cuenta_terceros"} <= _columnas(db, "cfdi_conceptos")
    assert "objeto_imp_dr" in _columnas(db, "pagos_relaciones")
    assert {"pago_id", "ambito", "impuesto", "tipo_factor", "tasa_o_cuota", "base", "importe"} == _columnas(db, "pagos_impuestos") - {"id"}
    assert {
        "cfdi_id", "monto_total_pagos", "total_retenciones_iva", "total_retenciones_isr", "total_retenciones_ieps",
        "total_traslados_base_iva16", "total_traslados_iva16", "total_traslados_base_iva8", "total_traslados_iva8",
        "total_traslados_base_iva0", "total_traslados_iva0", "total_traslados_base_exento",
    } == _columnas(db, "cfdi_pagos_totales")
    assert {
        "cfdi_id", "nodo", "tipo_nomina", "fecha_pago", "fecha_inicial_pago", "fecha_final_pago", "num_dias_pagados",
        "tipo_regimen", "num_empleado", "total_percepciones", "total_deducciones", "total_otros_pagos", "total_sueldos",
        "total_separacion_indemnizacion", "total_jubilacion_pension_retiro", "total_gravado", "total_exento",
        "total_otras_deducciones", "total_impuestos_retenidos", "sep_total_pagado", "sep_anios_servicio",
        "sep_ultimo_sueldo_mens_ord", "sep_ingreso_acumulable", "sep_ingreso_no_acumulable",
        "jub_total_una_exhibicion", "jub_total_parcialidad", "jub_monto_diario", "jub_ingreso_acumulable",
        "jub_ingreso_no_acumulable",
    } <= _columnas(db, "cfdi_nominas")
    assert {
        "nomina_id", "categoria", "linea", "tipo", "clave", "concepto", "importe_gravado", "importe_exento",
        "importe", "subsidio_causado", "saldo_a_favor", "anio_saldo_a_favor", "remanente_saldo_a_favor",
    } <= _columnas(db, "cfdi_nomina_conceptos")


def test_040_no_pierde_datos_al_repetirse():
    """Aplicarla otra vez sobre una base con datos no los borra (ADD/CREATE IF NOT EXISTS)."""
    from backend import db

    db.init_db()
    antes = db.query_one("SELECT COUNT(*) AS n FROM cfdi_nominas")["n"]
    db.init_db()
    assert db.query_one("SELECT COUNT(*) AS n FROM cfdi_nominas")["n"] == antes


def test_040_los_textos_crudos_del_xml_tienen_holgura():
    """Un valor fuera de catálogo no debe impedir guardar el comprobante (el reproceso
    lo marcaría como error y no lo reintentaría)."""
    from backend import db

    db.init_db()
    filas = db.query_all(
        """SELECT table_name, column_name, data_type, character_maximum_length AS largo
           FROM information_schema.columns
           WHERE table_schema = 'public' AND (
               (table_name = 'cfdi_nominas' AND column_name IN ('tipo_nomina', 'tipo_regimen', 'num_empleado'))
            OR (table_name = 'cfdi_nomina_conceptos' AND column_name IN ('tipo', 'clave', 'concepto'))
            OR (table_name = 'cfdi_conceptos' AND column_name IN ('rfc_a_cuenta_terceros', 'nombre_a_cuenta_terceros'))
            OR (table_name = 'pagos_relaciones' AND column_name = 'objeto_imp_dr'))""")
    assert len(filas) == 9
    for f in filas:
        assert f["data_type"] == "text" or f["largo"] >= 20, f
