# CFDI Intelligence — Guía de proyecto

Frontend React/Vite + backend FastAPI (FiscalCore). Plataforma de auditoría fiscal mexicana (dominio SAT/CFDI): concilia CFDIs contra estados de cuenta y detecta riesgos fiscales. Detalles completos en `AGENTS.md`.

## Estructura

- `src/` — frontend. Páginas en `src/pages/`, UI en `src/components/`, contexto en `src/context/`, helpers de API/formato en `src/lib/`.
- `backend/` — API Python. `backend/main_api.py` arma la app FastAPI; los routers viven en `backend/routers/`.
- `database/migrations/` — migraciones SQL idempotentes (`001`–`021`); `backend/db.py` las aplica al arrancar. Nuevas: `022_descripcion.sql`.
- `backend/motor_fiscal.py` — conciliación, riesgos y scoring; parsers en `cfdi_parser.py` / `banco_parser.py` / `constancia_parser.py`.
- Descarga masiva SAT con FIEL: routers `sat.py` / `sat_tasks.py` bajo `/api/v1/sat`; credenciales cifradas con Fernet (`fiel_store.py`).
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
- Reglas de dominio fiscal (no negociables): `Decimal` (nunca `float`) para montos; validar RFC con `RFC_REGEX` de `backend/cfdi_parser.py`; `bcrypt` directo (`import bcrypt as _bcrypt`), nunca passlib; soportar CFDI 3.3 y 4.0.

## Convenciones

- Commits con prefijos Conventional Commit (`feat:`, `fix:`, `chore:`), imperativos y acotados.
- Ejecuta `npm run build` (y `npm test` si aplica) antes de commitear cambios de frontend.

## Seguridad

- Nunca commitear `.env`, credenciales, archivos FIEL, uploads ni dumps de base de datos. Usa `.env.example` para los nombres de variables.
- Validar archivos subidos y entradas externas en los límites del backend.
