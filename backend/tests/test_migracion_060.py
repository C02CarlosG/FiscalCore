"""Migración 060: tabla documentos_fiscales (F8). Requiere Postgres."""
import psycopg2
import pytest

from backend.tests.conftest import db_disponible

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]

RFC = "MIG060101E2E"


def test_060_crea_documentos_fiscales_y_se_puede_repetir():
    from backend import db

    db.init_db()
    db.init_db()

    columnas = {f["column_name"] for f in db.query_all(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'documentos_fiscales'")}
    assert columnas == {
        "id", "empresa_id", "tipo", "nombre_archivo", "contenido", "tamano_bytes", "sha256",
        "rfc", "fecha_emision", "datos", "usuario_id", "created_at",
    }
    indices = {f["indexname"] for f in db.query_all(
        "SELECT indexname FROM pg_indexes WHERE tablename = 'documentos_fiscales'")}
    assert "idx_documentos_fiscales_empresa" in indices


def test_060_rechaza_otro_tipo_y_el_mismo_pdf_dos_veces():
    from backend import db

    db.init_db()
    db.execute("DELETE FROM empresas WHERE rfc = %s", (RFC,))
    empresa = db.execute(
        "INSERT INTO empresas (rfc, razon_social) VALUES (%s, 'Migración 060') RETURNING id",
        (RFC,), returning=True,
    )
    insertar = (
        "INSERT INTO documentos_fiscales (empresa_id, tipo, nombre_archivo, contenido, tamano_bytes, sha256, rfc) "
        "VALUES (%s, %s, 'a.pdf', %s, 3, %s, %s)"
    )
    try:
        db.execute(insertar, (empresa["id"], "constancia", b"pdf", "a" * 64, RFC))
        with pytest.raises(psycopg2.errors.UniqueViolation):
            db.execute(insertar, (empresa["id"], "constancia", b"pdf", "a" * 64, RFC))
        with pytest.raises(psycopg2.errors.CheckViolation):
            db.execute(insertar, (empresa["id"], "acta", b"pdf", "b" * 64, RFC))
        with pytest.raises(psycopg2.errors.CheckViolation):
            db.execute(
                "INSERT INTO documentos_fiscales (empresa_id, tipo, nombre_archivo, contenido, tamano_bytes, sha256, rfc) "
                "VALUES (%s, 'opinion', 'g.pdf', %s, 1, %s, %s)",
                (empresa["id"], b"x" * (5 * 1024 * 1024 + 1), "c" * 64, RFC),
            )
        # Se borra en cascada con la empresa.
        db.execute("DELETE FROM empresas WHERE id = %s", (empresa["id"],))
        fila = db.query_one("SELECT COUNT(*) AS n FROM documentos_fiscales WHERE rfc = %s", (RFC,))
        assert fila["n"] == 0
    finally:
        db.execute("DELETE FROM empresas WHERE rfc = %s", (RFC,))
