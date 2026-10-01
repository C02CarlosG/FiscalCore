# Repository Guidelines

## Project Structure & Module Organization

This repository contains the FastAPI backend for FiscalCore (`backend/`) and its Next.js frontend (`frontend/`: Next.js + TS + Tailwind + shadcn/ui + TanStack Query), the rewrite of the original React/Vite frontend, already merged into `main`; see `CLAUDE.md` and the spec at `docs/superpowers/specs/2026-07-10-reescritura-frontend-design.md`.

- `backend/` contains the Python API. `backend/main_api.py` wires the FastAPI app, while endpoint modules live in `backend/routers/`.
- `database/migrations/` contains ordered SQL migrations (`001_...` through `027_...`). Keep new migrations numeric, descriptive, and fully idempotent (`IF NOT EXISTS` / `IF EXISTS`), for example `028_nueva_tabla.sql`. Use `.opencode/agent/migration-validator.md` (or the `migration-validator` subagent) before committing new SQL.
- `docs/openapi.yaml` stores API documentation. Deployment targets Railway only, via `Procfile` and `nixpacks.toml` at the root (alongside `Dockerfile` and `docker-compose.yml` for local/container use).

## Build, Test, and Development Commands

- `./dev.sh` starts the full local stack: PostgreSQL (`docker compose`), the backend on `http://localhost:8000` and the frontend on `http://localhost:3000`. It reports which services respond, and Ctrl+C stops everything. `dev.bat` (Windows) only starts the backend.
- `python -m uvicorn backend.main_api:app --reload --port 8000` starts the backend directly.
- `cd frontend && npm run dev` starts the frontend directly (`npm test` runs vitest, `npm run test:e2e` runs playwright).
- `docker compose up -d db` starts PostgreSQL for data-backed endpoints.
- `python -m pytest` runs the test suite (see Testing Guidelines below).

Install backend dependencies inside a virtualenv with `pip install -r requirements.txt`. To also run tests, use `pip install -r requirements-dev.txt` instead (it pulls in `requirements.txt` plus `pytest`/`httpx`, which are test-only and not shipped in production).

## Coding Style & Naming Conventions

Use 4-space indentation for Python. Python modules use snake_case and should keep router responsibilities separated by domain.

## Testing Guidelines

Tests live under `backend/tests/` (`test_*.py`), configured via `pytest.ini` at the repo root (`testpaths = backend/tests`). Run them with the project's `.venv` (Python 3.11):

- `python -m pytest` — full suite (unit + router-mocked + real-Postgres integration/E2E tests).
- `python -m pytest -m "not db"` — fast unit-only run (a few seconds), no Postgres required; skips tests marked `db`.
- `python -m pytest -m db` — only the tests that hit a real Postgres (`docker compose up -d db` first).

Tests that need a real database use `pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason=...)]`, importing `db_disponible` from `backend/tests/conftest.py` — do not duplicate the connection-probe helper in new test files. For backend changes beyond what tests cover, also start Uvicorn and verify relevant routes through `/docs` or targeted HTTP requests.

CI (`.github/workflows/tests.yml`) runs on every push/PR to `main`: a `unit` job (`pytest -m "not db"`, no Postgres) and an `integration` job with an ephemeral Postgres 15 service running the full suite.

## Commit & Pull Request Guidelines

Git history uses Conventional Commit prefixes such as `feat:`, `fix:`, and `chore:`. Keep messages imperative and scoped, for example `fix: validar periodo de empresa`.

Pull requests should include a short summary, linked issue or task when available, test/build evidence, migration notes if SQL changes are included, and screenshots for visible UI changes.

## Subagents & Skills (`.opencode/`)

- `.opencode/agent/backend-dev.md` — desarrollo backend FastAPI (edit/bas permisos para routers, parsers, motor fiscal, schemas, deps).
- `.opencode/agent/dominio-fiscal.md` — revisión de normativa fiscal mexicana SAT (CFDI, conciliación PPD/REP, anticipos, scoring, precisión financiera).
- `.opencode/agent/test-writer.md` — generación de tests pytest con mocks de DB y auth JWT.
- `.opencode/agent/migration-validator.md` — validación de migraciones SQL (idempotencia y seguridad en producción).
- `.opencode/skills/` — skills disponibles: `api-test`, `create-migration`, `nueva-migracion`, `revision-fiscal`. Invocar según corresponda en tareas de código, migraciones o revisión fiscal.

## Specs & Implementation Plans (Estado del proyecto)

### Backend specs (`docs/`)
| Spec | Estado | Plan / Notas |
|---|---|---|
| `modulo-iva-spec.md` | **DISEÑO** (Días 2-5) | Blueprint para cédula de IVA (flujo de efectivo, PPD/REP, prorrateo). Sin bloqueo explícito. |
| `modulo-isr-provisional-spec.md` | **DISEÑO** (Días 7-10) | ISR provisional acumulado. **Bloqueo:** coeficiente de utilidad real (asumido 0.0850) y pago provisional real para calibración. |
| `modulo-cogs-deducciones-spec.md` | **COMPLETO** (Días 11-15, 2026-07-11) | Deducciones autorizadas. **Bloqueo:** caso real de empresa para reemplazar sintético; confirmar precisión de heurística `uso_cfdi`. |

### Frontend plans (`docs/superpowers/plans/` + `specs/`)
- **Fase 1 — Reescritura Next.js** (`feat/frontend-nextjs`): `2026-07-10-reescritura-frontend.md` / spec design. En curso; cubre login, empresas, dashboard, cédula IVA.
- **Fase 2a — Ingesta CFDI/Banco** (`feat/frontend-ingesta`): `2026-07-23-frontend-ingesta.md`. Pendiente; requiere soporte `FormData` en `apiFetch`.
- **Rediseño visual** (consolidación `feat/frontend-ingesta` + `feat/frontend-conciliacion-banco`): `2026-09-16-frontend-rediseno.md`. Pendiente.

### Notas para agentes
- Antes de implementar cualquier módulo de backend pendiente, verificar bloqueos listados (CU real, casos reales de empresa, datos sintéticos a reemplazar).
- Si se trabaja en frontend, confirmar la rama activa (`feat/frontend-nextjs`, `feat/frontend-ingesta`) y consultar el plan correspondiente antes de editar `frontend/`.

## Security & Configuration Tips

Never commit `.env`, credentials, FIEL files, uploads, or local database dumps. Use `.env.example` for required variable names. Note: a `.env` file is currently present in the workspace root — it is covered by `.gitignore`, but verify it is not accidentally staged (`git status`) before committing. Validate all uploaded files and external inputs at backend boundaries.
