"""IVA acreditable por contraparte (insumo de la DIOT, F6.2). Sin DB."""
from datetime import date
from decimal import Decimal

from backend import iva_flujo as f
from backend.tests.test_iva_flujo import D, PROV, RFC, doc, imp, pago, recibido, tras

OTRO_PROV = "OTR010101BBB"


def eventos(*docs, pagos=()):
    ev = [e for d in docs for e in f.eventos_de_documento(d, RFC)]
    por_uuid = {f.llave(d["uuid"]): d for d in docs}
    for p in pagos:
        ev += f.eventos_de_pago(p, por_uuid[f.llave(p["cfdi_uuid"])], RFC)
    return ev


def terceros(*docs, factor=D("1"), ajustes=None, operacion_de=None, pagos=(), periodo="2026-09"):
    return f.por_contraparte(eventos(*docs, pagos=pagos), periodo, ajustes or {}, factor, operacion_de)


def test_agrupa_por_tercero_con_valor_de_actos_e_iva_por_tasa():
    r = terceros(recibido("R1"), recibido("R2"), recibido("R3", rfc_emisor=OTRO_PROV, nombre_emisor="OTRO",
                                                           impuestos=[tras("0.08", 500, 40)], subtotal=D("500"), iva_trasladado=D("40")))

    assert [t["contraparte_rfc"] for t in r] == [OTRO_PROV, PROV] or [t["contraparte_rfc"] for t in r] == [PROV, OTRO_PROV]
    por = {t["contraparte_rfc"]: t for t in r}
    assert por[PROV]["cfdi"] == 2 and por[PROV]["actos"]["16"] == D("2000.00") and por[PROV]["iva_pagado"]["16"] == D("320.00")
    assert por[OTRO_PROV]["actos"]["8"] == D("500.00") and por[OTRO_PROV]["iva_pagado"]["8"] == D("40.00")


def test_la_suma_del_acreditable_por_tercero_es_el_acreditable_del_resumen():
    docs = [recibido("R1"), recibido("R2", rfc_emisor=OTRO_PROV, nombre_emisor="OTRO"),
            recibido("R3", forma_pago="01", total=D("5800"), subtotal=D("5000"), iva_trasladado=D("800"),
                     impuestos=[tras("0.16", 5000, 800)]),                              # efectivo > 2000: fuera
            recibido("R4", tipo_comprobante="E", subtotal=D("100"), iva_trasladado=D("16"), impuestos=[tras("0.16", 100, 16)])]
    ev = eventos(*docs)
    for factor in (D("1"), D("0.5")):
        resumen = f.resumen(ev, "2026-09", {}, factor)
        r = f.por_contraparte(ev, "2026-09", {}, factor)

        assert sum((t["iva_acreditable"] for t in r), D("0")) == resumen["acreditable"]["ajustado"]


def test_devoluciones_van_en_su_propia_columna_y_restan_del_neto():
    r = terceros(recibido("R1"), recibido("R2", tipo_comprobante="E", subtotal=D("100"), iva_trasladado=D("16"),
                                          impuestos=[tras("0.16", 100, 16)]))[0]

    assert r["devoluciones"] == {"base": D("100.00"), "iva": D("16.00")}
    assert r["iva_pagado"]["16"] == D("160.00") and r["iva_acreditable"] == D("144.00")


def test_no_objeto_y_exento_salen_en_los_actos():
    d = recibido("R1", impuestos=[tras("0.16", 1000, 160), imp("traslado", "002", "Exento", None, 200, 0)],
                 no_objeto=D("300"))
    r = terceros(d)[0]

    assert r["actos"]["exento"] == D("200.00") and r["actos"]["no_objeto"] == D("300.00")


def test_iva_no_acreditable_por_motivo_y_por_proporcion():
    r = terceros(recibido("R1"), recibido("R2", uso_cfdi="S01"), factor=D("0.75"))[0]

    assert r["iva_acreditable"] == D("120.00")
    no = r["iva_no_acreditable"]
    assert no["proporcion"] == D("40.00") and no["por_motivo"]["uso_no_deducible"] == {"cfdi": 1, "iva": D("160.00"), "base": D("1000.00")}
    assert no["total"] == D("200.00")


def test_cfdi_excluido_a_mano_o_reasignado_sigue_las_reglas_del_motor():
    ajustes = {("R1", "acreditable"): {"accion": "excluir", "periodo_destino": None, "motivo": "x"},
               ("R2", "acreditable"): {"accion": "reasignar", "periodo_destino": "2026-10", "motivo": "x"}}
    r = terceros(recibido("R1"), recibido("R2"), recibido("R3"), ajustes=ajustes)[0]

    assert r["iva_acreditable"] == D("160.00") and r["iva_no_acreditable"]["por_motivo"]["manual"]["cfdi"] == 1


def test_extranjeros_con_el_rfc_generico_salen_separados_por_nombre():
    r = terceros(recibido("R1", rfc_emisor=f.RFC_EXTRANJERO, nombre_emisor="ACME"),
                 recibido("R2", rfc_emisor=f.RFC_EXTRANJERO, nombre_emisor="GLOBEX"),
                 recibido("R3", rfc_emisor=f.RFC_EXTRANJERO, nombre_emisor="ACME"))

    assert sorted((t["contraparte"], t["cfdi"]) for t in r) == [("ACME", 2), ("GLOBEX", 1)]


def test_un_tercero_con_dos_operaciones_sale_en_dos_renglones():
    r = terceros(recibido("R1"), recibido("R2"), operacion_de=lambda ev: "06" if ev["uuid"] == "R2" else "85")

    assert sorted((t["tipo_operacion"], t["iva_acreditable"]) for t in r) == [("06", D("160.00")), ("85", D("160.00"))]


def test_cobros_a_credito_cuentan_en_su_tercero_y_las_ventas_no():
    r = terceros(recibido("R1", metodo_pago="PPD", fecha_emision=date(2026, 8, 1)), doc("V1"),
                 pagos=[pago("R1", "580")])

    assert len(r) == 1 and r[0]["iva_pagado"]["16"] == D("80.00") and r[0]["actos"]["16"] == D("500.00")
