---
name: api-test
description: Genera tests pytest para un router FastAPI de FiscalCore, con mocks de DB y auth JWT
---

Cuando el usuario invoque `/api-test <nombre_router>` (ej: `/api-test riesgos`), sigue estos pasos:

## Pasos

1. **Lee el router**: `backend/routers/<nombre_router>.py`
2. **Lee el contexto**: `backend/deps.py`, `backend/schemas.py`, `backend/db.py` (entender las dependencias inyectadas)
3. **Genera el archivo de tests**: `backend/tests/test_<nombre_router>.py`
4. Si no existe el directorio `tests/`, créalo con un `tests/__init__.py` vacío

## Estructura del archivo de tests

```python
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from backend.main_api import app

# --- Fixtures ---

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def auth_headers():
    """JWT válido para un usuario de prueba."""
    from jose import jwt
    import os
    secret = os.getenv("SECRET_KEY", "test_secret_key")
    token = jwt.encode(
        {"sub": "test@fiscalcore.mx", "user_id": "00000000-0000-0000-0000-000000000001"},
        secret, algorithm="HS256"
    )
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def empresa_id():
    return "00000000-0000-0000-0000-000000000002"

# --- Tests ---
```

## Qué cubrir por endpoint

Por cada endpoint en el router, genera **3 tests**:

1. **Happy path** — request válido con mock de DB, verifica status 200/201 y estructura de respuesta
2. **Sin autenticación** — sin `Authorization` header, verifica 401/403
3. **Input inválido** — body/params incorrectos, verifica 422 o el error apropiado

## Cómo mockear la DB

```python
@patch("backend.db.query_all")
@patch("backend.db.query_one")
def test_ejemplo(mock_one, mock_all, client, auth_headers, empresa_id):
    mock_all.return_value = [{"id": "...", "campo": "valor"}]
    mock_one.return_value = {"id": empresa_id, "rfc": "TEST123456ABC"}
    
    response = client.get(f"/api/v1/empresas/{empresa_id}/riesgos", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "riesgos" in data
```

## Reglas de este proyecto

- Usar `unittest.mock.patch` sobre `backend.db` (no mockear psycopg2 directo)
- Los UUIDs de prueba deben ser constantes fijas (facilita el debug)
- Los JWTs de prueba deben usar el mismo `SECRET_KEY` que el proyecto (leer de `os.getenv`)
- No hacer requests reales a la DB ni al SAT en los tests
- Mantener los tests independientes entre sí (sin estado compartido)

## Dependencias necesarias

Si no existe `requirements-dev.txt`, créalo con:
```
pytest>=8.0
pytest-asyncio>=0.23
httpx>=0.27
```

## Al terminar

Confirma: "Tests generados en `backend/tests/test_<nombre>.py` — N endpoints × 3 tests = N tests en total."
Muestra el comando para correrlos: `.venv/bin/python -m pytest backend/tests/test_<nombre>.py -v`
