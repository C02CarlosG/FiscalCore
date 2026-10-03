"""Tests del router backend/routers/sat.py (Día 24).

DB mockeada sobre `backend.db`. `validar_acceso_empresa` se monkeypatchea a
nivel de módulo de `sat.py` (importada arriba, igual que en los demás
routers). `cargar_fiel`/`solicitar_descarga`/`verificar_solicitud` también
se monkeypatchean en `backend.routers.sat` porque ahí quedan importadas al
cargar el módulo.

`guardar_fiel`/`estado_fiel`/`eliminar_fiel`/`obtener_signer` en cambio se
monkeypatchean en su módulo de origen (`backend.fiel_store`): `sat.py` los
importa con un `from ..fiel_store import ...` LOCAL dentro de cada función,
así que la búsqueda del nombre ocurre en tiempo de llamada contra
`backend.fiel_store`, no contra el namespace de `sat.py`.

Los endpoints `/descargar` y `/fiel/sync` agendan un `BackgroundTasks` que
Starlette's TestClient ejecuta de forma síncrona dentro de la misma llamada
HTTP (antes de devolver la respuesta al test). Para no arrastrar esa
ejecución real (que en `/fiel/sync` incluye un loop con `time.sleep`) se
monkeypatchean las funciones de background (`_importar_paquetes_bg`,
`_sync_completo_bg`) directamente — el objetivo aquí es la capa de router
(parseo/validación/respuesta), no los workers, que son otra unidad."""
import backend.fiel_store as fiel_store
from fastapi.testclient import TestClient

import backend.main_api as main
from backend import db, sat_sync
from backend.deps import get_current_user
from backend.routers import sat
from backend.sat_fiel import FIELError

client = TestClient(main.app)

EMPRESA = "emp-1"

_CER = ("fiel.cer", b"cer-bytes", "application/x-x509-ca-cert")
_KEY = ("fiel.key", b"key-bytes", "application/octet-stream")


def _auth(monkeypatch):
    main.app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "user_id": "u1"}
    monkeypatch.setattr(sat, "validar_acceso_empresa", lambda *a, **k: None)


def _teardown():
    main.app.dependency_overrides.clear()


class _FakeSigner:
    pass


# ─── POST /sat/solicitar ────────────────────────────────────────────────────────

def test_solicitar_descarga_exitoso(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {"rfc": "TEST010101AAA"})
    monkeypatch.setattr(db, "execute", lambda sql, params=(), returning=False: (
        {"id": "sol-1"} if returning else None
    ))
    monkeypatch.setattr(sat, "cargar_fiel", lambda *a, **k: _FakeSigner())
    monkeypatch.setattr(sat, "solicitar_descarga", lambda *a, **k: "id-sat-1")

    try:
        r = client.post(
            "/api/v1/sat/solicitar",
            data={
                "empresa_id": EMPRESA, "tipo": "emitidos",
                "fecha_inicio": "2026-01-01", "fecha_fin": "2026-01-31",
                "password": "x",
            },
            files={"cer_file": _CER, "key_file": _KEY},
        )
    finally:
        _teardown()

    assert r.status_code == 200
    body = r.json()
    assert body["solicitud_id"] == "sol-1"
    assert body["id_solicitud_sat"] == "id-sat-1"
    assert body["estado"] == "solicitado"


def test_solicitar_descarga_empresa_no_encontrada_da_404(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_one", lambda *a, **k: None)

    try:
        r = client.post(
            "/api/v1/sat/solicitar",
            data={
                "empresa_id": EMPRESA, "tipo": "emitidos",
                "fecha_inicio": "2026-01-01", "fecha_fin": "2026-01-31",
                "password": "x",
            },
            files={"cer_file": _CER, "key_file": _KEY},
        )
    finally:
        _teardown()

    assert r.status_code == 404


def test_solicitar_descarga_tipo_invalido_da_400(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {"rfc": "TEST010101AAA"})

    try:
        r = client.post(
            "/api/v1/sat/solicitar",
            data={
                "empresa_id": EMPRESA, "tipo": "no-valido",
                "fecha_inicio": "2026-01-01", "fecha_fin": "2026-01-31",
                "password": "x",
            },
            files={"cer_file": _CER, "key_file": _KEY},
        )
    finally:
        _teardown()

    assert r.status_code == 400


def test_solicitar_descarga_fechas_invalidas_da_400(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {"rfc": "TEST010101AAA"})

    try:
        r = client.post(
            "/api/v1/sat/solicitar",
            data={
                "empresa_id": EMPRESA, "tipo": "emitidos",
                "fecha_inicio": "no-es-fecha", "fecha_fin": "2026-01-31",
                "password": "x",
            },
            files={"cer_file": _CER, "key_file": _KEY},
        )
    finally:
        _teardown()

    assert r.status_code == 400


def test_solicitar_descarga_fiel_invalida_da_422(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {"rfc": "TEST010101AAA"})

    def _raise(*a, **k):
        raise FIELError("contraseña incorrecta")
    monkeypatch.setattr(sat, "cargar_fiel", _raise)

    try:
        r = client.post(
            "/api/v1/sat/solicitar",
            data={
                "empresa_id": EMPRESA, "tipo": "emitidos",
                "fecha_inicio": "2026-01-01", "fecha_fin": "2026-01-31",
                "password": "x",
            },
            files={"cer_file": _CER, "key_file": _KEY},
        )
    finally:
        _teardown()

    assert r.status_code == 422


def test_solicitar_descarga_error_sat_da_502(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {"rfc": "TEST010101AAA"})
    monkeypatch.setattr(db, "execute", lambda sql, params=(), returning=False: (
        {"id": "sol-1"} if returning else None
    ))
    monkeypatch.setattr(sat, "cargar_fiel", lambda *a, **k: _FakeSigner())

    def _raise(*a, **k):
        raise FIELError("SAT no disponible")
    monkeypatch.setattr(sat, "solicitar_descarga", _raise)

    try:
        r = client.post(
            "/api/v1/sat/solicitar",
            data={
                "empresa_id": EMPRESA, "tipo": "emitidos",
                "fecha_inicio": "2026-01-01", "fecha_fin": "2026-01-31",
                "password": "x",
            },
            files={"cer_file": _CER, "key_file": _KEY},
        )
    finally:
        _teardown()

    assert r.status_code == 502


def test_solicitar_descarga_sin_auth_da_401():
    r = client.post(
        "/api/v1/sat/solicitar",
        data={
            "empresa_id": EMPRESA, "tipo": "emitidos",
            "fecha_inicio": "2026-01-01", "fecha_fin": "2026-01-31",
        "password": "x",
        },
        files={"cer_file": _CER, "key_file": _KEY},
    )
    assert r.status_code == 401


# ─── GET /sat/solicitudes ───────────────────────────────────────────────────────

def test_listar_solicitudes(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_all", lambda *a, **k: [
        {"id": "sol-1", "tipo": "emitidos", "estado": "terminado"},
    ])

    try:
        r = client.get(f"/api/v1/sat/solicitudes?empresa_id={EMPRESA}")
    finally:
        _teardown()

    assert r.status_code == 200
    assert r.json()[0]["id"] == "sol-1"


# ─── POST /sat/solicitudes/{id}/verificar ───────────────────────────────────────

def test_verificar_solicitud_no_encontrada_da_404(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_one", lambda *a, **k: None)

    try:
        r = client.post(
            "/api/v1/sat/solicitudes/sol-x/verificar",
            data={"password": "x"},
            files={"cer_file": _CER, "key_file": _KEY},
        )
    finally:
        _teardown()

    assert r.status_code == 404


def test_verificar_solicitud_sin_id_sat_da_400(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {
        "id": "sol-1", "empresa_id": EMPRESA, "id_solicitud_sat": None,
    })

    try:
        r = client.post(
            "/api/v1/sat/solicitudes/sol-1/verificar",
            data={"password": "x"},
            files={"cer_file": _CER, "key_file": _KEY},
        )
    finally:
        _teardown()

    assert r.status_code == 400


def test_verificar_solicitud_exitosa_mapea_terminada_a_terminado(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {
        "id": "sol-1", "empresa_id": EMPRESA, "id_solicitud_sat": "id-sat-1",
    })
    monkeypatch.setattr(db, "execute", lambda *a, **k: None)
    monkeypatch.setattr(sat, "cargar_fiel", lambda *a, **k: _FakeSigner())
    monkeypatch.setattr(sat, "verificar_solicitud", lambda *a, **k: {
        "estado": "Terminada", "id_paquetes": ["pkg1"], "num_cfdi": 10, "mensaje": "OK",
    })

    try:
        r = client.post(
            "/api/v1/sat/solicitudes/sol-1/verificar",
            data={"password": "x"},
            files={"cer_file": _CER, "key_file": _KEY},
        )
    finally:
        _teardown()

    assert r.status_code == 200
    body = r.json()
    assert body["estado"] == "terminado"
    assert body["num_cfdi"] == 10
    assert body["id_paquetes"] == ["pkg1"]


def test_verificar_solicitud_error_sat_da_502(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {
        "id": "sol-1", "empresa_id": EMPRESA, "id_solicitud_sat": "id-sat-1",
    })
    monkeypatch.setattr(sat, "cargar_fiel", lambda *a, **k: _FakeSigner())

    def _raise(*a, **k):
        raise FIELError("timeout SAT")
    monkeypatch.setattr(sat, "verificar_solicitud", _raise)

    try:
        r = client.post(
            "/api/v1/sat/solicitudes/sol-1/verificar",
            data={"password": "x"},
            files={"cer_file": _CER, "key_file": _KEY},
        )
    finally:
        _teardown()

    assert r.status_code == 502


# ─── POST /sat/solicitudes/{id}/descargar ───────────────────────────────────────

def test_descargar_cfdi_no_encontrada_da_404(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_one", lambda *a, **k: None)

    try:
        r = client.post(
            "/api/v1/sat/solicitudes/sol-x/descargar",
            data={"password": "x", "id_paquetes": '["pkg1"]'},
            files={"cer_file": _CER, "key_file": _KEY},
        )
    finally:
        _teardown()

    assert r.status_code == 404


def test_descargar_cfdi_id_paquetes_invalido_da_400(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {
        "id": "sol-1", "empresa_id": EMPRESA, "periodo_inicio": "2026-01",
    })
    monkeypatch.setattr(sat, "cargar_fiel", lambda *a, **k: _FakeSigner())

    try:
        r = client.post(
            "/api/v1/sat/solicitudes/sol-1/descargar",
            data={"password": "x", "id_paquetes": "no-es-json"},
            files={"cer_file": _CER, "key_file": _KEY},
        )
    finally:
        _teardown()

    assert r.status_code == 400


def test_descargar_cfdi_exitoso_agenda_background(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {
        "id": "sol-1", "empresa_id": EMPRESA, "periodo_inicio": "2026-01",
    })
    monkeypatch.setattr(sat, "cargar_fiel", lambda *a, **k: _FakeSigner())
    sqls = []
    monkeypatch.setattr(db, "execute", lambda sql, params=(), returning=False: sqls.append(sql))
    llamadas_bg = []
    monkeypatch.setattr(sat, "_importar_paquetes_bg", lambda **kw: llamadas_bg.append(kw))

    try:
        r = client.post(
            "/api/v1/sat/solicitudes/sol-1/descargar",
            data={"password": "x", "id_paquetes": '["pkg1", "pkg2"]'},
            files={"cer_file": _CER, "key_file": _KEY},
        )
    finally:
        _teardown()

    assert r.status_code == 200
    body = r.json()
    assert body["paquetes"] == 2
    assert len(llamadas_bg) == 1
    assert llamadas_bg[0]["paquetes"] == ["pkg1", "pkg2"]
    # La importación acumula por paquete: arranca con los contadores en cero.
    assert "paquetes_descargados=0, cfdi_importados=0" in sqls[0]


# ─── POST /sat/empresas/{id}/fiel/guardar ───────────────────────────────────────

def test_guardar_fiel_exitoso(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {"id": EMPRESA})
    monkeypatch.setattr(fiel_store, "guardar_fiel", lambda **kw: {
        "rfc": "TEST010101AAA", "vigente_hasta": "2027-01-01", "tiene_fiel": True,
    })

    try:
        r = client.post(
            f"/api/v1/sat/empresas/{EMPRESA}/fiel/guardar",
            data={"password": "x"},
            files={"cer_file": _CER, "key_file": _KEY},
        )
    finally:
        _teardown()

    assert r.status_code == 200
    assert r.json()["tiene_fiel"] is True


def test_guardar_fiel_valida_contra_el_rfc_de_la_empresa(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {"id": EMPRESA, "rfc": "TEST010101AAA"})
    recibido = {}
    monkeypatch.setattr(fiel_store, "guardar_fiel", lambda **kw: recibido.update(kw) or {"guardada": True})

    try:
        r = client.post(
            f"/api/v1/sat/empresas/{EMPRESA}/fiel/guardar",
            data={"password": "x"},
            files={"cer_file": _CER, "key_file": _KEY},
        )
    finally:
        _teardown()

    assert r.status_code == 200
    assert recibido["rfc_esperado"] == "TEST010101AAA"


def test_guardar_fiel_empresa_no_encontrada_da_404(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_one", lambda *a, **k: None)

    try:
        r = client.post(
            f"/api/v1/sat/empresas/{EMPRESA}/fiel/guardar",
            data={"password": "x"},
            files={"cer_file": _CER, "key_file": _KEY},
        )
    finally:
        _teardown()

    assert r.status_code == 404


def test_guardar_fiel_invalida_da_422(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {"id": EMPRESA})

    def _raise(**kw):
        raise ValueError("FIEL inválida: contraseña incorrecta")
    monkeypatch.setattr(fiel_store, "guardar_fiel", _raise)

    try:
        r = client.post(
            f"/api/v1/sat/empresas/{EMPRESA}/fiel/guardar",
            data={"password": "x"},
            files={"cer_file": _CER, "key_file": _KEY},
        )
    finally:
        _teardown()

    assert r.status_code == 422


def test_guardar_fiel_error_runtime_da_500(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {"id": EMPRESA})

    def _raise(**kw):
        raise RuntimeError("FIEL_ENCRYPTION_KEY no configurada")
    monkeypatch.setattr(fiel_store, "guardar_fiel", _raise)

    try:
        r = client.post(
            f"/api/v1/sat/empresas/{EMPRESA}/fiel/guardar",
            data={"password": "x"},
            files={"cer_file": _CER, "key_file": _KEY},
        )
    finally:
        _teardown()

    assert r.status_code == 500


# ─── GET /sat/empresas/{id}/fiel/estado ─────────────────────────────────────────

def test_estado_fiel_con_fiel_guardada(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(fiel_store, "estado_fiel", lambda db_, eid: {
        "tiene_fiel": True, "rfc": "TEST010101AAA", "vencida": False,
    })

    try:
        r = client.get(f"/api/v1/sat/empresas/{EMPRESA}/fiel/estado")
    finally:
        _teardown()

    assert r.status_code == 200
    assert r.json()["tiene_fiel"] is True


def test_estado_fiel_sin_fiel_guardada(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(fiel_store, "estado_fiel", lambda db_, eid: None)

    try:
        r = client.get(f"/api/v1/sat/empresas/{EMPRESA}/fiel/estado")
    finally:
        _teardown()

    assert r.status_code == 200
    assert r.json() == {"tiene_fiel": False}


# ─── DELETE /sat/empresas/{id}/fiel ─────────────────────────────────────────────

def test_eliminar_fiel_exitoso(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(fiel_store, "eliminar_fiel", lambda db_, eid: True)

    try:
        r = client.delete(f"/api/v1/sat/empresas/{EMPRESA}/fiel")
    finally:
        _teardown()

    assert r.status_code == 200
    assert r.json() == {"eliminada": True}


def test_eliminar_fiel_no_existia(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(fiel_store, "eliminar_fiel", lambda db_, eid: False)

    try:
        r = client.delete(f"/api/v1/sat/empresas/{EMPRESA}/fiel")
    finally:
        _teardown()

    assert r.json() == {"eliminada": False}


# ─── POST /sat/empresas/{id}/fiel/sync ──────────────────────────────────────────

def test_sync_completo_empresa_no_encontrada_da_404(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_one", lambda *a, **k: None)

    try:
        r = client.post(
            f"/api/v1/sat/empresas/{EMPRESA}/fiel/sync",
            data={"tipo": "emitidos", "periodo": "2026-01"},
        )
    finally:
        _teardown()

    assert r.status_code == 404


def test_sync_completo_sin_fiel_guardada_da_422(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {"rfc": "TEST010101AAA"})
    monkeypatch.setattr(fiel_store, "estado_fiel", lambda db_, eid: None)

    try:
        r = client.post(
            f"/api/v1/sat/empresas/{EMPRESA}/fiel/sync",
            data={"tipo": "emitidos", "periodo": "2026-01"},
        )
    finally:
        _teardown()

    assert r.status_code == 422


def test_sync_completo_fiel_vencida_da_422(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {"rfc": "TEST010101AAA"})
    monkeypatch.setattr(fiel_store, "estado_fiel", lambda db_, eid: {"vencida": True})

    try:
        r = client.post(
            f"/api/v1/sat/empresas/{EMPRESA}/fiel/sync",
            data={"tipo": "emitidos", "periodo": "2026-01"},
        )
    finally:
        _teardown()

    assert r.status_code == 422


def test_sync_completo_tipo_invalido_da_400(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {"rfc": "TEST010101AAA"})
    monkeypatch.setattr(fiel_store, "estado_fiel", lambda db_, eid: {"vencida": False})
    monkeypatch.setattr(fiel_store, "obtener_signer", lambda db_, eid: _FakeSigner())

    try:
        r = client.post(
            f"/api/v1/sat/empresas/{EMPRESA}/fiel/sync",
            data={"tipo": "no-valido", "periodo": "2026-01"},
        )
    finally:
        _teardown()

    assert r.status_code == 400


def test_sync_completo_error_sat_al_solicitar_da_502(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {"rfc": "TEST010101AAA"})
    monkeypatch.setattr(fiel_store, "estado_fiel", lambda db_, eid: {"vencida": False})
    monkeypatch.setattr(fiel_store, "obtener_signer", lambda db_, eid: _FakeSigner())
    monkeypatch.setattr(db, "execute", lambda sql, params=(), returning=False: (
        {"id": "sol-1"} if returning else None
    ))

    def _raise(*a, **k):
        raise FIELError("SAT no disponible")
    monkeypatch.setattr(sat_sync, "solicitar_descarga", _raise)

    try:
        r = client.post(
            f"/api/v1/sat/empresas/{EMPRESA}/fiel/sync",
            data={"tipo": "emitidos", "periodo": "2026-01"},
        )
    finally:
        _teardown()

    assert r.status_code == 502


def test_sync_completo_exitoso_ambos_tipos_agenda_background(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {"rfc": "TEST010101AAA"})
    monkeypatch.setattr(fiel_store, "estado_fiel", lambda db_, eid: {"vencida": False})
    monkeypatch.setattr(fiel_store, "obtener_signer", lambda db_, eid: _FakeSigner())

    contador = {"n": 0}

    def _execute(sql, params=(), returning=False):
        if returning:
            contador["n"] += 1
            return {"id": f"sol-{contador['n']}"}
        return None
    monkeypatch.setattr(db, "execute", _execute)
    monkeypatch.setattr(sat_sync, "solicitar_descarga", lambda *a, **k: "id-sat-x")

    llamadas_bg = []
    monkeypatch.setattr(sat, "_sync_completo_bg", lambda **kw: llamadas_bg.append(kw))

    try:
        r = client.post(
            f"/api/v1/sat/empresas/{EMPRESA}/fiel/sync",
            data={"tipo": "ambos", "periodo": "2026-01"},
        )
    finally:
        _teardown()

    assert r.status_code == 200
    body = r.json()
    assert len(body["solicitudes"]) == 2
    assert {"emitidos", "recibidos"} == set(body["tipos"])
    assert len(llamadas_bg) == 1
    assert len(llamadas_bg[0]["solicitudes"]) == 2


def test_sync_completo_ventana_ya_en_curso_da_409(monkeypatch):
    import psycopg2.errors

    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {"rfc": "TEST010101AAA"})
    monkeypatch.setattr(fiel_store, "estado_fiel", lambda db_, eid: {"vencida": False})
    monkeypatch.setattr(fiel_store, "obtener_signer", lambda db_, eid: _FakeSigner())

    def _execute(sql, params=(), returning=False):
        raise psycopg2.errors.UniqueViolation("duplicada")
    monkeypatch.setattr(db, "execute", _execute)

    try:
        r = client.post(
            f"/api/v1/sat/empresas/{EMPRESA}/fiel/sync",
            data={"tipo": "emitidos", "periodo": "2026-01"},
        )
    finally:
        _teardown()

    assert r.status_code == 409
    assert "en curso" in r.json()["detail"]


# ─── POST /sat/empresas/{id}/fiel/sync/avanzar ──────────────────────────────────

_AVANZAR_URL = f"/api/v1/sat/empresas/{EMPRESA}/fiel/sync/avanzar"


def _solicitud_pendiente(estado="solicitado"):
    return {
        "id": "sol-1", "empresa_id": EMPRESA, "id_solicitud_sat": "id-sat-1",
        "estado": estado, "periodo_inicio": "2026-09",
    }


def _preparar_avanzar(monkeypatch, pendientes, verificacion, tomada=True):
    """Mockea DB, FIEL y SAT para una pasada; devuelve los SQL ejecutados y las importaciones."""
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_all", lambda *a, **k: pendientes)
    monkeypatch.setattr(fiel_store, "obtener_signer", lambda db_, eid: _FakeSigner())
    monkeypatch.setattr(sat_sync, "verificar_solicitud", lambda *a, **k: verificacion)

    sqls = []

    if tomada is True:
        tomada = {"id": "sol-1", "paquetes_descargados": 0}

    def _execute(sql, params=(), returning=False):
        sqls.append(sql)
        return (tomada or None) if returning else None
    monkeypatch.setattr(db, "execute", _execute)

    importaciones = []

    def _importar(**kw):
        importaciones.append(kw)
        return "descargado"
    monkeypatch.setattr(sat_sync, "importar_paquetes", _importar)
    return sqls, importaciones


def test_avanzar_sin_descargas_en_curso_no_toca_la_fiel(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_all", lambda *a, **k: [])

    def _no_debe_llamarse(*a, **k):
        raise AssertionError("no debe cargar la FIEL si no hay nada pendiente")
    monkeypatch.setattr(fiel_store, "obtener_signer", _no_debe_llamarse)

    try:
        r = client.post(_AVANZAR_URL)
    finally:
        _teardown()

    assert r.status_code == 200
    assert r.json() == {"avanzadas": []}


def test_avanzar_solicitud_terminada_descarga_e_importa(monkeypatch):
    _, importaciones = _preparar_avanzar(
        monkeypatch, [_solicitud_pendiente()],
        {"estado": "Terminada", "id_paquetes": ["pkg1"], "num_cfdi": 10},
    )

    try:
        r = client.post(_AVANZAR_URL)
    finally:
        _teardown()

    assert r.status_code == 200
    assert r.json() == {"avanzadas": [{"id": "sol-1", "estado": "descargado"}]}
    assert len(importaciones) == 1
    assert importaciones[0]["paquetes"] == ["pkg1"]
    assert importaciones[0]["periodo"] == "2026-09"
    assert importaciones[0]["empresa_id"] == EMPRESA


def test_avanzar_solicitud_ya_tomada_por_otra_pasada_no_descarga_dos_veces(monkeypatch):
    _, importaciones = _preparar_avanzar(
        monkeypatch, [_solicitud_pendiente()],
        {"estado": "Terminada", "id_paquetes": ["pkg1"], "num_cfdi": 10},
        tomada=False,
    )

    try:
        r = client.post(_AVANZAR_URL)
    finally:
        _teardown()

    assert r.json() == {"avanzadas": [{"id": "sol-1", "estado": "terminado"}]}
    assert importaciones == []


def test_avanzar_solicitud_en_proceso_sigue_esperando(monkeypatch):
    sqls, importaciones = _preparar_avanzar(
        monkeypatch, [_solicitud_pendiente()],
        {"estado": "En proceso", "id_paquetes": [], "num_cfdi": 0},
    )

    try:
        r = client.post(_AVANZAR_URL)
    finally:
        _teardown()

    assert r.json() == {"avanzadas": [{"id": "sol-1", "estado": "en_proceso"}]}
    assert importaciones == []
    assert "estado='en_proceso'" in sqls[0]


def test_avanzar_solicitud_rechazada_por_el_sat_queda_en_fallo(monkeypatch):
    sqls, importaciones = _preparar_avanzar(
        monkeypatch, [_solicitud_pendiente("en_proceso")],
        {"estado": "Rechazada", "id_paquetes": [], "num_cfdi": 0},
    )

    try:
        r = client.post(_AVANZAR_URL)
    finally:
        _teardown()

    assert r.json() == {"avanzadas": [{"id": "sol-1", "estado": "fallo"}]}
    assert importaciones == []
    assert "estado='fallo'" in sqls[0]


def test_avanzar_error_al_verificar_conserva_el_estado(monkeypatch):
    sqls, _ = _preparar_avanzar(monkeypatch, [_solicitud_pendiente("en_proceso")], {})

    def _raise(*a, **k):
        raise FIELError("timeout SAT")
    monkeypatch.setattr(sat_sync, "verificar_solicitud", _raise)

    try:
        r = client.post(_AVANZAR_URL)
    finally:
        _teardown()

    assert r.json() == {"avanzadas": [{"id": "sol-1", "estado": "en_proceso"}]}
    # el fallo transitorio cuenta un intento y agenda el siguiente; no cambia el estado
    assert any("intentos = intentos + 1" in q for q in sqls)
    assert not any("estado='fallo'" in q for q in sqls)


def test_avanzar_sin_fiel_guardada_da_422(monkeypatch):
    _preparar_avanzar(monkeypatch, [_solicitud_pendiente()], {})

    def _raise(db_, eid):
        raise ValueError("No hay FIEL guardada para esta empresa")
    monkeypatch.setattr(fiel_store, "obtener_signer", _raise)

    try:
        r = client.post(_AVANZAR_URL)
    finally:
        _teardown()

    assert r.status_code == 422


def test_avanzar_sin_auth_da_401():
    r = client.post(_AVANZAR_URL)
    assert r.status_code == 401


def test_avanzar_reconoce_el_estado_numerico_que_devuelve_satcfdi(monkeypatch):
    """satcfdi entrega EstadoSolicitud como entero: 3 es Terminada."""
    _, importaciones = _preparar_avanzar(
        monkeypatch, [_solicitud_pendiente("en_proceso")],
        {"estado": 3, "id_paquetes": ["pkg1"], "num_cfdi": 10},
    )

    try:
        r = client.post(_AVANZAR_URL)
    finally:
        _teardown()

    assert r.json() == {"avanzadas": [{"id": "sol-1", "estado": "descargado"}]}
    assert len(importaciones) == 1


def test_avanzar_estado_numerico_rechazada_guarda_el_mensaje_del_sat(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_all", lambda *a, **k: [_solicitud_pendiente()])
    monkeypatch.setattr(fiel_store, "obtener_signer", lambda db_, eid: _FakeSigner())
    monkeypatch.setattr(sat_sync, "verificar_solicitud", lambda *a, **k: {
        "estado": 5, "id_paquetes": [], "num_cfdi": 0, "mensaje": "No se encontró la información",
    })
    params_vistos = []
    monkeypatch.setattr(db, "execute", lambda sql, params=(), returning=False: params_vistos.append(params))

    try:
        r = client.post(_AVANZAR_URL)
    finally:
        _teardown()

    assert r.json() == {"avanzadas": [{"id": "sol-1", "estado": "fallo"}]}
    assert params_vistos[0][0] == "SAT reportó estado: rechazada. No se encontró la información"


def test_verificar_solicitud_estado_numerico_terminada(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {
        "id": "sol-1", "empresa_id": EMPRESA, "id_solicitud_sat": "id-sat-1",
    })
    monkeypatch.setattr(db, "execute", lambda *a, **k: None)
    monkeypatch.setattr(sat, "cargar_fiel", lambda *a, **k: _FakeSigner())
    monkeypatch.setattr(sat, "verificar_solicitud", lambda *a, **k: {
        "estado": 3, "id_paquetes": ["pkg1"], "num_cfdi": 10, "mensaje": "OK",
    })

    try:
        r = client.post(
            "/api/v1/sat/solicitudes/sol-1/verificar",
            data={"password": "x"},
            files={"cer_file": _CER, "key_file": _KEY},
        )
    finally:
        _teardown()

    assert r.json()["estado"] == "terminado"


def test_avanzar_estado_cero_del_sat_deja_de_esperar_y_guarda_el_motivo(monkeypatch):
    """El SAT responde EstadoSolicitud=0 cuando no hay información para la consulta."""
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_all", lambda *a, **k: [_solicitud_pendiente("en_proceso")])
    monkeypatch.setattr(fiel_store, "obtener_signer", lambda db_, eid: _FakeSigner())
    monkeypatch.setattr(sat_sync, "verificar_solicitud", lambda *a, **k: {
        "estado": 0, "id_paquetes": [], "num_cfdi": 0, "mensaje": "No se encontro la informacion",
    })
    params_vistos = []
    monkeypatch.setattr(db, "execute", lambda sql, params=(), returning=False: params_vistos.append(params))

    try:
        r = client.post(_AVANZAR_URL)
    finally:
        _teardown()

    assert r.json() == {"avanzadas": [{"id": "sol-1", "estado": "fallo"}]}
    assert params_vistos[0][0] == "El SAT respondió: No se encontro la informacion"


def test_avanzar_error_no_controlado_del_sat_se_reintenta(monkeypatch):
    """CodEstatus 404 es un error transitorio del SAT: la solicitud sigue en curso."""
    sqls, importaciones = _preparar_avanzar(
        monkeypatch, [_solicitud_pendiente()],
        {"estado": 0, "cod_estatus": "404", "id_paquetes": [], "num_cfdi": 0,
         "mensaje": "Error no controlado."},
    )

    try:
        r = client.post(_AVANZAR_URL)
    finally:
        _teardown()

    assert r.json() == {"avanzadas": [{"id": "sol-1", "estado": "en_proceso"}]}
    assert importaciones == []
    assert "estado='fallo'" not in sqls[0]


def test_avanzar_sin_informacion_en_el_periodo_queda_descargada_con_cero_cfdi(monkeypatch):
    """CodigoEstadoSolicitud 5004: no hay CFDI en el periodo. No es un fallo."""
    sqls, importaciones = _preparar_avanzar(
        monkeypatch, [_solicitud_pendiente("en_proceso")],
        {"estado": 5, "codigo_estado": "5004", "id_paquetes": [], "num_cfdi": 0,
         "mensaje": "No se encontró la información"},
    )

    try:
        r = client.post(_AVANZAR_URL)
    finally:
        _teardown()

    assert r.json() == {"avanzadas": [{"id": "sol-1", "estado": "descargado"}]}
    assert importaciones == []
    assert "estado='descargado'" in sqls[0]
    assert "estado='fallo'" not in sqls[0]


def test_avanzar_retoma_la_importacion_desde_el_paquete_pendiente(monkeypatch):
    """Una importación cortada sigue desde el primer paquete sin importar, no desde cero."""
    sqls, importaciones = _preparar_avanzar(
        monkeypatch, [_solicitud_pendiente("terminado")],
        {"estado": 3, "id_paquetes": ["pkg1", "pkg2", "pkg3"], "num_cfdi": 30},
        tomada={"id": "sol-1", "paquetes_descargados": 2},
    )

    try:
        r = client.post(_AVANZAR_URL)
    finally:
        _teardown()

    assert r.json() == {"avanzadas": [{"id": "sol-1", "estado": "descargado"}]}
    assert importaciones[0]["desde"] == 2
    assert "paquetes_descargados=0" not in sqls[0]


def test_avanzar_tolera_paquetes_nulos_del_sat(monkeypatch):
    _, importaciones = _preparar_avanzar(
        monkeypatch, [_solicitud_pendiente()],
        {"estado": 2, "id_paquetes": None, "num_cfdi": None},
    )

    try:
        r = client.post(_AVANZAR_URL)
    finally:
        _teardown()

    assert r.json() == {"avanzadas": [{"id": "sol-1", "estado": "en_proceso"}]}
    assert importaciones == []


def test_verificar_solicitud_sin_informacion_queda_descargada(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(db, "query_one", lambda *a, **k: {
        "id": "sol-1", "empresa_id": EMPRESA, "id_solicitud_sat": "id-sat-1",
    })
    ejecutados = []
    monkeypatch.setattr(db, "execute", lambda sql, params=(), returning=False: ejecutados.append((sql, params)))
    monkeypatch.setattr(sat, "cargar_fiel", lambda *a, **k: _FakeSigner())
    monkeypatch.setattr(sat, "verificar_solicitud", lambda *a, **k: {
        "estado": 5, "codigo_estado": "5004", "id_paquetes": [], "num_cfdi": 0,
        "mensaje": "No se encontró la información",
    })

    try:
        r = client.post(
            "/api/v1/sat/solicitudes/sol-1/verificar",
            data={"password": "x"},
            files={"cer_file": _CER, "key_file": _KEY},
        )
    finally:
        _teardown()

    assert r.json()["estado"] == "descargado"
    # Limpia el error de un intento anterior: si no, la UI la vería "Incompleta".
    sql, params = ejecutados[0]
    assert "error_msg = CASE WHEN %s = 'descargado' THEN NULL" in sql
    assert params[0] == params[3] == "descargado"


# ─── _importar_paquetes_bg ──────────────────────────────────────────────────────

class _CfdiOk:
    uuid = "UUID-OK"
    errores: list = []


class _CfdiConError:
    uuid = "UUID-MAL"
    errores = ["Total no puede ser negativo"]


class _FakeParser:
    def parse_xml(self, xml_bytes):
        return _CfdiConError() if xml_bytes == b"malo" else _CfdiOk()


def _preparar_importacion(monkeypatch, paquetes_sat, fila_final, pipeline=None):
    """`paquetes_sat` mapea id de paquete -> lista de XML, o una excepción."""
    import backend.cfdi_parser as cfdi_parser
    import backend.routers.ingesta as ingesta

    monkeypatch.setattr(cfdi_parser, "CFDIParser", _FakeParser)
    monkeypatch.setattr(sat_sync, "_insertar_cfdi", lambda *a, **k: None)
    monkeypatch.setattr(ingesta, "_correr_pipeline", lambda *a: (pipeline if pipeline is not None else []).append(a))

    descargados = []

    def _descargar(creds, id_paq):
        descargados.append(id_paq)
        xmls = paquetes_sat[id_paq]
        if isinstance(xmls, Exception):
            raise xmls
        return xmls
    monkeypatch.setattr(sat_sync, "descargar_paquete", _descargar)

    def _query_one(sql, params=()):
        if "FROM empresas" in sql:
            return {"rfc": "AAA010101AAA"}
        return fila_final
    monkeypatch.setattr(db, "query_one", _query_one)

    ejecutados = []
    monkeypatch.setattr(db, "execute", lambda sql, params=(), returning=False: ejecutados.append((sql, params)))
    return descargados, ejecutados


def _importar(paquetes, desde=0):
    return sat_sync.importar_paquetes(
        creds=_FakeSigner(), solicitud_id="sol-1", empresa_id=EMPRESA,
        periodo="2026-09", paquetes=paquetes, desde=desde,
    )


def test_importar_completa_queda_descargada_sin_aviso(monkeypatch):
    descargados, ejecutados = _preparar_importacion(
        monkeypatch, {"p1": [b"a", b"b"], "p2": [b"c"]},
        {"num_cfdi": 3, "cfdi_importados": 3},
    )

    assert _importar(["p1", "p2"]) == "descargado"
    assert descargados == ["p1", "p2"]
    # El avance se guarda paquete por paquete, con su número y sus CFDI.
    assert ejecutados[0][1] == (1, 2, "sol-1")
    assert ejecutados[1][1] == (2, 1, "sol-1")
    assert ejecutados[-1][1] == ("descargado", None, "sol-1")


def test_importar_con_cfdi_omitidos_avisa_que_la_descarga_quedo_incompleta(monkeypatch):
    _, ejecutados = _preparar_importacion(
        monkeypatch, {"p1": [b"a", b"malo", b"c"]},
        {"num_cfdi": 3, "cfdi_importados": 2},
    )

    assert _importar(["p1"]) == "descargado"
    assert ejecutados[0][1] == (1, 2, "sol-1")
    estado, error_msg, _ = ejecutados[-1][1]
    assert estado == "descargado"
    assert error_msg == (
        "Descarga incompleta: se importaron 2 de los 3 CFDI que reportó el SAT; "
        "1 no se pudieron importar."
    )


def test_importar_paquete_que_falla_no_se_salta_y_se_reintenta(monkeypatch):
    descargados, ejecutados = _preparar_importacion(
        monkeypatch,
        {"p1": [b"a"], "p2": FIELError("timeout"), "p3": [b"c"]},
        {"num_cfdi": 3, "cfdi_importados": 1},
    )

    assert _importar(["p1", "p2", "p3"]) == "terminado"
    assert descargados == ["p1", "p2"]  # p3 espera a que p2 se reintente
    sql, params = ejecutados[-1]
    assert "estado" not in sql  # sigue en 'terminado' para la siguiente pasada
    assert params[0] == (
        "No se pudo descargar el paquete 2 de 3 (intento 1 de 3): timeout. "
        "Se reintentará en unos minutos."
    )


def test_importar_cuenta_los_reintentos_del_mismo_paquete(monkeypatch):
    previo = "No se pudo descargar el paquete 2 de 3 (intento 1 de 3): timeout. Se reintentará en unos minutos."
    _, ejecutados = _preparar_importacion(
        monkeypatch, {"p2": FIELError("timeout")},
        {"num_cfdi": 3, "cfdi_importados": 1, "error_msg": previo},
    )

    assert _importar(["p1", "p2", "p3"], desde=1) == "terminado"
    assert "(intento 2 de 3)" in ejecutados[-1][1][0]


def test_importar_paquete_que_agota_los_reintentos_deja_la_solicitud_en_fallo(monkeypatch):
    """Un paquete que nunca se puede descargar no deja la solicitud 'Importando' para siempre."""
    previo = "No se pudo descargar el paquete 2 de 3 (intento 2 de 3): timeout. Se reintentará en unos minutos."
    _, ejecutados = _preparar_importacion(
        monkeypatch, {"p2": FIELError("timeout")},
        {"num_cfdi": 3, "cfdi_importados": 1, "error_msg": previo},
    )

    assert _importar(["p1", "p2", "p3"], desde=1) == "fallo"
    sql, params = ejecutados[-1]
    assert "estado='fallo'" in sql
    assert params[0] == (
        "No se pudo descargar el paquete 2 de 3 tras 3 intentos: timeout. "
        "Vuelve a solicitar el periodo."
    )


def test_importar_falla_de_otro_paquete_reinicia_la_cuenta(monkeypatch):
    previo = "No se pudo descargar el paquete 1 de 3 (intento 2 de 3): timeout. Se reintentará en unos minutos."
    _, ejecutados = _preparar_importacion(
        monkeypatch, {"p2": FIELError("timeout")},
        {"num_cfdi": 3, "cfdi_importados": 1, "error_msg": previo},
    )

    assert _importar(["p1", "p2", "p3"], desde=1) == "terminado"
    assert "(intento 1 de 3)" in ejecutados[-1][1][0]


def test_importar_retoma_desde_el_paquete_indicado(monkeypatch):
    descargados, ejecutados = _preparar_importacion(
        monkeypatch, {"p1": [b"a"], "p2": [b"b"], "p3": [b"c"]},
        {"num_cfdi": 3, "cfdi_importados": 3},
    )

    assert _importar(["p1", "p2", "p3"], desde=2) == "descargado"
    assert descargados == ["p3"]
    assert ejecutados[0][1] == (3, 1, "sol-1")


def test_importar_sin_ningun_cfdi_valido_queda_en_fallo(monkeypatch):
    pipeline = []
    _, ejecutados = _preparar_importacion(
        monkeypatch, {"p1": [b"malo"]}, {"num_cfdi": 1, "cfdi_importados": 0}, pipeline,
    )

    assert _importar(["p1"]) == "fallo"
    assert ejecutados[-1][1] == ("fallo", "Ningún CFDI pudo importarse correctamente", "sol-1")
    assert pipeline == []


def test_sync_en_background_reintenta_la_importacion_pendiente(monkeypatch):
    """Una solicitud que queda en 'terminado' (paquete por reintentar) no se abandona."""
    import time

    monkeypatch.setattr(time, "sleep", lambda s: None)
    monkeypatch.setattr(fiel_store, "obtener_signer", lambda db_, eid: _FakeSigner())
    filas = iter([
        {"rfc": "AAA010101AAA"},
        {**_solicitud_pendiente("en_proceso")},
        {**_solicitud_pendiente("terminado")},
    ])
    monkeypatch.setattr(db, "query_one", lambda *a, **k: next(filas))
    monkeypatch.setattr(db, "execute", lambda *a, **k: None)
    resultados = iter(["terminado", "descargado"])
    llamadas = []
    monkeypatch.setattr(sat, "_avanzar_solicitud", lambda creds, row: llamadas.append(row["estado"]) or next(resultados))

    sat._sync_completo_bg(EMPRESA, "2026-09", [{"id": "sol-1"}])

    assert llamadas == ["en_proceso", "terminado"]


def test_avanzar_estado_desconocido_del_sat_sigue_esperando(monkeypatch):
    """Solo el 0 explícito es un rechazo: otro número o una respuesta sin estado se espera."""
    for verificacion in (
        {"estado": 9, "id_paquetes": [], "num_cfdi": 0},
        {"id_paquetes": [], "num_cfdi": 0},
    ):
        sqls, importaciones = _preparar_avanzar(monkeypatch, [_solicitud_pendiente()], verificacion)

        try:
            r = client.post(_AVANZAR_URL)
        finally:
            _teardown()

        assert r.json() == {"avanzadas": [{"id": "sol-1", "estado": "en_proceso"}]}
        assert "estado='fallo'" not in sqls[0]
