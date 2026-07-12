# CFDI Intelligence — Guía de proyecto

Backend FastAPI (FiscalCore). El frontend fue removido; su reescritura futura todavía no tiene una rama asociada. Detalles completos en `AGENTS.md`.

## Estructura

- `backend/` — API Python. `backend/main_api.py` arma la app FastAPI; los routers viven en `backend/routers/`.
- `database/migrations/` — migraciones SQL ordenadas (`022_descripcion.sql`).
- `docs/openapi.yaml` — documentación de la API.

## Comandos

- `./dev.sh` (o `dev.bat` en Windows) — levanta el backend local en `:8000`.
- `python -m uvicorn backend.main_api:app --reload --port 8000` — arranca solo el backend.
- `docker compose up -d db` — PostgreSQL para endpoints con datos.
- `python -m pytest` — suite completa (`backend/tests/`, config en `pytest.ini`).
- `python -m pytest -m "not db"` — solo unitarios/mockeados, rápido, sin Postgres.
- `python -m pytest -m db` — solo integración/E2E contra Postgres real (requiere `docker compose up -d db`).

## Estilo

- 4 espacios en Python.
- Módulos Python en snake_case.

## Convenciones

- Commits con prefijos Conventional Commit (`feat:`, `fix:`, `chore:`), imperativos y acotados.

## Seguridad

- Nunca commitear `.env`, credenciales, archivos FIEL, uploads ni dumps de base de datos. Usa `.env.example` para los nombres de variables.
- Validar archivos subidos y entradas externas en los límites del backend.
