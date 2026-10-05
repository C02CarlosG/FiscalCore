"""Migración 064: el CHECK de objeto llega a bases donde validaciones_cfdi_config ya
existía sin él. Requiere Postgres."""
import psycopg2
import pytest

from backend.tests.conftest import db_disponible

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


def _checks(db):
    return [f["def"] for f in db.query_all(
        "SELECT pg_get_constraintdef(oid) AS def FROM pg_constraint "
        "WHERE conrelid = 'validaciones_cfdi_config'::regclass AND contype = 'c'")]


def test_064_agrega_el_check_a_una_tabla_vieja_y_no_lo_duplica():
    from backend import db

    db.init_db()
    # Simula la tabla creada antes de que la 061 tuviera el CHECK.
    for nombre in [f["conname"] for f in db.query_all(
            "SELECT conname FROM pg_constraint WHERE conrelid = 'validaciones_cfdi_config'::regclass AND contype = 'c'")]:
        db.execute(f'ALTER TABLE validaciones_cfdi_config DROP CONSTRAINT "{nombre}"')
    assert _checks(db) == []

    db.init_db()
    db.init_db()
    checks = _checks(db)
    assert len(checks) == 1 and "jsonb_typeof(config)" in checks[0]
    db.execute("DELETE FROM empresas WHERE rfc = 'MIG064101E2E'")
    empresa = db.execute("INSERT INTO empresas (rfc, razon_social) VALUES ('MIG064101E2E', 'Migración 064') RETURNING id",
                         returning=True)
    try:
        with pytest.raises(psycopg2.errors.CheckViolation):
            db.execute("INSERT INTO validaciones_cfdi_config (empresa_id, config) VALUES (%s, '[]'::jsonb)",
                       (empresa["id"],))
    finally:
        db.execute("DELETE FROM empresas WHERE id = %s", (empresa["id"],))
