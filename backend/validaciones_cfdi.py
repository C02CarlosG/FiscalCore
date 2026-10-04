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
from .cfdi_listado import rango as _rango_mes
from .iva import UMBRAL_EFECTIVO

DIRECCIONES = ("emitidos", "recibidos")
ALCANCES = ("periodo", "acumulado")
CENTAVOS = Decimal("0.01")
# El art. 27-III LISR fija $2,000: el umbral se puede bajar (más estricto), no subir.
# Si se subiera, la tarjeta dejaría de coincidir con IVA y deducciones (`UMBRAL_EFECTIVO`).
UMBRAL_MAXIMO = UMBRAL_EFECTIVO
# Clase SAT 151015 "Petróleo y destilados" (gasolinas, diésel): en efectivo no es
# deducible sin importar el monto (art. 27-III LISR, segundo párrafo).
PREFIJO_COMBUSTIBLES = "151015"
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
        "Notas de crédito sin relación 01, 03 o 07 al CFDI que disminuyen (o con forma de "
        "pago 30 sin relación 07): no se sabe a qué ingreso ni a qué periodo afectan.",
        ("emitidos", "recibidos"),
    ),
    Validacion(
        "no_bancarizado", "Gastos no bancarizados",
        "Recibidos pagados en efectivo por más del umbral, y combustibles en efectivo por "
        "cualquier monto: no deducibles (art. 27-III LISR) ni acreditables (art. 5-I LIVA).",
        ("recibidos",),
    ),
)
POR_CLAVE = {x.clave: x for x in CATALOGO}


def de_direccion(direccion: str) -> list[Validacion]:
    return [x for x in CATALOGO if direccion in x.direcciones]


def _a_umbral(valor: Any) -> Decimal:
    umbral = Decimal(str(valor))
    if not umbral.is_finite() or umbral < 0:
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
            # Un valor guardado arriba del legal se lee como el legal.
            umbral = min(_a_umbral(config["umbral_efectivo"]), UMBRAL_MAXIMO.quantize(CENTAVOS))
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
        if umbral > UMBRAL_MAXIMO:
            raise InvalidOperation
    except (InvalidOperation, ValueError, TypeError):
        raise ValidacionInvalida(
            "umbral_efectivo debe ser un importe entre 0 y 2,000 (el art. 27-III LISR fija $2,000; solo se puede bajar)"
        )
    return Configuracion(inactivas=frozenset(inactivas), umbral_efectivo=umbral)


def rangos(periodo: Any) -> tuple[date, date, date]:
    """(inicio del mes, inicio del mes siguiente, inicio del ejercicio)."""
    if not isinstance(periodo, str) or not _PERIODO_RE.fullmatch(periodo):
        raise ValidacionInvalida("periodo inválido; formato esperado YYYY-MM")
    # Mismo rango de mes que el listado de CFDI, para que la lista y el listado coincidan.
    inicio, siguiente = _rango_mes(periodo)
    return inicio, siguiente, date(inicio.year, 1, 1)


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


# ¿Trae alguna relación de esos tipos? cfdi_relacionados es [{"tipo_relacion", "uuids"}].
_TIENE_RELACION = (
    "EXISTS (SELECT 1 FROM jsonb_array_elements(CASE WHEN jsonb_typeof(c.cfdi_relacionados) = 'array' "
    "THEN c.cfdi_relacionados ELSE '[]'::jsonb END) r WHERE r->>'tipo_relacion' IN ({tipos}))"
)
_RELACION_QUE_IDENTIFICA = _TIENE_RELACION.format(tipos="'01', '03', '07'")
_RELACION_ANTICIPO = _TIENE_RELACION.format(tipos="'07'")

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
    # Solo las relaciones 01 (nota de crédito), 03 (devolución) y 07 (aplicación de
    # anticipo) identifican el ingreso que se disminuye; una 04 (sustitución) o 02 no.
    # Con forma de pago 30 (aplicación de anticipos) la relación debe ser 07.
    "egreso_sin_relacion": (
        "c.tipo_comprobante = 'E' AND ("
        f"NOT {_RELACION_QUE_IDENTIFICA} "
        f"OR (c.forma_pago = '30' AND NOT {_RELACION_ANTICIPO}))"
    ),
    "no_bancarizado": (
        f"c.tipo_comprobante = 'I' AND c.forma_pago = '01' AND (c.total * {A_PESOS} > %s "
        "OR EXISTS (SELECT 1 FROM cfdi_conceptos cc WHERE cc.cfdi_id = c.id "
        f"AND cc.clave_prod_serv LIKE '{PREFIJO_COMBUSTIBLES}%%'))"
    ),
}


def condicion(clave: str, config: Configuracion) -> tuple[str, list]:
    """Fragmento SQL de la validación y sus parámetros."""
    sql = _CONDICIONES[clave]
    params = [config.umbral_efectivo] if clave == "no_bancarizado" else []
    return f"({sql})", params
