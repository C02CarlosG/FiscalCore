"""
Categorización de movimientos bancarios.

Lógica pura de sugerencia (sin acceso a BD) + catálogos semilla.
La sugerencia prioriza: historial por RFC > historial por concepto > regla base.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Optional

# (nombre, tipo, color) — categorías sembradas por empresa
CATEGORIAS_BASE: list[tuple[str, str, str]] = [
    ("Nómina",        "retiro",   "#0EA5E9"),
    ("Servicios",     "retiro",   "#F59E0B"),
    ("Impuestos",     "retiro",   "#EF4444"),
    ("Transferencia", "ambos",    "#8B5CF6"),
    ("Ventas",        "deposito", "#22C55E"),
    ("Otros",         "ambos",    "#6B7280"),
]

# (palabra_clave_normalizada, nombre_categoria, tipo)
REGLAS_BASE: list[tuple[str, str, str]] = [
    ("NOMINA",   "Nómina",        "retiro"),
    ("CFE",      "Servicios",     "retiro"),
    ("TELMEX",   "Servicios",     "retiro"),
    ("SAT",      "Impuestos",     "retiro"),
    ("IVA",      "Impuestos",     "retiro"),
    ("ISR",      "Impuestos",     "retiro"),
    ("SPEI",     "Transferencia", "ambos"),
    ("TRASPASO", "Transferencia", "ambos"),
]


def normalizar_concepto(texto: str) -> str:
    """Mayúsculas, sin acentos, sin dígitos ni puntuación, espacios colapsados."""
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", texto)
    sin_acentos = "".join(c for c in nfkd if not unicodedata.combining(c))
    solo_letras = re.sub(r"[^A-Za-z\s]", "", sin_acentos)
    return re.sub(r"\s+", " ", solo_letras).strip().upper()


def _aplica_tipo(regla_tipo: str, tipo_mov: str) -> bool:
    return regla_tipo == "ambos" or regla_tipo == tipo_mov


def sugerir_categoria_id(
    concepto_norm: str,
    rfc: Optional[str],
    tipo_mov: str,
    reglas: list[dict],
) -> Optional[str]:
    """
    Devuelve el categoria_id sugerido o None.

    `reglas`: dicts con palabra_clave, tipo_match, categoria_id, origen, peso, tipo.
    Prioridad (primer grupo no vacío gana; dentro del grupo, mayor peso):
      1. historial por RFC exacto
      2. historial por concepto (palabra_clave contenida en concepto_norm)
      3. regla base por concepto (palabra_clave contenida en concepto_norm)
    """
    rfc_norm = (rfc or "").strip().upper()

    def candidatos(origen: str, tipo_match: str) -> list[dict]:
        out = []
        for r in reglas:
            if r["origen"] != origen or r["tipo_match"] != tipo_match:
                continue
            if not _aplica_tipo(r.get("tipo", "ambos"), tipo_mov):
                continue
            pk = (r["palabra_clave"] or "").strip().upper()
            if tipo_match == "rfc":
                if rfc_norm and pk == rfc_norm:
                    out.append(r)
            else:  # concepto
                if pk and pk in concepto_norm:
                    out.append(r)
        return out

    for origen, tipo_match in (("historial", "rfc"), ("historial", "concepto"), ("regla", "concepto")):
        grupo = candidatos(origen, tipo_match)
        if grupo:
            mejor = max(grupo, key=lambda r: r.get("peso", 1))
            return mejor["categoria_id"]

    return None
