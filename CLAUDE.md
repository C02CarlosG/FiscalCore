# CFDI Intelligence — Guía de proyecto

Backend FastAPI (FiscalCore) y frontend Next.js en `frontend/` (Next.js + TS + Tailwind + shadcn/ui + TanStack Query), reescritura del frontend original ya integrada a `main` — ver spec en `docs/superpowers/specs/2026-07-10-reescritura-frontend-design.md`. Detalles completos en `AGENTS.md`.

## Estructura

- `backend/` — API Python. `backend/main_api.py` arma la app FastAPI; los routers viven en `backend/routers/`.
- `frontend/` — app Next.js (App Router). Scripts en `frontend/package.json`.
- `database/migrations/` — migraciones SQL ordenadas (`022_descripcion.sql`).
- `docs/openapi.yaml` — documentación de la API.

## Comandos

- `./dev.sh` — levanta el stack local completo: PostgreSQL (`docker compose`), backend en `:8000` y frontend en `:3000`; avisa qué servicio responde y Ctrl+C detiene todo. `dev.bat` (Windows) solo levanta el backend.
- `python -m uvicorn backend.main_api:app --reload --port 8000` — arranca solo el backend.
- `cd frontend && npm run dev` — arranca solo el frontend (`npm test` para vitest, `npm run test:e2e` para playwright).
- `docker compose up -d db` — PostgreSQL para endpoints con datos.
- `pip install -r requirements-dev.txt` — instala dependencias de la app + de test (pytest, httpx). `requirements.txt` solo trae las de producción.
- `python -m pytest` — suite completa (`backend/tests/`, config en `pytest.ini`).
- `python -m pytest -m "not db"` — solo unitarios/mockeados, rápido, sin Postgres.
- `python -m pytest -m db` — solo integración/E2E contra Postgres real (requiere `docker compose up -d db`).
- CI (`.github/workflows/tests.yml`) corre ambos jobs en cada push/PR a `main`: unitarios sin Postgres, e integración completa con un servicio Postgres efímero.

## Estilo

- 4 espacios en Python.
- Módulos Python en snake_case.

## Convenciones

- Commits con prefijos Conventional Commit (`feat:`, `fix:`, `chore:`), imperativos y acotados.

## Seguridad

- Nunca commitear `.env`, credenciales, archivos FIEL, uploads ni dumps de base de datos. Usa `.env.example` para los nombres de variables.
- Validar archivos subidos y entradas externas en los límites del backend.
