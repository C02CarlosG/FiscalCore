"""
reinicio_empresa.py
«Reiniciar datos» de una empresa (carril D): borra sus datos operativos (los que se
vuelven a descargar del SAT o a cargar) con doble confirmación. La lista de tablas está
fijada en `docs/superpowers/specs/2026-10-06-reinicio-datos-design.md`; si un carril
agrega una tabla con datos por empresa, decide si entra aquí.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import timedelta
from typing import Optional

import psycopg2.extras

from . import db

ALCANCES = ("todo",)
MAX_CFDI = 50_000  # más grande: 409, se hará en segundo plano en una entrega futura
VIGENCIA_TOKEN = timedelta(minutes=10)

# (tabla, condición adicional) en orden de dependencias: primero lo que referencia sin
# cascada. pagos_cfdi y cfdi arrastran sus tablas hijas por ON DELETE CASCADE.
TABLAS: tuple[tuple[str, str], ...] = (
    ("recomendaciones", ""),
    ("detecciones", ""),
    ("conciliaciones", ""),
    ("scoring_fiscal", ""),
    ("periodos_procesados", ""),
    ("iva_ajustes", ""),
    ("isr_ajustes", ""),
    ("diot_operaciones_cfdi", ""),
    ("diot_terceros_periodo", ""),
    ("movimientos_bancarios", ""),
    ("pagos_cfdi", ""),
    ("cfdi", ""),
    # Las solicitudes en curso se conservan: el worker las termina (es la nueva descarga).
    ("sat_solicitudes", " AND estado IN ('fallo', 'descargado')"),
)


class ReinicioInvalido(ValueError):
    """Token, frase o alcance inválidos (400/422); nada se borra."""


class EmpresaDemasiadoGrande(RuntimeError):
    """Más de MAX_CFDI CFDI (409)."""


class TokenYaUsado(RuntimeError):
    """El token ya se usó o lo está usando otra confirmación (409)."""


def frase(rfc: str) -> str:
    return f"REINICIAR {rfc}"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def frase_correcta(escrita: Optional[str], rfc: str) -> bool:
    return isinstance(escrita, str) and hmac.compare_digest(escrita.strip(), frase(rfc))


def validar_alcance(alcance) -> str:
    if alcance not in ALCANCES:
        raise ReinicioInvalido("alcance debe ser 'todo' (por ejercicio llegará en una entrega posterior)")
    return alcance


def _conteos(cur, empresa_id: str) -> dict:
    conteos = {}
    for tabla, extra in TABLAS:
        cur.execute(f"SELECT COUNT(*) AS n FROM {tabla} WHERE empresa_id = %s{extra}", (empresa_id,))
        conteos[tabla] = int(cur.fetchone()["n"])
    return conteos


def previsualizar(empresa_id: str, usuario_id: str) -> dict:
    """Conteos de lo que se borraría y un token de un solo uso (solo se guarda su hash)."""
    with db.get_conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        conteos = _conteos(cur, empresa_id)
        if conteos["cfdi"] > MAX_CFDI:
            raise EmpresaDemasiadoGrande(
                f"La empresa tiene {conteos['cfdi']:,} CFDI: demasiado grande para reiniciarla aquí; "
                "se hará en segundo plano en una entrega futura."
            )
        token = secrets.token_urlsafe(32)
        cur.execute(
            "INSERT INTO reinicios_empresa (empresa_id, usuario_id, token_sha256, conteos, expira_en) "
            "VALUES (%s, %s, %s, %s, NOW() + %s) RETURNING expira_en",
            (empresa_id, usuario_id, hash_token(token), psycopg2.extras.Json(conteos), VIGENCIA_TOKEN),
        )
        expira = cur.fetchone()["expira_en"]
    return {"conteos": conteos, "total_cfdi": conteos["cfdi"], "token": token, "expira_en": expira.isoformat()}


def ejecutar(empresa_id: str, usuario_id: str, token: str) -> dict:
    """Borra en una sola transacción. El token se toma con FOR UPDATE NOWAIT: una segunda
    confirmación simultánea recibe TokenYaUsado en vez de esperar y repetir el borrado."""
    with db.get_conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        try:
            cur.execute(
                "SELECT id, usado_en, expira_en < NOW() AS vencido FROM reinicios_empresa "
                "WHERE token_sha256 = %s AND empresa_id = %s AND usuario_id = %s FOR UPDATE NOWAIT",
                (hash_token(token), empresa_id, usuario_id),
            )
        except psycopg2.errors.LockNotAvailable:
            raise TokenYaUsado("El reinicio ya se está ejecutando")
        fila = cur.fetchone()
        if fila is None:
            raise ReinicioInvalido("Token de confirmación inválido: vuelve a previsualizar")
        if fila["usado_en"] is not None:
            raise TokenYaUsado("Este reinicio ya se ejecutó")
        if fila["vencido"]:
            raise ReinicioInvalido("El token de confirmación venció: vuelve a previsualizar")
        cur.execute("SELECT id FROM empresas WHERE id = %s FOR UPDATE", (empresa_id,))
        borrados = {}
        for tabla, extra in TABLAS:
            cur.execute(f"DELETE FROM {tabla} WHERE empresa_id = %s{extra}", (empresa_id,))
            borrados[tabla] = cur.rowcount
        cur.execute(
            "UPDATE sat_sync_config SET activa = FALSE, estado = 'pausada', motivo_pausa = 'Reinicio de datos', "
            "updated_at = NOW() WHERE empresa_id = %s AND activa",
            (empresa_id,),
        )
        pausada = cur.rowcount > 0
        cur.execute("UPDATE reinicios_empresa SET usado_en = NOW(), borrados = %s WHERE id = %s",
                    (psycopg2.extras.Json(borrados), fila["id"]))
    return {"borrados": borrados, "sincronizacion_pausada": pausada}
