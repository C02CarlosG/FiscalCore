"""E2E de V1 contra Postgres real: conteos del periodo y del acumulado por validación y
dirección, lista de CFDI de cada tarjeta y configuración. Se salta sin DB."""
import pytest

from backend.tests.conftest import db_disponible, headers_usuario_e2e

RFC = "VAL010101AB1"
PROV = "PRV010101AA1"
CLIENTE = "CLI010101AA1"
EMAIL = "e2e-validaciones@test.local"
EMAIL_AJENO = "e2e-validaciones-ajeno@test.local"

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


def _uuid(n: int) -> str:
    return f"5A11{n:04d}-0000-4000-8000-000000000000"


def _cfdi(db, empresa_id, n, **kw):
    v = dict(
        uuid=_uuid(n), tipo_comprobante="I", serie="V", folio=str(n),
        rfc_emisor=RFC, nombre_emisor="Validaciones E2E", rfc_receptor=CLIENTE, nombre_receptor="CLIENTE",
        fecha_emision="2026-03-10", subtotal="100", total="116", estado="vigente",
        metodo_pago="PUE", forma_pago="03", uso_cfdi="G03", moneda="MXN", tipo_cambio="1",
        cfdi_relacionados="[]",
    )
    v.update(kw)
    fila = db.execute(
        f"INSERT INTO cfdi (empresa_id, {', '.join(v)}) VALUES (%s, {', '.join(['%s'] * len(v))}) RETURNING id",
        (empresa_id, *v.values()), returning=True,
    )
    return str(fila["id"])


def _recibido(db, empresa_id, n, **kw):
    return _cfdi(db, empresa_id, n, rfc_emisor=PROV, nombre_emisor="PROVEEDOR", rfc_receptor=RFC,
                 nombre_receptor="Validaciones E2E", **kw)


def _rep(db, empresa_id, n_rep, n_doc, estado="vigente", empresa_rep=None):
    rep = _cfdi(db, empresa_rep or empresa_id, n_rep, tipo_comprobante="P", total="0", subtotal="0", metodo_pago=None,
                forma_pago=None, uso_cfdi="CP01", moneda="XXX", estado=estado)
    pago = db.execute(
        "INSERT INTO pagos_cfdi (empresa_id, cfdi_id, uuid_cfdi_pago, fecha_pago, monto)"
        " VALUES (%s, %s, %s, '2026-03-20', 116) RETURNING id", (empresa_rep or empresa_id, rep, _uuid(n_rep)),
        returning=True)
    db.execute(
        "INSERT INTO pagos_relaciones (pago_id, cfdi_uuid, parcialidad, importe_pagado)"
        " VALUES (%s, %s, 1, 116)", (str(pago["id"]), _uuid(n_doc)))


def _sembrar(db, empresa_id, otra_empresa_id):
    # Emitidos
    _cfdi(db, empresa_id, 1, forma_pago="99")                                   # PUE 99, marzo
    _cfdi(db, empresa_id, 2, forma_pago="99", fecha_emision="2026-02-10")      # PUE 99, febrero
    _cfdi(db, empresa_id, 3, forma_pago="99", estado="cancelado")               # cancelado: no cuenta
    _cfdi(db, empresa_id, 4)                                                    # PUE con REP vigente
    _rep(db, empresa_id, 5, 4)
    _cfdi(db, empresa_id, 6)                                                    # PUE con REP cancelado
    _rep(db, empresa_id, 7, 6, estado="cancelado")
    _cfdi(db, empresa_id, 8, tipo_comprobante="E")                              # egreso sin relación
    _cfdi(db, empresa_id, 9, tipo_comprobante="E",
          cfdi_relacionados='[{"tipo_relacion": "01", "uuids": ["%s"]}]' % _uuid(1))
    _cfdi(db, empresa_id, 10, metodo_pago="PPD", forma_pago="99")               # PPD 99: correcto
    _cfdi(db, empresa_id, 11, forma_pago="01", total="9000")                    # efectivo emitido: no aplica
    _cfdi(db, empresa_id, 12, forma_pago="99", estado="sustituido")             # sustituido: no cuenta
    _cfdi(db, empresa_id, 13)                                                   # PUE con REP de OTRA empresa: no cuenta
    _rep(db, empresa_id, 14, 13, empresa_rep=otra_empresa_id)
    _cfdi(db, empresa_id, 15, tipo_comprobante="E",                             # solo relación 04: cuenta
          cfdi_relacionados='[{"tipo_relacion": "04", "uuids": ["%s"]}]' % _uuid(1))
    _cfdi(db, empresa_id, 16, tipo_comprobante="E", forma_pago="30",            # forma 30 sin 07: cuenta
          cfdi_relacionados='[{"tipo_relacion": "01", "uuids": ["%s"]}]' % _uuid(1))
    _cfdi(db, empresa_id, 17, tipo_comprobante="E", forma_pago="30",            # forma 30 con 07: correcto
          cfdi_relacionados='[{"tipo_relacion": "07", "uuids": ["%s"]}]' % _uuid(1))
    # Recibidos
    _recibido(db, empresa_id, 20, forma_pago="01", total="2000.00")             # igual al umbral: no
    _recibido(db, empresa_id, 21, forma_pago="01", total="2000.01")             # sí
    _recibido(db, empresa_id, 22, forma_pago="01", total="150", moneda="USD", tipo_cambio="17")  # 2,550: sí
    _recibido(db, empresa_id, 23, forma_pago="99")                              # PUE 99 recibido
    combustible = _recibido(db, empresa_id, 24, forma_pago="01", total="500")   # gasolina en efectivo: cuenta
    db.execute("INSERT INTO cfdi_conceptos (cfdi_id, linea, clave_prod_serv, descripcion, cantidad, valor_unitario, importe)"
               " VALUES (%s, 1, '15101514', 'Gasolina', 20, 25, 500)", (combustible,))
    # Otra empresa con el mismo RFC emisor: nunca cuenta.
    _cfdi(db, otra_empresa_id, 30, forma_pago="99")


def _limpiar(db):
    db.execute("DELETE FROM empresas WHERE rfc IN (%s, %s)", (RFC, "VAO010101AB1"))
    db.execute("DELETE FROM cfdi WHERE uuid LIKE '5A11%%'")
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
        r = client.post("/api/v1/mis-empresas", headers=headers, json={"rfc": RFC, "razon_social": "Validaciones E2E"})
        assert r.status_code == 201, r.text
        empresa_id = r.json()["empresa_id"]
        otra = db.execute("INSERT INTO empresas (rfc, razon_social) VALUES ('VAO010101AB1', 'Otra') RETURNING id",
                          returning=True)
        _sembrar(db, empresa_id, str(otra["id"]))
        yield db, client, headers, f"/api/v1/validaciones-cfdi/empresas/{empresa_id}"
    finally:
        _limpiar(db)


def _conteos(cuerpo, direccion):
    return {t["clave"]: (t["periodo"], t["acumulado"]) for t in cuerpo[direccion]}


def _lista(client, headers, base, direccion, validacion, alcance="periodo"):
    r = client.get(f"{base}/cfdis", headers=headers, params={
        "periodo": "2026-03", "direccion": direccion, "validacion": validacion, "alcance": alcance})
    assert r.status_code == 200, r.text
    return r.json()


def test_conteos_del_periodo_y_acumulado(entorno):
    _db, client, headers, base = entorno
    r = client.get(base, headers=headers, params={"periodo": "2026-03"})
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert _conteos(cuerpo, "emitidos") == {
        "pue_forma_99": (1, 2), "pue_con_rep": (1, 1), "egreso_sin_relacion": (3, 3),
    }
    assert _conteos(cuerpo, "recibidos") == {
        "pue_forma_99": (1, 1), "pue_con_rep": (0, 0), "egreso_sin_relacion": (0, 0), "no_bancarizado": (3, 3),
    }
    assert cuerpo["configuracion"] == {"inactivas": [], "umbral_efectivo": "2000.00"}


def test_lista_trae_exactamente_lo_que_se_cuenta(entorno):
    _db, client, headers, base = entorno
    lista = _lista(client, headers, base, "emitidos", "pue_forma_99", "acumulado")
    assert {f["uuid"] for f in lista["cfdis"]} == {_uuid(1), _uuid(2)}
    assert lista["total_filas"] == 2
    lista = _lista(client, headers, base, "recibidos", "no_bancarizado")
    assert {f["uuid"] for f in lista["cfdis"]} == {_uuid(21), _uuid(22), _uuid(24)}
    fila = next(f for f in lista["cfdis"] if f["uuid"] == _uuid(22))
    assert (fila["rfc"], fila["moneda"], fila["forma_pago"]) == (PROV, "USD", "01")
    assert [f["uuid"] for f in _lista(client, headers, base, "emitidos", "pue_con_rep")["cfdis"]] == [_uuid(4)]
    egresos = _lista(client, headers, base, "emitidos", "egreso_sin_relacion")
    assert {f["uuid"] for f in egresos["cfdis"]} == {_uuid(8), _uuid(15), _uuid(16)}


def test_configuracion_cambia_umbral_y_apaga_validaciones(entorno):
    _db, client, headers, base = entorno
    # El umbral legal no se puede subir.
    assert client.put(f"{base}/configuracion", headers=headers, json={"umbral_efectivo": "3000"}).status_code == 422
    r = client.put(f"{base}/configuracion", headers=headers,
                   json={"inactivas": ["pue_con_rep"], "umbral_efectivo": "1999"})
    assert r.status_code == 200, r.text
    assert r.json() == {"inactivas": ["pue_con_rep"], "umbral_efectivo": "1999.00"}
    try:
        cuerpo = client.get(base, headers=headers, params={"periodo": "2026-03"}).json()
        # Con 1,999 también cuenta el de 2,000.00.
        assert _conteos(cuerpo, "recibidos")["no_bancarizado"] == (4, 4)
        tarjeta = next(t for t in cuerpo["emitidos"] if t["clave"] == "pue_con_rep")
        assert (tarjeta["activa"], tarjeta["periodo"], tarjeta["acumulado"]) == (False, None, None)
        lista = _lista(client, headers, base, "emitidos", "pue_con_rep")
        assert lista == {"cfdis": [], "total_filas": 0}
    finally:
        client.put(f"{base}/configuracion", headers=headers, json={"inactivas": [], "umbral_efectivo": "2000"})


def test_otro_usuario_no_tiene_acceso(entorno):
    db, client, _headers, base = entorno
    ajeno = headers_usuario_e2e(db, EMAIL_AJENO)
    assert client.get(base, headers=ajeno, params={"periodo": "2026-03"}).status_code == 403
    assert client.put(f"{base}/configuracion", headers=ajeno, json={}).status_code == 403
