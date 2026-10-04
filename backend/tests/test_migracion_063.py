"""Migración 063: planes y suscripciones (M7.1). Requiere Postgres."""
import psycopg2
import pytest

from backend.tests.conftest import db_disponible

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


def test_063_siembra_planes_sin_pisar_los_editados():
    from backend import db

    db.init_db()
    original = db.query_one("SELECT nombre, max_rfc FROM planes WHERE clave = 'basico'")
    try:
        db.execute("UPDATE planes SET nombre = 'Básico editado', max_rfc = 7 WHERE clave = 'basico'")
        db.init_db()
        fila = db.query_one("SELECT nombre, max_rfc FROM planes WHERE clave = 'basico'")
        assert (fila["nombre"], fila["max_rfc"]) == ("Básico editado", 7)
    finally:
        db.execute("UPDATE planes SET nombre = %s, max_rfc = %s WHERE clave = 'basico'",
                   (original["nombre"], original["max_rfc"]))

    claves = {f["clave"] for f in db.query_all("SELECT clave FROM planes")}
    assert {"prueba", "basico", "despacho", "ilimitado"} <= claves
    assert db.query_one("SELECT COUNT(*) AS n FROM planes WHERE por_defecto")["n"] == 1
    with pytest.raises(psycopg2.errors.UniqueViolation):
        db.execute("UPDATE planes SET por_defecto = TRUE WHERE clave = 'despacho'")
    with pytest.raises(psycopg2.errors.CheckViolation):
        db.execute("INSERT INTO planes (clave, nombre, precio_mensual) VALUES ('Mal', 'x', 1)")

    columnas = {f["column_name"] for f in db.query_all(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'suscripciones'")}
    assert columnas == {"usuario_id", "plan_clave", "estado", "vigente_hasta", "notas", "asignada_por", "updated_at"}
