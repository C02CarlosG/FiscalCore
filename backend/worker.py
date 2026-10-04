# backend/worker.py
"""
Worker de descarga automática del SAT (F2).

Proceso aparte del servidor web:  ``python -m backend.worker``

Cada ``SAT_SYNC_INTERVALO_SEG`` segundos recorre las empresas con la automatización
activada y les da una vuelta (``sat_sync.procesar_empresa``): crea las solicitudes de la
carga inicial y de la corrida diaria, las avanza hasta importar los CFDI y programa la
siguiente corrida. Todo el estado vive en Postgres, así que un reinicio retoma donde iba.

La e.firma se descifra únicamente dentro de ``procesar_empresa`` y solo para empresas con
la automatización activada.
"""
from __future__ import annotations

import logging
import signal
import sys
import threading
import time
from datetime import datetime, timezone

from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / ".env")

from . import db, fiel_store, sat_sync  # noqa: E402  (después de cargar .env)

_log = logging.getLogger("backend.worker")

# Se activa con SIGTERM/SIGINT: el worker termina la empresa en curso y sale.
_detener = threading.Event()


def empresas_elegibles(ahora: datetime) -> list[str]:
    """Empresas con la automatización activada que tienen algo por hacer: corrida vencida
    (o sin programar), corrida en curso, solicitudes activas, o pausadas (para reanudar
    solas cuando se guarde una e.firma válida)."""
    filas = db.query_all(
        """SELECT c.empresa_id
           FROM sat_sync_config c
           WHERE c.activa
             AND (c.proxima_corrida IS NULL
                  OR c.proxima_corrida <= %s
                  OR c.corrida_inicio IS NOT NULL
                  OR c.estado = 'pausada'
                  OR EXISTS (SELECT 1 FROM sat_solicitudes s
                             WHERE s.empresa_id = c.empresa_id AND s.estado = ANY(%s)))
           ORDER BY c.empresa_id""",
        (ahora, list(sat_sync.ESTADOS_ACTIVOS)),
    )
    return [str(f["empresa_id"]) for f in filas]


def ciclo(ahora: datetime | None = None) -> list[tuple[str, str]]:
    """Una vuelta sobre todas las empresas elegibles. Devuelve ``(empresa_id, resultado)``.

    Una falla en una empresa se registra y no detiene a las demás.
    """
    ahora = ahora or datetime.now(timezone.utc)
    resultados: list[tuple[str, str]] = []
    for empresa_id in empresas_elegibles(ahora):
        if _detener.is_set():
            break
        try:
            resultados.append((empresa_id, sat_sync.procesar_empresa(empresa_id, ahora=ahora)))
        except Exception:
            _log.exception("Falló la descarga automática de la empresa %s", empresa_id)
            resultados.append((empresa_id, "error_interno"))
    return resultados


def _instalar_senales() -> None:
    def _pedir_detener(signum, frame):
        _log.info("Señal %s recibida: el worker termina tras la empresa en curso", signum)
        _detener.set()
    signal.signal(signal.SIGTERM, _pedir_detener)
    signal.signal(signal.SIGINT, _pedir_detener)


def _dormir(segundos: int) -> None:
    """Espera ``segundos`` en pasos de un segundo para atender una señal de detención."""
    for _ in range(segundos):
        if _detener.is_set():
            return
        time.sleep(1)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    # Sin la clave de cifrado no se puede leer ninguna e.firma: falla ruidosa y de inmediato.
    try:
        fiel_store._get_fernet()
    except RuntimeError as exc:
        print(f"worker: no puede arrancar. {exc}", file=sys.stderr)
        return 1

    db.init_db()
    _instalar_senales()
    config = sat_sync.config_sync()
    _log.info("Worker de descarga automática iniciado (intervalo %s s)", config.intervalo_seg)

    while not _detener.is_set():
        try:
            resultados = ciclo()
            if resultados:
                _log.info("Ciclo: %s", ", ".join(f"{e[:8]}={r}" for e, r in resultados))
        except Exception:
            _log.exception("Falló un ciclo del worker; se reintenta en el siguiente")
        _dormir(sat_sync.config_sync().intervalo_seg)

    _log.info("Worker detenido")
    return 0


if __name__ == "__main__":
    sys.exit(main())
