"""Reglas puras de M7.2 (D10): datos fiscales del cliente, pagos manuales y aviso de
vencimiento."""
from datetime import date
from decimal import Decimal

import pytest

from backend import suscripcion_pagos as sp
from backend.suscripcion import DatoInvalido

HOY = date(2026, 10, 6)
FISCALES = {"rfc": " ace010101aa1 ", "razon_social": " ACME SA DE CV ", "regimen_fiscal": "601",
            "codigo_postal": "68000", "uso_cfdi": "g03"}


def test_datos_fiscales_se_normalizan():
    assert sp.validar_datos_fiscales(FISCALES) == {
        "rfc": "ACE010101AA1", "razon_social": "ACME SA DE CV", "regimen_fiscal": "601",
        "codigo_postal": "68000", "uso_cfdi": "G03",
    }
    fisica = {**FISCALES, "rfc": "GOHC800101AB1", "regimen_fiscal": "612", "uso_cfdi": "S01"}
    assert sp.validar_datos_fiscales(fisica)["regimen_fiscal"] == "612"
    assert sp.validar_datos_fiscales({**FISCALES, "regimen_fiscal": "626"})["regimen_fiscal"] == "626"


@pytest.mark.parametrize("cambio", [
    {"rfc": "XYZ"},
    {"rfc": None},
    {"rfc": 123},
    {"razon_social": "  "},
    {"razon_social": "x" * 255},
    {"regimen_fiscal": "612"},             # persona moral con régimen de persona física
    {"regimen_fiscal": "999"},
    {"codigo_postal": "6800"},
    {"codigo_postal": "68A00"},
    {"uso_cfdi": "P01"},                   # ya no existe en CFDI 4.0
])
def test_datos_fiscales_invalidos(cambio):
    with pytest.raises(DatoInvalido):
        sp.validar_datos_fiscales({**FISCALES, **cambio})


def test_regimen_de_persona_moral_en_persona_fisica():
    with pytest.raises(DatoInvalido, match="persona física"):
        sp.validar_datos_fiscales({**FISCALES, "rfc": "GOHC800101AB1", "regimen_fiscal": "601"})


def test_pago_valido():
    assert sp.validar_pago({"fecha": "2026-10-01", "monto": "1499", "referencia": " SPEI 123 ", "folio_cfdi": "A-15"},
                           HOY) == {"fecha": date(2026, 10, 1), "monto": Decimal("1499.00"),
                                    "referencia": "SPEI 123", "folio_cfdi": "A-15"}
    assert sp.validar_pago({"fecha": "2026-10-06", "monto": 499}, HOY)["referencia"] is None


@pytest.mark.parametrize("cuerpo", [
    {"fecha": "2026-10-07", "monto": "10"},        # futura
    {"fecha": "06/10/2026", "monto": "10"},
    {"fecha": "2026-10-01", "monto": "0"},
    {"fecha": "2026-10-01", "monto": "-5"},
    {"fecha": "2026-10-01", "monto": "10.001"},
    {"fecha": "2026-10-01", "monto": 10.5},         # float: se pide texto
    {"fecha": "2026-10-01", "monto": True},
    {"fecha": "2026-10-01", "monto": "NaN"},
    {"fecha": "2026-10-01", "monto": "10000000.01"},
    {"fecha": "2026-10-01", "monto": "10", "referencia": 5},
    {"fecha": "2026-10-01", "monto": "10", "folio_cfdi": "x" * 41},
])
def test_pago_invalido(cuerpo):
    with pytest.raises(DatoInvalido):
        sp.validar_pago(cuerpo, HOY)


@pytest.mark.parametrize("vigente_hasta,motivo,dias", [
    (date(2026, 10, 21), None, 15),
    (date(2026, 10, 6), None, 0),
    (date(2026, 10, 22), None, None),     # más de 15 días
    (date(2026, 10, 5), None, None),      # ya vencida (se avisa por el motivo, no aquí)
    (None, None, None),
    (date(2026, 10, 10), "suspendida", None),
])
def test_aviso_de_vencimiento(vigente_hasta, motivo, dias):
    assert sp.aviso_vencimiento(vigente_hasta, motivo, HOY) == dias
