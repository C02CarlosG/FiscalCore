# backend/sat_sync.py
"""
Núcleo compartido de la descarga masiva del SAT.

Lo usan el router (`routers/sat.py`) y el worker de descarga automática (F2):
ventanas de fechas, esperas de reintento, configuración y, en las siguientes
tareas de F2.1, el avance e importación de solicitudes.

Las funciones de este bloque son puras: no tocan la base de datos ni el SAT.
"""
from __future__ import annotations

import calendar
import logging
import os
import re
from dataclasses import dataclass
from datetime import date, timedelta

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ventanas de fechas
# ---------------------------------------------------------------------------


def ventanas_mensuales(desde: date, hasta: date) -> list[tuple[date, date]]:
    """Parte ``[desde, hasta]`` por mes natural.

    Una solicitud al SAT nunca cubre más de un mes: así cada una se mantiene bajo
    los límites del servicio y se puede reintentar o retomar por separado.
    """
    ventanas: list[tuple[date, date]] = []
    inicio = desde
    while inicio <= hasta:
        fin_de_mes = date(inicio.year, inicio.month, calendar.monthrange(inicio.year, inicio.month)[1])
        fin = min(fin_de_mes, hasta)
        ventanas.append((inicio, fin))
        inicio = fin + timedelta(days=1)
    return ventanas


def partir_ventana(inicio: date, fin: date) -> list[tuple[date, date]] | None:
    """Parte una ventana en dos mitades contiguas, sin hueco ni solape.

    Se usa cuando el SAT rechaza una solicitud por volumen. Devuelve ``None``
    si la ventana ya es de un solo día (no hay nada más que partir).
    """
    dias = (fin - inicio).days + 1
    if dias <= 1:
        return None
    mitad = inicio + timedelta(days=(dias // 2) - 1)
    return [(inicio, mitad), (mitad + timedelta(days=1), fin)]


# ---------------------------------------------------------------------------
# Reintentos
# ---------------------------------------------------------------------------

# Espera tras el intento N fallido (1-indexado). Al agotarse, la solicitud falla.
_ESPERAS_REINTENTO = (
    timedelta(minutes=5),
    timedelta(minutes=15),
    timedelta(hours=1),
    timedelta(hours=6),
)


def espera_reintento(intentos: int) -> timedelta | None:
    """Cuánto esperar antes de reintentar tras ``intentos`` fallos seguidos.

    ``None`` si ``intentos`` no es un número de intento válido (0 o negativo)
    o si ya se agotaron los reintentos.
    """
    if intentos < 1 or intentos > len(_ESPERAS_REINTENTO):
        return None
    return _ESPERAS_REINTENTO[intentos - 1]


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConfigSync:
    intervalo_seg: int = 60
    hora_local: str = "03:00"
    traslape_dias: int = 7
    meses_cancelacion: int = 3
    max_en_vuelo: int = 4


_HORA_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _entero_positivo(nombre: str, defecto: int) -> int:
    crudo = os.environ.get(nombre, "").strip()
    try:
        valor = int(crudo)
    except ValueError:
        return defecto
    return valor if valor > 0 else defecto


def config_sync() -> ConfigSync:
    """Lee la configuración de las variables ``SAT_SYNC_*``.

    Un valor ausente o inválido cae al defecto (y se avisa en el log) en vez de
    impedir que el worker arranque.
    """
    base = ConfigSync()
    hora = os.environ.get("SAT_SYNC_HORA_LOCAL", "").strip() or base.hora_local
    if not _HORA_RE.match(hora):
        _log.warning("SAT_SYNC_HORA_LOCAL inválida (%r); se usa %s", hora, base.hora_local)
        hora = base.hora_local
    return ConfigSync(
        intervalo_seg=_entero_positivo("SAT_SYNC_INTERVALO_SEG", base.intervalo_seg),
        hora_local=hora,
        traslape_dias=_entero_positivo("SAT_SYNC_TRASLAPE_DIAS", base.traslape_dias),
        meses_cancelacion=_entero_positivo("SAT_SYNC_MESES_CANCELACION", base.meses_cancelacion),
        max_en_vuelo=_entero_positivo("SAT_SYNC_MAX_EN_VUELO", base.max_en_vuelo),
    )
