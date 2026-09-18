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
from backend import db
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
    monkeypatch.setattr(sat, "solicitar_descarga", _raise)

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
    monkeypatch.setattr(sat, "solicitar_descarga", lambda *a, **k: "id-sat-x")

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
