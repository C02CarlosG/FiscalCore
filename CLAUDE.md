# CFDI Intelligence — Guía de proyecto

Frontend React/Vite + backend FastAPI (FiscalCore). Detalles completos en `AGENTS.md`.

## Estructura

- `src/` — frontend. Páginas en `src/pages/`, UI en `src/components/`, contexto en `src/context/`, helpers de API/formato en `src/lib/`.
- `backend/` — API Python. `backend/main_api.py` arma la app FastAPI; los routers viven en `backend/routers/`.
- `database/migrations/` — migraciones SQL ordenadas (`022_descripcion.sql`).
- `docs/openapi.yaml` — documentación de la API.

## Comandos

- `./dev.sh` — levanta el stack local: FastAPI (`:8000`) + Vite (`:3001`).
- `npm run dev` / `npm run build` / `npm run preview` — frontend.
- `npm test` — Vitest.
- `python -m uvicorn backend.main_api:app --reload --port 8000` — solo backend.
- `docker compose up -d db` — PostgreSQL para endpoints con datos.

## Estilo

- 2 espacios en JSX/CSS, 4 en Python.
- Componentes React en PascalCase; hooks/helpers/variables JS en camelCase; módulos Python en snake_case.
- Reutiliza helpers de `src/lib/` y primitivos de `src/components/ui/` antes de crear abstracciones nuevas.

## Convenciones

- Commits con prefijos Conventional Commit (`feat:`, `fix:`, `chore:`), imperativos y acotados.
- Ejecuta `npm run build` (y `npm test` si aplica) antes de commitear cambios de frontend.

## Seguridad

- Nunca commitear `.env`, credenciales, archivos FIEL, uploads ni dumps de base de datos. Usa `.env.example` para los nombres de variables.
- Validar archivos subidos y entradas externas en los límites del backend.
