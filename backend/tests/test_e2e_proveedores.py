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
        _recibido(db, empresa_id, 6, rfc="XEXX010101000", nombre="ACME INC")      # extranjeros: comparten el RFC genérico
        _recibido(db, empresa_id, 7, rfc="XEXX010101000", nombre="GLOBEX LLC")
        _recibido(db, empresa_id, 8, rfc="XAXX010101000", nombre="PUBLICO")
        _recibido(db, empresa_id, 9, rfc="no-es-rfc", nombre="BASURA")            # RFC con formato inválido: no entra
        yield db, client, headers, empresa_id
    finally:
        _limpiar(db)


def _url(e, ruta=""):
    return f"/api/v1/empresas/{e[3]}/proveedores{ruta}"


def test_lista_se_alimenta_de_los_cfdi_recibidos_vigentes(entorno):
    r = entorno[1].get(_url(entorno), headers=entorno[2])

    assert r.status_code == 200, r.text
    items = {(i["rfc"], i["nombre"]): i for i in r.json()["items"]}
    assert set(items) == {(PROV, "NOMBRE NUEVO"), ("XEXX010101000", "ACME INC"), ("XEXX010101000", "GLOBEX LLC"),
                          ("XAXX010101000", "PUBLICO")}
    nacional = items[(PROV, "NOMBRE NUEVO")]
    assert (nacional["tipo_tercero"], nacional["tipo_operacion"], nacional["origen"]) == ("04", "85", "cfdi")
    extranjero = items[("XEXX010101000", "ACME INC")]
    assert (extranjero["tipo_tercero"], extranjero["pendiente"]) == ("05", True)           # falta ID fiscal y país
    assert items[("XAXX010101000", "PUBLICO")]["tipo_tercero"] == "15"
    assert (r.json()["agregados"], r.json()["omitidos"]) == (4, 1)
    again = entorno[1].get(_url(entorno), headers=entorno[2]).json()
    assert (again["agregados"], again["omitidos"]) == (0, 1)                                # idempotente


def test_sincronizar_deja_el_evento_en_la_auditoria(entorno):
    aud = entorno[0].query_all("SELECT metadata FROM auditoria WHERE empresa_id = %s AND accion = 'proveedores_sincronizados'", (entorno[3],))

    assert len(aud) == 1 and aud[0]["metadata"] == {"agregados": 4, "omitidos": 1}


def _por_rfc(entorno, rfc, nombre=None):
    items = entorno[1].get(_url(entorno), headers=entorno[2]).json()["items"]
    return next(i for i in items if i["rfc"] == rfc and (nombre is None or i["nombre"] == nombre))


def test_editar_audita_y_el_nombre_editado_no_se_pisa(entorno):
    db, client, headers = entorno[0], entorno[1], entorno[2]
    pid = _por_rfc(entorno, PROV)["id"]

    r = client.patch(_url(entorno, f"/{pid}"), headers=headers,
                     json={"nombre": "NOMBRE DEL CONTADOR", "tipo_tercero": "04", "tipo_operacion": "06"})

    assert r.status_code == 200, r.text
    assert (r.json()["nombre"], r.json()["tipo_operacion"], r.json()["nombre_editado"]) == ("NOMBRE DEL CONTADOR", "06", True)
    _recibido(db, entorno[3], 5, nombre="OTRO NOMBRE MAS RECIENTE", fecha="2026-09-20 10:00:00")
    assert _por_rfc(entorno, PROV)["nombre"] == "NOMBRE DEL CONTADOR"
    aud = db.query_all("SELECT metadata FROM auditoria WHERE empresa_id = %s AND accion = 'proveedor_editado'", (entorno[3],))
    assert len(aud) == 1 and aud[0]["metadata"]["despues"]["tipo_operacion"] == "06"


def test_nombre_editado_false_devuelve_el_nombre_a_la_alimentacion(entorno):
    client, headers = entorno[1], entorno[2]
    pid = _por_rfc(entorno, PROV)["id"]

    assert client.patch(_url(entorno, f"/{pid}"), headers=headers, json={"nombre_editado": False}).json()["nombre_editado"] is False
    assert _por_rfc(entorno, PROV)["nombre"] == "OTRO NOMBRE MAS RECIENTE"


def test_varios_extranjeros_comparten_el_rfc_y_se_distinguen_por_id_fiscal(entorno):
    client, headers = entorno[1], entorno[2]
    acme, globex = _por_rfc(entorno, "XEXX010101000", "ACME INC"), _por_rfc(entorno, "XEXX010101000", "GLOBEX LLC")

    r1 = client.patch(_url(entorno, f"/{acme['id']}"), headers=headers, json={"id_fiscal": "12-345", "pais": "usa", "tipo_tercero": "05"})
    r2 = client.patch(_url(entorno, f"/{globex['id']}"), headers=headers, json={"id_fiscal": "12-345", "pais": "usa", "tipo_tercero": "05"})

    assert r1.status_code == 200 and r1.json()["pais"] == "USA" and r1.json()["pendiente"] is False
    assert r2.status_code == 409                                              # mismo ID fiscal
    assert client.patch(_url(entorno, f"/{globex['id']}"), headers=headers,
                        json={"id_fiscal": "98-765", "pais": "can", "tipo_tercero": "05"}).status_code == 200


def test_alta_manual_de_otro_extranjero_y_duplicados(entorno):
    client, headers = entorno[1], entorno[2]

    r = client.post(_url(entorno), headers=headers, json={"rfc": "xexx010101000", "nombre": "INITECH", "pais": "gbr",
                                                           "id_fiscal": "GB-1", "tipo_tercero": "05"})
    assert r.status_code == 201, r.text
    assert (r.json()["origen"], r.json()["rfc"], r.json()["tipo_operacion"]) == ("manual", "XEXX010101000", "85")
    assert client.post(_url(entorno), headers=headers, json={"rfc": "XEXX010101000", "pais": "gbr", "id_fiscal": "GB-1",
                                                              "tipo_tercero": "05"}).status_code == 409
    assert client.post(_url(entorno), headers=headers, json={"rfc": PROV}).status_code == 409
    assert [i["nombre"] for i in client.get(_url(entorno), headers=headers, params={"q": "GB-1"}).json()["items"]] == ["INITECH"]


def test_la_base_rechaza_codigos_fuera_del_catalogo(entorno):
    import psycopg2

    db = entorno[0]
    for columna, valor in (("tipo_tercero", "ZZ"), ("tipo_operacion", "99")):
        with pytest.raises(psycopg2.errors.CheckViolation):
            db.execute(f"INSERT INTO proveedores (empresa_id, rfc, {columna}) VALUES (%s, 'AAA010101AAA', %s)", (entorno[3], valor))
    with pytest.raises(psycopg2.errors.CheckViolation):
        db.execute("INSERT INTO proveedores (empresa_id, rfc) VALUES (%s, 'aaa010101aaa')", (entorno[3],))


def test_otra_empresa_recibe_403(entorno):
    db, client = entorno[0], entorno[1]
    db.execute("DELETE FROM usuarios WHERE email = %s", (EMAIL_AJENO,))
    ajeno = headers_usuario_e2e(db, EMAIL_AJENO)
    pid = _por_rfc(entorno, PROV)["id"]

    assert client.get(_url(entorno), headers=ajeno).status_code == 403
    assert client.post(_url(entorno), headers=ajeno, json={"rfc": PROV}).status_code == 403
    assert client.patch(_url(entorno, f"/{pid}"), headers=ajeno, json={"nombre": "x"}).status_code == 403
