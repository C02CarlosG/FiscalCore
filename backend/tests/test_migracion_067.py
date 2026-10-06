"""Migración 067: tokens e historial de «Reiniciar datos». Requiere Postgres."""
import psycopg2
import pytest

from backend.tests.conftest import db_disponible

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


def test_067_idempotente_y_restricciones():
    from backend import db

    db.init_db()
    db.init_db()
    empresa = db.execute("INSERT INTO empresas (rfc, razon_social) VALUES ('RNM010101AB1', 'M067') RETURNING id",
                         returning=True)["id"]
    try:
        db.execute("INSERT INTO reinicios_empresa (empresa_id, token_sha256, conteos, expira_en) "
                   "VALUES (%s, %s, '{}', NOW())", (empresa, "a" * 64))
        with pytest.raises(psycopg2.errors.UniqueViolation):
            db.execute("INSERT INTO reinicios_empresa (empresa_id, token_sha256, conteos, expira_en) "
                       "VALUES (%s, %s, '{}', NOW())", (empresa, "a" * 64))
        with pytest.raises(psycopg2.errors.CheckViolation):
            db.execute("INSERT INTO reinicios_empresa (empresa_id, token_sha256, alcance, conteos, expira_en) "
                       "VALUES (%s, %s, 'ejercicio', '{}', NOW())", (empresa, "b" * 64))
    finally:
        db.execute("DELETE FROM empresas WHERE id = %s", (empresa,))
