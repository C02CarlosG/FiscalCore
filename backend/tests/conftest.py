import os

import psycopg2

# La app valida JWT_SECRET al importar deps.py; fijamos valores de prueba para
# que los tests de router puedan importar backend.main_api sin un .env real.
os.environ.setdefault("JWT_SECRET", "test-secret-para-tests")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:8000")
# DB local del docker-compose (puerto 5432). Solo se usa en tests E2E marcados;
# los tests de router mockean la DB y nunca abren conexión.
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/fiscalcore")


def db_disponible() -> bool:
    """Prueba de conexión a Postgres para el marcador `db` (skipif a nivel de módulo).

    Usada por los tests de integración/E2E via:
    ``pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason=...)]``
    Se llama en tiempo de colección, no puede ser un fixture normal.
    """
    try:
        conn = psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=2)
        conn.close()
        return True
    except Exception:
        return False
