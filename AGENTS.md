# Repository Guidelines

## Project Structure & Module Organization

This repository contains a React/Vite frontend and a FastAPI backend for FiscalCore.

- `src/` contains the frontend application. Pages live in `src/pages/`, reusable UI in `src/components/`, shared context in `src/context/`, and API/format helpers in `src/lib/`.
- `backend/` contains the Python API. `backend/main_api.py` wires the FastAPI app, while endpoint modules live in `backend/routers/`.
- `database/migrations/` contains ordered SQL migrations. Keep new migrations numeric and descriptive, for example `022_nueva_tabla.sql`.
- `docs/openapi.yaml` stores API documentation, and deployment/config files live at the root (`Dockerfile`, `docker-compose.yml`, `vercel.json`, `Procfile`).

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

## Testing Guidelines

There is currently no project test command or dedicated `tests/` directory. For frontend changes, run `npm run build` at minimum. For backend changes, manually start Uvicorn and verify relevant routes through `/docs` or targeted HTTP requests. When adding tests, place Python tests under `tests/` using `test_*.py`; add the matching test runner command to this guide and project config.

## Commit & Pull Request Guidelines

Git history uses Conventional Commit prefixes such as `feat:`, `fix:`, and `chore:`. Keep messages imperative and scoped, for example `fix: validar periodo de empresa`.

Pull requests should include a short summary, linked issue or task when available, test/build evidence, migration notes if SQL changes are included, and screenshots for visible UI changes.

## Security & Configuration Tips

Never commit `.env`, credentials, FIEL files, uploads, or local database dumps. Use `.env.example` for required variable names. Validate all uploaded files and external inputs at backend boundaries.
