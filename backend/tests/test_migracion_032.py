"""Migración 032: correos únicos sin distinguir mayúsculas y token_version. Requiere Postgres."""
import uuid
from pathlib import Path

import psycopg2
import pytest

from backend.tests.conftest import db_disponible

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]

_MIGRACION = Path(__file__).parent.parent.parent / "database" / "migrations" / "032_seguridad_usuarios.sql"


@pytest.fixture()
def correos():
    """Dos correos que solo difieren en mayúsculas; limpia al terminar y restaura el índice."""
    from backend import db

    db.init_db()
    base = f"mig032-{uuid.uuid4().hex[:8]}@Test.local"
    yield base, base.lower()
    db.execute("DELETE FROM usuarios WHERE lower(email) = %s", (base.lower(),))
    db._run_sql_file(_MIGRACION.name)


def _usuario(db, email):
    return db.execute(
        "INSERT INTO usuarios (email, password_hash, nombre) VALUES (%s, 'x', 'T') RETURNING id",
        (email,), returning=True)


def test_032_es_idempotente_y_agrega_token_version():
    from backend import db

    db.init_db()
    db.init_db()
    col = db.query_one(
        "SELECT column_default, is_nullable FROM information_schema.columns "
        "WHERE table_name = 'usuarios' AND column_name = 'token_version'")
    assert col and col["is_nullable"] == "NO" and "0" in col["column_default"]


def test_032_el_indice_impide_correos_que_solo_difieren_en_mayusculas(correos):
    from backend import db

    mixto, minus = correos
    _usuario(db, minus)
    with pytest.raises(psycopg2.errors.UniqueViolation):
        _usuario(db, mixto)


def test_032_normaliza_correos_existentes(correos):
    from backend import db

    mixto, minus = correos
    db.execute("DROP INDEX IF EXISTS idx_usuarios_email_lower")
    _usuario(db, f"  {mixto}")
    db._run_sql_file(_MIGRACION.name)
    assert db.query_one("SELECT 1 FROM usuarios WHERE email = %s", (minus,))


def test_032_falla_con_duplicados_sin_borrar_cuentas(correos):
    from backend import db

    mixto, minus = correos
    db.execute("DROP INDEX IF EXISTS idx_usuarios_email_lower")
    _usuario(db, mixto)
    _usuario(db, minus)
    with pytest.raises(Exception) as exc:
        db._run_sql_file(_MIGRACION.name)
    assert minus in str(exc.value) and "2 cuentas" in str(exc.value)
    assert db.query_one("SELECT count(*) AS n FROM usuarios WHERE lower(email) = %s", (minus,))["n"] == 2
    db.execute("DELETE FROM usuarios WHERE email = %s", (mixto,))   # el fixture restaura el índice
