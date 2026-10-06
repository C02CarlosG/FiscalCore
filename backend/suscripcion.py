"""
suscripcion.py
Reglas de M7.1 (carril D): plan efectivo de una cuenta, límite de RFC y validación de
asignaciones y planes. Módulo puro; las consultas viven en `suscripcion_datos.py`.

Decisión de Carlos (2026-10-04): sin cobro en línea por ahora; un administrador de la
plataforma asigna el plan y el plan solo limita el número de RFC.
"""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

ESTADOS = ("activa", "suspendida", "cancelada")
CENTAVOS = Decimal("0.01")
PRECIO_MAXIMO = Decimal("10000000")
MAX_RFC_TOPE = 2**31 - 1  # planes.max_rfc es INTEGER
MAX_NOTAS = 1000
_CLAVE_RE = re.compile(r"^[a-z][a-z0-9_]{1,29}$")


class DatoInvalido(ValueError):
    """Entrada inválida (422); el mensaje se muestra tal cual."""


class ConfiguracionInvalida(RuntimeError):
    """El catálogo no tiene plan por defecto: lo arregla un administrador."""


def plan_por_defecto(planes: dict) -> dict:
    for plan in planes.values():
        if plan["por_defecto"]:
            return plan
    raise ConfiguracionInvalida("No hay un plan marcado como por defecto")


def plan_efectivo(suscripcion: Optional[dict], planes: dict, hoy: date) -> tuple[dict, Optional[str]]:
    """``(plan, motivo)``. ``motivo`` dice por qué se usa el plan por defecto, o es None.

    Un plan desactivado sigue valiendo para quien ya lo tiene: desactivar solo lo quita
    del catálogo.
    """
    if suscripcion is None:
        return plan_por_defecto(planes), "sin_suscripcion"
    if suscripcion["estado"] != "activa":
        return plan_por_defecto(planes), suscripcion["estado"]
    hasta = suscripcion.get("vigente_hasta")
    if hasta is not None and hasta < hoy:
        return plan_por_defecto(planes), "vencida"
    plan = planes.get(suscripcion["plan_clave"])
    if plan is None:
        return plan_por_defecto(planes), "plan_no_disponible"
    return plan, None


def puede_agregar_rfc(plan: dict, uso: int, es_admin: bool) -> bool:
    if es_admin or plan["max_rfc"] is None:
        return True
    return uso < plan["max_rfc"]


def mensaje_limite(plan: dict, de_tercero: bool = False) -> str:
    """``de_tercero``: el límite es de otra cuenta (por ejemplo, la persona que se aprueba
    como administradora de una empresa), así que el mensaje no le habla a quien actúa."""
    n = plan["max_rfc"]
    if n == 0:
        if de_tercero:
            return (f"El plan {plan['nombre']} de esa persona no incluye RFC. "
                    "Necesita un cambio de plan para administrar una empresa.")
        return f"Tu plan {plan['nombre']} no incluye RFC. Pide un cambio de plan para agregar una empresa."
    if de_tercero:
        usados = "ya lo usa" if n == 1 else "ya los usa"
        return (
            f"El plan {plan['nombre']} de esa persona permite {n} RFC y {usados}. "
            "Necesita un cambio de plan para administrar otra empresa."
        )
    usados = "ya lo usaste" if n == 1 else "ya los usaste"
    return (
        f"Tu plan {plan['nombre']} permite {n} RFC y {usados}. "
        "Pide un cambio de plan para agregar otra empresa."
    )


def validar_asignacion(cuerpo: dict, planes: dict) -> dict:
    clave = cuerpo.get("plan_clave")
    plan = planes.get(clave) if isinstance(clave, str) else None
    if plan is None or not plan["activo"]:
        raise DatoInvalido("plan_clave debe ser un plan activo del catálogo")
    estado = cuerpo.get("estado", "activa")
    if not isinstance(estado, str) or estado not in ESTADOS:
        raise DatoInvalido("estado debe ser 'activa', 'suspendida' o 'cancelada'")
    hasta = cuerpo.get("vigente_hasta")
    if hasta not in (None, ""):
        try:
            hasta = date.fromisoformat(str(hasta))
        except ValueError:
            raise DatoInvalido("vigente_hasta debe tener formato AAAA-MM-DD")
    else:
        hasta = None
    notas = cuerpo.get("notas") or ""
    if not isinstance(notas, str):
        raise DatoInvalido("notas debe ser texto")
    notas = notas.strip()
    if len(notas) > MAX_NOTAS:
        raise DatoInvalido(f"notas no puede pasar de {MAX_NOTAS} caracteres")
    return {"plan_clave": clave, "estado": estado, "vigente_hasta": hasta, "notas": notas or None}


def validar_plan(clave: str, cuerpo: dict) -> dict:
    if not isinstance(clave, str) or not _CLAVE_RE.fullmatch(clave):
        raise DatoInvalido("clave: minúsculas, números y guion bajo (2 a 30 caracteres)")
    nombre = cuerpo.get("nombre")
    nombre = nombre.strip() if isinstance(nombre, str) else ""
    if not nombre or len(nombre) > 80:
        raise DatoInvalido("nombre es obligatorio (hasta 80 caracteres)")
    try:
        precio = Decimal(str(cuerpo.get("precio_mensual")))
        if not precio.is_finite() or precio < 0 or precio > PRECIO_MAXIMO:
            raise InvalidOperation
    except (InvalidOperation, ValueError, TypeError):
        raise DatoInvalido("precio_mensual debe ser un importe de 0 o más")
    max_rfc: Any = cuerpo.get("max_rfc")
    if max_rfc is not None and (isinstance(max_rfc, bool) or not isinstance(max_rfc, int)
                                or not 0 <= max_rfc <= MAX_RFC_TOPE):
        raise DatoInvalido(f"max_rfc debe ser un entero de 0 a {MAX_RFC_TOPE}, o null para ilimitado")
    activo = cuerpo.get("activo", True)
    if not isinstance(activo, bool):  # bool("false") sería True
        raise DatoInvalido("activo debe ser true o false")
    return {
        "clave": clave, "nombre": nombre, "precio_mensual": precio.quantize(CENTAVOS),
        "max_rfc": max_rfc, "activo": activo,
    }
