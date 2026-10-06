"""
suscripcion_pagos.py
Reglas de M7.2 (carril D, decisión D10 de Carlos, 2026-10-06): sin cobro en línea; el
administrador de la plataforma registra a mano los pagos de cada cuenta (cada pago
extiende la vigencia; anularlo la revierte si nada la cambió después), y la cuenta o el
administrador capturan los datos fiscales con los que se emite (fuera de FiscalCore) el
CFDI de la suscripción. Avisos de vencimiento solo en la interfaz. Módulo puro.
"""
from __future__ import annotations

import calendar
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from .cfdi_parser import validar_rfc
from .suscripcion import CENTAVOS, DatoInvalido
from .usuarios_empresa import DatoInvalido as CorreoInvalido, normalizar_correo

DIAS_AVISO = 15  # una suscripción que vence en 15 días o menos muestra el aviso
MONTO_MAXIMO = Decimal("10000000")
MAX_REFERENCIA = 200
MAX_FOLIO = 40
MAX_RAZON_SOCIAL = 254  # Anexo 20: Nombre del receptor
MAX_MOTIVO = 500
MESES_MAXIMO = 24
_UUID_RE = re.compile(r"^[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}$")

# Catálogo c_RegimenFiscal (Anexo 20, CFDI 4.0): para quién aplica cada régimen.
REGIMENES_MORALES = {"601", "603", "610", "620", "622", "623", "624", "626"}
REGIMENES_FISICAS = {"605", "606", "607", "608", "610", "611", "612", "614", "615", "616", "621", "625", "626"}
# Catálogo c_UsoCFDI (CFDI 4.0).
USOS_CFDI = {
    "G01", "G02", "G03", "I01", "I02", "I03", "I04", "I05", "I06", "I07", "I08",
    "D01", "D02", "D03", "D04", "D05", "D06", "D07", "D08", "D09", "D10",
    "S01", "CP01", "CN01",
}
_CP_RE = re.compile(r"^\d{5}$")


def _texto(cuerpo: dict, campo: str, maximo: int, obligatorio: bool) -> Optional[str]:
    valor = cuerpo.get(campo)
    if valor is None or valor == "":
        if obligatorio:
            raise DatoInvalido(f"{campo} es obligatorio")
        return None
    if not isinstance(valor, str):
        raise DatoInvalido(f"{campo} debe ser texto")
    valor = valor.strip()
    if obligatorio and not valor:
        raise DatoInvalido(f"{campo} es obligatorio")
    if len(valor) > maximo:
        raise DatoInvalido(f"{campo} no puede pasar de {maximo} caracteres")
    return valor or None


def validar_datos_fiscales(cuerpo: dict) -> dict:
    """RFC, razón social, régimen, código postal y uso del CFDI del cliente."""
    rfc = (_texto(cuerpo, "rfc", 13, True) or "").upper()
    if not validar_rfc(rfc):
        raise DatoInvalido("rfc inválido")
    razon = _texto(cuerpo, "razon_social", MAX_RAZON_SOCIAL, True)
    regimen = _texto(cuerpo, "regimen_fiscal", 3, True)
    persona_moral = len(rfc) == 12
    validos = REGIMENES_MORALES if persona_moral else REGIMENES_FISICAS
    if regimen not in validos:
        tipo = "moral" if persona_moral else "física"
        raise DatoInvalido(f"regimen_fiscal no corresponde a una persona {tipo} del catálogo del SAT")
    cp = _texto(cuerpo, "codigo_postal", 5, True)
    if not _CP_RE.fullmatch(cp):
        raise DatoInvalido("codigo_postal debe tener 5 dígitos")
    uso = (_texto(cuerpo, "uso_cfdi", 4, True) or "").upper()
    if uso not in USOS_CFDI:
        raise DatoInvalido("uso_cfdi no está en el catálogo c_UsoCFDI")
    correo = _texto(cuerpo, "correo", 255, False)
    if correo is not None:
        try:
            correo = normalizar_correo(correo)
        except CorreoInvalido:
            raise DatoInvalido("correo inválido")
    return {"rfc": rfc, "razon_social": razon, "regimen_fiscal": regimen, "codigo_postal": cp, "uso_cfdi": uso,
            "correo": correo}


def validar_pago(cuerpo: dict, hoy: date) -> dict:
    """Pago registrado a mano: fecha (no futura), monto, referencia y folio del CFDI."""
    try:
        fecha = date.fromisoformat(str(cuerpo.get("fecha")))
    except ValueError:
        raise DatoInvalido("fecha debe tener formato AAAA-MM-DD")
    if fecha > hoy:
        raise DatoInvalido("fecha no puede ser futura")
    monto: Any = cuerpo.get("monto")
    try:
        if isinstance(monto, (bool, float)):  # un float ya perdió centavos; se pide texto o entero
            raise InvalidOperation
        monto = Decimal(str(monto))
        if not monto.is_finite() or monto <= 0 or monto > MONTO_MAXIMO or monto != monto.quantize(CENTAVOS):
            raise InvalidOperation
    except (InvalidOperation, ValueError, TypeError):
        raise DatoInvalido("monto debe ser un importe mayor que 0 con hasta dos decimales (como texto)")
    meses = cuerpo.get("meses", 1)
    if isinstance(meses, bool) or not isinstance(meses, int) or not 1 <= meses <= MESES_MAXIMO:
        raise DatoInvalido(f"meses debe ser un entero de 1 a {MESES_MAXIMO}")
    uuid_cfdi = _texto(cuerpo, "uuid_cfdi", 36, False)
    if uuid_cfdi is not None:
        uuid_cfdi = uuid_cfdi.upper()
        if not _UUID_RE.fullmatch(uuid_cfdi):
            raise DatoInvalido("uuid_cfdi debe ser el UUID del CFDI (8-4-4-4-12 hexadecimal)")
    return {
        "fecha": fecha,
        "monto": monto.quantize(CENTAVOS),
        "referencia": _texto(cuerpo, "referencia", MAX_REFERENCIA, False),
        "folio_cfdi": _texto(cuerpo, "folio_cfdi", MAX_FOLIO, False),
        "uuid_cfdi": uuid_cfdi,
        "meses": meses,
    }


def validar_anulacion(cuerpo: dict) -> str:
    return _texto(cuerpo, "motivo", MAX_MOTIVO, True)


def sumar_meses(d: date, meses: int) -> date:
    """31 de enero + 1 mes = 28 (o 29) de febrero."""
    total = d.month - 1 + meses
    anio, mes = d.year + total // 12, total % 12 + 1
    return date(anio, mes, min(d.day, calendar.monthrange(anio, mes)[1]))


def nueva_vigencia(vigente_hasta: Optional[date], fecha_pago: date, meses: int) -> date:
    """Un pago extiende desde la vigencia actual si todavía no había vencido a la fecha
    del pago; si ya venció (o no tenía), desde la fecha del pago."""
    base = vigente_hasta if vigente_hasta is not None and vigente_hasta >= fecha_pago else fecha_pago
    return sumar_meses(base, meses)


def aviso_vencimiento(vigente_hasta: Optional[date], motivo: Optional[str], hoy: date) -> Optional[int]:
    """Días que faltan si la suscripción vigente vence en ``DIAS_AVISO`` días o menos
    (0 = vence hoy); negativo si venció (días desde el vencimiento); None si no hay aviso.
    Una suspendida o cancelada no avisa: ya se explica con su motivo."""
    if vigente_hasta is None or motivo not in (None, "vencida"):
        return None
    dias = (vigente_hasta - hoy).days
    return dias if dias <= DIAS_AVISO else None


def sumar_dias(d: date, dias: int) -> date:
    return d + timedelta(days=dias)
