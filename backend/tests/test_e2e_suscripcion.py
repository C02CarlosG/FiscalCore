"""E2E de M7.1 contra Postgres real: plan efectivo, uso de RFC, límite, asignación
manual por un administrador de la plataforma y edición de planes. Se salta sin DB."""
from datetime import date, timedelta

import pytest

from backend.tests.conftest import db_disponible, headers_usuario_e2e

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]

TITULAR = "m7-titular@test.local"
ADMIN = "m7-admin@test.local"
OTRO = "m7-otro@test.local"
RFCS = ("SUA010101AB1", "SUB010101AB1", "SUC010101AB1")


def _limpiar(db):
    db.execute("DELETE FROM empresas WHERE rfc IN %s", (RFCS,))
    db.execute("DELETE FROM usuarios WHERE email IN (%s, %s, %s)", (TITULAR, ADMIN, OTRO))


@pytest.fixture
def entorno():
    from fastapi.testclient import TestClient

    import backend.main_api as main
    from backend import db

    db.init_db()
    _limpiar(db)
    original = db.query_one("SELECT max_rfc FROM planes WHERE clave = 'despacho'")
    client = TestClient(main.app)
    try:
        h_titular = headers_usuario_e2e(db, TITULAR)
        h_admin = headers_usuario_e2e(db, ADMIN)
        db.execute("UPDATE usuarios SET rol = 'admin' WHERE email = %s", (ADMIN,))
        h_otro = headers_usuario_e2e(db, OTRO)
        yield db, client, h_titular, h_admin, h_otro
    finally:
        db.execute("UPDATE planes SET max_rfc = %s WHERE clave = 'despacho'", (original["max_rfc"],))
        _limpiar(db)


def _id(db, email):
    return str(db.query_one("SELECT id FROM usuarios WHERE email = %s", (email,))["id"])


def _vincular(db, email, rfc, rol="contador", created_at="2026-01-01"):
    empresa = db.query_one("SELECT id FROM empresas WHERE rfc = %s", (rfc,)) or db.execute(
        "INSERT INTO empresas (rfc, razon_social) VALUES (%s, 'Suscripción E2E') RETURNING id", (rfc,), returning=True)
    db.execute("INSERT INTO usuario_empresas (usuario_id, empresa_id, rol, created_at) VALUES (%s, %s, %s, %s)",
               (_id(db, email), empresa["id"], rol, created_at))


def _verificar(db, email, de_tercero=False):
    """Como lo usa un alta real: dentro de la transacción que crearía el vínculo."""
    from backend import suscripcion_datos

    with db.get_conn() as conn, conn.cursor() as cur:
        suscripcion_datos.verificar_alta_rfc(cur, _id(db, email), de_tercero)


def _mia(client, h):
    r = client.get("/api/v1/suscripcion", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def test_plan_por_defecto_y_limite(entorno):
    from backend import suscripcion_datos

    db, client, h_titular, _h_admin, _h_otro = entorno
    mia = _mia(client, h_titular)
    assert (mia["plan"]["clave"], mia["motivo"], mia["uso_rfc"], mia["puede_agregar_rfc"]) == ("prueba", "sin_suscripcion", 0, True)
    _verificar(db, TITULAR)

    # Una empresa que administra (primer vinculado) agota el plan de prueba.
    _vincular(db, TITULAR, RFCS[0])
    mia = _mia(client, h_titular)
    assert (mia["uso_rfc"], mia["puede_agregar_rfc"]) == (1, False)
    with pytest.raises(suscripcion_datos.LimiteRfcAlcanzado, match="Prueba permite 1 RFC"):
        _verificar(db, TITULAR)

    # Donde solo es contador (otro la creó antes) no cuenta.
    _vincular(db, OTRO, RFCS[1], created_at="2026-01-01")
    _vincular(db, TITULAR, RFCS[1], created_at="2026-02-01")
    assert _mia(client, h_titular)["uso_rfc"] == 1


def test_asignacion_manual_vigencia_y_edicion_de_planes(entorno):
    db, client, h_titular, h_admin, h_otro = entorno
    _vincular(db, TITULAR, RFCS[0])
    titular = _id(db, TITULAR)
    url = f"/api/v1/suscripcion/admin/cuentas/{titular}"

    # Solo el admin de la plataforma asigna planes.
    assert client.put(url, headers=h_otro, json={"plan_clave": "despacho"}).status_code == 403
    assert client.get("/api/v1/suscripcion/admin/cuentas", headers=h_otro).status_code == 403
    r = client.put(url, headers=h_admin, json={"plan_clave": "despacho", "vigente_hasta": "2099-12-31", "notas": "SPEI"})
    assert r.status_code == 200, r.text
    mia = _mia(client, h_titular)
    assert (mia["plan"]["clave"], mia["plan"]["max_rfc"], mia["puede_agregar_rfc"]) == ("despacho", 15, True)
    assert mia["plan"]["precio_mensual"] == "1499.00"

    # La lista del admin la muestra con su uso.
    cuentas = client.get("/api/v1/suscripcion/admin/cuentas", headers=h_admin, params={"q": "m7-titular"}).json()
    assert [(c["email"], c["plan_clave"], c["uso_rfc"]) for c in cuentas] == [(TITULAR, "despacho", 1)]
    # % y _ en la búsqueda son literales.
    assert client.get("/api/v1/suscripcion/admin/cuentas", headers=h_admin, params={"q": "m7_titular"}).json() == []
    assert client.get("/api/v1/suscripcion/admin/cuentas", headers=h_admin, params={"q": "m7%titular"}).json() == []

    # Vencida o suspendida vuelve al plan por defecto.
    ayer = (date.today() - timedelta(days=2)).isoformat()
    client.put(url, headers=h_admin, json={"plan_clave": "despacho", "vigente_hasta": ayer})
    assert _mia(client, h_titular)["motivo"] == "vencida"
    client.put(url, headers=h_admin, json={"plan_clave": "despacho", "estado": "suspendida"})
    assert (_mia(client, h_titular)["plan"]["clave"], _mia(client, h_titular)["motivo"]) == ("prueba", "suspendida")

    # Editar el plan cambia el límite de quien lo tiene.
    client.put(url, headers=h_admin, json={"plan_clave": "despacho"})
    r = client.put("/api/v1/suscripcion/admin/planes/despacho", headers=h_admin,
                   json={"nombre": "Despacho", "precio_mensual": "1499", "max_rfc": 1, "activo": True})
    assert r.status_code == 200, r.text
    assert _mia(client, h_titular)["puede_agregar_rfc"] is False
    assert client.put("/api/v1/suscripcion/admin/planes/despacho", headers=h_otro,
                      json={"nombre": "x", "precio_mensual": 0, "max_rfc": 1}).status_code == 403

    acciones = {f["accion"] for f in db.query_all(
        "SELECT accion FROM auditoria WHERE usuario_id = %s", (_id(db, ADMIN),))}
    assert {"suscripcion.asignar", "suscripcion.editar_plan"} <= acciones


def test_admin_de_plataforma_no_tiene_limite(entorno):
    from backend import suscripcion_datos

    db, client, _h_titular, h_admin, _h_otro = entorno
    for rfc in RFCS:
        _vincular(db, ADMIN, rfc)
    mia = _mia(client, h_admin)
    assert (mia["uso_rfc"], mia["puede_agregar_rfc"], mia["es_admin_plataforma"]) == (3, True, True)
    _verificar(db, ADMIN)


def test_planes_activos(entorno):
    _db, client, h_titular, _h_admin, _h_otro = entorno
    planes = client.get("/api/v1/suscripcion/planes", headers=h_titular).json()
    claves = [p["clave"] for p in planes]
    assert claves[:1] == ["prueba"] and "ilimitado" in claves
    assert next(p for p in planes if p["clave"] == "ilimitado")["max_rfc"] is None


def test_dos_altas_simultaneas_no_pasan_el_limite(entorno):
    """Con el plan de prueba (1 RFC), dos altas concurrentes de la misma cuenta: el
    candado por cuenta hace que la segunda cuente después del commit de la primera."""
    import threading
    import time

    from backend import suscripcion_datos

    db, client, h_titular, _h_admin, _h_otro = entorno
    titular = _id(db, TITULAR)
    barrera = threading.Barrier(2)
    resultados = []

    def alta(rfc):
        barrera.wait()
        try:
            with db.get_conn() as conn, conn.cursor() as cur:
                suscripcion_datos.verificar_alta_rfc(cur, titular)
                time.sleep(0.3)  # sin el candado, la otra alta contaría aquí y también pasaría
                cur.execute("INSERT INTO empresas (rfc, razon_social) VALUES (%s, 'Concurrente') RETURNING id", (rfc,))
                empresa_id = cur.fetchone()[0]
                cur.execute("INSERT INTO usuario_empresas (usuario_id, empresa_id, rol) VALUES (%s, %s, 'administrador')",
                            (titular, empresa_id))
            resultados.append("ok")
        except suscripcion_datos.LimiteRfcAlcanzado:
            resultados.append("limite")

    hilos = [threading.Thread(target=alta, args=(rfc,)) for rfc in RFCS[:2]]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    assert sorted(resultados) == ["limite", "ok"]
    assert _mia(client, h_titular)["uso_rfc"] == 1


def test_historial_de_asignaciones(entorno):
    """M7.2: cada asignación queda en el historial; la cuenta lo ve sin notas internas
    ni quién asignó, el administrador de la plataforma lo ve completo."""
    db, client, h_titular, h_admin, h_otro = entorno
    titular = _id(db, TITULAR)
    url = f"/api/v1/suscripcion/admin/cuentas/{titular}"
    assert client.get("/api/v1/suscripcion/historial", headers=h_titular).json() == []

    assert client.put(url, headers=h_admin, json={"plan_clave": "basico", "notas": "pago SPEI 01/10"}).status_code == 200
    assert client.put(url, headers=h_admin, json={"plan_clave": "despacho", "vigente_hasta": "2099-12-31"}).status_code == 200

    mio = client.get("/api/v1/suscripcion/historial", headers=h_titular).json()
    assert [(f["plan_clave"], f["plan_nombre"], f["vigente_hasta"]) for f in mio] == [
        ("despacho", "Despacho", "2099-12-31"), ("basico", "Básico", None)]
    assert all(set(f) == {"fecha", "plan_clave", "plan_nombre", "estado", "vigente_hasta"} for f in mio)

    completo = client.get(f"{url}/historial", headers=h_admin).json()
    assert [(f["notas"], f["asignada_por"]) for f in completo] == [(None, ADMIN), ("pago SPEI 01/10", ADMIN)]
    assert client.get(f"{url}/historial", headers=h_otro).status_code == 403
    assert client.get("/api/v1/suscripcion/admin/cuentas/00000000-0000-0000-0000-000000000000/historial",
                      headers=h_admin).status_code == 404
    # Una cuenta no ve el historial de otra.
    assert client.get("/api/v1/suscripcion/historial", headers=h_otro).json() == []


def test_datos_fiscales_pagos_y_aviso_de_vencimiento(entorno):
    """M7.2 (D10): el admin captura datos fiscales y registra pagos a mano; la cuenta los
    ve sin quién los registró y recibe el aviso de vencimiento próximo."""
    from datetime import timedelta

    from backend import suscripcion_datos

    db, client, h_titular, h_admin, h_otro = entorno
    titular = _id(db, TITULAR)
    base = f"/api/v1/suscripcion/admin/cuentas/{titular}"
    fiscales = {"rfc": "ace010101aa1", "razon_social": "ACME SA DE CV", "regimen_fiscal": "601",
                "codigo_postal": "68000", "uso_cfdi": "G03"}

    assert client.get("/api/v1/suscripcion/datos-fiscales", headers=h_titular).json() is None
    assert client.put(f"{base}/datos-fiscales", headers=h_otro, json=fiscales).status_code == 403
    assert client.put(f"{base}/datos-fiscales", headers=h_admin, json={**fiscales, "regimen_fiscal": "612"}).status_code == 422
    r = client.put(f"{base}/datos-fiscales", headers=h_admin, json=fiscales)
    assert r.status_code == 200, r.text
    mios = client.get("/api/v1/suscripcion/datos-fiscales", headers=h_titular).json()
    assert (mios["rfc"], mios["uso_cfdi"]) == ("ACE010101AA1", "G03")

    # Pagos: solo el admin registra; la cuenta ve los suyos sin quién los registró.
    hoy = suscripcion_datos.hoy()
    assert client.post(f"{base}/pagos", headers=h_otro, json={"fecha": hoy.isoformat(), "monto": "1"}).status_code == 403
    assert client.post(f"{base}/pagos", headers=h_admin,
                       json={"fecha": (hoy + timedelta(days=1)).isoformat(), "monto": "1"}).status_code == 422
    for dias, monto, folio in ((40, "1499", "A-1"), (10, "1499.50", None)):
        r = client.post(f"{base}/pagos", headers=h_admin,
                        json={"fecha": (hoy - timedelta(days=dias)).isoformat(), "monto": monto,
                              "referencia": "SPEI", "folio_cfdi": folio})
        assert r.status_code == 201, r.text
    mios = client.get("/api/v1/suscripcion/pagos", headers=h_titular).json()
    assert [(p["monto"], p["folio_cfdi"]) for p in mios] == [("1499.50", None), ("1499.00", "A-1")]
    assert all("registrado_por" not in p for p in mios)
    completos = client.get(f"{base}/pagos", headers=h_admin).json()
    assert {p["registrado_por"] for p in completos} == {ADMIN}
    assert client.get("/api/v1/suscripcion/pagos", headers=h_otro).json() == []
    acciones = [f["accion"] for f in db.query_all(
        "SELECT accion FROM auditoria WHERE entidad_id = %s ORDER BY creado_en", (titular,))]
    assert acciones.count("suscripcion.registrar_pago") == 2 and "suscripcion.datos_fiscales" in acciones

    # Aviso: vence en 5 días → 5; en 30, sin aviso.
    for dias, aviso in ((5, 5), (30, None)):
        vence = (hoy + timedelta(days=dias)).isoformat()
        assert client.put(base, headers=h_admin, json={"plan_clave": "basico", "vigente_hasta": vence}).status_code == 200
        assert _mia(client, h_titular)["dias_para_vencer"] == aviso
        [cuenta] = client.get("/api/v1/suscripcion/admin/cuentas", headers=h_admin, params={"q": "m7-titular"}).json()
        assert cuenta["dias_para_vencer"] == aviso
