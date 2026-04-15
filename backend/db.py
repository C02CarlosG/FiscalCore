"""
Módulo de conexión PostgreSQL con connection pool.
Soporta init automático del schema en Railway y entornos sin Docker.
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

import psycopg2
import psycopg2.extras
from psycopg2.pool import SimpleConnectionPool

log = logging.getLogger(__name__)

# ─── DATABASE_URL ─────────────────────────────────────────────
# Railway inyecta DATABASE_URL automáticamente al vincular PostgreSQL.
# El default solo aplica para desarrollo local con Docker Compose.
_LOCAL_DEFAULT = "postgresql://postgres:fiscalcore2024@127.0.0.1:5432/auditoria_fiscal"
DATABASE_URL = os.getenv("DATABASE_URL", _LOCAL_DEFAULT)

if DATABASE_URL == _LOCAL_DEFAULT and os.getenv("RAILWAY_ENVIRONMENT"):
    log.warning("DB: usando credenciales locales en Railway — configura DATABASE_URL")

# ─── Connection pool ──────────────────────────────────────────
_pool: Optional[SimpleConnectionPool] = None


def get_pool() -> SimpleConnectionPool:
    global _pool
    if _pool is None:
        try:
            # maxconn=5: apropiado para Railway Hobby (PostgreSQL compartido).
            # Incrementar a 10-20 en planes dedicados.
            _pool = SimpleConnectionPool(minconn=1, maxconn=5, dsn=DATABASE_URL)
            log.info("DB: connection pool inicializado (maxconn=5)")
        except Exception as e:
            log.error("DB: no se pudo crear el connection pool: %s", e)
            raise
    return _pool


@contextmanager
def get_conn():
    pool = get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


# ─── Query helpers ────────────────────────────────────────────

def query_all(sql: str, params: tuple = ()) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]


def query_one(sql: str, params: tuple = ()) -> Optional[dict]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            return dict(row) if row else None


def execute(sql: str, params: tuple = (), returning: bool = False) -> Optional[dict]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            if returning:
                row = cur.fetchone()
                return dict(row) if row else None
            return None


# ─── Schema init ──────────────────────────────────────────────

def _run_sql_file(filename: str) -> None:
    """Ejecuta un archivo SQL completo en una sola transacción."""
    path = Path(__file__).parent.parent / "database" / "migrations" / filename
    if not path.exists():
        log.warning("DB: archivo SQL no encontrado: %s", path)
        return
    sql = path.read_text(encoding="utf-8")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
    log.info("DB: %s aplicado", filename)


def init_db() -> None:
    """
    Inicializa el schema si no existe. Seguro para llamar en cada startup.

    - Si 'empresas' no existe → aplica 001 + 002 (schema completo + usuarios)
    - Siempre aplica 003 (idempotente: ADD COLUMN IF NOT EXISTS + UPDATE)
    """
    try:
        row = query_one("SELECT to_regclass('public.empresas') AS tbl")
        schema_exists = bool(row and row.get("tbl"))

        if not schema_exists:
            log.info("DB: schema no encontrado — ejecutando migraciones iniciales...")
            _run_sql_file("001_schema_inicial.sql")
            _run_sql_file("002_usuarios.sql")
            log.info("DB: schema base creado correctamente")

        # 003 es idempotente — aplicar siempre para garantizar
        # que accion_sugerida y estados intermedios estén presentes
        _run_sql_file("003_acciones.sql")

        # 004 es idempotente — tablas pagos_cfdi/pagos_relaciones + estado_pago en cfdi
        _run_sql_file("004_pagos_cfdi.sql")

        # 005 es idempotente — columnas CFDI 4.0: exportacion, lugar_expedicion, etc.
        _run_sql_file("005_cfdi40_campos.sql")

        # 006 es idempotente — tipo_match agrupado/parcial_multiple en conciliaciones
        _run_sql_file("006_match_multiple.sql")

        # 007 es idempotente — tipo_match heuristico en conciliaciones
        _run_sql_file("007_match_heuristico.sql")

        # 008 es idempotente — columna confianza en conciliaciones
        _run_sql_file("008_confianza_conciliacion.sql")

        # 009 es idempotente — estados PPD: pendiente_rep / pagado_parcial en conciliaciones y cfdi
        _run_sql_file("009_ppd_estados.sql")

        # 010 es idempotente — tipos específicos REP: complemento_pago_total/_parcial + columnas pago_id/saldo_insoluto
        _run_sql_file("010_complemento_tipos.sql")

        # 011 es idempotente — tabla usuario_empresas (M:N), migra relaciones existentes
        _run_sql_file("011_usuario_empresas.sql")

        # 012 es idempotente — columnas representante_legal + rfc_representante en empresas
        _run_sql_file("012_empresa_representante.sql")

        # 013 es idempotente — perfil extendido del contador: telefono, rfc, nombre_despacho, cedula
        _run_sql_file("013_perfil_contador.sql")

    except Exception as e:
        log.error("DB: init_db falló: %s", e)
        raise
