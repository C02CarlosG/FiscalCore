# CFDI Intelligence — Guía de proyecto

Backend FastAPI (FiscalCore). El frontend fue removido mientras se reescribe en la rama `refactor/modularizar-frontend-backend`. Detalles completos en `AGENTS.md`.

## Estructura

- `backend/` — API Python. `backend/main_api.py` arma la app FastAPI; los routers viven en `backend/routers/`.
- `database/migrations/` — migraciones SQL ordenadas (`022_descripcion.sql`).
- `docs/openapi.yaml` — documentación de la API.

## Comandos

- `./dev.sh` (o `dev.bat` en Windows) — levanta el backend local en `:8000`.
- `python -m uvicorn backend.main_api:app --reload --port 8000` — arranca solo el backend.
- `docker compose up -d db` — PostgreSQL para endpoints con datos.

## Estilo

- 4 espacios en Python.
- Módulos Python en snake_case.

## Convenciones

- Commits con prefijos Conventional Commit (`feat:`, `fix:`, `chore:`), imperativos y acotados.

## Seguridad

- Nunca commitear `.env`, credenciales, archivos FIEL, uploads ni dumps de base de datos. Usa `.env.example` para los nombres de variables.
- Validar archivos subidos y entradas externas en los límites del backend.
