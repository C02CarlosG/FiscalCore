"""Migración 072: criterio de efectivo por empresa. Requiere Postgres."""
import psycopg2
import pytest

from backend.tests.conftest import db_disponible

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


def test_072_idempotente_default_legal_y_check():
    from backend import db

    db.init_db()
    db.init_db()
    empresa = db.execute("INSERT INTO empresas (rfc, razon_social) VALUES ('RCE010101AB1', 'M072') RETURNING id",
                         returning=True)["id"]
    try:
        fila = db.query_one("SELECT criterio_efectivo FROM empresas WHERE id = %s", (empresa,))
        assert fila["criterio_efectivo"] == "legal"
        db.execute("UPDATE empresas SET criterio_efectivo = 'estricto' WHERE id = %s", (empresa,))
        with pytest.raises(psycopg2.errors.CheckViolation):
            db.execute("UPDATE empresas SET criterio_efectivo = 'laxo' WHERE id = %s", (empresa,))
        with pytest.raises(psycopg2.errors.NotNullViolation):
            db.execute("UPDATE empresas SET criterio_efectivo = NULL WHERE id = %s", (empresa,))
    finally:
        db.execute("DELETE FROM empresas WHERE id = %s", (empresa,))
