import os

# La app valida JWT_SECRET al importar deps.py; fijamos valores de prueba para
# que los tests de router puedan importar backend.main_api sin un .env real.
os.environ.setdefault("JWT_SECRET", "test-secret-para-tests")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:8000")
