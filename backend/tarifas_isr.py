"""Tarifas del ISR publicadas en el Anexo 8 de la RMF (solo las verificadas contra el documento oficial).

Hoy: ejercicio 2026, tarifa mensual acumulada del Art. 106 LISR (``backend/datos/anexo8_rmf_2026.json``, copia de
``docs/referencias/anexo-8-rmf-2026-tarifas.json``). Un ejercicio sin tarifa cargada no se calcula: no se asume la de otro."""
from __future__ import annotations

import json
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Optional

_ARCHIVOS = {2026: Path(__file__).parent / "datos" / "anexo8_rmf_2026.json"}


@lru_cache(maxsize=None)
def _cargar(ejercicio: int) -> Optional[dict]:
    ruta = _ARCHIVOS.get(ejercicio)
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta else None


def ejercicios_soportados() -> tuple[int, ...]:
    return tuple(sorted(_ARCHIVOS))


def tarifa_art_106(ejercicio: int, mes: int) -> Optional[list[tuple[Decimal, Optional[Decimal], Decimal, Decimal]]]:
    """Renglones ``(límite inferior, límite superior o None, cuota fija, % sobre el excedente)`` de la tarifa del mes
    (acumulada del ejercicio hasta ese mes), o ``None`` si no hay tarifa cargada para el ejercicio."""
    datos = _cargar(ejercicio)
    if datos is None or not 1 <= mes <= 12:
        return None
    return [(Decimal(a), None if b is None else Decimal(b), Decimal(c), Decimal(p)) for a, b, c, p in datos["art_106"][str(mes)]]


def fuente(ejercicio: int) -> Optional[dict]:
    datos = _cargar(ejercicio)
    return None if datos is None else {"url": datos["fuente"], "consultado": datos["consultado"]}
