"""Criterio de efectivo en ISR base flujo (spec 2026-10-13). Sin DB."""
from datetime import date
from decimal import Decimal

import pytest

from backend import isr_flujo as f

D = Decimal
RFC = "AAA010101AAA"
OTRO = "XAXX010101000"
PROV = "PRO010101AAA"


def doc(uuid="U1", **kw):
    base = dict(uuid=uuid, tipo_comprobante="I", metodo_pago="PUE", forma_pago="03", uso_cfdi="G03", estado="vigente",
                es_anticipo_sat=False, rfc_emisor=RFC, nombre_emisor="EMISORA", rfc_receptor=OTRO,
                nombre_receptor="CLIENTE", fecha_emision=date(2026, 9, 10), subtotal=D("1000"), descuento=D("0"),
                total=D("1160"), isr_retenido=D("0"), moneda="MXN", tipo_cambio=D("1"))
    base.update(kw)
    return base


def recibido(uuid="R1", **kw):
    base = dict(rfc_emisor=PROV, nombre_emisor="PROVEEDOR", rfc_receptor=RFC, nombre_receptor="EMISORA")
    base.update(kw)
    return doc(uuid, **base)


def pago(cfdi_uuid="U1", importe="580", fecha=date(2026, 9, 25), **kw):
    base = dict(uuid_pago="REP1", fecha_pago=fecha, version_pago="2.0", pago_estado="vigente", pago_moneda="MXN",
                pago_tipo_cambio=D("1"), cfdi_uuid=cfdi_uuid, parcialidad=1, importe_pagado=D(importe),
                moneda_dr="MXN", equivalencia_dr=D("1"))
    base.update(kw)
    return base


def nomina(uuid="N1", percepciones=None, fecha=date(2026, 9, 15), retenido="100", **kw):
    base = dict(uuid=uuid, estado="vigente", fecha_pago=fecha, fecha_emision=fecha, rfc_emisor=RFC, nombre_emisor="EMISORA",
                rfc_receptor="TRA010101AAA", nombre_receptor="TRABAJADOR", isr_retenido=D(retenido),
                percepciones=percepciones if percepciones is not None else [{"tipo": "001", "gravado": D("800"), "exento": D("200")}])
    base.update(kw)
    return base


LEGAL, ESTRICTO = D("2000"), D("0")


def _rel(forma_pago="03", total="1000", uso_cfdi="G03"):
    return {"metodo_pago": "PUE", "forma_pago": forma_pago, "uso_cfdi": uso_cfdi, "total": total,
            "moneda": "MXN", "tipo_cambio": "1"}


def _deduccion(evs):
    return [e for e in evs if e["lado"] == "deduccion"]


def test_compra_en_efectivo_de_1000_se_deduce_con_legal_y_no_con_estricto():
    c = recibido("R1", forma_pago="01", total=D("1000"))
    assert f.motivo_exclusion(_deduccion(f.eventos_de_documento(c, RFC, LEGAL))[0]) is None
    assert f.motivo_exclusion(_deduccion(f.eventos_de_documento(c, RFC, ESTRICTO))[0]) == "efectivo"


def test_efectivo_exactamente_en_2000_se_deduce_con_legal_y_no_con_estricto():
    c = recibido("R2", forma_pago="01", total=D("2000.00"))
    assert f.motivo_exclusion(_deduccion(f.eventos_de_documento(c, RFC, LEGAL))[0]) is None
    assert f.motivo_exclusion(_deduccion(f.eventos_de_documento(c, RFC, ESTRICTO))[0]) == "efectivo"


def test_efectivo_mayor_a_2000_se_excluye_con_ambos_criterios():
    c = recibido("R3", forma_pago="01", total=D("2000.01"))
    for umbral in (LEGAL, ESTRICTO):
        assert f.motivo_exclusion(_deduccion(f.eventos_de_documento(c, RFC, umbral))[0]) == "efectivo"


def test_marca_efectivo_hasta_umbral_solo_con_umbral_positivo():
    c = recibido("R4", forma_pago="01", total=D("1000"))
    assert "efectivo_hasta_umbral" in _deduccion(f.eventos_de_documento(c, RFC, LEGAL))[0]["marcas"]
    assert "efectivo_hasta_umbral" not in _deduccion(f.eventos_de_documento(c, RFC, ESTRICTO))[0]["marcas"]


def test_ingresos_cobrados_en_efectivo_no_se_afectan():
    c = doc("U1", forma_pago="01", total=D("1000"))
    ev = [e for e in f.eventos_de_documento(c, RFC, ESTRICTO) if e["lado"] == "ingreso"][0]
    assert f.motivo_exclusion(ev) is None


def test_pago_en_efectivo_de_factura_ppd_sigue_el_criterio():
    c = recibido("R5", metodo_pago="PPD", forma_pago="99", total=D("1160"))
    p = pago("R5", importe="580", forma_pago_p="01")
    ev_l = _deduccion(f.eventos_de_pago(p, c, RFC, LEGAL))[0]
    ev_e = _deduccion(f.eventos_de_pago(p, c, RFC, ESTRICTO))[0]
    assert f.motivo_exclusion(ev_l) is None
    assert f.motivo_exclusion(ev_e) == "efectivo"


def test_devolucion_de_original_en_efectivo_hereda_motivo_solo_con_estricto():
    nc = recibido("N1", tipo_comprobante="E", forma_pago="03", total=D("100"),
                  relacionados_info=[_rel(forma_pago="01", total="1000")])
    ev_l = _deduccion(f.eventos_de_documento(nc, RFC, LEGAL))[0]
    ev_e = _deduccion(f.eventos_de_documento(nc, RFC, ESTRICTO))[0]
    assert "original_no_deducible" not in ev_l["marcas"]
    assert "original_no_deducible" in ev_e["marcas"]


def test_sin_argumento_el_umbral_es_el_legal():
    c = recibido("R6", forma_pago="01", total=D("1000"))
    assert _deduccion(f.eventos_de_documento(c, RFC))[0]["umbral_efectivo"] == LEGAL
