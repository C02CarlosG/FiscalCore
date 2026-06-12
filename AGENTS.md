# Repository Guidelines

## Project Structure & Module Organization

FiscalCore is a Mexican tax-audit platform (SAT/CFDI domain): it reconciles CFDIs against bank statements and surfaces fiscal risks. The repository contains a React/Vite frontend and a FastAPI backend.

- `src/` contains the frontend application. Pages live in `src/pages/`, reusable UI in `src/components/`, shared context in `src/context/`, and API/format helpers in `src/lib/`.
- `backend/` contains the Python API. `backend/main_api.py` wires the FastAPI app, while endpoint modules live in `backend/routers/` (`auth`, `empresas`, `ingesta`, `riesgos`, `scoring`, `conciliacion`, `emitidos`, `dashboard`, `reportes`, `admin`, `sat`, `sat_tasks`). Core logic sits in `motor_fiscal.py` (reconciliation, risks, scoring), the parsers (`cfdi_parser.py`, `banco_parser.py`, `constancia_parser.py`), `risk_patterns_service.py`, and the SAT FIEL stack (`sat_fiel.py`, `fiel_store.py`).
- `database/migrations/` contains ordered, idempotent SQL migrations (`001`–`021`); `backend/db.py` applies them all at startup via `init_db()`. Keep new migrations numeric and descriptive, for example `022_nueva_tabla.sql`.
- `docs/openapi.yaml` stores API documentation, and deployment/config files live at the root (`Dockerfile`, `docker-compose.yml`, `vercel.json`, `Procfile`, `nixpacks.toml`).

### Domain & key flows

- Pipeline: user files (CFDI XML / bank CSV-XLSX / Constancia PDF) → parser layer → `motor_fiscal.py` → REST API → PostgreSQL.
- SAT bulk download with FIEL lives under `/api/v1/sat`: request/track downloads (`/solicitar`, `/solicitudes`, `/solicitudes/{id}/verificar`, `/solicitudes/{id}/descargar`) and per-company FIEL management (`/empresas/{id}/fiel/{guardar,estado,sync}`, `DELETE .../fiel`). FIEL credentials are stored Fernet-encrypted (`FIEL_ENCRYPTION_KEY`).
- Auth is JWT (`python-jose`); the model is accountant-centric (one user → many companies via `usuario_empresas`).

## Build, Test, and Development Commands

- `./dev.sh` starts the local stack: FastAPI on `http://localhost:8000` and Vite on `http://localhost:3001`.
- `npm run dev` starts only the Vite frontend.
- `npm run build` creates the production frontend bundle in `dist/`.
- `npm run preview` serves the built frontend locally.
- `python -m uvicorn backend.main_api:app --reload --port 8000` starts only the backend.
- `docker compose up -d db` starts PostgreSQL for data-backed endpoints.

Install frontend dependencies with `npm install`. Install backend dependencies inside a virtualenv with `pip install -r requirements.txt`.

## Coding Style & Naming Conventions

Use 2-space indentation for JSX/CSS and 4-space indentation for Python. React components use PascalCase (`DashboardPage.jsx`, `ScoreGauge.jsx`); hooks, helpers, and variables use camelCase in JavaScript. Python modules use snake_case and should keep router responsibilities separated by domain. Prefer existing shared helpers in `src/lib/` and shared UI primitives in `src/components/ui/` before adding new abstractions.

Fiscal-domain rules are non-negotiable: use `Decimal` (never `float`) for monetary amounts; validate RFCs with the shared `RFC_REGEX` in `backend/cfdi_parser.py`; hash passwords with `bcrypt` imported directly (`import bcrypt as _bcrypt`), never through passlib. CFDI parsing must handle both 3.3 and 4.0 namespaces.

## Testing Guidelines

Frontend tests run with Vitest: `npm test` (CI mode) or `npm run test:watch`. Specs live under `tests/` as `*.test.{js,jsx}` (config in `vitest.config.mjs`). Run `npm test` and `npm run build` before committing frontend changes. The backend has no automated test suite yet — start Uvicorn and verify relevant routes through `/docs` or targeted HTTP requests. When adding backend tests, place them under `tests/` using `test_*.py` and add the runner command to this guide and project config.

## Commit & Pull Request Guidelines

Git history uses Conventional Commit prefixes such as `feat:`, `fix:`, and `chore:`. Keep messages imperative and scoped, for example `fix: validar periodo de empresa`.

Pull requests should include a short summary, linked issue or task when available, test/build evidence, migration notes if SQL changes are included, and screenshots for visible UI changes.

## Security & Configuration Tips

Never commit `.env`, credentials, FIEL files, uploads, or local database dumps. Use `.env.example` for required variable names. Validate all uploaded files and external inputs at backend boundaries.
