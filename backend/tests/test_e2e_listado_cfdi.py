"""E2E del listado de CFDI contra Postgres real: filtros, orden, paginación,
conteos por tipo y totales del periodo y del acumulado. Se salta sin DB."""
import json
from datetime import date

import pytest

from backend.tests.conftest import db_disponible, headers_usuario_e2e

RFC = "LST010101E2E"
OTRO = "XAXX010101000"
EMAIL = "e2e-listado-cfdi@test.local"
EMAIL_AJENO = "e2e-listado-ajeno@test.local"

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


def _uuid(n: int) -> str:
    return f"1F3A{n:04d}-0000-4000-8000-000000000000"


def _cfdi(db, empresa_id, n, **kw):
    v = dict(
        uuid=_uuid(n), tipo_comprobante="I", serie="A", folio=str(n),
        rfc_emisor=RFC, nombre_emisor="Emisora E2E", rfc_receptor=OTRO, nombre_receptor="CLIENTE",
        fecha_emision="2026-03-10", subtotal="100", descuento="0", iva_trasladado="16",
        iva_retenido="0", isr_retenido="0", total="116", estado="vigente", metodo_pago="PUE",
        forma_pago="03", uso_cfdi="G03", moneda="MXN", tipo_cambio="1", monto_cobrado="0",
        cfdi_relacionados="[]",
    )
    v.update(kw)
    fila = db.execute(
        f"INSERT INTO cfdi (empresa_id, {', '.join(v)}) VALUES (%s, {', '.join(['%s'] * len(v))}) RETURNING id",
        (empresa_id, *v.values()), returning=True,
    )
    return str(fila["id"])


def _limpiar(db):
    db.execute("DELETE FROM empresas WHERE rfc = %s", (RFC,))
    db.execute("DELETE FROM cfdi WHERE uuid LIKE '1F3A%%'")
    db.execute("DELETE FROM usuarios WHERE email IN (%s, %s)", (EMAIL, EMAIL_AJENO))


def _sembrar(db, empresa_id):
    for i in range(1, 36):
        _cfdi(db, empresa_id, i, fecha_emision=date(2026, 3, 1 + i % 28).isoformat(),
              subtotal=str(100 * i), iva_trasladado=str(16 * i), total=str(116 * i))
    dolares = _cfdi(db, empresa_id, 900, nombre_receptor="CLIENTE 50%_DOLARES", subtotal="10",
                    iva_trasladado="1.60", total="11.60", moneda="USD", tipo_cambio="20", forma_pago="99")
    db.execute(
        "INSERT INTO cfdi_impuestos (cfdi_id, ambito, impuesto, tipo_factor, tasa_o_cuota, base, importe)"
        " VALUES (%s, 'traslado', '003', 'Tasa', 0.08, 10, 5.00)", (dolares,))
    _cfdi(db, empresa_id, 901, estado="cancelado", subtotal="1000", iva_trasladado="160", total="1160")
    _cfdi(db, empresa_id, 902, metodo_pago="PPD", forma_pago="99", subtotal="1000", iva_trasladado="160",
          total="1160", monto_cobrado="1160")
    _cfdi(db, empresa_id, 903, metodo_pago="PPD", forma_pago="99", subtotal="2000", iva_trasladado="320",
          total="2320", monto_cobrado="500")
    _cfdi(db, empresa_id, 910, tipo_comprobante="E", subtotal="50", iva_trasladado="8", total="58")
    rep = _cfdi(db, empresa_id, 911, tipo_comprobante="P", subtotal="0", iva_trasladado="0", total="0",
                metodo_pago=None, forma_pago=None, uso_cfdi="CP01", moneda="XXX")
    _cfdi(db, empresa_id, 912, tipo_comprobante="N", subtotal="5000", iva_trasladado="0", total="4500",
          uso_cfdi="CN01")
    _cfdi(db, empresa_id, 920, rfc_emisor="PROV010101AAA", nombre_emisor="PROVEEDOR UNO", rfc_receptor=RFC,
          nombre_receptor="Emisora E2E", subtotal="300", iva_trasladado="48", total="348")
    _cfdi(db, empresa_id, 921, rfc_emisor="PROV010101AAA", nombre_emisor="PROVEEDOR UNO", rfc_receptor=RFC,
          nombre_receptor="Emisora E2E", subtotal="700", iva_trasladado="112", total="812")
    _cfdi(db, empresa_id, 950, fecha_emision="2026-02-15", subtotal="500", iva_trasladado="80", total="580")
    pago = db.execute(
        "INSERT INTO pagos_cfdi (empresa_id, cfdi_id, uuid_cfdi_pago, fecha_pago, monto)"
        " VALUES (%s, %s, %s, '2026-03-20', 1160) RETURNING id", (empresa_id, rep, _uuid(911)), returning=True)
    db.execute(
        "INSERT INTO pagos_relaciones (pago_id, cfdi_uuid, parcialidad, importe_pagado, saldo_anterior, saldo_restante)"
        " VALUES (%s, %s, 1, 1160, 1160, 0)", (str(pago["id"]), _uuid(902)))


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
        r = client.post("/api/v1/mis-empresas", headers=headers, json={"rfc": RFC, "razon_social": "Emisora E2E"})
        assert r.status_code == 201, r.text
        empresa_id = r.json()["empresa_id"]
        _sembrar(db, empresa_id)
        yield db, client, headers, empresa_id
    finally:
        _limpiar(db)


def _get(entorno, ruta="", **params):
    _db, client, headers, empresa_id = entorno
    base = {"direccion": "emitidos", "periodo": "2026-03"}
    base.update(params)
    r = client.get(f"/api/v1/empresas/{empresa_id}/cfdis{ruta}", headers=headers, params=base)
    assert r.status_code == 200, r.text
    return r.json()


def test_listado_pagina_en_el_servidor(entorno):
    primera = _get(entorno)
    segunda = _get(entorno, pagina=2)

    assert (primera["total"], primera["pagina"], primera["por_pagina"]) == (38, 1, 30)
    assert (len(primera["items"]), len(segunda["items"])) == (30, 8)
    assert not {i["uuid"] for i in primera["items"]} & {i["uuid"] for i in segunda["items"]}
    fechas = [i["fecha_emision"] for i in primera["items"] + segunda["items"]]
    assert fechas == sorted(fechas)


def test_orden_por_columna(entorno):
    datos = _get(entorno, orden="total", dir="desc")

    assert [i["total"] for i in datos["items"][:3]] == [4060.0, 3944.0, 3828.0]


def test_filtro_de_estado(entorno):
    assert _get(entorno, estado="cancelado")["total"] == 1
    assert _get(entorno, estado="todos")["total"] == 39


def test_filtro_de_metodo_y_de_pago(entorno):
    assert _get(entorno, metodo="PPD")["total"] == 2
    pendientes = _get(entorno, metodo="PPD", pago="pendientes")["items"]
    pagadas = _get(entorno, metodo="PPD", pago="pagadas")["items"]

    assert [(i["folio"], i["saldo"]) for i in pendientes] == [("903", 1820.0)]
    assert [(i["folio"], i["saldo"], i["pagos_relacionados"]) for i in pagadas] == [("902", 0.0, [_uuid(911)])]


def test_busqueda_trata_los_comodines_como_texto(entorno):
    assert [i["folio"] for i in _get(entorno, q="50%_DOL")["items"]] == ["900"]
    assert _get(entorno, q="%")["total"] == 1          # solo el que trae el signo, no todos
    assert _get(entorno, q=_uuid(7).lower())["total"] == 1


def test_moneda_extranjera_muestra_importe_original_y_en_pesos(entorno):
    item = _get(entorno, q="DOLARES")["items"][0]

    assert (item["total"], item["total_mxn"], item["subtotal_mxn"], item["traslado_iva_mxn"]) == (11.6, 232.0, 200.0, 32.0)
    assert (item["moneda"], item["tipo_cambio"], item["traslado_ieps"]) == ("USD", 20.0, 5.0)
    assert item["forma_pago_desc"] == "99 - Por definir"
    assert item["categoria"] == "venta"


def test_filtro_avanzado(entorno):
    filtros = json.dumps([{"campo": "total", "op": "mayor", "valor": 4000}])
    assert [i["folio"] for i in _get(entorno, filtros=filtros)["items"]] == ["35"]

    filtros = json.dumps([{"campo": "fecha_emision", "op": "entre", "valor": ["2026-03-02", "2026-03-03"]}])
    assert sorted(i["folio"] for i in _get(entorno, filtros=filtros)["items"]) == ["1", "2", "29", "30"]


def test_recibidos_muestran_al_emisor_como_contraparte(entorno):
    datos = _get(entorno, direccion="recibidos")

    assert datos["total"] == 2
    assert {(i["rfc_contraparte"], i["contraparte"], i["categoria"]) for i in datos["items"]} == {
        ("PROV010101AAA", "PROVEEDOR UNO", "compra")}


def test_resumen_conteos_por_tipo_y_totales_en_pesos(entorno):
    r = _get(entorno, "/resumen")

    assert r["conteos"] == {"I": 38, "E": 1, "T": 0, "N": 1, "P": 1}
    assert r["totales"]["periodo"] == {
        "conteo": 38, "retencion_iva": 0.0, "retencion_ieps": 0.0, "retencion_isr": 0.0,
        "traslado_iva": 10592.0, "traslado_ieps": 100.0, "traslado_isr": 0.0, "total_retenciones": 0.0,
        "subtotal": 66200.0, "descuento": 0.0, "neto": 66200.0, "total": 76792.0,
    }
    acumulado = r["totales"]["acumulado"]
    assert (acumulado["conteo"], acumulado["subtotal"], acumulado["traslado_iva"], acumulado["total"]) == (
        39, 66700.0, 10672.0, 77372.0)
    assert r["advertencias"] == []


def test_resumen_respeta_los_filtros(entorno):
    r = _get(entorno, "/resumen", metodo="PPD")

    assert r["conteos"] == {"I": 2, "E": 0, "T": 0, "N": 0, "P": 0}
    assert (r["totales"]["periodo"]["conteo"], r["totales"]["periodo"]["total"]) == (2, 3480.0)


def test_resumen_sin_cfdi_devuelve_nulos(entorno):
    r = _get(entorno, "/resumen", tipo="T")

    assert r["totales"]["periodo"] == {
        "conteo": 0, "retencion_iva": None, "retencion_ieps": None, "retencion_isr": None,
        "traslado_iva": None, "traslado_ieps": None, "traslado_isr": None, "total_retenciones": None,
        "subtotal": None, "descuento": None, "neto": None, "total": None,
    }
    assert r["totales"]["acumulado"]["conteo"] == 0


def test_advertencia_de_factura_con_anticipo_sin_egreso(entorno):
    db, _client, _headers, empresa_id = entorno
    relacion = json.dumps([{"tipo_relacion": "07", "uuids": [_uuid(1)]}])
    _cfdi(db, empresa_id, 960, fecha_emision="2026-04-10", cfdi_relacionados=relacion)

    r = _get(entorno, "/resumen", periodo="2026-04")
    assert [(a["tipo"], a["uuid_factura"]) for a in r["advertencias"]] == [("sin_egreso_anticipo", _uuid(960))]
    assert _get(entorno, periodo="2026-04")["items"][0]["categoria"] == "factura_con_anticipo"

    egreso = json.dumps([{"tipo_relacion": "07", "uuids": [_uuid(960)]}])
    _cfdi(db, empresa_id, 961, fecha_emision="2026-04-11", tipo_comprobante="E", forma_pago="30",
          cfdi_relacionados=egreso)
    assert _get(entorno, "/resumen", periodo="2026-04")["advertencias"] == []


def test_columnas_publica_el_catalogo_sin_sql(entorno):
    r = _get(entorno, "/columnas")

    assert r["encabezado"][0]["clave"] == "fecha_emision"
    assert all("sql" not in c for c in r["encabezado"] + r["concepto"])
    assert {c["grupo"] for c in r["concepto"]} == {"concepto"}


@pytest.mark.parametrize("ruta", ["", "/resumen", "/columnas"])
def test_usuario_sin_acceso_a_la_empresa_recibe_403(entorno, ruta):
    db, client, _headers, empresa_id = entorno
    db.execute("DELETE FROM usuarios WHERE email = %s", (EMAIL_AJENO,))
    ajeno = headers_usuario_e2e(db, EMAIL_AJENO)

    r = client.get(f"/api/v1/empresas/{empresa_id}/cfdis{ruta}", headers=ajeno,
                   params={"direccion": "emitidos", "periodo": "2026-03", "tipo": "I"})
    assert r.status_code == 403
