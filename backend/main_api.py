"""
API FastAPI — Plataforma de Auditoría Fiscal Preventiva
Conectada a PostgreSQL via db.py
"""
from __future__ import annotations

import logging
import os

from pathlib import Path
from dotenv import load_dotenv

# Cargar .env desde la raíz del proyecto
load_dotenv(Path(__file__).parent.parent / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from . import db
from .deps import JWT_SECRET, _JWT_INSECURE_DEFAULT
from .routers import auth, empresas, ingesta, riesgos, scoring, conciliacion, emitidos, dashboard, sat, reportes, admin

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
_log = logging.getLogger(__name__)

_ALLOWED_ORIGINS_ENV = os.getenv("ALLOWED_ORIGINS", "")
_ALLOWED_ORIGINS = (
    [o.strip() for o in _ALLOWED_ORIGINS_ENV.split(",") if o.strip()]
    if _ALLOWED_ORIGINS_ENV
    else ["*"]
)

app = FastAPI(
    title="Plataforma de Auditoría Fiscal Preventiva",
    version="1.0.0",
    description="Sistema de detección automática de riesgos fiscales (SAT interno)",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(empresas.router)
app.include_router(ingesta.router)
app.include_router(riesgos.router)
app.include_router(scoring.router)
app.include_router(conciliacion.router)
app.include_router(emitidos.router)
app.include_router(dashboard.router)
app.include_router(sat.router)
app.include_router(reportes.router)
app.include_router(admin.router)


@app.on_event("startup")
async def _startup() -> None:
    if JWT_SECRET == _JWT_INSECURE_DEFAULT:
        _log.warning("JWT_SECRET no configurado — usando clave de desarrollo (inseguro en producción)")
    _log.info("CORS permitido para: %s", _ALLOWED_ORIGINS)
    _log.info("Inicializando schema de base de datos...")
    try:
        db.init_db()
        _log.info("FiscalCore API lista")
    except Exception as e:
        _log.warning("DB no disponible al startup — el servidor arranca sin base de datos: %s", e)
        _log.warning("Inicia PostgreSQL (docker compose up -d db) para habilitar endpoints de datos")


@app.get("/api/health", tags=["Sistema"])
async def health():
    return {"estado": "operativo", "version": "1.0.0"}

# Servir frontend React (dist/) en producción
_DIST = Path(__file__).parent.parent / "dist"
if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        index = _DIST / "index.html"
        return FileResponse(str(index))
