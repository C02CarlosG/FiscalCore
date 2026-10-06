"""ISR base flujo (F7.1): ingresos al cobro, deducciones al pago, nómina y retenciones. Sin DB."""
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


def todos(*docs, pagos=(), nominas=()):
    eventos = [e for d in docs for e in f.eventos_de_documento(d, RFC)]
    por_uuid = {f.llave(d["uuid"]): d for d in docs}
    for p in pagos:
        eventos += f.eventos_de_pago(p, por_uuid[f.llave(p["cfdi_uuid"])], RFC)
    eventos += [e for n in nominas if (e := f.evento_de_nomina(n))]
    return eventos


def res(*docs, periodo="2026-09", ajustes=None, pct=f.PORCENTAJE_NOMINA_EXENTA, **kw):
    return f.resumen(todos(*docs, **kw), periodo, ajustes or {}, pct)


# ── ingresos ─────────────────────────────────────────────────────────────────

def test_contado_es_ingreso_en_su_emision_con_base_sin_iva_y_descuento():
    r = res(doc("U1", subtotal=D("2000"), descuento=D("500")))

    assert r["mes"]["ingresos"]["contado"] == D("1500.00") and r["mes"]["ingresos"]["total"] == D("1500.00")


def test_ppd_es_ingreso_solo_en_la_proporcion_cobrada_y_en_la_fecha_del_pago():
    d = doc("U1", metodo_pago="PPD", fecha_emision=date(2026, 8, 20))
    r = res(d, pagos=[pago("U1", "580")])

    assert r["mes"]["ingresos"]["credito"] == D("500.00") and r["mes"]["ingresos"]["contado"] == D("0.00")
    assert res(d, periodo="2026-08", pagos=[pago("U1", "580")])["mes"]["ingresos"]["total"] == D("0.00")


def test_rep_cancelado_o_documento_cancelado_no_cuentan():
    d = doc("U1", metodo_pago="PPD")
    assert res(d, pagos=[pago("U1", pago_estado="cancelado")])["mes"]["ingresos"]["total"] == D("0.00")
    assert res(doc("U2", estado="cancelado"))["mes"]["ingresos"]["total"] == D("0.00")


def test_pago_en_dolares_se_lleva_a_pesos_con_el_tipo_de_cambio_del_pago():
    d = doc("U1", metodo_pago="PPD", moneda="USD", tipo_cambio=D("19"), subtotal=D("100"), total=D("116"))
    r = res(d, pagos=[pago("U1", "116", moneda_dr="USD", equivalencia_dr=D("1"), pago_moneda="USD", pago_tipo_cambio=D("20"))])

    assert r["mes"]["ingresos"]["credito"] == D("2000.00")        # 100 USD × 20 del día del pago


def test_pago_en_otra_moneda_sin_equivalencia_no_suma_y_se_advierte():
    d = doc("U1", metodo_pago="PPD", moneda="USD", tipo_cambio=D("19"))
    r = res(d, pagos=[pago("U1", moneda_dr="USD", equivalencia_dr=None, pago_moneda="MXN")])

    assert r["mes"]["ingresos"]["total"] == D("0.00")
    assert {a["codigo"] for a in r["advertencias"]} >= {"sin_equivalencia"}


def test_egreso_emitido_resta_de_los_ingresos():
    r = res(doc("U1"), doc("U2", tipo_comprobante="E", subtotal=D("300")))

    assert r["mes"]["ingresos"]["devoluciones"] == D("300.00") and r["mes"]["ingresos"]["total"] == D("700.00")


def test_anticipo_mas_factura_menos_aplicacion_deja_la_factura():
    a = doc("A", es_anticipo_sat=True, subtotal=D("2000"), fecha_emision=date(2026, 8, 5))
    b = doc("B", subtotal=D("5000"))
    c = doc("C", tipo_comprobante="E", forma_pago="30", subtotal=D("2000"))

    assert res(a, b, c)["acumulado"]["ingresos"]["total"] == D("5000.00")


def test_aplicacion_de_anticipo_a_una_factura_ppd_no_resta_porque_el_rep_ya_trae_el_remanente():
    c = doc("C", tipo_comprobante="E", forma_pago="30", subtotal=D("2000"),
            relacionados_info=[{"metodo_pago": "PPD", "forma_pago": "99", "total": "5800", "moneda": "MXN"}])
    r = res(c)

    assert r["mes"]["ingresos"]["devoluciones"] == D("0.00")
    assert r["mes"]["ingresos"]["no_considerados"]["por_motivo"]["aplicado_en_rep"]["cfdi"] == 1


def test_retencion_de_isr_a_favor_en_contado_y_proporcional_en_ppd():
    contado = doc("U1", isr_retenido=D("100"))
    credito = doc("U2", metodo_pago="PPD", isr_retenido=D("100"))
    r = res(contado, credito, pagos=[pago("U2", "580")])

    assert r["mes"]["ingresos"]["retenciones_a_favor"] == D("150.00")


# ── deducciones ──────────────────────────────────────────────────────────────

def test_compra_de_contado_y_pago_con_rep_deducen_y_las_notas_recibidas_restan():
    c = recibido("R1")
    p = recibido("R2", metodo_pago="PPD", fecha_emision=date(2026, 8, 1))
    nc = recibido("R3", tipo_comprobante="E", subtotal=D("100"))
    r = res(c, p, nc, pagos=[pago("R2", "580")])

    ded = r["mes"]["deducciones"]
    assert (ded["contado"], ded["credito"], ded["devoluciones_recibidas"], ded["total"]) == \
           (D("1000.00"), D("500.00"), D("100.00"), D("1400.00"))


@pytest.mark.parametrize("extra,motivo", [
    ({"forma_pago": "01", "total": D("2500")}, "efectivo"),
    ({"uso_cfdi": "S01"}, "uso_no_deducible"),
])
def test_no_deducibles_automaticos_salen_con_su_motivo(extra, motivo):
    r = res(recibido("R1", **extra))["mes"]["deducciones"]

    assert r["total"] == D("0.00") and r["no_considerados"]["por_motivo"][motivo]["cfdi"] == 1


def test_efectivo_hasta_el_umbral_si_deduce():
    assert res(recibido("R1", forma_pago="01", total=D("2000")))["mes"]["deducciones"]["total"] == D("1000.00")


def test_inversiones_se_identifican_y_no_suman():
    r = res(recibido("R1", uso_cfdi="I01"), recibido("R2"))["mes"]["deducciones"]

    assert r["total"] == D("1000.00") and r["inversiones"] == {"cfdi": 1, "base": D("1000.00")}


def test_nota_de_credito_recibida_de_una_compra_no_deducible_no_resta():
    nc = recibido("R3", tipo_comprobante="E", subtotal=D("100"),
                  relacionados_info=[{"metodo_pago": "PUE", "forma_pago": "01", "total": "5800", "moneda": "MXN"}])

    assert res(recibido("R1"), nc)["mes"]["deducciones"]["total"] == D("1000.00")


def test_retencion_a_proveedores_es_a_cargo():
    r = res(recibido("R1", isr_retenido=D("100")))["mes"]["retenciones_a_cargo"]

    assert r == {"trabajadores": D("0.00"), "proveedores": D("100.00"), "total": D("100.00")}


# ── nómina ───────────────────────────────────────────────────────────────────

def test_nomina_gravado_al_100_y_exento_al_porcentaje():
    d = res(nominas=[nomina()])["mes"]["deducciones"]["nomina"]

    assert (d["gravado"], d["exento"], d["exento_deducible"], d["deducible"]) == (D("800.00"), D("200.00"), D("94.00"), D("894.00"))


def test_porcentaje_configurable():
    d = res(nominas=[nomina()], pct=D("0.53"))["mes"]["deducciones"]

    assert d["nomina"]["exento_deducible"] == D("106.00") and d["total"] == D("906.00")


def test_ptu_y_viaticos_quedan_fuera_de_la_base():
    n = nomina(percepciones=[{"tipo": "001", "gravado": D("800"), "exento": D("0")},
                             {"tipo": "003", "gravado": D("0"), "exento": D("300")},
                             {"tipo": "050", "gravado": D("0"), "exento": D("50")}])
    d = res(nominas=[n])["mes"]["deducciones"]["nomina"]

    assert d["deducible"] == D("800.00") and d["excluido_ptu"] == D("300.00") and d["excluido_viaticos"] == D("50.00")


def test_isr_retenido_a_trabajadores_es_a_cargo_y_la_nomina_cancelada_no_cuenta():
    r = res(nominas=[nomina(retenido="100"), nomina("N2", estado="cancelado", retenido="999")])["mes"]

    assert r["retenciones_a_cargo"]["trabajadores"] == D("100.00") and r["deducciones"]["nomina"]["gravado"] == D("800.00")


# ── ajustes, acumulado y detalle ─────────────────────────────────────────────

def test_no_considerar_saca_el_cfdi_por_lado():
    ajustes = {("U1", "ingreso"): {"accion": "excluir", "motivo": "x"}}
    r = res(doc("U1"), ajustes=ajustes)["mes"]["ingresos"]

    assert r["total"] == D("0.00") and r["no_considerados"]["por_motivo"]["manual"] == {"cfdi": 1, "base": D("1000.00")}


def test_el_ajuste_de_un_lado_no_afecta_al_otro():
    autofactura = doc("U1", rfc_receptor=RFC)
    ajustes = {("U1", "ingreso"): {"accion": "excluir", "motivo": "x"}}
    r = res(autofactura, ajustes=ajustes)["mes"]

    assert r["ingresos"]["total"] == D("0.00") and r["deducciones"]["total"] == D("1000.00")


def test_acumulado_suma_los_meses_del_ejercicio_hasta_el_periodo():
    r = res(doc("U1", fecha_emision=date(2026, 1, 5)), doc("U2"), doc("U3", fecha_emision=date(2025, 12, 31)),
            doc("U4", fecha_emision=date(2026, 10, 1)))

    assert r["mes"]["ingresos"]["total"] == D("1000.00") and r["acumulado"]["ingresos"]["total"] == D("2000.00")


def test_utilidad_fiscal_estimada():
    r = res(doc("U1"), recibido("R1", subtotal=D("300")), nominas=[nomina()])["mes"]

    assert r["utilidad_fiscal_estimada"] == D("1000.00") - D("300.00") - D("894.00")


def test_detalle_trae_los_cfdi_de_cada_cifra_con_sus_marcas():
    d1, d2 = doc("U1"), doc("U2", metodo_pago="PPD", fecha_emision=date(2026, 8, 1))
    eventos = todos(d1, d2, pagos=[pago("U2", "580")])

    contado = f.detalle(eventos, "2026-09", "ingreso", "contado", {})
    credito = f.detalle(eventos, "2026-09", "ingreso", "credito", {})

    assert [i["uuid"] for i in contado["items"]] == ["U1"] and contado["total"] == 1
    assert credito["items"][0]["uuid_pago"] == "REP1" and credito["items"][0]["base"] == 500.0


def test_detalle_valida_entradas():
    with pytest.raises(ValueError):
        f.detalle([], "2026-09", "otro", "contado", {})
    with pytest.raises(ValueError):
        f.detalle([], "2026-09", "ingreso", "contado", {}, pagina=0)


def test_el_redondeo_es_medio_hacia_arriba():
    assert res(doc("U1", subtotal=D("0.125")))["mes"]["ingresos"]["total"] == D("0.13")


@pytest.mark.parametrize("texto,codigo,modulo", [
    ("612", "612", "flujo"), ("612 - Personas Físicas con Actividades Empresariales", "612", "flujo"),
    ("606", "606", "flujo"), ("601 General de Ley Personas Morales", "601", "coeficiente"),
    ("626", "626", "no_soportado"), ("6120", None, "no_soportado"), ("", None, "no_soportado"), (None, None, "no_soportado"),
])
def test_aplicabilidad_por_regimen(texto, codigo, modulo):
    a = f.aplicabilidad(texto)
    assert (a["codigo"], a["modulo"]) == (codigo, modulo)
    assert bool(a["avisos"]) == (codigo == "606")


# ── revisión del #39 ─────────────────────────────────────────────────────────

def test_b1_usd_con_rep_en_pesos_y_equivalencia_invertida_se_excluye_con_estimado():
    d = recibido("R1", moneda="USD", tipo_cambio=D("20"), subtotal=D("1000"), total=D("1160"), forma_pago="03",
                 metodo_pago="PPD", isr_retenido=D("100"))
    p = pago("R1", "23200", pago_moneda="MXN", pago_tipo_cambio=D("1"), moneda_dr="USD", equivalencia_dr=D("20"),
             pago_monto=D("23200"), suma_equivalente="1160", n_relaciones=1)
    r = res(d, pagos=[p])["mes"]["deducciones"]

    assert r["credito"] == D("0.00") and r["total"] == D("0.00")


def test_b2_pago_en_efectivo_mayor_a_2000_via_rep_no_se_deduce():
    d = recibido("R1", metodo_pago="PPD", forma_pago="99", subtotal=D("5000"), total=D("5800"))
    p = pago("R1", "5800", forma_pago_p="01")
    r = res(d, pagos=[p])["mes"]["deducciones"]

    assert r["total"] == D("0.00")


def test_b3_devolucion_resta_la_retencion_a_favor():
    ing = doc("U1", isr_retenido=D("1000"))
    nc = doc("U2", tipo_comprobante="E", subtotal=D("100"), total=D("116"), isr_retenido=D("100"),
             relacionados_info=[{"metodo_pago": "PUE", "forma_pago": "03", "total": "1160", "moneda": "MXN"}])

    assert res(ing, nc)["mes"]["ingresos"]["retenciones_a_favor"] == D("900.00")


def test_b4_efectivo_no_deducible_conserva_la_retencion_a_cargo():
    r = res(recibido("R1", forma_pago="01", subtotal=D("5000"), total=D("5800"), isr_retenido=D("500")))["mes"]

    assert r["deducciones"]["total"] == D("0.00") and r["retenciones_a_cargo"]["proveedores"] == D("500.00")


# ── menores de la re-revisión del #39 ────────────────────────────────────────

def test_efectivo_hasta_el_umbral_solo_marca_pagos_de_2000_o_menos():
    chico = res(recibido("R1", forma_pago="01", subtotal=D("1000"), total=D("1160")))
    grande = res(recibido("R2", forma_pago="01", subtotal=D("5000"), total=D("5800")))

    assert "efectivo_hasta_umbral" in [a["codigo"] for a in chico["advertencias"]]
    assert "efectivo_hasta_umbral" not in [a["codigo"] for a in grande["advertencias"]]


def test_en_pagos_con_rep_la_marca_de_efectivo_sigue_la_forma_de_pago_p():
    d = recibido("R1", metodo_pago="PPD", forma_pago="99", subtotal=D("1000"), total=D("1160"))
    con = res(d, pagos=[pago("R1", "1160", forma_pago_p="01")])
    sin = res(d, pagos=[pago("R1", "1160", forma_pago_p="03")])

    assert "efectivo_hasta_umbral" in [a["codigo"] for a in con["advertencias"]]
    assert "efectivo_hasta_umbral" not in [a["codigo"] for a in sin["advertencias"]]


def test_nomina_no_considerada_conserva_su_retencion_a_cargo():
    n = nomina("N1", retenido="100")
    r = res(nominas=[n], ajustes={("N1", "deduccion"): {"accion": "excluir", "motivo": "x"}})["mes"]

    assert r["deducciones"]["nomina"]["deducible"] == D("0.00")
    assert r["retenciones_a_cargo"]["trabajadores"] == D("100.00") and r["retenciones_a_cargo"]["total"] == D("100.00")


def test_el_total_de_ingresos_es_la_suma_de_las_partes_redondeadas():
    r = res(doc("U1", subtotal=D("0.125")), doc("U2", subtotal=D("0.125")))["mes"]["ingresos"]

    assert r["contado"] == D("0.25") and r["total"] == r["contado"] + r["credito"] - r["devoluciones"]
