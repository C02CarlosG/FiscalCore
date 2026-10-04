"""Composición de la DIOT por flujo (F6.2). Sin DB."""
from decimal import Decimal

from backend import diot, iva_flujo
from backend.tests.test_iva_flujo import D, PROV, RFC, recibido
from backend.tests.test_iva_flujo_contraparte import eventos


def prov(rfc=PROV, nombre="PROVEEDOR", **kw):
    base = {"id": f"id-{rfc}-{nombre}", "rfc": rfc, "nombre": nombre, "tipo_tercero": "04", "tipo_operacion": "85",
            "pais": None, "id_fiscal": None}
    base.update(kw)
    return base


def componer(*docs, proveedores=(), overrides=None, operacion_de=None, factor=D("1")):
    terceros = iva_flujo.por_contraparte(eventos(*docs), "2026-09", {}, factor, operacion_de)
    return diot.componer(terceros, diot.indice_de_catalogo(list(proveedores)), overrides or {})


def test_toma_la_clasificacion_del_catalogo():
    r = componer(recibido("R1"), proveedores=[prov()])

    t = r["terceros"][0]
    assert (t["tipo_tercero"], t["tipo_operacion"], t["advertencias"]) == ("04", "85", [])
    assert t["proveedor_id"] == f"id-{PROV}-PROVEEDOR"


def test_el_override_del_periodo_manda_sobre_el_catalogo():
    p = prov()
    r = componer(recibido("R1"), proveedores=[p], overrides={p["id"]: {"tipo_operacion": "06"}})

    assert (r["terceros"][0]["tipo_tercero"], r["terceros"][0]["tipo_operacion"]) == ("04", "06")


def test_la_operacion_por_cfdi_manda_sobre_todo():
    p = prov()
    r = componer(recibido("R1"), recibido("R2"), proveedores=[p], overrides={p["id"]: {"tipo_operacion": "06"}},
                 operacion_de=lambda ev: "03" if ev["uuid"] == "R2" else "06")

    assert sorted(t["tipo_operacion"] for t in r["terceros"]) == ["03", "06"]


def test_advierte_lo_que_falta_para_declarar():
    r = componer(recibido("R1"), recibido("R2", rfc_emisor=iva_flujo.RFC_EXTRANJERO, nombre_emisor="ACME"),
                 recibido("R3", rfc_emisor="no-es-rfc", nombre_emisor="RARO"),
                 proveedores=[prov(), prov(iva_flujo.RFC_EXTRANJERO, "ACME", tipo_tercero="05")])
    por = {t["contraparte"]: t for t in r["terceros"]}

    assert por["ACME"]["advertencias"] == ["extranjero_pendiente"]
    assert por["RARO"]["advertencias"] == ["sin_catalogo", "rfc_invalido", "sin_tipo_tercero", "sin_tipo_operacion"]
    assert r["totales"]["con_advertencias"] == 2


def test_operacion_87_solo_con_tercero_global():
    r = componer(recibido("R1"), proveedores=[prov(tipo_operacion="87")])

    assert r["terceros"][0]["advertencias"] == ["operacion_incompatible"]


def test_extranjeros_del_mismo_rfc_se_ligan_a_su_propio_renglon_del_catalogo():
    a, b = prov(iva_flujo.RFC_EXTRANJERO, "ACME", tipo_tercero="05", pais="USA", id_fiscal="1"), \
        prov(iva_flujo.RFC_EXTRANJERO, "GLOBEX", tipo_tercero="05")
    r = componer(recibido("R1", rfc_emisor=iva_flujo.RFC_EXTRANJERO, nombre_emisor="ACME"),
                 recibido("R2", rfc_emisor=iva_flujo.RFC_EXTRANJERO, nombre_emisor="GLOBEX"), proveedores=[a, b])
    por = {t["contraparte"]: t for t in r["terceros"]}

    assert por["ACME"]["proveedor_id"] == a["id"] and por["ACME"]["advertencias"] == []
    assert por["GLOBEX"]["proveedor_id"] == b["id"] and por["GLOBEX"]["advertencias"] == ["extranjero_pendiente"]


def test_totales_suman_los_terceros():
    r = componer(recibido("R1"), recibido("R2", rfc_emisor="OTR010101BBB", nombre_emisor="OTRO"),
                 recibido("R3", tipo_comprobante="E", subtotal=D("100"), iva_trasladado=D("16"),
                          impuestos=[iva_flujo_tras()]), proveedores=[prov(), prov("OTR010101BBB", "OTRO")], factor=D("0.5"))

    t = r["totales"]
    assert (t["terceros"], t["cfdi"]) == (2, 3)
    assert t["iva_pagado"] == D("320.00") and t["devoluciones_iva"] == D("16.00")
    assert t["iva_acreditable"] == D("152.00") and t["iva_no_acreditable"] == D("152.00")


def iva_flujo_tras():
    from backend.tests.test_iva_flujo import tras
    return tras("0.16", 100, 16)
