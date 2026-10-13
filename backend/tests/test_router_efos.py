"""Router de EFOS (estado e importación). DB y red simuladas."""
import pytest
from fastapi.testclient import TestClient

import backend.main_api as main
from backend import deps, efos, efos_datos
from backend.deps import get_current_user
from backend.routers import efos as router

client = TestClient(main.app)


@pytest.fixture
def sesion(monkeypatch):
    main.app.dependency_overrides[get_current_user] = lambda: {"user_id": "u1"}
    monkeypatch.setattr(router.auditoria, "registrar_evento", lambda *a, **k: None)
    yield monkeypatch
    main.app.dependency_overrides.clear()


def _como(monkeypatch, rol):
    monkeypatch.setattr(deps.db, "query_one", lambda *a, **k: {"rol": rol})


def test_estado_para_cualquier_usuario_autenticado(sesion):
    sesion.setattr(efos_datos, "estado", lambda: {"hay_lista": True, "desactualizada": False})
    assert client.get("/api/v1/efos/estado").json() == {"hay_lista": True, "desactualizada": False}


def test_estado_sin_token_da_401():
    assert client.get("/api/v1/efos/estado").status_code == 401


@pytest.mark.parametrize("ruta", ["/api/v1/admin/efos/importar", "/api/v1/admin/efos/subir"])
def test_importar_y_subir_exigen_administrador_de_plataforma(sesion, ruta):
    _como(sesion, "contador")
    sesion.setattr(efos_datos, "importar", lambda *a, **k: pytest.fail("no debe importar"))
    sesion.setattr(efos_datos, "descargar", lambda *a, **k: pytest.fail("no debe descargar"))
    r = client.post(ruta, files={"archivo": ("lista.csv", b"x", "text/csv")} if ruta.endswith("subir") else None)
    assert r.status_code == 403


def test_forzar_importacion_descarga_e_importa_como_manual_con_usuario(sesion):
    _como(sesion, "admin")
    visto = {}
    sesion.setattr(efos_datos, "descargar", lambda *a, **k: b"csv")
    sesion.setattr(efos_datos, "importar", lambda c, o, u=None: visto.update(c=c, o=o, u=u) or {"estado": "correcta", "filas": 3})
    r = client.post("/api/v1/admin/efos/importar")
    assert r.status_code == 200 and r.json()["estado"] == "correcta"
    assert visto == {"c": b"csv", "o": "manual", "u": "u1"}


def test_forzar_importacion_con_el_sat_caido_da_502_y_registra(sesion):
    _como(sesion, "admin")
    registros = []

    def _sin_red(*a, **k):
        raise OSError("timed out")

    sesion.setattr(efos_datos, "descargar", _sin_red)
    sesion.setattr(efos_datos, "_registrar", lambda *a, **k: registros.append(a))
    r = client.post("/api/v1/admin/efos/importar")
    assert r.status_code == 502 and "timed out" in r.json()["detail"]
    assert registros and registros[0][2] == "fallida"


def test_subir_importa_el_archivo(sesion):
    _como(sesion, "admin")
    visto = {}
    sesion.setattr(efos_datos, "importar", lambda c, o, u=None: visto.update(c=c, o=o, u=u) or {"estado": "correcta", "filas": 2})
    r = client.post("/api/v1/admin/efos/subir", files={"archivo": ("lista.csv", b"contenido", "text/csv")})
    assert r.status_code == 200 and visto == {"c": b"contenido", "o": "manual", "u": "u1"}


def test_subir_rechaza_extension_y_tamano(sesion):
    _como(sesion, "admin")
    sesion.setattr(efos_datos, "importar", lambda *a, **k: pytest.fail("no debe importar"))
    assert client.post("/api/v1/admin/efos/subir", files={"archivo": ("lista.exe", b"x", "application/octet-stream")}).status_code == 400
    sesion.setattr(efos, "MAX_BYTES", 5)
    assert client.post("/api/v1/admin/efos/subir", files={"archivo": ("lista.csv", b"123456", "text/csv")}).status_code == 413


def test_un_archivo_invalido_da_422_con_el_motivo(sesion):
    _como(sesion, "admin")

    def _invalido(*a, **k):
        raise efos.ErrorImportacion("La cabecera del archivo no es la esperada")

    sesion.setattr(efos_datos, "importar", _invalido)
    r = client.post("/api/v1/admin/efos/subir", files={"archivo": ("lista.csv", b"x", "text/csv")})
    assert r.status_code == 422 and "cabecera" in r.json()["detail"]
