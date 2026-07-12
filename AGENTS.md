# Repository Guidelines

## Project Structure & Module Organization

This repository contains the FastAPI backend for FiscalCore. The previous React/Vite frontend was removed as legacy cleanup; its future rewrite does not yet have an associated branch.

- `backend/` contains the Python API. `backend/main_api.py` wires the FastAPI app, while endpoint modules live in `backend/routers/`.
- `database/migrations/` contains ordered SQL migrations. Keep new migrations numeric and descriptive, for example `022_nueva_tabla.sql`.
- `docs/openapi.yaml` stores API documentation. Deployment targets Railway only, via `Procfile` and `nixpacks.toml` at the root (alongside `Dockerfile` and `docker-compose.yml` for local/container use).

## Build, Test, and Development Commands

- `./dev.sh` (or `dev.bat` on Windows) starts the backend locally on `http://localhost:8000`.
- `python -m uvicorn backend.main_api:app --reload --port 8000` starts the backend directly.
- `docker compose up -d db` starts PostgreSQL for data-backed endpoints.
- `python -m pytest` runs the test suite (see Testing Guidelines below).

Install backend dependencies inside a virtualenv with `pip install -r requirements.txt`.

## Coding Style & Naming Conventions

Use 4-space indentation for Python. Python modules use snake_case and should keep router responsibilities separated by domain.

## Testing Guidelines

Tests live under `backend/tests/` (`test_*.py`), configured via `pytest.ini` at the repo root (`testpaths = backend/tests`). Run them with the project's `.venv` (Python 3.11):

- `python -m pytest` — full suite (unit + router-mocked + real-Postgres integration/E2E tests).
- `python -m pytest -m "not db"` — fast unit-only run (a few seconds), no Postgres required; skips tests marked `db`.
- `python -m pytest -m db` — only the tests that hit a real Postgres (`docker compose up -d db` first).

Tests that need a real database use `pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason=...)]`, importing `db_disponible` from `backend/tests/conftest.py` — do not duplicate the connection-probe helper in new test files. For backend changes beyond what tests cover, also start Uvicorn and verify relevant routes through `/docs` or targeted HTTP requests.

## Commit & Pull Request Guidelines

Git history uses Conventional Commit prefixes such as `feat:`, `fix:`, and `chore:`. Keep messages imperative and scoped, for example `fix: validar periodo de empresa`.

Pull requests should include a short summary, linked issue or task when available, test/build evidence, migration notes if SQL changes are included, and screenshots for visible UI changes.

## Security & Configuration Tips

Never commit `.env`, credentials, FIEL files, uploads, or local database dumps. Use `.env.example` for required variable names. Validate all uploaded files and external inputs at backend boundaries.
