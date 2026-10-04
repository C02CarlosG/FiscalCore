"""DIOT por flujo (F6.2) — composición pura: terceros del motor de IVA + catálogo de proveedores + clasificación del periodo.

El valor de actos, el IVA acreditable y el no acreditable los produce ``iva_flujo.por_contraparte`` (mismas reglas y mismos
ajustes que la pantalla de IVA y la cédula). Aquí solo se les pone el tercero del catálogo, su tipo de tercero y de operación
(el del periodo o, en su defecto, el del catálogo) y las advertencias de lo que falta para poder declararlo."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from . import diot_catalogos
from .iva_flujo import RFC_EXTRANJERO, clave_de_contraparte

CENTAVOS = Decimal("0.01")
CERO = Decimal("0")

ADVERTENCIAS = {
    "sin_catalogo": "El tercero no está en el catálogo de proveedores.",
    "sin_tipo_tercero": "Falta el tipo de tercero.",
    "sin_tipo_operacion": "Falta el tipo de operación.",
    "extranjero_pendiente": "Un proveedor extranjero necesita país e ID fiscal.",
    "rfc_invalido": "El RFC del tercero no tiene un formato válido.",
    "operacion_incompatible": "El tipo de operación no corresponde al tipo de tercero.",
}


def _q(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def indice_de_catalogo(proveedores: list[dict]) -> dict:
    """Catálogo por la llave de ``iva_flujo`` (RFC; más el nombre si es extranjero)."""
    return {clave_de_contraparte(p["rfc"], p["nombre"] if p["rfc"] == RFC_EXTRANJERO else ""): p for p in proveedores}


def clasificacion(proveedor: Optional[dict], periodo_override: Optional[dict]) -> tuple[Optional[str], Optional[str]]:
    """``(tipo_tercero, tipo_operacion)`` por defecto de un tercero: el del periodo, si existe; si no el del catálogo."""
    base_t = proveedor.get("tipo_tercero") if proveedor else None
    base_o = proveedor.get("tipo_operacion") if proveedor else None
    if periodo_override:
        return periodo_override.get("tipo_tercero") or base_t, periodo_override.get("tipo_operacion") or base_o
    return base_t, base_o


def _advertencias(fila: dict, proveedor: Optional[dict]) -> list[str]:
    avisos = []
    if proveedor is None:
        avisos.append("sin_catalogo")
    if not diot_catalogos.es_rfc_valido(fila["contraparte_rfc"]):
        avisos.append("rfc_invalido")
    if not fila["tipo_tercero"]:
        avisos.append("sin_tipo_tercero")
    if not fila["tipo_operacion"]:
        avisos.append("sin_tipo_operacion")
    if fila["tipo_tercero"] == "05" and not (proveedor and proveedor.get("pais") and proveedor.get("id_fiscal")):
        avisos.append("extranjero_pendiente")
    if fila["tipo_operacion"] in diot_catalogos.OPERACION_SOLO_GLOBAL and fila["tipo_tercero"] != "15":
        avisos.append("operacion_incompatible")
    return avisos


def componer(terceros: list[dict], catalogo: dict, overrides: dict) -> dict:
    """Renglones de la DIOT y totales. ``terceros`` sale de ``iva_flujo.por_contraparte``; ``catalogo`` de
    ``indice_de_catalogo``; ``overrides`` mapea ``proveedor_id`` → clasificación del periodo."""
    filas = []
    for t in terceros:
        proveedor = catalogo.get(clave_de_contraparte(t["contraparte_rfc"], t["contraparte"]))
        pid = proveedor["id"] if proveedor else None
        tipo_tercero, tipo_operacion = clasificacion(proveedor, overrides.get(pid))
        fila = {
            **t,
            "proveedor_id": pid,
            "tipo_tercero": tipo_tercero,
            "tipo_operacion": t.get("tipo_operacion") or tipo_operacion,
            "pais": proveedor.get("pais") if proveedor else None,
            "id_fiscal": proveedor.get("id_fiscal") if proveedor else None,
        }
        fila["advertencias"] = _advertencias(fila, proveedor)
        filas.append(fila)
    return {"terceros": filas, "totales": totales(filas)}


def totales(filas: list[dict]) -> dict:
    suma = lambda f: _q(sum((f(x) for x in filas), CERO))      # noqa: E731
    return {
        "terceros": len({(x["contraparte_rfc"], x["contraparte"] if x["contraparte_rfc"] == RFC_EXTRANJERO else "") for x in filas}),
        "cfdi": sum(x["cfdi"] for x in filas),
        "valor_de_actos": suma(lambda x: sum((v for k, v in x["actos"].items()), CERO)),
        "iva_pagado": suma(lambda x: x["iva_pagado"]["total"]),
        "devoluciones_iva": suma(lambda x: x["devoluciones"]["iva"]),
        "iva_acreditable": suma(lambda x: x["iva_acreditable"]),
        "iva_no_acreditable": suma(lambda x: x["iva_no_acreditable"]["total"]),
        "con_advertencias": sum(1 for x in filas if x["advertencias"]),
    }
