"""IVA base flujo (F5.1): desglose por tasa, eventos, exclusiones, ajustes y resumen. Sin DB."""
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

def test_desglose_separa_16_8_0_y_exento():
    d = f.desglose([
        tras("0.16", 1000, 160), tras("0.08", 500, 40), tras("0.00", 300, 0),
        imp("traslado", "002", "Exento", None, 200, 0),
    ])

    assert d["bases"] == {"16": D("1000"), "8": D("500"), "0": D("300"), "exento": D("200"), "otras": D("0"), "no_objeto": D("0")}
    assert d["iva"] == {"16": D("160"), "8": D("40"), "otras": D("0"), "total": D("200")}


def test_desglose_ignora_ieps_isr_y_otras_tasas_van_aparte():
    d = f.desglose([
        tras("0.16", 1000, 160), tras("0.08", 100, 8, impuesto="003"),      # IEPS: no es IVA
        tras("0.11", 100, 11),                                              # histórica
        imp("traslado", "002", "Cuota", None, 50, 5),
    ])

    assert d["bases"]["16"] == D("1000") and d["bases"]["8"] == D("0")
    assert d["bases"]["otras"] == D("150") and d["iva"]["otras"] == D("16")
    assert d["iva"]["total"] == D("176")


def test_desglose_retenciones_de_iva_suman_importe_y_no_son_tasa_cero():
    d = f.desglose([tras("0.16", 1000, 160), imp("retencion", "002", "Tasa", "0.106667", 1000, "106.67"),
                    imp("retencion", "002", "Tasa", None, 0, 20), imp("retencion", "001", "Tasa", "0.10", 1000, 100)])

    assert d["retencion"] == D("126.67")
    assert d["bases"]["0"] == D("0")


def test_desglose_vacio_y_no_objeto():
    d = f.desglose([], no_objeto=D("300"))

    assert d["iva"]["total"] == D("0") and d["bases"]["no_objeto"] == D("300")


def test_escalar_multiplica_bases_iva_y_retencion():
    d = f.escalar(f.desglose([tras("0.16", 1000, 160), imp("retencion", "002", "Tasa", None, 0, 10)]), D("0.5"))

    assert d["bases"]["16"] == D("500") and d["iva"]["total"] == D("80") and d["retencion"] == D("5")


# ── conversión a pesos ───────────────────────────────────────────────────────

@pytest.mark.parametrize("moneda_dr,eq,moneda_p,tc,esperado", [
    ("MXN", D("1"), "MXN", D("1"), D("1")),            # todo en pesos
    ("MXN", D("20"), "USD", D("20"), D("1")),          # documento en MXN pagado en USD: neto 1
    ("USD", D("1"), "USD", D("20"), D("20")),          # documento en USD pagado en USD: × tipo de cambio
    ("USD", D("0.05"), "MXN", D("1"), D("20")),        # documento en USD pagado en MXN: 1/0.05
    ("MXN", None, "MXN", D("1"), D("1")),              # sin equivalencia pero misma moneda: 1
    (None, None, "MXN", D("1"), D("1")),
])
def test_factor_a_pesos(moneda_dr, eq, moneda_p, tc, esperado):
    assert f.factor_a_pesos(moneda_dr, eq, moneda_p, tc) == esperado


def test_factor_a_pesos_sin_equivalencia_y_monedas_distintas_no_se_asume_uno():
    assert f.factor_a_pesos("USD", None, "MXN", D("1")) is None


# ── eventos de un documento ──────────────────────────────────────────────────

def test_pue_emitido_es_un_evento_de_contado_trasladado():
    evs = f.eventos_de_documento(doc(), RFC)

    assert len(evs) == 1
    e = evs[0]
    assert (e["direccion"], e["origen"], e["periodo_natural"]) == ("trasladado", "contado", "2026-09")
    assert e["iva_total"] == D("160") and e["bases"]["16"] == D("1000")


def test_pue_recibido_es_acreditable():
    e = f.eventos_de_documento(recibido(), RFC)[0]

    assert (e["direccion"], e["origen"]) == ("acreditable", "contado")


def test_nota_de_credito_es_origen_aparte_con_sus_impuestos():
    e = f.eventos_de_documento(doc("N1", tipo_comprobante="E", impuestos=[tras("0.16", 300, 48)], iva_trasladado=D("48")), RFC)[0]

    assert e["origen"] == "notas_credito" and e["iva_total"] == D("48")


def test_egreso_con_forma_de_pago_30_se_marca_como_aplicacion_de_anticipo():
    e = f.eventos_de_documento(doc("C1", tipo_comprobante="E", forma_pago="30"), RFC)[0]

    assert "aplicacion_anticipo" in e["marcas"] and e["origen"] == "notas_credito"


def test_el_anticipo_si_causa_iva_en_su_fecha():
    e = f.eventos_de_documento(doc("A1", es_anticipo_sat=True), RFC)[0]

    assert e["origen"] == "contado" and e["iva_total"] == D("160") and "anticipo" in e["marcas"]


def test_ppd_no_genera_evento_por_si_mismo():
    assert f.eventos_de_documento(doc(metodo_pago="PPD"), RFC) == []


def test_cancelado_y_tipos_ajenos_no_generan_evento():
    assert f.eventos_de_documento(doc(estado="cancelado"), RFC) == []
    for tipo in ("T", "N", "P"):
        assert f.eventos_de_documento(doc(tipo_comprobante=tipo), RFC) == []


def test_documento_ajeno_a_la_empresa_no_genera_evento():
    assert f.eventos_de_documento(doc(rfc_emisor="ZZZ010101AAA", rfc_receptor="YYY010101AAA"), RFC) == []


def test_autofactura_genera_ambos_lados():
    evs = f.eventos_de_documento(doc(rfc_receptor=RFC), RFC)

    assert sorted(e["direccion"] for e in evs) == ["acreditable", "trasladado"]


def test_moneda_extranjera_se_convierte_con_el_tipo_de_cambio_del_cfdi():
    e = f.eventos_de_documento(doc(moneda="USD", tipo_cambio=D("20"), iva_trasladado=D("1.6"),
                                   impuestos=[tras("0.16", 10, "1.6")], total=D("11.6")), RFC)[0]

    assert e["iva_total"] == D("32.00") and e["bases"]["16"] == D("200")


def test_tipo_cambio_nulo_o_cero_cuenta_como_uno():
    for tc in (None, D("0")):
        e = f.eventos_de_documento(doc(tipo_cambio=tc), RFC)[0]
        assert e["iva_total"] == D("160")


def test_descuadre_entre_desglose_y_encabezado_manda_el_encabezado():
    e = f.eventos_de_documento(doc(iva_trasladado=D("161"), impuestos=[tras("0.16", 1000, 160)]), RFC)[0]

    assert "descuadre" in e["marcas"] and e["iva_total"] == D("161")


def test_diferencia_de_centavos_no_es_descuadre():
    e = f.eventos_de_documento(doc(iva_trasladado=D("160.01")), RFC)[0]

    assert "descuadre" not in e["marcas"]


def test_sin_desglose_guardado_usa_el_encabezado_y_lo_marca():
    e = f.eventos_de_documento(doc(impuestos=[]), RFC)[0]

    assert "sin_desglose" in e["marcas"] and e["iva_total"] == D("160") and e["bases"]["16"] == D("0")


def test_no_objeto_se_informa_como_base_sin_iva():
    e = f.eventos_de_documento(doc(impuestos=[], iva_trasladado=D("0"), no_objeto=D("700")), RFC)[0]

    assert e["bases"]["no_objeto"] == D("700") and e["iva_total"] == D("0")


# ── eventos de un pago (REP) ─────────────────────────────────────────────────

def test_pago_rep_2_usa_los_impuestos_del_documento_y_la_fecha_del_pago():
    d = doc(metodo_pago="PPD", forma_pago="99", total=D("1160"))
    e = f.evento_de_pago(pago(), d, RFC)

    assert (e["direccion"], e["origen"], e["fecha_efecto"], e["periodo_natural"]) == ("trasladado", "credito", date(2026, 9, 25), "2026-09")
    assert e["iva_total"] == D("80") and e["bases"]["16"] == D("500") and e["uuid_pago"] == "REP1"
    assert not (e["marcas"] & {"aproximado", "pago_v1"})


def test_pago_de_un_documento_recibido_es_acreditable():
    e = f.evento_de_pago(pago("R1"), recibido("R1", metodo_pago="PPD"), RFC)

    assert e["direccion"] == "acreditable"


def test_pago_v1_aproxima_por_proporcion_y_avisa():
    d = doc(metodo_pago="PPD", total=D("1160"))
    e = f.evento_de_pago(pago(version_pago="1.0", impuestos_dr=[]), d, RFC)

    assert e["iva_total"] == D("80.00") and e["bases"]["16"] == D("500.00")      # 160 × 580/1160
    assert {"aproximado", "pago_v1"} <= e["marcas"]


def test_pago_2_sin_impuestos_dr_tambien_aproxima_pero_no_dice_v1():
    d = doc(metodo_pago="PPD", total=D("1160"))
    e = f.evento_de_pago(pago(impuestos_dr=[]), d, RFC)

    assert "aproximado" in e["marcas"] and "pago_v1" not in e["marcas"]


def test_pago_en_moneda_extranjera_convierte_con_equivalencia_y_tipo_de_cambio_del_pago():
    d = doc(metodo_pago="PPD", moneda="USD", tipo_cambio=D("19"), total=D("116"))
    p = pago(importe="58", moneda_dr="USD", equivalencia_dr=D("1"), pago_moneda="USD", pago_tipo_cambio=D("20"),
             impuestos_dr=[tras("0.16", 50, 8)])

    e = f.evento_de_pago(p, d, RFC)

    assert e["iva_total"] == D("160") and e["bases"]["16"] == D("1000")       # × 20, no × 19 del CFDI


def test_pago_sin_equivalencia_y_monedas_distintas_no_suma():
    d = doc(metodo_pago="PPD", moneda="USD", total=D("116"))
    e = f.evento_de_pago(pago(moneda_dr="USD", equivalencia_dr=None), d, RFC)

    assert "sin_equivalencia" in e["marcas"] and e["iva_total"] == D("0")


def test_pago_de_rep_cancelado_no_genera_evento():
    assert f.evento_de_pago(pago(pago_estado="cancelado"), doc(metodo_pago="PPD"), RFC) is None


def test_pago_con_retencion_del_documento_la_conserva_proporcional():
    d = doc(metodo_pago="PPD", total=D("1160"), impuestos=[tras("0.16", 1000, 160), imp("retencion", "002", "Tasa", "0.106667", 1000, "106.67")])
    e = f.evento_de_pago(pago(version_pago="1.0", impuestos_dr=[]), d, RFC)

    assert e["retencion"] == D("53.335")


# ── exclusiones y ajustes ────────────────────────────────────────────────────

def _ev(**kw):
    d = recibido(**kw)
    return f.eventos_de_documento(d, RFC)[0]


@pytest.mark.parametrize("kw,motivo", [
    ({"forma_pago": "01", "total": D("2500")}, "efectivo"),
    ({"forma_pago": "01", "total": D("2000")}, None),            # el umbral es "mayor a"
    ({"forma_pago": "03", "total": D("2500")}, None),
    ({"uso_cfdi": "S01"}, "uso_no_deducible"),
    ({"uso_cfdi": "CP01"}, "uso_no_deducible"),
    ({"uso_cfdi": "CN01"}, "uso_no_deducible"),
    ({"uso_cfdi": "G03"}, None),
])
def test_motivos_de_exclusion_del_acreditable(kw, motivo):
    assert f.motivo_exclusion(_ev(**kw)) == motivo


def test_el_trasladado_no_aplica_las_reglas_de_efectivo_ni_de_uso():
    e = f.eventos_de_documento(doc(forma_pago="01", total=D("9000"), uso_cfdi="S01"), RFC)[0]

    assert f.motivo_exclusion(e) is None


def test_pago_v1_se_excluye_solo_en_modo_excluir(monkeypatch):
    d = doc(metodo_pago="PPD", total=D("1160"))
    e = f.evento_de_pago(pago(version_pago="1.0", impuestos_dr=[]), d, RFC)
    assert f.motivo_exclusion(e) is None

    monkeypatch.setattr(f, "PAGOS_V1_MODO", "excluir")
    assert f.motivo_exclusion(e) == "pago_v1"


def test_sin_equivalencia_siempre_queda_fuera():
    d = doc(metodo_pago="PPD", moneda="USD", total=D("116"))
    e = f.evento_de_pago(pago(moneda_dr="USD", equivalencia_dr=None), d, RFC)

    assert f.motivo_exclusion(e) == "sin_equivalencia"


def test_estado_en_periodo_sin_ajustes():
    e = f.eventos_de_documento(doc(), RFC)[0]

    assert f.estado_en_periodo(e, "2026-09", {}) == ("considerado", None)
    assert f.estado_en_periodo(e, "2026-10", {}) is None              # no es de ese periodo


def test_excluir_manual_saca_el_cfdi_y_lo_marca_manual():
    e = f.eventos_de_documento(doc(), RFC)[0]
    aj = {("U1", "trasladado"): {"accion": "excluir", "periodo_destino": None, "motivo": "duplicado"}}

    assert f.estado_en_periodo(e, "2026-09", aj) == ("no_considerado", "manual")


def test_reasignar_mueve_el_efecto_al_periodo_destino():
    e = f.eventos_de_documento(doc(), RFC)[0]
    aj = {("U1", "trasladado"): {"accion": "reasignar", "periodo_destino": "2026-10", "motivo": "se cobró en octubre"}}

    assert f.estado_en_periodo(e, "2026-09", aj) == ("reasignado", "reasignado")
    assert f.estado_en_periodo(e, "2026-10", aj) == ("considerado", None)
    assert f.estado_en_periodo(e, "2026-11", aj) is None


def test_reasignar_no_salta_las_reglas_automaticas_en_el_destino():
    e = _ev(uso_cfdi="S01")
    aj = {("R1", "acreditable"): {"accion": "reasignar", "periodo_destino": "2026-10", "motivo": "x"}}

    assert f.estado_en_periodo(e, "2026-10", aj) == ("no_considerado", "uso_no_deducible")


def test_el_ajuste_de_una_direccion_no_afecta_a_la_otra():
    e = f.eventos_de_documento(doc(), RFC)[0]
    aj = {("U1", "acreditable"): {"accion": "excluir", "periodo_destino": None, "motivo": "x"}}

    assert f.estado_en_periodo(e, "2026-09", aj) == ("considerado", None)


def test_la_llave_del_ajuste_ignora_mayusculas():
    e = f.eventos_de_documento(doc("abc-1"), RFC)[0]
    aj = {("ABC-1", "trasladado"): {"accion": "excluir", "periodo_destino": None, "motivo": "x"}}

    assert f.estado_en_periodo(e, "2026-09", aj) == ("no_considerado", "manual")


# ── resumen del periodo ──────────────────────────────────────────────────────

def _construir(docs, pagos=(), rfc=RFC):
    por_uuid = {f.llave(d["uuid"]): d for d in docs}
    eventos = [e for d in docs for e in f.eventos_de_documento(d, rfc)]
    for p in pagos:
        d = por_uuid.get(f.llave(p["cfdi_uuid"]))
        if d:
            e = f.evento_de_pago(p, d, rfc)
            if e:
                eventos.append(e)
    return eventos


def test_resumen_trasladado_por_origen_y_total():
    docs = [
        doc("U1", impuestos=[tras("0.16", 1000, 160), tras("0.08", 500, 40)], iva_trasladado=D("200")),
        doc("U2", metodo_pago="PPD", total=D("1160")),
        doc("N1", tipo_comprobante="E", impuestos=[tras("0.16", 300, 48)], iva_trasladado=D("48")),
    ]
    r = f.resumen(_construir(docs, [pago("U2")]), "2026-09", {})

    t = r["trasladado"]
    assert t["origenes"]["contado"]["iva"]["total"] == D("200.00") and t["origenes"]["contado"]["cfdi"] == 1
    assert t["origenes"]["contado"]["bases"]["16"] == D("1000.00") and t["origenes"]["contado"]["bases"]["8"] == D("500.00")
    assert t["origenes"]["credito"]["iva"]["total"] == D("80.00")
    assert (t["origenes"]["credito"]["pagos"], t["origenes"]["credito"]["cfdi"]) == (1, 1)
    assert t["origenes"]["notas_credito"]["iva"]["total"] == D("48.00")
    assert t["total"]["iva"]["total"] == D("232.00")          # 200 + 80 − 48
    assert t["total"]["bases"]["16"] == D("1000.00") + D("500.00") - D("300.00")


def test_resumen_acreditable_con_factor_de_prorrateo():
    r = f.resumen(_construir([recibido("R1", impuestos=[tras("0.16", 1000, 160)])]), "2026-09", {}, factor=D("0.5"))

    a = r["acreditable"]
    assert a["total"]["iva"]["total"] == D("160.00") and a["ajustado"] == D("80.00") and r["factor_prorrateo"] == D("0.5")


def test_resumen_no_considerados_se_cuentan_aparte_con_su_iva():
    docs = [recibido("R1"), recibido("R2", uso_cfdi="S01"), recibido("R3", forma_pago="01", total=D("5000"))]
    r = f.resumen(_construir(docs), "2026-09", {})

    a = r["acreditable"]
    assert a["total"]["iva"]["total"] == D("160.00")
    assert a["no_considerados"] == {"cfdi": 2, "iva": D("320.00")}


def test_resumen_reasignados_salen_del_periodo_original_y_entran_al_destino():
    docs = [doc("U1")]
    aj = {("U1", "trasladado"): {"accion": "reasignar", "periodo_destino": "2026-10", "motivo": "x"}}
    eventos = _construir(docs)

    sep, octubre = f.resumen(eventos, "2026-09", aj), f.resumen(eventos, "2026-10", aj)

    assert sep["trasladado"]["total"]["iva"]["total"] == D("0.00")
    assert sep["trasladado"]["reasignados"] == {"cfdi": 1, "iva": D("160.00")}
    assert octubre["trasladado"]["total"]["iva"]["total"] == D("160.00")


def test_resumen_resultado_resta_acreditable_y_retenciones_a_favor():
    docs = [
        doc("U1", impuestos=[tras("0.16", 1000, 160), imp("retencion", "002", "Tasa", "0.106667", 1000, "106.67")]),
        recibido("R1", impuestos=[tras("0.16", 250, 40), imp("retencion", "002", "Tasa", "0.106667", 250, "26.67")], iva_trasladado=D("40")),
    ]
    r = f.resumen(_construir(docs), "2026-09", {})

    assert r["resultado"] == {
        "trasladado": D("160.00"), "acreditable": D("40.00"), "retenciones_a_favor": D("106.67"),
        "iva_por_pagar": D("13.33"), "saldo_a_cargo": D("13.33"), "saldo_a_favor": D("0.00"),
    }
    assert r["retenciones_a_enterar"] == D("26.67")                   # no reduce el acreditable


def test_resumen_saldo_a_favor():
    r = f.resumen(_construir([recibido("R1", impuestos=[tras("0.16", 2000, 320)], iva_trasladado=D("320"))]), "2026-09", {})

    assert r["resultado"]["iva_por_pagar"] == D("-320.00")
    assert (r["resultado"]["saldo_a_cargo"], r["resultado"]["saldo_a_favor"]) == (D("0.00"), D("320.00"))


def test_resumen_periodo_sin_movimiento_es_ceros():
    r = f.resumen([], "2026-09", {})

    assert r["trasladado"]["total"]["iva"]["total"] == D("0.00")
    assert r["resultado"]["iva_por_pagar"] == D("0.00")
    assert r["advertencias"] == []
    assert set(r["trasladado"]["origenes"]) == {"contado", "credito", "notas_credito"}


def test_resumen_anticipo_mas_factura_menos_aplicacion_es_la_factura():
    docs = [
        doc("A1", es_anticipo_sat=True, fecha_emision=date(2026, 8, 5), impuestos=[tras("0.16", 2000, 320)], iva_trasladado=D("320")),
        doc("B1", impuestos=[tras("0.16", 5000, 800)], iva_trasladado=D("800")),
        doc("C1", tipo_comprobante="E", forma_pago="30", impuestos=[tras("0.16", 2000, 320)], iva_trasladado=D("320")),
    ]
    eventos = _construir(docs)

    agosto, septiembre = f.resumen(eventos, "2026-08", {}), f.resumen(eventos, "2026-09", {})

    assert agosto["trasladado"]["total"]["iva"]["total"] == D("320.00")          # el anticipo cuando se cobró
    assert septiembre["trasladado"]["total"]["iva"]["total"] == D("480.00")      # 800 − 320
    assert agosto["trasladado"]["total"]["iva"]["total"] + septiembre["trasladado"]["total"]["iva"]["total"] == D("800.00")


def test_resumen_advertencias_cuentan_por_codigo():
    docs = [doc("U1", metodo_pago="PPD", total=D("1160")), doc("U2", iva_trasladado=D("161"))]
    pagos = [pago("U1", version_pago="1.0", impuestos_dr=[])]
    r = f.resumen(_construir(docs, pagos), "2026-09", {})

    codigos = {a["codigo"]: a["cfdi"] for a in r["advertencias"]}
    assert codigos == {"pago_v1": 1, "descuadre": 1}
    assert all(a["mensaje"] for a in r["advertencias"])


def test_resumen_sin_equivalencia_se_advierte_aunque_no_sume():
    d = doc("U1", metodo_pago="PPD", moneda="USD", total=D("116"))
    r = f.resumen(_construir([d], [pago("U1", moneda_dr="USD", equivalencia_dr=None)]), "2026-09", {})

    assert r["trasladado"]["total"]["iva"]["total"] == D("0.00")
    assert {a["codigo"] for a in r["advertencias"]} == {"sin_equivalencia"}


def test_resumen_cuenta_documentos_distintos_en_credito():
    d = doc("U1", metodo_pago="PPD", total=D("1160"))
    r = f.resumen(_construir([d], [pago("U1", importe="500"), pago("U1", importe="80", uuid_pago="REP2", parcialidad=2)]), "2026-09", {})

    c = r["trasladado"]["origenes"]["credito"]
    assert (c["pagos"], c["cfdi"]) == (2, 1)


# ── detalle ──────────────────────────────────────────────────────────────────

def test_detalle_de_contado_lista_cada_cfdi_con_sus_bases():
    eventos = _construir([doc("U1"), doc("U2", fecha_emision=date(2026, 9, 2)), doc("U3", fecha_emision=date(2026, 8, 2))])

    det = f.detalle(eventos, "2026-09", "trasladado", "contado", {})

    assert [r["uuid"] for r in det["items"]] == ["U2", "U1"]               # por fecha de efecto
    assert det["total"] == 2
    r = det["items"][1]
    assert r["bases"]["16"] == 1000.0 and r["iva"]["16"] == 160.0 and r["iva_total"] == 160.0
    assert r["contraparte_rfc"] == OTRO and r["motivo"] is None and r["fecha_emision"] == "2026-09-10"


def test_detalle_de_credito_trae_fecha_de_pago_y_uuid_del_rep():
    d = doc("U1", metodo_pago="PPD", total=D("1160"))
    det = f.detalle(_construir([d], [pago("U1")]), "2026-09", "trasladado", "credito", {})

    r = det["items"][0]
    assert (r["fecha_pago"], r["uuid_pago"], r["parcialidad"]) == ("2026-09-25", "REP1", 1)
    assert r["fecha_emision"] == "2026-09-10"


def test_detalle_de_no_considerados_trae_el_motivo():
    det = f.detalle(_construir([recibido("R1", uso_cfdi="S01"), recibido("R2")]), "2026-09", "acreditable", "no_considerados", {})

    assert [(r["uuid"], r["motivo"]) for r in det["items"]] == [("R1", "uso_no_deducible")]


def test_detalle_trae_el_ajuste_vigente():
    aj = {("U1", "trasladado"): {"accion": "excluir", "periodo_destino": None, "motivo": "duplicado"}}
    det = f.detalle(_construir([doc("U1")]), "2026-09", "trasladado", "no_considerados", aj)

    assert det["items"][0]["ajuste"] == {"accion": "excluir", "periodo_destino": None, "motivo": "duplicado"}
    assert det["items"][0]["motivo"] == "manual"


def test_detalle_de_reasignados():
    aj = {("U1", "trasladado"): {"accion": "reasignar", "periodo_destino": "2026-10", "motivo": "x"}}
    det = f.detalle(_construir([doc("U1")]), "2026-09", "trasladado", "reasignados", aj)

    assert det["items"][0]["uuid"] == "U1" and det["items"][0]["ajuste"]["periodo_destino"] == "2026-10"


def test_detalle_pagina():
    docs = [doc(f"U{i:02d}", fecha_emision=date(2026, 9, i)) for i in range(1, 8)]
    det = f.detalle(_construir(docs), "2026-09", "trasladado", "contado", {}, pagina=2, por_pagina=3)

    assert det["total"] == 7 and (det["pagina"], det["por_pagina"]) == (2, 3)
    assert [r["uuid"] for r in det["items"]] == ["U04", "U05", "U06"]


def test_detalle_rechaza_origen_o_direccion_invalidos():
    with pytest.raises(ValueError):
        f.detalle([], "2026-09", "trasladado", "inventado", {})
    with pytest.raises(ValueError):
        f.detalle([], "2026-09", "otra", "contado", {})
    with pytest.raises(ValueError):
        f.detalle([], "2026-09", "trasladado", "contado", {}, por_pagina=0)


def test_un_pago_solo_aplica_a_ingresos_ppd():
    assert f.evento_de_pago(pago("U1"), doc("U1", metodo_pago="PUE"), RFC) is None             # PUE ya causó en su emisión
    assert f.evento_de_pago(pago("N1"), doc("N1", tipo_comprobante="E", metodo_pago="PPD"), RFC) is None


# ── Correcciones de la revisión fiscal ───────────────────────────────────────

def test_moneda_extranjera_sin_tipo_de_cambio_no_se_convierte_a_uno():
    for tc in (None, D("0")):
        e = f.eventos_de_documento(doc(moneda="USD", tipo_cambio=tc), RFC)[0]

        assert "sin_tipo_cambio" in e["marcas"] and e["iva_total"] == D("0")
        assert f.motivo_exclusion(e) == "sin_tipo_cambio"


def test_xxx_sin_tipo_de_cambio_cuenta_como_pesos():
    e = f.eventos_de_documento(doc(moneda="XXX", tipo_cambio=None), RFC)[0]

    assert "sin_tipo_cambio" not in e["marcas"] and e["iva_total"] == D("160")


def test_una_nota_de_credito_recibida_no_se_excluye_por_efectivo_ni_por_uso():
    for kw in ({"forma_pago": "01", "total": D("5000")}, {"uso_cfdi": "S01"}):
        e = f.eventos_de_documento(recibido("R9", tipo_comprobante="E", **kw), RFC)[0]

        assert e["origen"] == "notas_credito" and f.motivo_exclusion(e) is None


def test_el_efectivo_de_un_ppd_se_mide_con_lo_pagado_no_con_el_total_del_documento():
    d = recibido("R1", metodo_pago="PPD", forma_pago="01", total=D("9000"))

    chico = f.evento_de_pago(pago("R1", importe="1500", impuestos_dr=[tras("0.16", 1000, 160)]), d, RFC)
    grande = f.evento_de_pago(pago("R1", importe="2500", impuestos_dr=[tras("0.16", 1000, 160)]), d, RFC)

    assert f.motivo_exclusion(chico) is None
    assert f.motivo_exclusion(grande) == "efectivo"


def test_autofactura_ppd_genera_el_cobro_en_ambas_direcciones():
    d = doc("U1", metodo_pago="PPD", total=D("1160"), rfc_receptor=RFC)

    evs = f.eventos_de_pago(pago(), d, RFC)

    assert sorted(e["direccion"] for e in evs) == ["acreditable", "trasladado"]


def test_iva_de_pago_es_la_funcion_aislada_que_decide_el_iva_de_un_cobro():
    d = doc(metodo_pago="PPD", total=D("1160"))

    desg, iva_total, marcas = f.iva_de_pago(pago(), d)

    assert iva_total == D("80") and desg["bases"]["16"] == D("500") and marcas == set()


def test_pago_de_un_documento_con_total_en_cero_se_marca_y_no_suma():
    d = doc(metodo_pago="PPD", total=D("0"))
    e = f.evento_de_pago(pago(version_pago="1.0", impuestos_dr=[]), d, RFC)

    assert "sin_proporcion" in e["marcas"] and f.motivo_exclusion(e) == "sin_proporcion"


def test_la_retencion_de_un_cfdi_no_acreditable_por_efectivo_o_uso_igual_se_entera():
    ret = imp("retencion", "002", "Tasa", "0.106667", 250, "26.67")
    docs = [
        recibido("R1", impuestos=[tras("0.16", 250, 40), ret], iva_trasladado=D("40")),                                   # considerado
        recibido("R2", forma_pago="01", total=D("5000"), impuestos=[tras("0.16", 250, 40), ret], iva_trasladado=D("40")),  # efectivo
        recibido("R3", uso_cfdi="S01", impuestos=[tras("0.16", 250, 40), ret], iva_trasladado=D("40")),                    # uso
        recibido("R4", impuestos=[tras("0.16", 250, 40), ret], iva_trasladado=D("40")),                                    # excluido a mano
    ]
    aj = {("R4", "acreditable"): {"accion": "excluir", "periodo_destino": None, "motivo": "duplicado"}}

    r = f.resumen(_construir(docs), "2026-09", aj)

    assert r["acreditable"]["total"]["iva"]["total"] == D("40.00")        # solo R1 es acreditable
    assert r["retenciones_a_enterar"] == D("80.01")                       # R1 + R2 + R3; R4 salió por decisión del contador


def test_el_total_suma_los_valores_redondeados_de_cada_origen():
    chico = [tras("0.16", "0.0375", "0.006")]
    contado = doc("U1", impuestos=chico, iva_trasladado=D("0.006"))
    credito = doc("U2", metodo_pago="PPD", total=D("1160"))
    r = f.resumen(_construir([contado, credito], [pago("U2", impuestos_dr=chico)]), "2026-09", {})

    t = r["trasladado"]
    assert t["origenes"]["contado"]["iva"]["total"] == D("0.01") and t["origenes"]["credito"]["iva"]["total"] == D("0.01")
    assert t["total"]["iva"]["total"] == D("0.02")                         # no 0.01 por redondear 0.012 una sola vez


def test_el_redondeo_es_medio_hacia_arriba():
    e = f.eventos_de_documento(doc("U1", impuestos=[tras("0.16", "0.78125", "0.125")], iva_trasladado=D("0.125")), RFC)[0]
    r = f.resumen([e], "2026-09", {})

    assert r["trasladado"]["total"]["iva"]["total"] == D("0.13")           # al par daría 0.12


def test_aviso_de_forma_de_pago_del_rep_en_acreditable_a_credito():
    d = recibido("R1", metodo_pago="PPD", total=D("1160"))
    r = f.resumen(_construir([d], [pago("R1")]), "2026-09", {})

    assert "forma_pago_rep" in {a["codigo"] for a in r["advertencias"]}


# ── Segunda revisión fiscal (I-1 a I-3 y cifras exactas) ─────────────────────

def _rel(metodo_pago="PUE", forma_pago="03", uso_cfdi="G03", total="11600", moneda="MXN", tipo_cambio="1"):
    return {"metodo_pago": metodo_pago, "forma_pago": forma_pago, "uso_cfdi": uso_cfdi,
            "total": total, "moneda": moneda, "tipo_cambio": tipo_cambio}


def test_doc_en_usd_con_pago_sin_moneda_dr_no_se_suma_como_pesos():
    d = doc("U1", metodo_pago="PPD", moneda="USD", tipo_cambio=D("20"), total=D("1160"),
            impuestos=[tras("0.16", 1000, 160)], iva_trasladado=D("160"))
    p = pago("U1", importe="1160", moneda_dr=None, equivalencia_dr=None, impuestos_dr=[tras("0.16", 1000, 160)])

    e = f.evento_de_pago(p, d, RFC)

    assert "sin_equivalencia" in e["marcas"] and e["iva_total"] == D("0")           # no 160 como si fueran pesos


def test_doc_en_mxn_con_pago_sin_moneda_dr_si_se_suma():
    p = pago("U1", moneda_dr=None, equivalencia_dr=None)

    e = f.evento_de_pago(p, doc("U1", metodo_pago="PPD", total=D("1160")), RFC)

    assert "sin_equivalencia" not in e["marcas"] and e["iva_total"] == D("80")


def _anticipo_trasladado(b_metodo):
    """A (anticipo, enero) + B (factura final) + C (aplicación, marzo). B PUE o PPD."""
    A = doc("A1", es_anticipo_sat=True, fecha_emision=date(2026, 1, 10), impuestos=[tras("0.16", 100000, 16000)],
            iva_trasladado=D("16000"), subtotal=D("100000"), total=D("116000"))
    B = doc("B1", metodo_pago=b_metodo, fecha_emision=date(2026, 3, 10), impuestos=[tras("0.16", 1000000, 160000)],
            iva_trasladado=D("160000"), subtotal=D("1000000"), total=D("1160000"))
    C = doc("C1", tipo_comprobante="E", forma_pago="30", fecha_emision=date(2026, 3, 10),
            impuestos=[tras("0.16", 100000, 16000)], iva_trasladado=D("16000"), subtotal=D("100000"), total=D("116000"),
            relacionados_info=[_rel(metodo_pago=b_metodo, total="1160000")])
    return A, B, C


def test_anticipo_con_factura_final_pue_da_16000_en_enero_y_144000_en_marzo():
    A, B, C = _anticipo_trasladado("PUE")
    ev = _construir([A, B, C])

    enero, marzo = f.resumen(ev, "2026-01", {}), f.resumen(ev, "2026-03", {})

    assert enero["trasladado"]["total"]["iva"]["total"] == D("16000.00")
    assert marzo["trasladado"]["total"]["iva"]["total"] == D("144000.00")


def test_anticipo_con_factura_final_ppd_no_resta_dos_veces_la_aplicacion():
    A, B, C = _anticipo_trasladado("PPD")
    rep = pago("B1", importe="1044000", fecha=date(2026, 3, 20), impuestos_dr=[tras("0.16", 900000, 144000)])    # el remanente
    ev = _construir([A, B, C], [rep])

    enero, marzo = f.resumen(ev, "2026-01", {}), f.resumen(ev, "2026-03", {})

    assert enero["trasladado"]["total"]["iva"]["total"] == D("16000.00")
    assert marzo["trasladado"]["total"]["iva"]["total"] == D("144000.00")                  # y no 128,000
    total = enero["trasladado"]["total"]["iva"]["total"] + marzo["trasladado"]["total"]["iva"]["total"]
    assert total == D("160000.00")                                                            # A + remanente de B = B
    motivos = [r["motivo"] for r in f.detalle(ev, "2026-03", "trasladado", "no_considerados", {})["items"]]
    assert motivos == ["aplicado_en_rep"]


def test_anticipo_recibido_tambien_netea_del_lado_acreditable():
    A = recibido("A1", es_anticipo_sat=True, fecha_emision=date(2026, 1, 10), impuestos=[tras("0.16", 100000, 16000)],
                 iva_trasladado=D("16000"), subtotal=D("100000"), total=D("116000"))
    B = recibido("B1", fecha_emision=date(2026, 3, 10), impuestos=[tras("0.16", 1000000, 160000)],
                 iva_trasladado=D("160000"), subtotal=D("1000000"), total=D("1160000"))
    C = recibido("C1", tipo_comprobante="E", forma_pago="30", fecha_emision=date(2026, 3, 10),
                 impuestos=[tras("0.16", 100000, 16000)], iva_trasladado=D("16000"), subtotal=D("100000"), total=D("116000"),
                 relacionados_info=[_rel(total="1160000")])
    ev = _construir([A, B, C])

    assert f.resumen(ev, "2026-01", {})["acreditable"]["total"]["iva"]["total"] == D("16000.00")
    assert f.resumen(ev, "2026-03", {})["acreditable"]["total"]["iva"]["total"] == D("144000.00")


def test_moneda_extranjera_1000_usd_con_160_de_iva_a_tc_20_son_3200_pesos():
    e = f.eventos_de_documento(doc(moneda="USD", tipo_cambio=D("20"), subtotal=D("1000"), total=D("1160"),
                                   impuestos=[tras("0.16", 1000, 160)], iva_trasladado=D("160")), RFC)[0]

    assert e["iva_total"] == D("3200") and e["bases"]["16"] == D("20000")


@pytest.mark.parametrize("original", [
    _rel(forma_pago="01", total="11600"),                    # compra en efectivo: nunca se acreditó
    _rel(uso_cfdi="S01"),
    _rel(forma_pago="01", total="1000", moneda="USD", tipo_cambio="20"),     # 20,000 pesos en efectivo
])
def test_nota_de_credito_recibida_hereda_la_exclusion_del_original(original):
    nc = recibido("NC1", tipo_comprobante="E", impuestos=[tras("0.16", 1000, 160)], iva_trasladado=D("160"),
                  relacionados_info=[original])
    e = f.eventos_de_documento(nc, RFC)[0]

    assert "original_no_acreditable" in e["marcas"] and f.motivo_exclusion(e) == "original_no_acreditable"
    assert f.resumen([e], "2026-09", {})["acreditable"]["total"]["iva"]["total"] == D("0.00")


def test_nota_de_credito_recibida_de_un_original_acreditable_si_resta():
    nc = recibido("NC1", tipo_comprobante="E", impuestos=[tras("0.16", 1000, 160)], iva_trasladado=D("160"),
                  relacionados_info=[_rel(forma_pago="03", total="11600")])

    e = f.eventos_de_documento(nc, RFC)[0]

    assert f.motivo_exclusion(e) is None


def test_la_herencia_de_la_exclusion_solo_aplica_al_acreditable():
    nc = doc("NC1", tipo_comprobante="E", relacionados_info=[_rel(forma_pago="01", total="11600")])

    e = f.eventos_de_documento(nc, RFC)[0]

    assert f.motivo_exclusion(e) is None
