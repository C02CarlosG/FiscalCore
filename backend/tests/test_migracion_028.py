"""Migración 028: detalle fiscal del CFDI. Requiere Postgres real."""
import pytest

from backend.tests.conftest import db_disponible

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


def _columnas(db, tabla):
    filas = db.query_all(
        "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s",
        (tabla,),
    )
    return {f["column_name"] for f in filas}


def test_028_crea_tablas_y_columnas_y_se_puede_repetir():
    from backend import db

    db.init_db()
    db.init_db()  # idempotente: aplicarla dos veces no debe fallar

    assert {
        "regimen_emisor", "condiciones_pago", "no_certificado", "periodicidad", "meses",
        "anio_global", "nomina_percepciones", "nomina_deducciones", "nomina_otros_pagos",
        "nomina_gravado", "nomina_exento", "nomina_isr_retenido", "detalle_version",
    } <= _columnas(db, "cfdi")
    assert {"cfdi_id", "ambito", "impuesto", "tipo_factor", "tasa_o_cuota", "base", "importe"} <= _columnas(db, "cfdi_impuestos")
    assert {
        "cfdi_id", "linea", "clave_prod_serv", "no_identificacion", "cantidad", "clave_unidad", "unidad",
        "descripcion", "valor_unitario", "importe", "descuento", "objeto_imp", "cuenta_predial", "impuestos",
    } <= _columnas(db, "cfdi_conceptos")
    assert {"relacion_id", "ambito", "impuesto", "tipo_factor", "tasa_o_cuota", "base", "importe"} <= _columnas(db, "pagos_relaciones_impuestos")
    assert {"moneda_dr", "equivalencia_dr"} <= _columnas(db, "pagos_relaciones")
    assert "version_pago" in _columnas(db, "pagos_cfdi")
