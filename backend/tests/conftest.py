import os

# La app valida JWT_SECRET al importar deps.py; fijamos valores de prueba para
# que los tests de router puedan importar backend.main_api sin un .env real.
os.environ.setdefault("JWT_SECRET", "test-secret-para-tests")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:8000")
# DB local del docker-compose (puerto 5432). Solo se usa en tests E2E marcados;
# los tests de router mockean la DB y nunca abren conexión.
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/fiscalcore")
