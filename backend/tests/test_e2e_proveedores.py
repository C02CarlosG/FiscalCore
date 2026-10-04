"""E2E del catálogo de proveedores contra Postgres real. Se salta sin DB."""
import pytest

from backend.tests.conftest import db_disponible, headers_usuario_e2e

RFC = "PVD010101E2E"
PROV = "PRO010101AAA"
EMAIL = "e2e-proveedores@test.local"
EMAIL_AJENO = "e2e-proveedores-ajeno@test.local"

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


def _recibido(db, empresa_id, n, rfc=PROV, nombre="PROVEEDOR UNO", fecha="2026-09-10 10:00:00", **kw):
    v = dict(uuid=f"6F6A{n:04d}-0000-4000-8000-000000000000", tipo_comprobante="I", serie="A", folio=str(n),
             rfc_emisor=rfc, nombre_emisor=nombre, rfc_receptor=RFC, nombre_receptor="Empresa",
             fecha_emision=fecha, subtotal="100", descuento="0", iva_trasladado="16", iva_retenido="0",
             isr_retenido="0", total="116", estado="vigente", metodo_pago="PUE", forma_pago="03", uso_cfdi="G03",
             moneda="MXN", tipo_cambio="1", monto_cobrado="0", cfdi_relacionados="[]", es_anticipo_sat=False)
    v.update(kw)
    db.execute(f"INSERT INTO cfdi (empresa_id, {', '.join(v)}) VALUES (%s, {', '.join(['%s'] * len(v))})",
               (empresa_id, *v.values()))


def _limpiar(db):
    db.execute("DELETE FROM empresas WHERE rfc = %s", (RFC,))
    db.execute("DELETE FROM cfdi WHERE uuid LIKE '6F6A%%'")
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
        r = client.post("/api/v1/mis-empresas", headers=headers, json={"rfc": RFC, "razon_social": "Empresa"})
        assert r.status_code == 201, r.text
        empresa_id = r.json()["empresa_id"]
        _recibido(db, empresa_id, 1, fecha="2026-08-01 10:00:00", nombre="NOMBRE VIEJO")
        _recibido(db, empresa_id, 2, nombre="NOMBRE NUEVO")                       # el más reciente manda
        _recibido(db, empresa_id, 3, rfc="OTR010101BBB", nombre="OTRO", estado="cancelado")   # cancelado: no entra
        _recibido(db, empresa_id, 4, rfc=RFC, nombre="YO MISMO")                  # autofactura: no es proveedor
        yield db, client, headers, empresa_id
    finally:
        _limpiar(db)


def _url(e, ruta=""):
    return f"/api/v1/empresas/{e[3]}/proveedores{ruta}"


def test_lista_se_alimenta_de_los_cfdi_recibidos_vigentes(entorno):
    r = entorno[1].get(_url(entorno), headers=entorno[2])

    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert [(i["rfc"], i["nombre"], i["origen"]) for i in items] == [(PROV, "NOMBRE NUEVO", "cfdi")]
    assert r.json()["agregados"] == 1
    assert entorno[1].get(_url(entorno), headers=entorno[2]).json()["agregados"] == 0     # idempotente


def test_editar_audita_y_el_nombre_editado_no_se_pisa(entorno):
    db, client, headers = entorno[0], entorno[1], entorno[2]

    r = client.patch(_url(entorno, f"/{PROV.lower()}"), headers=headers,
                     json={"nombre": "NOMBRE DEL CONTADOR", "tipo_tercero": "04", "tipo_operacion": "85"})

    assert r.status_code == 200, r.text
    assert (r.json()["nombre"], r.json()["tipo_tercero"], r.json()["nombre_editado"]) == ("NOMBRE DEL CONTADOR", "04", True)
    _recibido(db, entorno[3], 5, nombre="OTRO NOMBRE MAS RECIENTE", fecha="2026-09-20 10:00:00")
    item = client.get(_url(entorno), headers=headers).json()["items"][0]
    assert item["nombre"] == "NOMBRE DEL CONTADOR" and item["tipo_operacion"] == "85"
    aud = db.query_all("SELECT accion, metadata FROM auditoria WHERE empresa_id = %s AND accion = 'proveedor_editado'", (entorno[3],))
    assert len(aud) == 1 and aud[0]["metadata"]["despues"]["tipo_tercero"] == "04"


def test_alta_manual_y_duplicado(entorno):
    client, headers = entorno[1], entorno[2]

    r = client.post(_url(entorno), headers=headers, json={"rfc": "xexx010101000", "nombre": "EXTRANJERO", "pais": "Estados Unidos",
                                                           "id_fiscal": "12-3456789", "tipo_tercero": "05"})
    assert r.status_code == 201, r.text
    assert r.json()["origen"] == "manual" and r.json()["rfc"] == "XEXX010101000"
    assert client.post(_url(entorno), headers=headers, json={"rfc": "XEXX010101000"}).status_code == 409
    assert [i["rfc"] for i in client.get(_url(entorno), headers=headers, params={"q": "extranj"}).json()["items"]] == ["XEXX010101000"]


def test_otra_empresa_recibe_403(entorno):
    db, client = entorno[0], entorno[1]
    db.execute("DELETE FROM usuarios WHERE email = %s", (EMAIL_AJENO,))
    ajeno = headers_usuario_e2e(db, EMAIL_AJENO)

    assert client.get(_url(entorno), headers=ajeno).status_code == 403
    assert client.post(_url(entorno), headers=ajeno, json={"rfc": PROV}).status_code == 403
    assert client.patch(_url(entorno, f"/{PROV}"), headers=ajeno, json={"nombre": "x"}).status_code == 403
