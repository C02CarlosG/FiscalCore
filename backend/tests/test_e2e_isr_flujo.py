"""E2E del ISR base flujo contra Postgres real: ingresos, deducciones, REP, nómina, ajustes y auditoría."""
import pytest

from backend.tests.conftest import db_disponible, headers_usuario_e2e

RFC = "ISR010101E2E"
OTRO = "XAXX010101000"
PROV = "PRO010101AAA"
TRAB = "TRA010101AAA"
EMAIL = "e2e-isr-flujo@test.local"
EMAIL_AJENO = "e2e-isr-flujo-ajeno@test.local"

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


def _uuid(n):
    return f"7F7A{n:04d}-0000-4000-8000-000000000000"


def _cfdi(db, e, n, **kw):
    v = dict(uuid=_uuid(n), tipo_comprobante="I", serie="A", folio=str(n), rfc_emisor=RFC, nombre_emisor="Empresa ISR",
             rfc_receptor=OTRO, nombre_receptor="CLIENTE", fecha_emision="2026-09-10 10:00:00", subtotal="1000",
             descuento="0", iva_trasladado="160", iva_retenido="0", isr_retenido="0", total="1160", estado="vigente",
             metodo_pago="PUE", forma_pago="03", uso_cfdi="G03", moneda="MXN", tipo_cambio="1", monto_cobrado="0",
             cfdi_relacionados="[]", es_anticipo_sat=False)
    v.update(kw)
    fila = db.execute(f"INSERT INTO cfdi (empresa_id, {', '.join(v)}) VALUES (%s, {', '.join(['%s'] * len(v))}) RETURNING id",
                      (e, *v.values()), returning=True)
    return str(fila["id"])


def _recibido(db, e, n, **kw):
    base = dict(rfc_emisor=PROV, nombre_emisor="PROVEEDOR", rfc_receptor=RFC, nombre_receptor="Empresa ISR")
    base.update(kw)
    return _cfdi(db, e, n, **base)


def _rep(db, e, n, uuid_docto, importe, fecha, estado="vigente"):
    rep = _cfdi(db, e, n, tipo_comprobante="P", subtotal="0", iva_trasladado="0", total="0", metodo_pago=None, forma_pago=None,
                uso_cfdi="CP01", moneda="XXX", estado=estado)
    pago = db.execute(
        "INSERT INTO pagos_cfdi (empresa_id, cfdi_id, uuid_cfdi_pago, fecha_pago, monto, moneda, tipo_cambio, version_pago)"
        " VALUES (%s, %s, %s, %s, %s, 'MXN', 1, '2.0') RETURNING id", (e, rep, _uuid(n), fecha, importe), returning=True)
    db.execute("INSERT INTO pagos_relaciones (pago_id, cfdi_uuid, parcialidad, importe_pagado, saldo_anterior, saldo_restante,"
               " moneda_dr, equivalencia_dr) VALUES (%s, %s, 1, %s, %s, 0, 'MXN', 1)",
               (str(pago["id"]), uuid_docto, importe, importe))


def _nomina(db, e, n, percepciones, retenido="100", fecha_pago="2026-09-15", estado="vigente"):
    cid = _cfdi(db, e, n, tipo_comprobante="N", rfc_receptor=TRAB, nombre_receptor="TRABAJADOR", subtotal="0",
                iva_trasladado="0", total="0", metodo_pago=None, forma_pago=None, uso_cfdi="CN01", estado=estado)
    nom = db.execute("INSERT INTO cfdi_nominas (cfdi_id, nodo, fecha_pago, total_impuestos_retenidos) VALUES (%s, 1, %s, %s) RETURNING id",
                     (cid, fecha_pago, retenido), returning=True)
    for linea, (tipo, gravado, exento) in enumerate(percepciones, start=1):
        db.execute("INSERT INTO cfdi_nomina_conceptos (nomina_id, categoria, linea, tipo, importe_gravado, importe_exento)"
                   " VALUES (%s, 'percepcion', %s, %s, %s, %s)", (str(nom["id"]), linea, tipo, gravado, exento))


def _limpiar(db):
    db.execute("DELETE FROM empresas WHERE rfc = %s", (RFC,))
    db.execute("DELETE FROM cfdi WHERE uuid LIKE '7F7A%%'")
    db.execute("DELETE FROM usuarios WHERE email IN (%s, %s)", (EMAIL, EMAIL_AJENO))


def _sembrar(db, e):
    _cfdi(db, e, 1)                                                                      # ingreso contado 1000
    _cfdi(db, e, 2, subtotal="400", isr_retenido="40")                                    # 400 con retención a favor
    _cfdi(db, e, 3, tipo_comprobante="E", subtotal="100")                                 # devolución
    _cfdi(db, e, 4, estado="cancelado", subtotal="9999")
    _cfdi(db, e, 5, fecha_emision="2026-01-15 10:00:00", subtotal="500")                  # enero: solo acumulado
    ppd = _cfdi(db, e, 10, metodo_pago="PPD", forma_pago="99", fecha_emision="2026-08-20 09:00:00")
    _rep(db, e, 11, _uuid(10), 580, "2026-09-25 12:00:00")                                 # cobra 500 de base
    _rep(db, e, 12, _uuid(10), 580, "2026-09-26 12:00:00", estado="cancelado")             # REP cancelado: no cuenta
    _recibido(db, e, 20, subtotal="300")                                                  # gasto 300
    _recibido(db, e, 21, subtotal="250", forma_pago="01", total="2900")                   # efectivo > 2000: no deducible
    _recibido(db, e, 22, subtotal="700", uso_cfdi="I01")                                  # inversión: aparte
    _recibido(db, e, 23, subtotal="200", isr_retenido="20")                               # retención a proveedor
    _nomina(db, e, 30, [("001", 800, 200), ("003", 0, 300), ("050", 0, 50)], retenido="100")
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
        r = client.post("/api/v1/mis-empresas", headers=headers,
                        json={"rfc": RFC, "razon_social": "Empresa ISR", "regimen_fiscal": "612"})
        assert r.status_code == 201, r.text
        e = r.json()["empresa_id"]
        _sembrar(db, e)
        yield db, client, headers, e
    finally:
        _limpiar(db)


def _url(ent, ruta):
    return f"/api/v1/empresas/{ent[3]}/isr-flujo/{ruta}"


def _resumen(ent, periodo="2026-09"):
    r = ent[1].get(_url(ent, periodo), headers=ent[2])
    assert r.status_code == 200, r.text
    return r.json()


def test_ingresos_del_mes_y_acumulado(entorno):
    d = _resumen(entorno)

    ing = d["mes"]["ingresos"]
    assert (ing["contado"], ing["credito"], ing["devoluciones"], ing["total"]) == (1400.0, 500.0, 100.0, 1800.0)
    assert ing["retenciones_a_favor"] == 40.0
    assert d["acumulado"]["ingresos"]["total"] == 2300.0                  # + enero
    assert d["regimen"]["codigo"] == "612" and d["regimen"]["modulo"] == "flujo"


def test_deducciones_con_efectivo_inversion_y_nomina(entorno):
    d = _resumen(entorno)["mes"]["deducciones"]

    assert d["compras_y_gastos"] == 500.0                                  # 300 + 200 (el de 250 en efectivo no)
    assert d["no_considerados"]["por_motivo"]["efectivo"] == {"cfdi": 1, "base": 250.0}
    assert d["inversiones"] == {"cfdi": 1, "base": 700.0}
    n = d["nomina"]
    assert (n["gravado"], n["exento"], n["exento_deducible"], n["deducible"]) == (800.0, 200.0, 94.0, 894.0)
    assert (n["excluido_ptu"], n["excluido_viaticos"]) == (300.0, 50.0)
    assert d["total"] == 500.0 + 894.0


def test_retenciones_y_utilidad_fiscal(entorno):
    mes = _resumen(entorno)["mes"]

    assert mes["retenciones_a_cargo"] == {"trabajadores": 100.0, "proveedores": 20.0, "total": 120.0}
    assert mes["utilidad_fiscal_estimada"] == 1800.0 - 1394.0


def test_cambiar_el_porcentaje_de_nomina_exenta_recalcula_y_audita(entorno):
    db, client, headers, e = entorno

    r = client.put(_url(entorno, "config/2026"), headers=headers, json={"pct_nomina_exenta": 0.53})

    assert r.status_code == 200 and client.get(_url(entorno, "config/2026"), headers=headers).json()["pct_nomina_exenta"] == 0.53
    n = _resumen(entorno)["mes"]["deducciones"]["nomina"]
    assert n["exento_deducible"] == 106.0 and n["porcentaje_exento"] == 0.53
    assert db.query_one("SELECT COUNT(*) AS n FROM auditoria WHERE empresa_id = %s AND accion = 'isr_config_flujo'", (e,))["n"] == 1
    client.put(_url(entorno, "config/2026"), headers=headers, json={"pct_nomina_exenta": 0.47})


def test_no_considerar_saca_el_cfdi_audita_y_se_puede_retirar(entorno):
    db, client, headers, e = entorno
    antes = _resumen(entorno)["mes"]["ingresos"]["total"]

    r = client.put(_url(entorno, "ajustes"), headers=headers, json={"uuid": _uuid(1).lower(), "lado": "ingreso", "motivo": "duplicado"})

    assert r.status_code == 200, r.text
    ing = _resumen(entorno)["mes"]["ingresos"]
    assert ing["total"] == antes - 1000.0 and ing["no_considerados"]["por_motivo"]["manual"] == {"cfdi": 1, "base": 1000.0}
    aud = db.query_all("SELECT metadata FROM auditoria WHERE empresa_id = %s AND accion = 'isr_ajuste'", (e,))
    assert len(aud) == 1 and aud[0]["metadata"]["motivo"] == "duplicado"
    assert client.delete(_url(entorno, f"ajustes/ingreso/{_uuid(1)}"), headers=headers).status_code == 204
    assert _resumen(entorno)["mes"]["ingresos"]["total"] == antes
    assert client.delete(_url(entorno, f"ajustes/ingreso/{_uuid(1)}"), headers=headers).status_code == 404


def test_ajuste_de_un_cfdi_que_no_es_del_lado_es_404(entorno):
    client, headers = entorno[1], entorno[2]

    assert client.put(_url(entorno, "ajustes"), headers=headers, json={"uuid": _uuid(20), "lado": "ingreso", "motivo": "x"}).status_code == 404
    assert client.put(_url(entorno, "ajustes"), headers=headers, json={"uuid": "no-existe", "lado": "ingreso", "motivo": "x"}).status_code == 404
    assert client.put(_url(entorno, "ajustes"), headers=headers, json={"uuid": _uuid(30), "lado": "deduccion", "motivo": "x"}).status_code == 200
    client.delete(_url(entorno, f"ajustes/deduccion/{_uuid(30)}"), headers=headers)


def test_detalle_lista_los_cfdi_de_cada_cifra(entorno):
    client, headers = entorno[1], entorno[2]

    r = client.get(_url(entorno, "2026-09/detalle"), headers=headers, params={"lado": "deduccion", "bloque": "nomina"})
    cred = client.get(_url(entorno, "2026-09/detalle"), headers=headers, params={"lado": "ingreso", "bloque": "credito"}).json()

    assert r.status_code == 200 and [i["uuid"] for i in r.json()["items"]] == [_uuid(30)]
    assert r.json()["items"][0]["nomina"]["ptu"] == 300.0
    assert [i["uuid_pago"] for i in cred["items"]] == [_uuid(11)] and cred["items"][0]["base"] == 500.0


def test_otra_empresa_recibe_403(entorno):
    db, client = entorno[0], entorno[1]
    db.execute("DELETE FROM usuarios WHERE email = %s", (EMAIL_AJENO,))
    ajeno = headers_usuario_e2e(db, EMAIL_AJENO)

    assert client.get(_url(entorno, "2026-09"), headers=ajeno).status_code == 403
    assert client.put(_url(entorno, "config/2026"), headers=ajeno, json={"pct_nomina_exenta": 0.53}).status_code == 403
    assert client.put(_url(entorno, "ajustes"), headers=ajeno, json={"uuid": _uuid(1), "lado": "ingreso", "motivo": "x"}).status_code == 403


def test_pago_provisional_con_ptu_y_perdidas_de_la_configuracion(entorno):
    db, client, headers = entorno[0], entorno[1], entorno[2]
    try:
        r = client.put(_url(entorno, "config/2026"), headers=headers,
                       json={"pct_nomina_exenta": 0.47, "ptu_pagada": "100.50", "perdidas_pendientes": "200"})
        assert r.status_code == 200 and r.json()["ptu_pagada"] == 100.5, r.text
        # omitir ptu/pérdidas conserva lo guardado
        assert client.put(_url(entorno, "config/2026"), headers=headers, json={"pct_nomina_exenta": 0.47}).json()["perdidas_pendientes"] == 200.0

        d = client.get(_url(entorno, "2026-09/pago-provisional"), headers=headers).json()

        assert d["calculado"] is True and d["ptu_pagada"] == 100.5 and d["perdidas_pendientes"] == 200.0
        assert d["ingresos_acumulados"] == 2300.0 and d["deducciones_acumuladas"] == 1394.0
        assert d["utilidad_antes_de_ajustes"] == 906.0 and d["base_gravable"] == 605.5            # 906 − 100.50 − 200
        assert d["tarifa"]["porcentaje"] == 1.92 and d["impuesto_causado"] == 11.63               # 605.49 × 1.92 %
        assert d["pagos_provisionales_anteriores"] == 3.83 and d["isr_retenido_del_mes"] == 40.0   # solo enero causa (199.50 × 1.92 %)
        assert d["pago_del_mes"] == 0.0 and d["exceso_de_pagos_y_retenciones"] == 32.2
        assert d["meses_con_pago_estimado"] == [1, 2, 3, 4, 5, 6, 7, 8] and d["fuente"]["url"].startswith("https://www.sat.gob.mx/")
    finally:
        client.put(_url(entorno, "config/2026"), headers=headers, json={"pct_nomina_exenta": 0.47, "ptu_pagada": 0, "perdidas_pendientes": 0})
