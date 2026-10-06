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


def test_datos_fiscales_los_editan_la_cuenta_y_el_admin(entorno):
    db, client, h_titular, h_admin, h_otro = entorno
    titular = _id(db, TITULAR)
    base = f"/api/v1/suscripcion/admin/cuentas/{titular}"
    fiscales = {"rfc": "ace010101aa1", "razon_social": "ACME SA DE CV", "regimen_fiscal": "601",
                "codigo_postal": "68000", "uso_cfdi": "G03", "correo": "Facturas@ACME.mx"}

    assert client.get("/api/v1/suscripcion/datos-fiscales", headers=h_titular).json() is None
    assert client.put(f"{base}/datos-fiscales", headers=h_otro, json=fiscales).status_code == 403
    assert client.put("/api/v1/suscripcion/datos-fiscales", headers=h_titular,
                      json={**fiscales, "regimen_fiscal": "612"}).status_code == 422
    # La cuenta los captura…
    r = client.put("/api/v1/suscripcion/datos-fiscales", headers=h_titular, json=fiscales)
    assert r.status_code == 200, r.text
    assert (r.json()["rfc"], r.json()["correo"]) == ("ACE010101AA1", "facturas@acme.mx")
    # …y el administrador los corrige; la cuenta ve la corrección.
    r = client.put(f"{base}/datos-fiscales", headers=h_admin, json={**fiscales, "uso_cfdi": "S01"})
    assert r.status_code == 200, r.text
    assert client.get("/api/v1/suscripcion/datos-fiscales", headers=h_titular).json()["uso_cfdi"] == "S01"
    assert client.get(f"{base}/datos-fiscales", headers=h_admin).json()["uso_cfdi"] == "S01"
    # Otra cuenta no ve ni toca los de esta.
    assert client.get("/api/v1/suscripcion/datos-fiscales", headers=h_otro).json() is None
    por = [f["metadata"]["por"] for f in db.query_all(
        "SELECT metadata FROM auditoria WHERE accion = 'suscripcion.datos_fiscales' AND entidad_id = %s "
        "ORDER BY creado_en", (titular,))]
    assert por == ["cuenta", "admin"]


def test_pagos_extienden_la_vigencia_y_anular_la_revierte(entorno):
    from datetime import timedelta

    from backend import suscripcion_datos

    db, client, h_titular, h_admin, h_otro = entorno
    titular = _id(db, TITULAR)
    base = f"/api/v1/suscripcion/admin/cuentas/{titular}"
    hoy = suscripcion_datos.hoy()

    def pagar(dias_atras, monto, meses=1, **extra):
        return client.post(f"{base}/pagos", headers=h_admin,
                           json={"fecha": (hoy - timedelta(days=dias_atras)).isoformat(), "monto": monto,
                                 "meses": meses, "referencia": "SPEI", **extra})

    # Sin plan asignado no se registran pagos.
    assert pagar(0, "1").status_code == 409
    vence = hoy + timedelta(days=10)
    assert client.put(base, headers=h_admin, json={"plan_clave": "basico", "vigente_hasta": vence.isoformat()}).status_code == 200

    assert client.post(f"{base}/pagos", headers=h_otro, json={"fecha": hoy.isoformat(), "monto": "1"}).status_code == 403
    assert pagar(-1, "1").status_code == 422      # fecha futura

    # Un pago de 1 mes extiende desde la vigencia (todavía no vencía).
    r = pagar(0, "499", meses=1, folio_cfdi="A-1")
    assert r.status_code == 201, r.text
    primero = r.json()
    from backend.suscripcion_pagos import sumar_meses
    assert primero["vigente_hasta_nueva"] == sumar_meses(vence, 1).isoformat()
    assert _mia(client, h_titular)["vigente_hasta"] == primero["vigente_hasta_nueva"]
    # El segundo, de 12 meses, parte de la nueva vigencia.
    segundo = pagar(0, "4990.50", meses=12, uuid_cfdi="6f9619ff-8b86-d011-b42d-00c04fc964ff").json()
    assert segundo["vigente_hasta_nueva"] == sumar_meses(sumar_meses(vence, 1), 12).isoformat()

    mios = client.get("/api/v1/suscripcion/pagos", headers=h_titular).json()
    assert {p["monto"] for p in mios} == {"499.00", "4990.50"}
    assert all("registrado_por" not in p for p in mios)
    assert {p["registrado_por"] for p in client.get(f"{base}/pagos", headers=h_admin).json()} == {ADMIN}
    assert client.get("/api/v1/suscripcion/pagos", headers=h_otro).json() == []

    # Anular el primero no revierte: el segundo ya movió la vigencia después.
    url_primero = f"{base}/pagos/{primero['id']}/anular"
    assert client.post(url_primero, headers=h_admin, json={}).status_code == 422
    assert client.post(url_primero, headers=h_otro, json={"motivo": "x"}).status_code == 403
    r = client.post(url_primero, headers=h_admin, json={"motivo": "duplicado"})
    assert (r.status_code, r.json()) == (200, {"vigencia_revertida": False,
                                               "vigente_hasta": segundo["vigente_hasta_nueva"]})
    assert client.post(url_primero, headers=h_admin, json={"motivo": "otra vez"}).status_code == 404
    # Anular el segundo revierte en cadena: su anterior es la que dejó el primero, que ya
    # está anulado, así que la vigencia vuelve a la de antes de los dos pagos.
    r = client.post(f"{base}/pagos/{segundo['id']}/anular", headers=h_admin, json={"motivo": "rebotó"})
    assert r.json() == {"vigencia_revertida": True, "vigente_hasta": vence.isoformat()}
    assert _mia(client, h_titular)["vigente_hasta"] == vence.isoformat()
    estados = {p["id"]: (p["estado"], p["motivo_anulacion"]) for p in client.get(f"{base}/pagos", headers=h_admin).json()}
    assert estados == {primero["id"]: ("anulado", "duplicado"), segundo["id"]: ("anulado", "rebotó")}
    # La cuenta ve el estado pero no el motivo interno.
    assert {p["estado"] for p in client.get("/api/v1/suscripcion/pagos", headers=h_titular).json()} == {"anulado"}

    # Un pago con la suscripción ya vencida extiende desde la fecha del pago.
    assert client.put(base, headers=h_admin,
                      json={"plan_clave": "basico", "vigente_hasta": (hoy - timedelta(days=20)).isoformat()}).status_code == 200
    r = pagar(5, "499")
    assert r.json()["vigente_hasta_nueva"] == sumar_meses(hoy - timedelta(days=5), 1).isoformat()

    # Cada pago y cada anulación que movió la vigencia quedan en el historial.
    notas = [f["notas"] for f in client.get(f"{base}/historial", headers=h_admin).json()]
    assert notas.count("Pago anulado") == 1 and sum(1 for n in notas if n and n.startswith("Pago registrado")) == 3
    acciones = [f["accion"] for f in db.query_all("SELECT accion FROM auditoria WHERE entidad_id = %s", (titular,))]
    assert acciones.count("suscripcion.registrar_pago") == 3 and acciones.count("suscripcion.anular_pago") == 2


def test_avisos_y_lista_de_vencimientos(entorno):
    from datetime import timedelta

    from backend import suscripcion_datos

    db, client, h_titular, h_admin, h_otro = entorno
    hoy = suscripcion_datos.hoy()
    titular, otro = _id(db, TITULAR), _id(db, OTRO)
    url = "/api/v1/suscripcion/admin/vencimientos"
    assert client.get(url, headers=h_titular).status_code == 403

    def asignar(uid, dias, estado="activa"):
        r = client.put(f"/api/v1/suscripcion/admin/cuentas/{uid}", headers=h_admin,
                       json={"plan_clave": "basico", "estado": estado, "vigente_hasta": (hoy + timedelta(days=dias)).isoformat()})
        assert r.status_code == 200, r.text

    # Vence en 5 días → aviso 5; vencida hace 3 → -3; en 30 → sin aviso.
    for dias, aviso in ((5, 5), (-3, -3), (30, None)):
        asignar(titular, dias)
        assert _mia(client, h_titular)["dias_para_vencer"] == aviso
        [cuenta] = client.get("/api/v1/suscripcion/admin/cuentas", headers=h_admin, params={"q": "m7-titular"}).json()
        assert cuenta["dias_para_vencer"] == aviso

    asignar(titular, -3)
    asignar(otro, 2)
    propias = [v for v in client.get(url, headers=h_admin).json() if v["email"] in (TITULAR, OTRO)]
    assert [(v["email"], v["dias_para_vencer"]) for v in propias] == [(TITULAR, -3), (OTRO, 2)]
    # Una suspendida no aparece (se explica con su estado).
    asignar(otro, 2, estado="suspendida")
    assert all(v["email"] != OTRO for v in client.get(url, headers=h_admin).json())


def test_anular_solo_el_ultimo_vuelve_al_pago_activo_anterior(entorno):
    """Sin pagos anulados antes, anular el último regresa a la vigencia que dejó el pago
    anterior (que sigue activo), no más atrás."""
    from datetime import timedelta

    from backend import suscripcion_datos
    from backend.suscripcion_pagos import sumar_meses

    db, client, _h_titular, h_admin, _h_otro = entorno
    base = f"/api/v1/suscripcion/admin/cuentas/{_id(db, TITULAR)}"
    hoy = suscripcion_datos.hoy()
    vence = hoy + timedelta(days=10)
    assert client.put(base, headers=h_admin, json={"plan_clave": "basico", "vigente_hasta": vence.isoformat()}).status_code == 200
    pagos = [client.post(f"{base}/pagos", headers=h_admin, json={"fecha": hoy.isoformat(), "monto": "499"}).json()
             for _ in range(2)]
    r = client.post(f"{base}/pagos/{pagos[1]['id']}/anular", headers=h_admin, json={"motivo": "error"})
    assert r.json() == {"vigencia_revertida": True, "vigente_hasta": sumar_meses(vence, 1).isoformat()}


def test_dos_pagos_simultaneos_se_suman(entorno):
    """La suscripción se bloquea al pagar: dos pagos al mismo tiempo extienden uno después
    del otro (dos meses), no los dos desde la misma vigencia."""
    import threading
    from datetime import timedelta

    from fastapi.testclient import TestClient

    import backend.main_api as main
    from backend import suscripcion_datos
    from backend.suscripcion_pagos import sumar_meses

    db, client, h_titular, h_admin, _h_otro = entorno
    base = f"/api/v1/suscripcion/admin/cuentas/{_id(db, TITULAR)}"
    hoy = suscripcion_datos.hoy()
    vence = hoy + timedelta(days=10)
    assert client.put(base, headers=h_admin, json={"plan_clave": "basico", "vigente_hasta": vence.isoformat()}).status_code == 200

    barrera = threading.Barrier(2)
    resultados = []

    def pagar():
        propio = TestClient(main.app)
        barrera.wait()
        resultados.append(propio.post(f"{base}/pagos", headers=h_admin,
                                      json={"fecha": hoy.isoformat(), "monto": "499"}).json()["vigente_hasta_nueva"])

    hilos = [threading.Thread(target=pagar) for _ in range(2)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    uno, dos = sumar_meses(vence, 1).isoformat(), sumar_meses(sumar_meses(vence, 1), 1).isoformat()
    assert sorted(resultados) == [uno, dos]
    assert _mia(client, h_titular)["vigente_hasta"] == dos
