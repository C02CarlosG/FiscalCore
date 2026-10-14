"""Criterio de efectivo en IVA base flujo (spec 2026-10-13). Sin DB."""
from datetime import date
from decimal import Decimal

import pytest

from backend import iva_flujo as f

D = Decimal
RFC = "AAA010101AAA"
OTRO = "XAXX010101000"
PROV = "PRO010101AAA"


def imp(ambito, impuesto, factor, tasa, base, importe):
    return {"ambito": ambito, "impuesto": impuesto, "tipo_factor": factor,
            "tasa_o_cuota": None if tasa is None else D(str(tasa)), "base": D(str(base)), "importe": D(str(importe))}


def tras(tasa, base, importe, impuesto="002"):
    return imp("traslado", impuesto, "Tasa", tasa, base, importe)


def doc(uuid="U1", **kw):
    base = dict(uuid=uuid, tipo_comprobante="I", metodo_pago="PUE", forma_pago="03", uso_cfdi="G03", estado="vigente",
                es_anticipo_sat=False, rfc_emisor=RFC, nombre_emisor="EMISORA", rfc_receptor=OTRO,
                nombre_receptor="CLIENTE", fecha_emision=date(2026, 9, 10), subtotal=D("1000"), descuento=D("0"),
                total=D("1160"), iva_trasladado=D("160"), iva_retenido=D("0"), moneda="MXN", tipo_cambio=D("1"),
                impuestos=[tras("0.16", 1000, 160)], no_objeto=D("0"))
    base.update(kw)
    return base


def recibido(uuid="R1", **kw):
    base = dict(rfc_emisor=PROV, nombre_emisor="PROVEEDOR", rfc_receptor=RFC, nombre_receptor="EMISORA")
    base.update(kw)
    return doc(uuid, **base)


def pago(cfdi_uuid="U1", importe="580", fecha=date(2026, 9, 25), **kw):
    base = dict(uuid_pago="REP1", fecha_pago=fecha, version_pago="2.0", pago_estado="vigente", pago_moneda="MXN",
                pago_tipo_cambio=D("1"), cfdi_uuid=cfdi_uuid, parcialidad=1, importe_pagado=D(importe),
                moneda_dr="MXN", equivalencia_dr=D("1"), impuestos_dr=[tras("0.16", 500, 80)])
    base.update(kw)
    return base


# ── desglose por tasa ────────────────────────────────────────────────────────

LEGAL, ESTRICTO = D("2000"), D("0")


def _rel(forma_pago="03", total="1160", uso_cfdi="G03"):
    return {"metodo_pago": "PUE", "forma_pago": forma_pago, "uso_cfdi": uso_cfdi, "total": total,
            "moneda": "MXN", "tipo_cambio": "1"}


def _acreditable(evs):
    return [e for e in evs if e["direccion"] == "acreditable"]


def test_compra_de_1160_en_efectivo_legal_se_considera_y_estricto_se_excluye():
    c = recibido("R1", forma_pago="01", total=D("1160"))
    ev_legal = _acreditable(f.eventos_de_documento(c, RFC, LEGAL))[0]
    ev_estricto = _acreditable(f.eventos_de_documento(c, RFC, ESTRICTO))[0]
    assert f.motivo_exclusion(ev_legal) is None
    assert f.motivo_exclusion(ev_estricto) == "efectivo"


def test_efectivo_exactamente_en_el_umbral_no_se_excluye_con_legal_y_si_con_estricto():
    c = recibido("R2", forma_pago="01", total=D("2000.00"))
    assert f.motivo_exclusion(_acreditable(f.eventos_de_documento(c, RFC, LEGAL))[0]) is None
    assert f.motivo_exclusion(_acreditable(f.eventos_de_documento(c, RFC, ESTRICTO))[0]) == "efectivo"


def test_efectivo_de_2000_01_se_excluye_con_ambos_criterios():
    c = recibido("R3", forma_pago="01", total=D("2000.01"))
    for umbral in (LEGAL, ESTRICTO):
        assert f.motivo_exclusion(_acreditable(f.eventos_de_documento(c, RFC, umbral))[0]) == "efectivo"


def test_transferencia_nunca_se_excluye_por_efectivo():
    c = recibido("R4", forma_pago="03", total=D("1160"))
    assert f.motivo_exclusion(_acreditable(f.eventos_de_documento(c, RFC, ESTRICTO))[0]) is None


def test_el_criterio_no_aplica_a_lo_trasladado():
    c = doc("U1", forma_pago="01", total=D("1160"))      # emitida por la empresa y cobrada en efectivo
    ev = [e for e in f.eventos_de_documento(c, RFC, ESTRICTO) if e["direccion"] == "trasladado"][0]
    assert f.motivo_exclusion(ev) is None


def test_sin_argumento_el_umbral_es_el_legal():
    c = recibido("R5", forma_pago="01", total=D("1160"))
    ev = _acreditable(f.eventos_de_documento(c, RFC))[0]
    assert ev["umbral_efectivo"] == LEGAL
    assert f.motivo_exclusion(ev) is None


def test_pago_en_efectivo_de_factura_ppd_sigue_el_criterio():
    c = recibido("R6", metodo_pago="PPD", forma_pago="99", total=D("1160"))
    p = pago("R6", importe="580", forma_pago_p="01")
    ev_l = _acreditable(f.eventos_de_pago(p, c, RFC, LEGAL))[0]
    ev_e = _acreditable(f.eventos_de_pago(p, c, RFC, ESTRICTO))[0]
    assert f.motivo_exclusion(ev_l) is None
    assert f.motivo_exclusion(ev_e) == "efectivo"


def test_pago_en_efectivo_en_moneda_extranjera_se_mide_en_pesos():
    # 100 USD a 20 = 2,000 pesos: en el umbral no se excluye con legal; con estricto sí.
    c = recibido("R8", metodo_pago="PPD", forma_pago="99", moneda="USD", tipo_cambio=D("20"), total=D("200"))
    p = pago("R8", importe="100", forma_pago_p="01", moneda_dr="USD", equivalencia_dr=D("1"),
             pago_moneda="USD", pago_tipo_cambio=D("20"))
    assert f.motivo_exclusion(_acreditable(f.eventos_de_pago(p, c, RFC, LEGAL))[0]) is None
    assert f.motivo_exclusion(_acreditable(f.eventos_de_pago(p, c, RFC, ESTRICTO))[0]) == "efectivo"


def test_nota_de_credito_de_un_original_en_efectivo_hereda_motivo_solo_con_estricto():
    nc = recibido("N1", tipo_comprobante="E", impuestos=[tras("0.16", 100, 16)], iva_trasladado=D("16"),
                  relacionados_info=[_rel(forma_pago="01", total="1160")])
    ev_l = _acreditable(f.eventos_de_documento(nc, RFC, LEGAL))[0]
    ev_e = _acreditable(f.eventos_de_documento(nc, RFC, ESTRICTO))[0]
    assert "original_no_acreditable" not in ev_l["marcas"] and f.motivo_exclusion(ev_l) is None
    assert "original_no_acreditable" in ev_e["marcas"] and f.motivo_exclusion(ev_e) == "original_no_acreditable"


def test_retencion_de_iva_de_compra_en_efectivo_se_sigue_enterando_con_estricto():
    c = recibido("R7", forma_pago="01", impuestos=[tras("0.16", 250, 40), imp("retencion", "002", "Tasa", "0.106667", 250, "26.67")],
                 iva_trasladado=D("40"))
    evs = f.eventos_de_documento(c, RFC, ESTRICTO)
    r = f.resumen(evs, "2026-09", {})
    assert r["acreditable"]["total"]["iva"]["total"] == D("0.00")      # el IVA en efectivo no se acredita
    assert r["retenciones_a_enterar"] == D("26.67")                    # la retención se entera igual (LIVA 1-A)
