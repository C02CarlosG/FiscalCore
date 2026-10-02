"""Migración 030: índices del listado de CFDI y preferencias de tabla. Requiere Postgres."""
import pytest

from backend.tests.conftest import db_disponible

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


def test_030_crea_indices_y_preferencias_y_se_puede_repetir():
    from backend import db

    db.init_db()
    db.init_db()

    indices = {f["indexname"] for f in db.query_all(
        "SELECT indexname FROM pg_indexes WHERE schemaname = 'public' AND tablename IN ('cfdi', 'cfdi_impuestos')")}
    assert {"idx_cfdi_emp_emisor_fecha", "idx_cfdi_emp_receptor_fecha", "idx_cfdi_impuestos_no_iva"} <= indices

    columnas = {f["column_name"] for f in db.query_all(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'preferencias_tabla'")}
    assert columnas == {"usuario_id", "vista", "config", "updated_at"}
