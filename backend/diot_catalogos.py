"""Catálogos cerrados de la DIOT (F6) y sus validaciones cruzadas.

IMPORTANTE: estas claves se tomaron de la referencia del revisor fiscal, **no** del instructivo oficial del SAT (el entorno de
desarrollo no puede consultarlo). Deben confirmarse contra el «Instructivo para el armado del archivo de carga masiva» antes de
F6.3. Si el instructivo difiere, se corrigen aquí y en los CHECK de la migración 051 (misma lista)."""
from __future__ import annotations

from typing import Optional

from .cfdi_parser import RFC_REGEX

TIPOS_TERCERO = ("04", "05", "15")            # nacional, extranjero, global
TIPOS_OPERACION = ("02", "03", "06", "07", "08", "85", "87")
OPERACION_SOLO_GLOBAL = frozenset({"87"})     # la 87 solo con tercero 15
RFC_EXTRANJERO = "XEXX010101000"
RFC_PUBLICO_GENERAL = "XAXX010101000"
RFC_GENERICOS = frozenset({RFC_EXTRANJERO, RFC_PUBLICO_GENERAL})
OPERACION_POR_DEFECTO = "85"


def es_rfc_valido(rfc: str) -> bool:
    return bool(rfc and RFC_REGEX.match(rfc))


def tipo_tercero_por_defecto(rfc: str) -> Optional[str]:
    """Nacional con RFC válido → 04; XEXX → 05 (pendiente de ID fiscal y país); XAXX → 15."""
    if rfc == RFC_EXTRANJERO:
        return "05"
    if rfc == RFC_PUBLICO_GENERAL:
        return "15"
    return "04" if es_rfc_valido(rfc) else None


def pendiente(prov: dict) -> bool:
    """Un extranjero sin país o sin ID fiscal no se puede declarar todavía."""
    return prov.get("tipo_tercero") == "05" and not (prov.get("pais") and prov.get("id_fiscal"))


def validar(prov: dict) -> list[str]:
    """Errores de las reglas cruzadas del estado resultante de un proveedor (lista vacía = válido)."""
    errores = []
    tercero, operacion = prov.get("tipo_tercero"), prov.get("tipo_operacion")
    if tercero is not None and tercero not in TIPOS_TERCERO:
        errores.append(f"tipo de tercero inválido (permitidos: {', '.join(TIPOS_TERCERO)})")
    if operacion is not None and operacion not in TIPOS_OPERACION:
        errores.append(f"tipo de operación inválido (permitidos: {', '.join(TIPOS_OPERACION)})")
    if tercero == "05" and not (prov.get("id_fiscal") and prov.get("pais")):
        errores.append("un proveedor extranjero (05) exige ID fiscal y país")
    if tercero == "04" and (not es_rfc_valido(prov.get("rfc", "")) or prov.get("rfc") in RFC_GENERICOS):
        errores.append("un proveedor nacional (04) exige un RFC válido y no genérico")
    if operacion in OPERACION_SOLO_GLOBAL and tercero != "15":
        errores.append("la operación 87 solo aplica al proveedor global (15)")
    return errores
