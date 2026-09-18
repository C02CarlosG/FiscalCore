"""
Log de auditoría — eventos sensibles (subida CFDI, FIEL, cambios admin, reportes).

Uso: registrar_evento(usuario_id, "cfdi_subido", empresa_id=empresa_id, metadata={...})

Nunca debe tumbar la operación principal: si el insert de auditoría falla
(ej. Postgres momentáneamente caído), se loguea el error y se continúa.
"""
from __future__ import annotations

import logging
from typing import Optional

import psycopg2.extras

from . import db

_log = logging.getLogger(__name__)


def registrar_evento(
    usuario_id: Optional[str],
    accion: str,
    empresa_id: Optional[str] = None,
    entidad: Optional[str] = None,
    entidad_id: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> None:
    """Inserta un evento en el log de auditoría.

    No lanza excepciones: un fallo aquí no debe interrumpir la operación que
    está siendo auditada (ej. una subida de CFDI exitosa no debe fallar porque
    el log de auditoría no pudo escribirse).
    """
    try:
        db.execute(
            """
            INSERT INTO auditoria (usuario_id, empresa_id, accion, entidad, entidad_id, metadata)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                usuario_id,
                empresa_id,
                accion,
                entidad,
                entidad_id,
                psycopg2.extras.Json(metadata) if metadata is not None else None,
            ),
        )
    except Exception:
        _log.exception("auditoria: no se pudo registrar evento accion=%s", accion)
