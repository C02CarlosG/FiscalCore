"""Migración 061: configuración de validaciones de CFDI (V1). Requiere Postgres."""
import pytest

from backend.tests.conftest import db_disponible

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]

RFC = "MIG061101E2E"


def test_061_crea_la_tabla_se_puede_repetir_y_borra_en_cascada():
    from backend import db

    db.init_db()
    db.init_db()

    columnas = {f["column_name"] for f in db.query_all(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'validaciones_cfdi_config'")}
    assert columnas == {"empresa_id", "config", "usuario_id", "updated_at"}

    db.execute("DELETE FROM empresas WHERE rfc = %s", (RFC,))
    empresa = db.execute("INSERT INTO empresas (rfc, razon_social) VALUES (%s, 'Migración 061') RETURNING id",
                         (RFC,), returning=True)
    try:
        db.execute("INSERT INTO validaciones_cfdi_config (empresa_id) VALUES (%s)", (empresa["id"],))
        fila = db.query_one("SELECT config FROM validaciones_cfdi_config WHERE empresa_id = %s", (empresa["id"],))
        assert fila["config"] == {}
        db.execute("DELETE FROM empresas WHERE id = %s", (empresa["id"],))
        assert db.query_one("SELECT 1 AS x FROM validaciones_cfdi_config WHERE empresa_id = %s", (empresa["id"],)) is None
    finally:
        db.execute("DELETE FROM empresas WHERE rfc = %s", (RFC,))
