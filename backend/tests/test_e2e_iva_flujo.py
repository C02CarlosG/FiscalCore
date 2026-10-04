"""E2E del IVA base flujo contra Postgres real: tasas, crédito con REP 2.0 y 1.0, notas de
crédito, anticipo, moneda extranjera, exclusiones, ajustes con auditoría y aislamiento."""
import json
from decimal import Decimal

import pytest

from backend.tests.conftest import db_disponible, headers_usuario_e2e

RFC = "IVF010101E2E"
OTRO = "XAXX010101000"
PROV = "PRO010101AAA"
EMAIL = "e2e-iva-flujo@test.local"
EMAIL_AJENO = "e2e-iva-flujo-ajeno@test.local"

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


def _uuid(n: int) -> str:
    return f"5F5A{n:04d}-0000-4000-8000-000000000000"


def _cfdi(db, empresa_id, n, impuestos=(), **kw):
    v = dict(
        uuid=_uuid(n), tipo_comprobante="I", serie="A", folio=str(n), rfc_emisor=RFC, nombre_emisor="Empresa IVA",
        rfc_receptor=OTRO, nombre_receptor="CLIENTE", fecha_emision="2026-09-10 10:00:00", subtotal="1000",
        descuento="0", iva_trasladado="160", iva_retenido="0", isr_retenido="0", total="1160", estado="vigente",
        metodo_pago="PUE", forma_pago="03", uso_cfdi="G03", moneda="MXN", tipo_cambio="1", monto_cobrado="0",
        cfdi_relacionados="[]", es_anticipo_sat=False,
    )
    v.update(kw)
    fila = db.execute(
        f"INSERT INTO cfdi (empresa_id, {', '.join(v)}) VALUES (%s, {', '.join(['%s'] * len(v))}) RETURNING id",
        (empresa_id, *v.values()), returning=True)
    cfdi_id = str(fila["id"])
    for ambito, impuesto, factor, tasa, base, importe in impuestos:
        db.execute(
            "INSERT INTO cfdi_impuestos (cfdi_id, ambito, impuesto, tipo_factor, tasa_o_cuota, base, importe)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s)", (cfdi_id, ambito, impuesto, factor, tasa, base, importe))
    return cfdi_id


def _t(tasa, base, importe):
    return ("traslado", "002", "Tasa", tasa, base, importe)


def _recibido(db, empresa_id, n, impuestos=(), **kw):
    base = dict(rfc_emisor=PROV, nombre_emisor="PROVEEDOR", rfc_receptor=RFC, nombre_receptor="Empresa IVA")
    base.update(kw)
    return _cfdi(db, empresa_id, n, impuestos, **base)


def _rep(db, empresa_id, n, documentos, fecha="2026-09-25 12:00:00", version="2.0", estado="vigente",
         moneda="MXN", tipo_cambio="1", rfc_emisor=RFC, rfc_receptor=OTRO):
    """REP con un pago a ``documentos`` = [(uuid_docto, importe, [(tasa, base, importe)], moneda_dr, equivalencia)]."""
    rep = _cfdi(db, empresa_id, n, (), tipo_comprobante="P", subtotal="0", iva_trasladado="0", total="0",
                metodo_pago=None, forma_pago=None, uso_cfdi="CP01", moneda="XXX", estado=estado,
                rfc_emisor=rfc_emisor, rfc_receptor=rfc_receptor)
    pago = db.execute(
        "INSERT INTO pagos_cfdi (empresa_id, cfdi_id, uuid_cfdi_pago, fecha_pago, monto, moneda, tipo_cambio, version_pago)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
        (empresa_id, rep, _uuid(n), fecha, sum(Decimal(str(d[1])) for d in documentos), moneda, tipo_cambio, version), returning=True)
    for i, (uuid_docto, importe, impuestos, moneda_dr, equivalencia) in enumerate(documentos, start=1):
        rel = db.execute(
            "INSERT INTO pagos_relaciones (pago_id, cfdi_uuid, parcialidad, importe_pagado, saldo_anterior, saldo_restante,"
            " moneda_dr, equivalencia_dr) VALUES (%s, %s, %s, %s, %s, 0, %s, %s) RETURNING id",
            (str(pago["id"]), uuid_docto, i, importe, importe, moneda_dr, equivalencia), returning=True)
        for tasa, base, imp in impuestos:
            db.execute(
                "INSERT INTO pagos_relaciones_impuestos (relacion_id, ambito, impuesto, tipo_factor, tasa_o_cuota, base, importe)"
                " VALUES (%s, 'traslado', '002', 'Tasa', %s, %s, %s)", (str(rel["id"]), tasa, base, imp))


def _limpiar(db):
    db.execute("DELETE FROM empresas WHERE rfc IN (%s, 'AJE010101E2E')", (RFC,))
    db.execute("DELETE FROM cfdi WHERE uuid LIKE '5F5A%%'")
    db.execute("DELETE FROM usuarios WHERE email IN (%s, %s)", (EMAIL, EMAIL_AJENO))


def _sembrar(db, e):
    # ── Trasladado, contado (septiembre): 16 %, 8 %, 0 % y exento en un mismo CFDI ──
    _cfdi(db, e, 1, [_t("0.16", 1000, 160), _t("0.08", 500, 40), _t("0.00", 300, 0),
                     ("traslado", "002", "Exento", None, 200, 0)], iva_trasladado="200", subtotal="2000", total="2200")
    _cfdi(db, e, 2, [_t("0.16", 400, 64)], iva_trasladado="64", subtotal="400", total="464",
          iva_retenido="42.67")                                                       # con retención (el cliente retiene)
    db.execute("INSERT INTO cfdi_impuestos (cfdi_id, ambito, impuesto, tipo_factor, tasa_o_cuota, base, importe)"
               " SELECT id, 'retencion', '002', 'Tasa', 0.106667, 400, 42.67 FROM cfdi WHERE uuid = %s", (_uuid(2),))
    # nota de crédito, anticipo + factura + aplicación (A + B − C = B)
    _cfdi(db, e, 3, [_t("0.16", 300, 48)], tipo_comprobante="E", iva_trasladado="48", subtotal="300", total="348")
    _cfdi(db, e, 40, [_t("0.16", 2000, 320)], es_anticipo_sat=True, fecha_emision="2026-08-05 10:00:00",
          iva_trasladado="320", subtotal="2000", total="2320")
    _cfdi(db, e, 41, [_t("0.16", 5000, 800)], iva_trasladado="800", subtotal="5000", total="5800")
    _cfdi(db, e, 42, [_t("0.16", 2000, 320)], tipo_comprobante="E", forma_pago="30", iva_trasladado="320", subtotal="2000", total="2320")
    # cancelado y sin desglose guardado
    _cfdi(db, e, 5, [_t("0.16", 9000, 1440)], estado="cancelado", iva_trasladado="1440", subtotal="9000", total="10440")
    _cfdi(db, e, 6, [], iva_trasladado="16", subtotal="100", total="116")             # CFDI sin detalle reprocesado
    # USD
    _cfdi(db, e, 7, [_t("0.16", 10, "1.6")], moneda="USD", tipo_cambio="20", iva_trasladado="1.6", subtotal="10", total="11.6")

    # ── Crédito: PPD cobrado con REP 2.0 (dos pagos, meses distintos), REP 1.0, USD sin equivalencia ──
    _cfdi(db, e, 10, [_t("0.16", 1000, 160)], metodo_pago="PPD", forma_pago="99", fecha_emision="2026-08-20 09:00:00")
    _rep(db, e, 11, [(_uuid(10), 580, [("0.16", 500, 80)], "MXN", 1)], fecha="2026-09-25 12:00:00")
    _rep(db, e, 12, [(_uuid(10), 580, [("0.16", 500, 80)], "MXN", 1)], fecha="2026-10-05 12:00:00")
    _cfdi(db, e, 13, [_t("0.16", 1000, 160)], metodo_pago="PPD", forma_pago="99", fecha_emision="2026-08-21 09:00:00")
    _rep(db, e, 14, [(_uuid(13), 580, [], "MXN", 1)], fecha="2026-09-26 12:00:00", version="1.0")     # sin ImpuestosDR
    _cfdi(db, e, 15, [_t("0.16", 10, "1.6")], metodo_pago="PPD", forma_pago="99", moneda="USD", tipo_cambio="20",
          fecha_emision="2026-08-22 09:00:00", iva_trasladado="1.6", subtotal="10", total="11.6")
    _rep(db, e, 16, [(_uuid(15), "11.6", [("0.16", 10, "1.6")], "USD", None)], fecha="2026-09-27 12:00:00")   # sin equivalencia
    _rep(db, e, 17, [(_uuid(10), 100, [("0.16", 100, 16)], "MXN", 1)], fecha="2026-09-28 12:00:00", estado="cancelado")

    # ── Acreditable ──
    _recibido(db, e, 20, [_t("0.16", 250, 40)], iva_trasladado="40", subtotal="250", total="290")
    _recibido(db, e, 21, [_t("0.16", 100, 16)], uso_cfdi="S01", iva_trasladado="16", subtotal="100", total="116")
    _recibido(db, e, 22, [_t("0.16", 5000, 800)], forma_pago="01", iva_trasladado="800", subtotal="5000", total="5800")
    _recibido(db, e, 23, [_t("0.16", 1000, 160)], metodo_pago="PPD", forma_pago="99", fecha_emision="2026-08-10 09:00:00")
    _rep(db, e, 24, [(_uuid(23), 580, [("0.16", 500, 80)], "MXN", 1)], rfc_emisor=PROV, rfc_receptor=RFC)
    # un REP que paga DOS documentos PPD en septiembre; el UUID de uno viene en minúsculas en la relación
    _cfdi(db, e, 50, [_t("0.16", 250, 40)], metodo_pago="PPD", forma_pago="99", fecha_emision="2026-08-12 09:00:00",
          iva_trasladado="40", subtotal="250", total="290")
    _cfdi(db, e, 51, [_t("0.16", 250, 40)], metodo_pago="PPD", forma_pago="99", fecha_emision="2026-08-13 09:00:00",
          iva_trasladado="40", subtotal="250", total="290")
    _rep(db, e, 52, [(_uuid(50), 290, [("0.16", 250, 40)], "MXN", 1),
                     (_uuid(51).lower(), 290, [("0.16", 250, 40)], "MXN", 1)], fecha="2026-09-29 12:00:00")
    # recibido en efectivo con retención: no es acreditable, pero la retención se entera
    _recibido(db, e, 26, [_t("0.16", 250, 40)], forma_pago="01", iva_trasladado="40", subtotal="250", total="2900")
    db.execute("INSERT INTO cfdi_impuestos (cfdi_id, ambito, impuesto, tipo_factor, tasa_o_cuota, base, importe)"
               " SELECT id, 'retencion', '002', 'Tasa', 0.106667, 250, 26.67 FROM cfdi WHERE uuid = %s", (_uuid(26),))
    # retención que la empresa hace a su proveedor
    _recibido(db, e, 25, [_t("0.16", 250, 40)], iva_trasladado="40", subtotal="250", total="263.33")
    db.execute("INSERT INTO cfdi_impuestos (cfdi_id, ambito, impuesto, tipo_factor, tasa_o_cuota, base, importe)"
               " SELECT id, 'retencion', '002', 'Tasa', 0.106667, 250, 26.67 FROM cfdi WHERE uuid = %s", (_uuid(25),))


def _sembrar_anticipo_con_factura_ppd(db, e):
    """Anticipo en enero (100,000 + 16,000), factura final PPD y su REP en febrero con el remanente
    (144,000), y el egreso que aplica el anticipo (forma de pago 30) relacionado a la factura."""
    _cfdi(db, e, 60, [_t("0.16", 100000, 16000)], es_anticipo_sat=True, fecha_emision="2026-01-10 10:00:00",
          iva_trasladado="16000", subtotal="100000", total="116000")
    _cfdi(db, e, 61, [_t("0.16", 1000000, 160000)], metodo_pago="PPD", forma_pago="99", fecha_emision="2026-01-20 10:00:00",
          iva_trasladado="160000", subtotal="1000000", total="1160000")
    _rep(db, e, 62, [(_uuid(61), 1044000, [("0.16", 900000, 144000)], "MXN", 1)], fecha="2026-02-15 12:00:00")
    _cfdi(db, e, 63, [_t("0.16", 100000, 16000)], tipo_comprobante="E", forma_pago="30", fecha_emision="2026-02-15 12:05:00",
          iva_trasladado="16000", subtotal="100000", total="116000",
          cfdi_relacionados=json.dumps([{"tipo_relacion": "07", "uuids": [_uuid(61)]}]))


def _sembrar_nota_de_credito_de_una_compra_en_efectivo(db, e):
    """Compra en efectivo (no acreditable) y su nota de crédito: la nota no debe restar acreditable."""
    _recibido(db, e, 70, [_t("0.16", 10000, 1600)], forma_pago="01", fecha_emision="2026-03-05 10:00:00",
              iva_trasladado="1600", subtotal="10000", total="11600")
    _recibido(db, e, 71, [_t("0.16", 1000, 160)], tipo_comprobante="E", fecha_emision="2026-03-06 10:00:00",
              iva_trasladado="160", subtotal="1000", total="1160",
              cfdi_relacionados=json.dumps([{"tipo_relacion": "01", "uuids": [_uuid(70)]}]))


@pytest.fixture(scope="module")
def entorno():
    from fastapi.testclient import TestClient

    import backend.main_api as main
    from backend import db

    db.init_db()
    _limpiar(db)
    client = TestClient(main.app)
    try:
        headers = headers_usuario_e2e(db, EMAIL)
        r = client.post("/api/v1/mis-empresas", headers=headers, json={"rfc": RFC, "razon_social": "Empresa IVA"})
        assert r.status_code == 201, r.text
        empresa_id = r.json()["empresa_id"]
        _sembrar(db, empresa_id)
        _sembrar_anticipo_con_factura_ppd(db, empresa_id)
        _sembrar_nota_de_credito_de_una_compra_en_efectivo(db, empresa_id)
        yield db, client, headers, empresa_id
    finally:
        _limpiar(db)


@pytest.fixture(autouse=True)
def _sin_ajustes(entorno):
    entorno[0].execute("DELETE FROM iva_ajustes WHERE empresa_id = %s", (entorno[3],))
    yield


def _url(entorno, ruta):
    return f"/api/v1/empresas/{entorno[3]}/iva-flujo/{ruta}"


def _resumen(entorno, periodo="2026-09", **params):
    r = entorno[1].get(_url(entorno, periodo), headers=entorno[2], params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _detalle(entorno, periodo, direccion, origen, **params):
    r = entorno[1].get(_url(entorno, f"{periodo}/detalle"), headers=entorno[2],
                       params={"direccion": direccion, "origen": origen, **params})
    assert r.status_code == 200, r.text
    return r.json()


def test_contado_separa_las_tasas_y_suma_con_el_encabezado(entorno):
    c = _resumen(entorno)["trasladado"]["origenes"]["contado"]

    # CFDI 1 (16/8/0/exento) + 2 + 41 (factura B) + 6 (sin detalle: IVA del encabezado) + 7 (USD × 20) + 3 NC aparte + 40 anticipo es de agosto
    assert c["bases"]["16"] == 1000 + 400 + 5000 + 200
    assert c["bases"]["8"] == 500 and c["bases"]["0"] == 300 and c["bases"]["exento"] == 200
    assert c["iva"]["16"] == 160 + 64 + 800 + 32 and c["iva"]["8"] == 40
    assert c["iva"]["total"] == 160 + 40 + 64 + 800 + 16 + 32                       # + 16 del CFDI sin desglose
    assert c["cfdi"] == 5 and c["retenciones"] == 42.67


def test_credito_toma_solo_el_pago_del_mes_con_impuestos_dr(entorno):
    cred = _resumen(entorno)["trasladado"]["origenes"]["credito"]

    # REP 2.0 de septiembre (80) + REP 1.0 aproximado (160 × 580/1160 = 80) + un REP de dos documentos (40 + 40);
    # el de octubre y el cancelado no; el USD sin equivalencia no suma
    assert cred["iva"]["total"] == 240.0
    assert cred["pagos"] == 4 and cred["cfdi"] == 4
    octubre = _resumen(entorno, "2026-10")["trasladado"]["origenes"]["credito"]
    assert octubre["iva"]["total"] == 80.0 and octubre["pagos"] == 1


def test_detalle_de_credito_trae_fecha_de_pago_y_uuid_del_rep(entorno):
    items = _detalle(entorno, "2026-09", "trasladado", "credito")["items"]

    por = {i["uuid"]: i for i in items}
    assert por[_uuid(10)]["fecha_pago"] == "2026-09-25T12:00:00" and por[_uuid(10)]["uuid_pago"] == _uuid(11)
    assert por[_uuid(10)]["fecha_emision"] == "2026-08-20T09:00:00"
    assert "aproximado" not in por[_uuid(10)]["marcas"]
    assert {"aproximado", "pago_v1"} <= set(por[_uuid(13)]["marcas"])


def test_notas_de_credito_y_anticipo_neteados(entorno):
    sep = _resumen(entorno)["trasladado"]
    agosto = _resumen(entorno, "2026-08")["trasladado"]

    assert sep["origenes"]["notas_credito"]["iva"]["total"] == 48 + 320                # NC + aplicación del anticipo
    assert agosto["origenes"]["contado"]["iva"]["total"] == 320                        # el anticipo, cuando se cobró
    marcas = {i["uuid"]: i["marcas"] for i in _detalle(entorno, "2026-09", "trasladado", "notas_credito")["items"]}
    assert "aplicacion_anticipo" in marcas[_uuid(42)] and "aplicacion_anticipo" not in marcas[_uuid(3)]


def test_total_trasladado_y_resultado(entorno):
    r = _resumen(entorno)

    # contado 1112 + crédito 240 − notas 368 = 984; menos el acreditable (160) y la retención a favor (42.67)
    assert r["trasladado"]["total"]["iva"]["total"] == 984.0
    assert r["resultado"]["retenciones_a_favor"] == 42.67
    assert r["resultado"]["iva_por_pagar"] == 781.33
    assert (r["resultado"]["saldo_a_cargo"], r["resultado"]["saldo_a_favor"]) == (781.33, 0.0)


def test_un_rep_con_dos_documentos_y_uuid_en_minusculas_cuenta_los_dos(entorno):
    items = {i["uuid"]: i for i in _detalle(entorno, "2026-09", "trasladado", "credito")["items"]}

    assert items[_uuid(50)]["uuid_pago"] == _uuid(52) and items[_uuid(51)]["uuid_pago"] == _uuid(52)
    assert items[_uuid(50)]["iva_total"] == 40.0 and items[_uuid(51)]["iva_total"] == 40.0


def test_acreditable_excluye_efectivo_y_uso_no_deducible_y_los_lista(entorno):
    r = _resumen(entorno)["acreditable"]

    # 20 (40) + 25 (40) + REP 24 de septiembre (80); 21 (S01), 22 y 26 (efectivo) no
    assert r["total"]["iva"]["total"] == 160.0
    assert r["no_considerados"] == {"cfdi": 3, "iva": 856.0}
    motivos = {i["uuid"]: i["motivo"] for i in _detalle(entorno, "2026-09", "acreditable", "no_considerados")["items"]}
    assert motivos == {_uuid(21): "uso_no_deducible", _uuid(22): "efectivo", _uuid(26): "efectivo"}


def test_retencion_que_hace_la_empresa_no_reduce_el_acreditable_y_se_entera_aunque_no_sea_acreditable(entorno):
    r = _resumen(entorno)

    # 26.67 del CFDI 25 (acreditable) + 26.67 del CFDI 26 (pagado en efectivo: no acreditable, pero la retención se entera)
    assert r["retenciones_a_enterar"] == 53.34
    assert r["acreditable"]["ajustado"] == 160.0


def test_factor_de_prorrateo_ajusta_el_acreditable(entorno):
    r = _resumen(entorno, factor=0.5)

    assert r["acreditable"]["ajustado"] == 80.0 and r["factor_prorrateo"] == 0.5


def test_advertencias(entorno):
    codigos = {a["codigo"]: a["cfdi"] for a in _resumen(entorno)["advertencias"]}

    assert codigos["pago_v1"] == 1 and codigos["sin_equivalencia"] == 1 and codigos["sin_desglose"] == 1


def test_periodo_sin_movimiento_devuelve_ceros(entorno):
    r = _resumen(entorno, "2024-05")

    assert r["trasladado"]["total"]["iva"]["total"] == 0.0 and r["resultado"]["iva_por_pagar"] == 0.0
    assert r["advertencias"] == []


def test_excluir_un_cfdi_lo_saca_lo_audita_y_se_puede_deshacer(entorno):
    db, client, headers, empresa_id = entorno
    antes = _resumen(entorno)["trasladado"]["total"]["iva"]["total"]

    r = client.put(_url(entorno, "ajustes"), headers=headers,
                   json={"uuid": _uuid(41).lower(), "direccion": "trasladado", "accion": "excluir", "motivo": "factura duplicada"})
    assert r.status_code == 200, r.text
    despues = _resumen(entorno)["trasladado"]
    assert despues["total"]["iva"]["total"] == antes - 800
    # el CFDI excluido (800) y el cobro en USD sin equivalencia (0), que nunca suma
    assert despues["no_considerados"] == {"cfdi": 2, "iva": 800.0}
    fila = next(i for i in _detalle(entorno, "2026-09", "trasladado", "no_considerados")["items"] if i["uuid"] == _uuid(41))
    assert fila["motivo"] == "manual" and fila["ajuste"]["motivo"] == "factura duplicada"
    n = db.query_one("SELECT COUNT(*) AS n FROM auditoria WHERE accion = 'iva_ajuste' AND entidad_id = %s", (_uuid(41),))
    assert n["n"] >= 1

    d = client.delete(_url(entorno, f"ajustes/trasladado/{_uuid(41)}"), headers=headers)
    assert d.status_code == 204
    assert _resumen(entorno)["trasladado"]["total"]["iva"]["total"] == antes
    assert client.delete(_url(entorno, f"ajustes/trasladado/{_uuid(41)}"), headers=headers).status_code == 404
    retirado = db.query_one("SELECT COUNT(*) AS n FROM auditoria WHERE accion = 'iva_ajuste_retirado' AND entidad_id = %s", (_uuid(41),))
    assert retirado["n"] >= 1


def test_reasignar_mueve_el_efecto_al_periodo_destino(entorno):
    client, headers = entorno[1], entorno[2]
    r = client.put(_url(entorno, "ajustes"), headers=headers,
                   json={"uuid": _uuid(41), "direccion": "trasladado", "accion": "reasignar", "periodo_destino": "2026-10", "motivo": "se cobró en octubre"})
    assert r.status_code == 200, r.text

    sep = _resumen(entorno)["trasladado"]
    octubre = _resumen(entorno, "2026-10")["trasladado"]

    assert sep["reasignados"] == {"cfdi": 1, "iva": 800.0}
    assert octubre["origenes"]["contado"]["iva"]["total"] == 800.0
    assert _detalle(entorno, "2026-10", "trasladado", "contado")["items"][0]["uuid"] == _uuid(41)


def test_reasignar_un_ppd_mueve_todos_sus_cobros_al_destino(entorno):
    client, headers = entorno[1], entorno[2]
    client.put(_url(entorno, "ajustes"), headers=headers,
               json={"uuid": _uuid(10), "direccion": "trasladado", "accion": "reasignar", "periodo_destino": "2026-11", "motivo": "x"})

    nov = _resumen(entorno, "2026-11")["trasladado"]["origenes"]["credito"]

    assert nov["iva"]["total"] == 160.0 and nov["pagos"] == 2          # sus pagos de septiembre y octubre
    assert _resumen(entorno, "2026-10")["trasladado"]["origenes"]["credito"]["pagos"] == 0


def test_ajuste_de_un_cfdi_ajeno_o_de_otra_direccion_es_404(entorno):
    client, headers = entorno[1], entorno[2]

    assert client.put(_url(entorno, "ajustes"), headers=headers,
                      json={"uuid": _uuid(41), "direccion": "acreditable", "accion": "excluir", "motivo": "x"}).status_code == 404
    assert client.put(_url(entorno, "ajustes"), headers=headers,
                      json={"uuid": "no-existe", "direccion": "trasladado", "accion": "excluir", "motivo": "x"}).status_code == 404


def test_listar_ajustes(entorno):
    client, headers = entorno[1], entorno[2]
    client.put(_url(entorno, "ajustes"), headers=headers, json={"uuid": _uuid(2), "direccion": "trasladado", "accion": "excluir", "motivo": "x"})

    items = client.get(_url(entorno, "ajustes"), headers=headers).json()["items"]

    assert [(i["uuid"], i["accion"]) for i in items] == [(_uuid(2), "excluir")]


def test_otra_empresa_no_ve_ni_ajusta(entorno):
    db, client, _h, empresa_id = entorno
    db.execute("DELETE FROM usuarios WHERE email = %s", (EMAIL_AJENO,))
    ajeno = headers_usuario_e2e(db, EMAIL_AJENO)

    for metodo, ruta, kw in (
        ("get", "2026-09", {}), ("get", "2026-09/detalle?direccion=trasladado&origen=contado", {}),
        ("get", "ajustes", {}),
        ("put", "ajustes", {"json": {"uuid": _uuid(41), "direccion": "trasladado", "accion": "excluir", "motivo": "x"}}),
    ):
        r = getattr(client, metodo)(f"/api/v1/empresas/{empresa_id}/iva-flujo/{ruta}", headers=ajeno, **kw)
        assert r.status_code == 403, (metodo, ruta)


def test_el_detalle_pagina(entorno):
    d = _detalle(entorno, "2026-09", "trasladado", "contado", por_pagina=2, pagina=2)

    assert d["total"] == 5 and d["pagina"] == 2 and len(d["items"]) == 2


def test_anticipo_con_factura_final_ppd_no_descuenta_dos_veces(entorno):
    enero = _resumen(entorno, "2026-01")["trasladado"]
    febrero = _resumen(entorno, "2026-02")["trasladado"]

    assert enero["total"]["iva"]["total"] == 16000.0                          # el anticipo, cuando se cobró
    assert febrero["origenes"]["credito"]["iva"]["total"] == 144000.0         # el remanente de la factura, con ImpuestosDR
    assert febrero["total"]["iva"]["total"] == 144000.0                       # la aplicación (C) no resta otra vez
    assert enero["total"]["iva"]["total"] + febrero["total"]["iva"]["total"] == 160000.0
    motivos = {i["uuid"]: i["motivo"] for i in _detalle(entorno, "2026-02", "trasladado", "no_considerados")["items"]}
    assert motivos == {_uuid(63): "aplicado_en_rep"}


def test_nota_de_credito_de_una_compra_en_efectivo_no_resta_acreditable(entorno):
    r = _resumen(entorno, "2026-03")["acreditable"]

    assert r["total"]["iva"]["total"] == 0.0 and r["origenes"]["notas_credito"]["iva"]["total"] == 0.0
    motivos = {i["uuid"]: i["motivo"] for i in _detalle(entorno, "2026-03", "acreditable", "no_considerados")["items"]}
    assert motivos == {_uuid(70): "efectivo", _uuid(71): "original_no_acreditable"}


def test_si_la_auditoria_falla_el_ajuste_no_queda_guardado(entorno, monkeypatch):
    from fastapi.testclient import TestClient

    import backend.main_api as main
    from backend import iva_flujo_datos

    db, _client, headers, empresa_id = entorno

    def _falla(*a, **k):
        raise RuntimeError("auditoría caída")

    monkeypatch.setattr(iva_flujo_datos, "_auditar", _falla)
    sin_propagar = TestClient(main.app, raise_server_exceptions=False)

    r = sin_propagar.put(_url(entorno, "ajustes"), headers=headers,
                         json={"uuid": _uuid(41), "direccion": "trasladado", "accion": "excluir", "motivo": "x"})

    assert r.status_code == 500
    n = db.query_one("SELECT COUNT(*) AS n FROM iva_ajustes WHERE empresa_id = %s", (empresa_id,))
    assert n["n"] == 0                                           # el cambio se deshizo junto con la auditoría
