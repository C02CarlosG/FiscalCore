"""
suscripcion_pagos.py
Reglas de M7.2 (carril D, decisión D10 de Carlos, 2026-10-06): sin cobro en línea; el
administrador de la plataforma registra a mano los pagos de cada cuenta y los datos
fiscales con los que emite (fuera de FiscalCore) el CFDI de la suscripción. Avisos de
vencimiento próximo solo en la interfaz. Módulo puro.
"""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from .cfdi_parser import validar_rfc
from .suscripcion import CENTAVOS, DatoInvalido

DIAS_AVISO = 15  # una suscripción que vence en 15 días o menos muestra el aviso
MONTO_MAXIMO = Decimal("10000000")
MAX_REFERENCIA = 200
MAX_FOLIO = 40
MAX_RAZON_SOCIAL = 254  # Anexo 20: Nombre del receptor

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
    return {"rfc": rfc, "razon_social": razon, "regimen_fiscal": regimen, "codigo_postal": cp, "uso_cfdi": uso}


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
    return {
        "fecha": fecha,
        "monto": monto.quantize(CENTAVOS),
        "referencia": _texto(cuerpo, "referencia", MAX_REFERENCIA, False),
        "folio_cfdi": _texto(cuerpo, "folio_cfdi", MAX_FOLIO, False),
    }


def aviso_vencimiento(vigente_hasta: Optional[date], motivo: Optional[str], hoy: date) -> Optional[int]:
    """Días que faltan si la suscripción vigente vence en ``DIAS_AVISO`` días o menos
    (0 = vence hoy); None si no hay aviso."""
    if vigente_hasta is None or motivo is not None:
        return None
    dias = (vigente_hasta - hoy).days
    return dias if 0 <= dias <= DIAS_AVISO else None
