"""
API FastAPI — Plataforma de Auditoría Fiscal Preventiva
Conectada a PostgreSQL via db.py
"""
from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .deps import JWT_SECRET, _JWT_INSECURE_DEFAULT
from .routers import auth, empresas, ingesta, riesgos, scoring, conciliacion, emitidos, dashboard, sat

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


@app.on_event("startup")
async def _startup() -> None:
    if JWT_SECRET == _JWT_INSECURE_DEFAULT:
        _log.warning("JWT_SECRET no configurado — usando clave de desarrollo (inseguro en producción)")
    _log.info("CORS permitido para: %s", _ALLOWED_ORIGINS)
    _log.info("Inicializando schema de base de datos...")
    db.init_db()
    _log.info("FiscalCore API lista")


@app.get("/", tags=["Sistema"])
async def raiz():
    return {
        "sistema": "Plataforma de Auditoría Fiscal Preventiva",
        "version": "1.0.0",
        "estado": "operativo",
    }
