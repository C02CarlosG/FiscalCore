"""E2E del detalle y del XML de un CFDI contra Postgres real. Se salta sin DB."""
import json

import pytest

from backend.tests.conftest import db_disponible, headers_usuario_e2e

RFC = "VIS010101E2E"
OTRO = "XAXX010101000"
EMAIL = "e2e-visor-cfdi@test.local"
EMAIL_AJENO = "e2e-visor-ajeno@test.local"
UUID = "2F3A0001-0000-4000-8000-000000000000"
UUID_SIN_XML = "2F3A0002-0000-4000-8000-000000000000"
UUID_REP = "2F3A0009-0000-4000-8000-000000000000"
XML = '<?xml version="1.0"?><cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4"/>'

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


def _limpiar(db):
    db.execute("DELETE FROM empresas WHERE rfc = %s", (RFC,))
    db.execute("DELETE FROM cfdi WHERE uuid LIKE '2F3A%%'")
    db.execute("DELETE FROM usuarios WHERE email IN (%s, %s)", (EMAIL, EMAIL_AJENO))


def _insertar(db, empresa_id, uuid, **kw):
    v = dict(
        uuid=uuid, tipo_comprobante="I", serie="A", folio="1", rfc_emisor=RFC, nombre_emisor="Emisora E2E",
        rfc_receptor=OTRO, nombre_receptor="CLIENTE", fecha_emision="2026-03-10 09:30:00",
        subtotal="1000", descuento="0", iva_trasladado="160", iva_retenido="0", isr_retenido="0",
        total="1160", estado="vigente", metodo_pago="PPD", forma_pago="99", uso_cfdi="G03", moneda="MXN",
        tipo_cambio="1", monto_cobrado="400", cfdi_relacionados=json.dumps(
            [{"tipo_relacion": "04", "uuids": ["AAAAAAAA-0000-4000-8000-000000000000"]}]),
        regimen_emisor="601", regimen_fiscal_receptor="612", domicilio_fiscal_receptor="68000",
        xml_raw=XML,
    )
    v.update(kw)
    fila = db.execute(
        f"INSERT INTO cfdi (empresa_id, {', '.join(v)}) VALUES (%s, {', '.join(['%s'] * len(v))}) RETURNING id",
        (empresa_id, *v.values()), returning=True)
    return str(fila["id"])


def _sembrar(db, empresa_id):
    cfdi = _insertar(db, empresa_id, UUID)
    db.execute(
        "INSERT INTO cfdi_impuestos (cfdi_id, ambito, impuesto, tipo_factor, tasa_o_cuota, base, importe)"
        " VALUES (%s, 'traslado', '002', 'Tasa', 0.16, 1000, 160)", (cfdi,))
    for linea, (desc, importe) in enumerate([("Servicio uno", "600"), ("Servicio dos", "400")], start=1):
        db.execute(
            "INSERT INTO cfdi_conceptos (cfdi_id, linea, clave_prod_serv, cantidad, clave_unidad, descripcion,"
            " valor_unitario, importe, descuento, objeto_imp, impuestos) VALUES (%s,%s,'84111506',1,'E48',%s,%s,%s,0,'02',%s)",
            (cfdi, linea, desc, importe, importe, json.dumps([
                {"ambito": "traslado", "impuesto": "002", "tipo_factor": "Tasa", "tasa_o_cuota": "0.160000",
                 "base": importe, "importe": str(float(importe) * 0.16)}])))
    rep = _insertar(db, empresa_id, UUID_REP, tipo_comprobante="P", subtotal="0", iva_trasladado="0", total="0",
                    metodo_pago=None, forma_pago=None, uso_cfdi="CP01", moneda="XXX", cfdi_relacionados="[]")
    pago = db.execute(
        "INSERT INTO pagos_cfdi (empresa_id, cfdi_id, uuid_cfdi_pago, fecha_pago, monto)"
        " VALUES (%s, %s, %s, '2026-03-20 12:00:00', 400) RETURNING id", (empresa_id, rep, UUID_REP), returning=True)
    db.execute(
        "INSERT INTO pagos_relaciones (pago_id, cfdi_uuid, parcialidad, importe_pagado, saldo_anterior, saldo_restante)"
        " VALUES (%s, %s, 1, 400, 1160, 760)", (str(pago["id"]), UUID))
    _insertar(db, empresa_id, UUID_SIN_XML, xml_raw=None, cfdi_relacionados="[]")


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


def _url(entorno, uuid, sufijo=""):
    return f"/api/v1/empresas/{entorno[3]}/cfdis/{uuid}{sufijo}"


def test_detalle_trae_encabezado_partes_conceptos_pagos_y_relacionados(entorno):
    r = entorno[1].get(_url(entorno, UUID), headers=entorno[2])

    assert r.status_code == 200, r.text
    d = r.json()
    e = d["encabezado"]
    assert (e["uuid"], e["tipo_comprobante"], e["total"], e["saldo"]) == (UUID, "I", 1160.0, 760.0)
    assert e["fecha_emision"] == "2026-03-10T09:30:00"          # sin zona: no se desplaza
    assert e["metodo_pago_desc"] == "PPD - Pago en parcialidades o diferido"
    assert (d["emisor"]["rfc"], d["emisor"]["regimen"]) == (RFC, "601")
    assert d["emisor"]["regimen_desc"].startswith("601 - ")
    assert (d["receptor"]["rfc"], d["receptor"]["domicilio_fiscal"]) == (OTRO, "68000")
    assert d["impuestos"] == [{"ambito": "traslado", "impuesto": "002", "tipo_factor": "Tasa",
                               "tasa_o_cuota": 0.16, "base": 1000.0, "importe": 160.0}]
    assert d["total_conceptos"] == 2
    assert [c["descripcion"] for c in d["conceptos"]] == ["Servicio uno", "Servicio dos"]
    assert d["conceptos"][0]["iva_traslado_importe"] == 96.0
    assert d["pagos"] == [{"uuid_pago": UUID_REP, "fecha_pago": "2026-03-20T12:00:00", "parcialidad": 1,
                           "importe_pagado": 400.0, "saldo_anterior": 1160.0, "saldo_restante": 760.0}]
    assert d["relacionados"][0]["tipo_relacion"] == "04"
    assert d["tiene_xml"] is True


def test_detalle_sin_xml_lo_avisa(entorno):
    d = entorno[1].get(_url(entorno, UUID_SIN_XML), headers=entorno[2]).json()

    assert d["tiene_xml"] is False and d["conceptos"] == [] and d["pagos"] == []


def test_uuid_inexistente_es_404(entorno):
    assert entorno[1].get(_url(entorno, "2F3AFFFF-0000-4000-8000-000000000000"), headers=entorno[2]).status_code == 404


def test_xml_se_descarga_y_deja_auditoria(entorno):
    db = entorno[0]
    r = entorno[1].get(_url(entorno, UUID, "/xml"), headers=entorno[2])

    assert r.status_code == 200
    assert r.text == XML
    assert f'filename="{UUID}.xml"' in r.headers["content-disposition"]
    n = db.query_one("SELECT COUNT(*) AS n FROM auditoria WHERE accion = 'cfdi_xml_descargado' AND entidad_id = %s", (UUID,))
    assert n["n"] >= 1


def test_xml_ausente_es_404(entorno):
    assert entorno[1].get(_url(entorno, UUID_SIN_XML, "/xml"), headers=entorno[2]).status_code == 404


@pytest.mark.parametrize("sufijo", ["", "/xml"])
def test_otra_empresa_no_ve_el_cfdi(entorno, sufijo):
    db, client, _h, _e = entorno
    db.execute("DELETE FROM usuarios WHERE email = %s", (EMAIL_AJENO,))
    ajeno = headers_usuario_e2e(db, EMAIL_AJENO)
    r = client.post("/api/v1/mis-empresas", headers=ajeno, json={"rfc": "AJE010101E2E", "razon_social": "Ajena"})
    ajena_id = r.json()["empresa_id"]
    try:
        # Con acceso a SU empresa, el UUID de la otra no existe.
        assert client.get(f"/api/v1/empresas/{ajena_id}/cfdis/{UUID}{sufijo}", headers=ajeno).status_code == 404
        # Sin acceso a la empresa ajena: 403.
        assert client.get(_url(entorno, UUID, sufijo), headers=ajeno).status_code == 403
    finally:
        db.execute("DELETE FROM empresas WHERE rfc = 'AJE010101E2E'")
