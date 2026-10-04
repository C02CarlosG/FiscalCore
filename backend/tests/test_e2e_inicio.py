"""E2E del Inicio contra Postgres real: ingresos, gastos, serie de 12 meses e IVA anual,
y que el IVA de cada mes sea idéntico al de la cédula de IVA. Se salta sin DB."""
import pytest

from backend.tests.conftest import db_disponible, headers_usuario_e2e

RFC = "INI010101E2E"
OTRO = "XAXX010101000"
PROV = "PRO010101AAA"
EMAIL = "e2e-inicio@test.local"
EMAIL_AJENO = "e2e-inicio-ajeno@test.local"

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


def _uuid(n: int) -> str:
    return f"4F4A{n:04d}-0000-4000-8000-000000000000"


def _cfdi(db, empresa_id, n, **kw):
    v = dict(
        uuid=_uuid(n), tipo_comprobante="I", serie="A", folio=str(n),
        rfc_emisor=RFC, nombre_emisor="Empresa Inicio", rfc_receptor=OTRO, nombre_receptor="CLIENTE",
        fecha_emision="2026-09-10 10:00:00", subtotal="1000", descuento="0", iva_trasladado="160",
        iva_retenido="0", isr_retenido="0", total="1160", estado="vigente", metodo_pago="PUE",
        forma_pago="03", uso_cfdi="G03", moneda="MXN", tipo_cambio="1", monto_cobrado="0",
        cfdi_relacionados="[]", es_anticipo_sat=False,
    )
    v.update(kw)
    fila = db.execute(
        f"INSERT INTO cfdi (empresa_id, {', '.join(v)}) VALUES (%s, {', '.join(['%s'] * len(v))}) RETURNING id",
        (empresa_id, *v.values()), returning=True)
    return str(fila["id"])


def _recibido(db, empresa_id, n, **kw):
    base = dict(rfc_emisor=PROV, nombre_emisor="PROVEEDOR", rfc_receptor=RFC, nombre_receptor="Empresa Inicio")
    base.update(kw)
    return _cfdi(db, empresa_id, n, **base)


def _limpiar(db):
    db.execute("DELETE FROM empresas WHERE rfc = %s", (RFC,))
    db.execute("DELETE FROM cfdi WHERE uuid LIKE '4F4A%%'")
    db.execute("DELETE FROM usuarios WHERE email IN (%s, %s)", (EMAIL, EMAIL_AJENO))


def _sembrar(db, empresa_id):
    # Septiembre 2026 — emitidos
    _cfdi(db, empresa_id, 1)                                              # 1000
    _cfdi(db, empresa_id, 2, subtotal="2000", descuento="500", iva_trasladado="240", total="1740")  # base 1500
    _cfdi(db, empresa_id, 3, tipo_comprobante="E", subtotal="300", iva_trasladado="48", total="348")  # NC -300
    _cfdi(db, empresa_id, 4, moneda="USD", tipo_cambio="20", subtotal="10", iva_trasladado="1.6", total="11.6")  # 200 MXN
    _cfdi(db, empresa_id, 5, estado="cancelado", subtotal="9999", total="11598")   # no cuenta
    _cfdi(db, empresa_id, 6, es_anticipo_sat=True, subtotal="7777", total="9021")  # no cuenta
    _cfdi(db, empresa_id, 7, tipo_comprobante="T", subtotal="5555", iva_trasladado="0", total="5555")  # no es ingreso
    _cfdi(db, empresa_id, 8, tipo_comprobante="N", rfc_receptor="EMP010101AAA", subtotal="800", descuento="100",
          iva_trasladado="0", total="700", metodo_pago=None, forma_pago=None, uso_cfdi="CN01")  # nómina: percepciones 800
    # Septiembre 2026 — recibidos
    _recibido(db, empresa_id, 10, subtotal="400", iva_trasladado="64", total="464")
    _recibido(db, empresa_id, 11, tipo_comprobante="E", subtotal="50", iva_trasladado="8", total="58")
    # Anticipo: A (anticipo, 2000) + B (factura final 5000, relacionada con A) + C (egreso de aplicación, forma 30, 2000)
    _cfdi(db, empresa_id, 40, es_anticipo_sat=True, fecha_emision="2026-09-02 10:00:00", subtotal="2000", total="2320")
    _cfdi(db, empresa_id, 41, fecha_emision="2026-09-12 10:00:00", subtotal="5000", iva_trasladado="800", total="5800")
    _cfdi(db, empresa_id, 42, tipo_comprobante="E", forma_pago="30", fecha_emision="2026-09-12 10:05:00",
          subtotal="2000", iva_trasladado="320", total="2320")
    # Fronteras del mes
    _cfdi(db, empresa_id, 43, fecha_emision="2026-09-30 23:59:59", subtotal="11", total="12.76")
    _cfdi(db, empresa_id, 44, fecha_emision="2026-10-01 00:00:00", subtotal="13", total="15.08")
    # Otros meses
    _cfdi(db, empresa_id, 20, fecha_emision="2026-03-05 09:00:00", subtotal="700", iva_trasladado="112", total="812")
    _cfdi(db, empresa_id, 21, fecha_emision="2025-11-05 09:00:00", subtotal="250", iva_trasladado="40", total="290")
    _cfdi(db, empresa_id, 22, fecha_emision="2025-02-05 09:00:00", subtotal="9000", total="10440")   # fuera de la ventana
    _cfdi(db, empresa_id, 23, fecha_emision="2026-10-05 09:00:00", subtotal="4000", total="4640")    # posterior al periodo
    _recibido(db, empresa_id, 24, fecha_emision="2026-03-15 09:00:00", subtotal="100", iva_trasladado="16", total="116")
    # PPD con pago en septiembre
    ppd = _cfdi(db, empresa_id, 30, fecha_emision="2026-08-20 09:00:00", metodo_pago="PPD", forma_pago="99",
                subtotal="1000", iva_trasladado="160", total="1160")
    rep = _cfdi(db, empresa_id, 31, tipo_comprobante="P", subtotal="0", iva_trasladado="0", total="0",
                metodo_pago=None, forma_pago=None, uso_cfdi="CP01", moneda="XXX")
    pago = db.execute(
        "INSERT INTO pagos_cfdi (empresa_id, cfdi_id, uuid_cfdi_pago, fecha_pago, monto)"
        " VALUES (%s, %s, %s, '2026-09-25 12:00:00', 580) RETURNING id", (empresa_id, rep, _uuid(31)), returning=True)
    db.execute(
        "INSERT INTO pagos_relaciones (pago_id, cfdi_uuid, parcialidad, importe_pagado, saldo_anterior, saldo_restante)"
        " VALUES (%s, %s, 1, 580, 1160, 580)", (str(pago["id"]), _uuid(30)))
    return ppd


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
        r = client.post("/api/v1/mis-empresas", headers=headers, json={"rfc": RFC, "razon_social": "Empresa Inicio"})
        assert r.status_code == 201, r.text
        empresa_id = r.json()["empresa_id"]
        _sembrar(db, empresa_id)
        yield db, client, headers, empresa_id
    finally:
        _limpiar(db)


def _get(entorno, ruta, **params):
    _db, client, headers, empresa_id = entorno
    r = client.get(f"/api/v1/empresas/{empresa_id}/inicio/{ruta}", headers=headers, params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_ingresos_del_periodo(entorno):
    d = _get(entorno, "resumen", periodo="2026-09")["ingresos"]["periodo"]

    # 1000 + 1500 (2000 − 500 de descuento) + 200 (10 USD × 20); la PPD de agosto es de agosto
    # 1000 + 1500 + 200 + 5000 (factura B del anticipo) + 11 (30 de septiembre 23:59); el 1 de octubre no entra
    assert d["facturado"] == 7711.0
    assert d["notas_credito"] == 300.0       # el egreso de aplicación de anticipo (forma de pago 30) NO es nota de crédito
    assert d["neto"] == 7411.0
    assert d["cfdi"] == 6                    # 5 ingresos + 1 nota de crédito; cancelado, anticipo, C y T no cuentan


def test_gastos_del_periodo_y_nomina_aparte(entorno):
    g = _get(entorno, "resumen", periodo="2026-09")["gastos"]["periodo"]

    assert (g["facturado"], g["notas_credito"], g["neto"], g["cfdi"]) == (400.0, 50.0, 350.0, 2)
    assert g["nomina"] == 800.0              # percepciones (subtotal), no el neto pagado de 700


def test_acumulado_del_ejercicio(entorno):
    d = _get(entorno, "resumen", periodo="2026-09")

    # marzo 700 + agosto 1000 (PPD emitido en agosto, es facturado) + septiembre 7411; octubre no entra
    assert d["ingresos"]["acumulado"]["neto"] == 700.0 + 1000.0 + 7411.0
    assert d["gastos"]["acumulado"]["neto"] == 100.0 + 350.0


def test_serie_de_12_meses(entorno):
    meses = _get(entorno, "resumen", periodo="2026-09")["meses"]

    assert [m["periodo"] for m in meses][0] == "2025-10" and meses[-1]["periodo"] == "2026-09" and len(meses) == 12
    por = {m["periodo"]: m for m in meses}
    assert por["2025-11"]["ingresos"]["neto"] == 250.0      # ejercicio anterior, sí está en la ventana
    assert por["2026-08"]["ingresos"]["neto"] == 1000.0
    assert por["2026-09"]["ingresos"]["neto"] == 7411.0
    assert por["2026-09"]["gastos"]["neto"] == 350.0
    assert por["2026-01"]["ingresos"]["neto"] == 0.0        # mes vacío presente en cero
    assert "2025-02" not in por                              # fuera de la ventana


def test_periodo_sin_datos_devuelve_ceros(entorno):
    d = _get(entorno, "resumen", periodo="2024-05")

    assert d["ingresos"]["periodo"]["neto"] == 0.0 and d["ingresos"]["acumulado"]["neto"] == 0.0
    assert len(d["meses"]) == 12


def test_iva_anual_coincide_con_la_cedula_de_cada_mes(entorno):
    _db, client, headers, empresa_id = entorno
    anual = _get(entorno, "iva-anual", ejercicio=2026)

    assert len(anual["meses"]) == 12
    for mes in anual["meses"]:
        r = client.get(f"/api/v1/empresas/{empresa_id}/cedula-iva/{mes['periodo']}", headers=headers)
        assert r.status_code == 200, r.text
        cedula = r.json()
        assert mes["trasladado"]["total"] == cedula["trasladado"]["total"], mes["periodo"]
        assert mes["trasladado"]["pue"] == cedula["trasladado"]["pue"]["iva"], mes["periodo"]
        assert mes["trasladado"]["ppd"] == cedula["trasladado"]["ppd"]["iva"], mes["periodo"]
        assert mes["acreditable"]["bruto"] == cedula["acreditable"]["bruto"], mes["periodo"]
        assert mes["resultado"]["iva_por_pagar"] == cedula["resultado"]["iva_por_pagar"], mes["periodo"]


def test_iva_anual_septiembre_y_totales(entorno):
    anual = _get(entorno, "iva-anual", ejercicio=2026)
    sep = anual["meses"][8]

    # PUE: 160 + 240 + 1.6 (USD sin convertir: F5) ; PPD: 160 × 580/1160 = 80 ; NC: 48
    assert sep["trasladado"]["ppd"] == 80.0
    # La cédula (y por tanto esta tabla) resta TODO egreso emitido, también el de aplicación de
    # anticipo (forma de pago 30, IVA 320): 48 + 320. F5 lo corrige en ambas; ver el spec, "Limitaciones".
    assert sep["trasladado"]["notas_credito"] == 48.0 + 320.0
    assert sep["acreditable"]["bruto"] == 64.0 - 8.0
    assert sep["resultado"]["saldo_a_cargo"] > 0 and sep["resultado"]["saldo_a_favor"] == 0.0
    assert anual["totales"]["trasladado"] == round(sum(m["trasladado"]["total"] for m in anual["meses"]), 2)
    assert anual["iva_retenido_incluido"] is False


def test_iva_anual_vacia_los_meses_posteriores_al_periodo(entorno):
    anual = _get(entorno, "iva-anual", ejercicio=2026, periodo="2026-03")

    assert anual["meses"][2]["trasladado"]["total"] == 112.0     # marzo
    assert anual["meses"][8]["trasladado"]["total"] == 0.0       # septiembre es posterior


def test_otra_empresa_recibe_403(entorno):
    db, client, _h, empresa_id = entorno
    db.execute("DELETE FROM usuarios WHERE email = %s", (EMAIL_AJENO,))
    ajeno = headers_usuario_e2e(db, EMAIL_AJENO)

    for ruta, params in (("resumen", {"periodo": "2026-09"}), ("iva-anual", {"ejercicio": 2026})):
        r = client.get(f"/api/v1/empresas/{empresa_id}/inicio/{ruta}", headers=ajeno, params=params)
        assert r.status_code == 403


def test_periodo_de_diciembre_lee_hasta_enero_del_ejercicio_siguiente_sin_incluirlo(entorno):
    d = _get(entorno, "resumen", periodo="2026-12")

    assert [m["periodo"] for m in d["meses"]][0] == "2026-01" and d["meses"][-1]["periodo"] == "2026-12"
    # marzo 700 + agosto 1000 + septiembre 7411 + octubre (4000 + 13); diciembre está vacío
    assert d["ingresos"]["acumulado"]["neto"] == 700.0 + 1000.0 + 7411.0 + 4013.0
    assert d["ingresos"]["periodo"]["neto"] == 0.0
