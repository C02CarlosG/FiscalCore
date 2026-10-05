"""Reglas comunes de los cobros y pagos con complemento de pago (REP) para los motores de flujo de efectivo.

IVA (``iva_flujo``) e ISR (``isr_flujo``) leen un REP igual: el mismo factor a pesos, la misma validación de la equivalencia
contra el ``Monto`` del propio complemento y la misma forma de pago. Vive aquí, una sola vez, para que no diverjan.
Funciones puras, sin base de datos."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

UNO = Decimal("1")
CERO = Decimal("0")
TOLERANCIA_DESCUADRE = Decimal("0.01")
TOLERANCIA_RELATIVA_MONTO = Decimal("0.01")              # 1 % del Monto del pago al validar equivalencias


def dec(valor: Any) -> Decimal:
    if valor is None or valor == "":
        return CERO
    return valor if isinstance(valor, Decimal) else Decimal(str(valor))


def tc_documento(doc: dict) -> Optional[Decimal]:
    """Tipo de cambio a pesos del comprobante. En MXN (o XXX, sin moneda) es 1; en moneda
    extranjera sin tipo de cambio no se adivina: devuelve ``None``."""
    if (doc.get("moneda") or "MXN") in ("MXN", "XXX"):
        return UNO
    tc = dec(doc.get("tipo_cambio"))
    return tc if tc > 0 else None


def factor_a_pesos(moneda_dr: Optional[str], equivalencia_dr: Any, pago_moneda: Optional[str], pago_tc: Any) -> Optional[Decimal]:
    """Factor que lleva un importe del documento relacionado a pesos.

    ``importe_en_moneda_del_pago = importe_dr / equivalencia_dr``; a pesos con el tipo de
    cambio del pago (1 si es en MXN). Con equivalencia nula solo se asume 1 si el documento
    está en la misma moneda del pago; con monedas distintas no se adivina: devuelve ``None``.
    """
    pago_moneda = pago_moneda or "MXN"
    eq = dec(equivalencia_dr)
    if eq <= 0:
        if moneda_dr in (None, pago_moneda):
            eq = UNO
        else:
            return None
    if pago_moneda == "MXN":
        tc = UNO
    else:
        tc = dec(pago_tc)
        if tc <= 0:
            return None
    return tc / eq


def factor_del_pago(pago: dict, doc: dict) -> Optional[Decimal]:
    """Factor a pesos de un cobro. Si el pago no trae ``moneda_dr`` (filas anteriores al detalle
    fiscal) se usa la moneda del documento: un CFDI en USD con un REP en MXN y sin equivalencia
    queda sin dato, no se suma como si fueran pesos."""
    return factor_a_pesos(pago.get("moneda_dr") or doc.get("moneda"), pago.get("equivalencia_dr"),
                          pago.get("pago_moneda"), pago.get("pago_tipo_cambio"))


def equivalencia_invertida(pago: dict) -> bool:
    """``True`` si la equivalencia del documento no cuadra con lo que el propio REP declara.

    El Anexo 20 (Pagos 2.0) exige ``Σ importe pagado / equivalencia ≤ Monto`` del pago, en la moneda del pago: un
    ``Monto`` mayor es válido (remanente sin aplicar a documentos). Por eso solo se sospecha cuando la suma **excede** el
    ``Monto`` (más la tolerancia) o es **menos de la mitad** de él: una equivalencia invertida (20 en lugar de 0.05) rompe
    esa relación por órdenes de magnitud, un redondeo o un remanente no. Sin ``Monto`` o sin la suma no hay con qué
    comparar y se da por buena. Nota: una equivalencia mala excluye todo el cobro de ese documento (y, si el REP trae varios
    documentos con la misma equivalencia mala, todos)."""
    monto, suma = dec(pago.get("pago_monto")), pago.get("suma_equivalente")
    if monto <= 0 or suma is None:
        return False
    suma = dec(suma)
    tolerancia = max(TOLERANCIA_DESCUADRE * max(1, int(pago.get("n_relaciones") or 1)), monto * TOLERANCIA_RELATIVA_MONTO)
    return suma > monto + tolerancia or suma < monto / 2


def forma_pago_del_cobro(pago: dict) -> Optional[str]:
    """``FormaDePagoP`` del REP (``forma_pago_p``), o ``None`` si no se guardó. Es el único lugar que la
    lee: en cuanto la extracción la guarde, la exclusión por efectivo de un cobro a crédito se activa sola."""
    return pago.get("forma_pago_p")
