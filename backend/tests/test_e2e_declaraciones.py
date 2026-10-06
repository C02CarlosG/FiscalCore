"""E2E del comparativo contra lo declarado (M5) con Postgres real: captura, diferencia, borrado y auditoría."""
import pytest

from backend.tests.conftest import db_disponible, headers_usuario_e2e

RFC = "DEC010101E2E"
EMAIL = "e2e-declaraciones@test.local"
EMAIL_AJENO = "e2e-declaraciones-ajeno@test.local"

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


def _limpiar(db):
    db.execute("DELETE FROM empresas WHERE rfc = %s", (RFC,))
    db.execute("DELETE FROM cfdi WHERE uuid LIKE '7D5C%%'")
    db.execute("DELETE FROM usuarios WHERE email IN (%s, %s)", (EMAIL, EMAIL_AJENO))


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
        r = client.post("/api/v1/mis-empresas", headers=headers,
                        json={"rfc": RFC, "razon_social": "Empresa Declaraciones", "regimen_fiscal": "612"})
        assert r.status_code == 201, r.text
        e = r.json()["empresa_id"]
        db.execute(
            "INSERT INTO cfdi (empresa_id, uuid, tipo_comprobante, rfc_emisor, nombre_emisor, rfc_receptor, nombre_receptor,"
            " fecha_emision, subtotal, descuento, iva_trasladado, iva_retenido, isr_retenido, total, estado, metodo_pago,"
            " forma_pago, uso_cfdi, moneda, tipo_cambio, monto_cobrado, cfdi_relacionados, es_anticipo_sat)"
            " VALUES (%s, '7D5C0001-0000-4000-8000-000000000000', 'I', %s, 'Empresa', 'XAXX010101000', 'CLIENTE',"
            " '2026-09-10 10:00:00', 1000, 0, 160, 0, 0, 1160, 'vigente', 'PUE', '03', 'G03', 'MXN', 1, 0, '[]', false)",
            (e, RFC))
        yield db, client, headers, e
    finally:
        _limpiar(db)


def _url(ent, ruta=""):
    return f"/api/v1/empresas/{ent[3]}/declaraciones{ruta}"


def test_captura_compara_reemplaza_y_borra_con_auditoria(entorno):
    db, client, headers = entorno[0], entorno[1], entorno[2]

    sin = client.get(_url(entorno, "/2026-09"), headers=headers).json()
    assert sin["iva"]["estado"] == "sin_declaracion" and sin["isr"]["estado"] == "sin_declaracion"
    assert {r["clave"]: r for r in sin["iva"]["renglones"]}["impuesto_trasladado"]["calculado"] == 160.0

    r = client.put(_url(entorno, "/2026-09/iva"), headers=headers,
                   json={"impuesto_trasladado": "160", "impuesto_a_cargo": "150", "monto_pagado": "100"})
    assert r.status_code == 200, r.text
    d = client.get(_url(entorno, "/2026-09"), headers=headers).json()["iva"]
    renglones = {x["clave"]: x for x in d["renglones"]}
    assert renglones["impuesto_trasladado"]["estado"] == "cuadra"
    assert renglones["impuesto_a_cargo"]["estado"] == "diferencia" and renglones["impuesto_a_cargo"]["diferencia"] == -10.0
    assert d["estado"] == "con_diferencias" and d["pendiente_de_pago"] == 50.0

    # una complementaria reemplaza a la anterior
    r = client.put(_url(entorno, "/2026-09/iva"), headers=headers,
                   json={"tipo": "complementaria", "impuesto_trasladado": "160", "impuesto_a_cargo": "160"})
    assert r.status_code == 200 and r.json()["tipo"] == "complementaria"
    assert client.get(_url(entorno, "/2026-09"), headers=headers).json()["iva"]["estado"] == "cuadra"
    assert [i["impuesto"] for i in client.get(_url(entorno), headers=headers, params={"ejercicio": 2026}).json()["items"]] == ["iva"]

    assert client.delete(_url(entorno, "/2026-09/iva"), headers=headers).status_code == 204
    assert client.delete(_url(entorno, "/2026-09/iva"), headers=headers).status_code == 404

    acciones = [f["accion"] for f in db.query_all(
        "SELECT accion FROM auditoria WHERE empresa_id = %s AND accion LIKE 'declaracion_%%' ORDER BY creado_en", (entorno[3],))]
    assert acciones == ["declaracion_guardada", "declaracion_guardada", "declaracion_eliminada"]


def test_otra_empresa_recibe_403(entorno):
    db, client = entorno[0], entorno[1]
    db.execute("DELETE FROM usuarios WHERE email = %s", (EMAIL_AJENO,))
    ajeno = headers_usuario_e2e(db, EMAIL_AJENO)

    assert client.get(_url(entorno, "/2026-09"), headers=ajeno).status_code == 403
    assert client.put(_url(entorno, "/2026-09/iva"), headers=ajeno, json={}).status_code == 403
    assert client.delete(_url(entorno, "/2026-09/iva"), headers=ajeno).status_code == 403
