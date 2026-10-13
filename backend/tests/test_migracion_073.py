"""Migración 073: lista 69-B. Requiere Postgres."""
import psycopg2
import pytest

from backend.tests.conftest import db_disponible

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


def _importacion(db, estado="correcta"):
    return db.execute(
        "INSERT INTO efos_importaciones (origen, sha256, filas, rfc_unicos, estado) VALUES ('manual', %s, 2, 1, %s) RETURNING id",
        ("a" * 64, estado), returning=True)["id"]


def test_073_idempotente_checks_y_vista_con_mayor_no():
    from backend import db

    db.init_db()
    db.init_db()
    db.execute("DELETE FROM efos_lista")
    db.execute("DELETE FROM efos_importaciones")
    imp = _importacion(db)
    try:
        for no, sit in ((155, "Definitivo"), (156, "Sentencia Favorable")):
            db.execute("INSERT INTO efos_lista (importacion_id, no_sat, rfc, nombre, situacion) VALUES (%s, %s, 'AAS110331G59', 'X', %s)",
                       (imp, no, sit))
        assert db.query_one("SELECT situacion FROM efos_vigente WHERE rfc = 'AAS110331G59'")["situacion"] == "Sentencia Favorable"
        with pytest.raises(psycopg2.errors.CheckViolation):
            db.execute("INSERT INTO efos_lista (importacion_id, no_sat, rfc, nombre, situacion) VALUES (%s, 1, 'AAA010101AB1', 'X', 'Otra')", (imp,))
        with pytest.raises(psycopg2.errors.UniqueViolation):
            db.execute("INSERT INTO efos_lista (importacion_id, no_sat, rfc, nombre, situacion) VALUES (%s, 155, 'BBB010101AB1', 'X', 'Presunto')", (imp,))
        with pytest.raises(psycopg2.errors.CheckViolation):
            _importacion(db, estado="rara")
    finally:
        db.execute("DELETE FROM efos_lista")
        db.execute("DELETE FROM efos_importaciones")
