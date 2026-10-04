"""
validaciones_cfdi.py
Reglas de V1 (carril D): validaciones puramente de CFDI que señalan comprobantes con
posibles situaciones incorrectas. Módulo puro: catálogo, configuración, periodos y la
condición SQL de cada validación (siempre parametrizada). Las consultas viven en
`validaciones_cfdi_datos.py`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from .cfdi_columnas import A_PESOS
from .iva import UMBRAL_EFECTIVO

DIRECCIONES = ("emitidos", "recibidos")
ALCANCES = ("periodo", "acumulado")
CENTAVOS = Decimal("0.01")
UMBRAL_MAXIMO = Decimal("1000000000")
_PERIODO_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class ValidacionInvalida(ValueError):
    """Entrada inválida; el mensaje se devuelve tal cual como 422."""


@dataclass(frozen=True)
class Validacion:
    clave: str
    titulo: str
    descripcion: str
    direcciones: tuple[str, ...]


CATALOGO: tuple[Validacion, ...] = (
    Validacion(
        "pue_forma_99", "PUE con forma de pago 99",
        "Ingresos de pago en una sola exhibición con forma de pago «99 Por definir»: en PUE "
        "la forma de pago debe ser la real.",
        ("emitidos", "recibidos"),
    ),
    Validacion(
        "pue_con_rep", "PUE con complemento de pago",
        "Ingresos PUE que tienen un complemento de pago (REP) vigente relacionado: se "
        "debieron emitir como PPD y el cobro podría contarse dos veces.",
        ("emitidos", "recibidos"),
    ),
    Validacion(
        "egreso_sin_relacion", "Egresos sin CFDI relacionado",
        "Notas de crédito sin el CFDI que disminuyen: no se sabe a qué ingreso ni a qué "
        "periodo afectan.",
        ("emitidos", "recibidos"),
    ),
    Validacion(
        "no_bancarizado", "Gastos no bancarizados",
        "Recibidos pagados en efectivo por más del umbral: no deducibles (art. 27-III LISR) "
        "ni acreditables (art. 5-I LIVA).",
        ("recibidos",),
    ),
)
POR_CLAVE = {x.clave: x for x in CATALOGO}


def de_direccion(direccion: str) -> list[Validacion]:
    return [x for x in CATALOGO if direccion in x.direcciones]


def _a_umbral(valor: Any) -> Decimal:
    umbral = Decimal(str(valor))
    if not umbral.is_finite() or umbral < 0 or umbral > UMBRAL_MAXIMO:
        raise InvalidOperation
    return umbral.quantize(CENTAVOS)


@dataclass(frozen=True)
class Configuracion:
    inactivas: frozenset = field(default_factory=frozenset)
    umbral_efectivo: Decimal = UMBRAL_EFECTIVO.quantize(CENTAVOS)

    @classmethod
    def desde_json(cls, config: Optional[dict]) -> "Configuracion":
        """Lectura tolerante: lo que falta o no se entiende toma el valor por defecto."""
        config = config if isinstance(config, dict) else {}
        inactivas = config.get("inactivas")
        inactivas = frozenset(k for k in inactivas if k in POR_CLAVE) if isinstance(inactivas, list) else frozenset()
        try:
            umbral = _a_umbral(config["umbral_efectivo"])
        except (KeyError, InvalidOperation, ValueError, TypeError):
            umbral = cls.umbral_efectivo
        return cls(inactivas=inactivas, umbral_efectivo=umbral)

    def activa(self, clave: str) -> bool:
        return clave not in self.inactivas

    def a_json(self) -> dict:
        return {
            "inactivas": [x.clave for x in CATALOGO if x.clave in self.inactivas],
            "umbral_efectivo": str(self.umbral_efectivo),
        }


def validar_cambio(cuerpo: dict) -> Configuracion:
    """Valida lo que manda el usuario; a diferencia de la lectura, aquí se rechaza."""
    inactivas = cuerpo.get("inactivas", [])
    if not isinstance(inactivas, list) or any(k not in POR_CLAVE for k in inactivas):
        raise ValidacionInvalida(f"inactivas debe ser una lista de: {', '.join(POR_CLAVE)}")
    umbral = cuerpo.get("umbral_efectivo", Configuracion.umbral_efectivo)
    try:
        umbral = _a_umbral(umbral)
    except (InvalidOperation, ValueError, TypeError):
        raise ValidacionInvalida("umbral_efectivo debe ser un importe entre 0 y 1,000,000,000")
    return Configuracion(inactivas=frozenset(inactivas), umbral_efectivo=umbral)


def rangos(periodo: Any) -> tuple[date, date, date]:
    """(inicio del mes, inicio del mes siguiente, inicio del ejercicio)."""
    if not isinstance(periodo, str) or not _PERIODO_RE.fullmatch(periodo):
        raise ValidacionInvalida("periodo inválido; formato esperado YYYY-MM")
    anio, mes = int(periodo[:4]), int(periodo[5:7])
    siguiente = date(anio + 1, 1, 1) if mes == 12 else date(anio, mes + 1, 1)
    return date(anio, mes, 1), siguiente, date(anio, 1, 1)


def validar_direccion(direccion: Any) -> str:
    if direccion not in DIRECCIONES:
        raise ValidacionInvalida("direccion debe ser 'emitidos' o 'recibidos'")
    return direccion


def validar_validacion(clave: Any, direccion: str) -> Validacion:
    validacion = POR_CLAVE.get(clave)
    if validacion is None or direccion not in validacion.direcciones:
        raise ValidacionInvalida(f"validacion inválida para {direccion}")
    return validacion


def validar_alcance(alcance: Any) -> str:
    if alcance not in ALCANCES:
        raise ValidacionInvalida("alcance debe ser 'periodo' o 'acumulado'")
    return alcance


# Condiciones sobre la tabla `cfdi` con alias `c`. Los CFDI ya vienen filtrados por
# empresa, dirección, vigencia y fecha en la consulta que las usa.
_CONDICIONES = {
    "pue_forma_99": "c.tipo_comprobante = 'I' AND c.metodo_pago = 'PUE' AND c.forma_pago = '99'",
    # Solo cuenta un REP vigente de la misma empresa (uno cancelado no prueba el pago).
    "pue_con_rep": (
        "c.tipo_comprobante = 'I' AND c.metodo_pago = 'PUE' AND EXISTS ("
        "SELECT 1 FROM pagos_relaciones pr "
        "JOIN pagos_cfdi pc ON pc.id = pr.pago_id "
        "JOIN cfdi p ON p.id = pc.cfdi_id "
        "WHERE pr.cfdi_uuid = c.uuid AND p.empresa_id = c.empresa_id AND p.estado = 'vigente')"
    ),
    "egreso_sin_relacion": (
        "c.tipo_comprobante = 'E' AND (c.cfdi_relacionados IS NULL "
        "OR c.cfdi_relacionados IN ('[]'::jsonb, '{}'::jsonb, 'null'::jsonb))"
    ),
    "no_bancarizado": f"c.tipo_comprobante = 'I' AND c.forma_pago = '01' AND c.total * {A_PESOS} > %s",
}


def condicion(clave: str, config: Configuracion) -> tuple[str, list]:
    """Fragmento SQL de la validación y sus parámetros."""
    sql = _CONDICIONES[clave]
    params = [config.umbral_efectivo] if clave == "no_bancarizado" else []
    return f"({sql})", params
