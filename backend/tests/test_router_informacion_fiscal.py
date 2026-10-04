"""Router de información fiscal (F8) con la base mockeada: acceso, validaciones de
la carga, respuesta del resumen y entrega del PDF."""
from datetime import date, datetime, timezone

import psycopg2
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import backend.main_api as main
from backend import db
from backend.deps import get_current_user, limiter
from backend.routers import informacion_fiscal as router_if
from backend.tests.pdf_sintetico import RFC_PRUEBA, constancia_sintetica, opinion_sintetica

client = TestClient(main.app)
EMPRESA = "11111111-1111-1111-1111-111111111111"
DOC = "22222222-2222-2222-2222-222222222222"
BASE = f"/api/v1/informacion-fiscal/empresas/{EMPRESA}"


class _Db:
    """Base falsa: responde por el texto del SQL y registra lo ejecutado."""

    def __init__(self, filas=None, documento=None, error_insert=None):
        self.filas = filas or []
        self.documento = documento
        self.error_insert = error_insert
        self.ejecutado = []

    def query_one(self, sql, params=()):
        if "FROM empresas" in sql:
            return {"id": EMPRESA, "rfc": RFC_PRUEBA}
        if "FROM documentos_fiscales" in sql:
            return self.documento
        raise AssertionError(f"consulta inesperada: {sql}")

    def query_all(self, sql, params=()):
        assert "FROM documentos_fiscales" in sql
        return self.filas

    def execute(self, sql, params=(), returning=False):
        self.ejecutado.append((sql, params))
        if sql.lstrip().startswith("INSERT INTO documentos_fiscales"):
            if self.error_insert:
                raise self.error_insert
            return _fila("constancia", fecha=date(2026, 10, 3))
        if sql.lstrip().startswith("DELETE FROM documentos_fiscales"):
            return {"id": DOC} if self.documento else None
        if "INSERT INTO auditoria" in sql:
            return None
        raise AssertionError(f"execute inesperado: {sql}")

    def instalar(self, monkeypatch):
        monkeypatch.setattr(db, "query_one", self.query_one)
        monkeypatch.setattr(db, "query_all", self.query_all)
        monkeypatch.setattr(db, "execute", self.execute)
        return self


def _fila(tipo, fecha=None, datos=None, creado=datetime(2026, 10, 4, 10, 0, tzinfo=timezone.utc)):
    return {
        "id": DOC, "tipo": tipo, "nombre_archivo": f"{tipo}.pdf", "tamano_bytes": 1234,
        "rfc": RFC_PRUEBA, "fecha_emision": fecha, "datos": datos or {}, "created_at": creado,
    }


@pytest.fixture(autouse=True)
def sesion(monkeypatch):
    main.app.dependency_overrides[get_current_user] = lambda: {"user_id": "u1"}
    monkeypatch.setattr(router_if, "validar_acceso_empresa", lambda *a, **k: None)
    monkeypatch.setattr(router_if, "_hoy", lambda: date(2026, 10, 10))
    limiter.reset()  # la carga permite 20 por minuto
    yield
    limiter.reset()
    main.app.dependency_overrides.clear()


def _subir(tipo, contenido, nombre="doc.pdf", content_type="application/pdf"):
    return client.post(f"{BASE}/documentos/{tipo}", files={"archivo": (nombre, contenido, content_type)})


# ─── Acceso ───────────────────────────────────────────────────────────────────

def test_sin_sesion_responde_401():
    main.app.dependency_overrides.clear()
    assert client.get(BASE).status_code == 401


def test_sin_acceso_a_la_empresa_responde_403(monkeypatch):
    def _negar(*a, **k):
        raise HTTPException(status_code=403, detail="Sin acceso a esta empresa")

    monkeypatch.setattr(router_if, "validar_acceso_empresa", _negar)
    base = _Db().instalar(monkeypatch)
    assert client.get(BASE).status_code == 403
    assert client.get(f"{BASE}/documentos").status_code == 403
    assert _subir("constancia", constancia_sintetica()).status_code == 403
    assert client.get(f"{BASE}/documentos/{DOC}/pdf").status_code == 403
    assert client.delete(f"{BASE}/documentos/{DOC}").status_code == 403
    assert base.ejecutado == []


# ─── Resumen e historial ──────────────────────────────────────────────────────

def test_resumen_trae_el_ultimo_de_cada_tipo_con_vigencia(monkeypatch):
    _Db(filas=[
        _fila("opinion", fecha=date(2026, 10, 3), datos={"sentido": "positivo"}),
    ]).instalar(monkeypatch)
    r = client.get(BASE)
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["constancia"] is None
    opinion = cuerpo["opinion"]
    assert opinion["fecha_emision"] == "2026-10-03"
    assert opinion["vigente_hasta"] == "2026-11-01"
    assert opinion["vigente"] is True
    assert opinion["motivo"] is None
    assert opinion["antiguedad_dias"] == 7
    assert opinion["datos"] == {"sentido": "positivo"}
    assert "contenido" not in opinion


def test_opinion_negativa_no_es_vigente(monkeypatch):
    _Db(filas=[
        _fila("opinion", fecha=date(2026, 10, 3), datos={"sentido": "negativo"}),
    ]).instalar(monkeypatch)
    opinion = client.get(BASE).json()["opinion"]
    assert (opinion["vigente"], opinion["vigente_hasta"], opinion["motivo"]) == (False, None, "sentido_no_positivo")


def test_constancia_no_tiene_vigencia(monkeypatch):
    _Db(filas=[_fila("constancia", fecha=date(2026, 9, 1))]).instalar(monkeypatch)
    constancia = client.get(BASE).json()["constancia"]
    assert constancia["vigente_hasta"] is None
    assert constancia["vigente"] is None
    assert constancia["antiguedad_dias"] == 39


def test_resumen_elige_por_fecha_de_emision(monkeypatch):
    vistos = []
    base = _Db()
    base.query_all = lambda sql, params=(): vistos.append(sql) or []
    base.instalar(monkeypatch)
    client.get(BASE)
    assert "ORDER BY tipo, fecha_emision DESC NULLS LAST, created_at DESC" in " ".join(vistos[0].split())


def test_nombre_de_archivo_sin_caracteres_de_control():
    assert router_if._nombre_seguro("CSF\r\nX-Evil: 1.pdf") == "CSFX-Evil: 1.pdf"
    assert router_if._nombre_seguro("../../etc/passwd") == "passwd"
    assert router_if._nombre_seguro("\x00") == "documento.pdf"


def test_historial_filtra_por_tipo(monkeypatch):
    base = _Db(filas=[_fila("opinion"), _fila("opinion")])
    vistos = []
    base.query_all = lambda sql, params=(): vistos.append(params) or base.filas
    base.instalar(monkeypatch)
    r = client.get(f"{BASE}/documentos", params={"tipo": "opinion"})
    assert r.status_code == 200
    assert len(r.json()) == 2
    assert vistos == [(EMPRESA, "opinion")]


def test_historial_con_tipo_invalido_responde_422(monkeypatch):
    _Db().instalar(monkeypatch)
    assert client.get(f"{BASE}/documentos", params={"tipo": "acta"}).status_code == 422


# ─── Carga ────────────────────────────────────────────────────────────────────

def test_sube_constancia_valida(monkeypatch):
    base = _Db().instalar(monkeypatch)
    pdf = constancia_sintetica()
    r = _subir("constancia", pdf, nombre="CSF.pdf")
    assert r.status_code == 201, r.text
    insert = next(p for sql, p in base.ejecutado if "INSERT INTO documentos_fiscales" in sql)
    empresa_id, tipo, nombre, contenido, tamano, sha, rfc, fecha, datos, usuario = insert
    assert (empresa_id, tipo, nombre, rfc, fecha, usuario) == (EMPRESA, "constancia", "CSF.pdf", RFC_PRUEBA, "2026-10-03", "u1")
    assert contenido == pdf and tamano == len(pdf) and len(sha) == 64
    assert datos.adapted["cp_fiscal"] == "68000"
    assert any("INSERT INTO auditoria" in sql for sql, _ in base.ejecutado)


def test_rechaza_tipo_de_ruta_desconocido(monkeypatch):
    base = _Db().instalar(monkeypatch)
    assert _subir("acta", constancia_sintetica()).status_code == 422
    assert base.ejecutado == []


def test_rechaza_extension_y_content_type(monkeypatch):
    base = _Db().instalar(monkeypatch)
    assert _subir("constancia", constancia_sintetica(), nombre="csf.docx").status_code == 400
    assert _subir("constancia", constancia_sintetica(), content_type="image/png").status_code == 400
    assert base.ejecutado == []


def test_rechaza_mas_de_5_mb(monkeypatch):
    base = _Db().instalar(monkeypatch)
    grande = constancia_sintetica() + b"\n%" + b"x" * (5 * 1024 * 1024)
    assert _subir("constancia", grande).status_code == 413
    assert base.ejecutado == []


def test_rechaza_rfc_de_otra_empresa_sin_guardar(monkeypatch):
    base = _Db().instalar(monkeypatch)
    r = _subir("constancia", constancia_sintetica(rfc="XYZ990101AB2"))
    assert r.status_code == 422
    assert "XYZ990101AB2" in r.json()["detail"] and RFC_PRUEBA in r.json()["detail"]
    assert base.ejecutado == []


def test_rechaza_opinion_subida_como_constancia(monkeypatch):
    _Db().instalar(monkeypatch)
    r = _subir("constancia", opinion_sintetica())
    assert r.status_code == 422
    assert "no parece una constancia" in r.json()["detail"]


def test_rechaza_archivo_que_no_es_pdf(monkeypatch):
    _Db().instalar(monkeypatch)
    assert _subir("opinion", b"no soy un pdf").status_code == 422


def test_carga_limitada_a_20_por_minuto(monkeypatch):
    _Db().instalar(monkeypatch)
    codigos = [_subir("opinion", b"no soy un pdf").status_code for _ in range(21)]
    assert codigos[:20] == [422] * 20
    assert codigos[20] == 429


def test_mismo_pdf_dos_veces_responde_409(monkeypatch):
    _Db(error_insert=psycopg2.errors.UniqueViolation()).instalar(monkeypatch)
    r = _subir("constancia", constancia_sintetica())
    assert r.status_code == 409
    assert "ya está cargado" in r.json()["detail"]


# ─── PDF y eliminación ────────────────────────────────────────────────────────

def test_entrega_el_pdf_para_el_visor_y_para_descargar(monkeypatch):
    pdf = opinion_sintetica()
    _Db(documento={"nombre_archivo": "32D ACME.pdf", "contenido": memoryview(pdf)}).instalar(monkeypatch)
    r = client.get(f"{BASE}/documentos/{DOC}/pdf")
    assert r.status_code == 200
    assert r.content == pdf
    assert r.headers["content-type"] == "application/pdf"
    assert r.headers["content-disposition"].startswith("inline")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["content-security-policy"] == "sandbox"

    r = client.get(f"{BASE}/documentos/{DOC}/pdf", params={"descargar": "true"})
    assert r.headers["content-disposition"].startswith("attachment")
    assert "32D" in r.headers["content-disposition"]


def test_pdf_de_otra_empresa_o_inexistente_responde_404(monkeypatch):
    vistos = []
    base = _Db(documento=None)
    original = base.query_one
    base.query_one = lambda sql, params=(): (
        original(sql, params) if "FROM empresas" in sql else vistos.append(params)
    )
    base.instalar(monkeypatch)
    assert client.get(f"{BASE}/documentos/{DOC}/pdf").status_code == 404
    assert vistos == [(DOC, EMPRESA)]


def test_documento_id_invalido_responde_422(monkeypatch):
    _Db().instalar(monkeypatch)
    assert client.get(f"{BASE}/documentos/no-es-uuid/pdf").status_code == 422


def test_elimina_y_audita(monkeypatch):
    base = _Db(documento={"id": DOC}).instalar(monkeypatch)
    r = client.delete(f"{BASE}/documentos/{DOC}")
    assert r.status_code == 204
    delete = next(p for sql, p in base.ejecutado if "DELETE FROM documentos_fiscales" in sql)
    assert delete == (DOC, EMPRESA)
    assert any("INSERT INTO auditoria" in sql for sql, _ in base.ejecutado)


def test_eliminar_inexistente_responde_404(monkeypatch):
    _Db(documento=None).instalar(monkeypatch)
    assert client.delete(f"{BASE}/documentos/{DOC}").status_code == 404
