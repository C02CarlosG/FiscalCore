"""E2E de F8 contra Postgres real: subir constancia y opinión sintéticas, consultar,
descargar idéntico, rechazar duplicados y RFC ajenos, aislar empresas y eliminar."""
import pytest

from backend.tests.conftest import db_disponible, headers_usuario_e2e
from backend.tests.pdf_sintetico import constancia_sintetica, opinion_sintetica

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]

RFC = "INF010101AB1"
EMAIL = "e2e-informacion-fiscal@test.local"
EMAIL_AJENO = "e2e-informacion-fiscal-ajeno@test.local"


def _limpiar(db):
    db.execute("DELETE FROM empresas WHERE rfc = %s", (RFC,))
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
        r = client.post("/api/v1/mis-empresas", headers=headers, json={"rfc": RFC, "razon_social": "Información Fiscal E2E"})
        assert r.status_code == 201, r.text
        yield db, client, headers, f"/api/v1/informacion-fiscal/empresas/{r.json()['empresa_id']}"
    finally:
        _limpiar(db)


def _subir(client, headers, base, tipo, pdf):
    return client.post(f"{base}/documentos/{tipo}", headers=headers,
                       files={"archivo": (f"{tipo}.pdf", pdf, "application/pdf")})


def test_ciclo_completo(entorno):
    db, client, headers, base = entorno

    assert client.get(base, headers=headers).json() == {"constancia": None, "opinion": None}

    constancia = constancia_sintetica(rfc=RFC)
    r = _subir(client, headers, base, "constancia", constancia)
    assert r.status_code == 201, r.text
    doc = r.json()
    assert (doc["rfc"], doc["fecha_emision"]) == (RFC, "2026-10-03")
    assert doc["datos"]["regimenes"] == ["Régimen General de Ley Personas Morales"]

    r = _subir(client, headers, base, "opinion", opinion_sintetica(rfc=RFC))
    assert r.status_code == 201, r.text
    assert r.json()["datos"]["sentido"] == "positivo"
    assert r.json()["vigente_hasta"] == "2026-11-01"

    resumen = client.get(base, headers=headers).json()
    assert resumen["constancia"]["id"] == doc["id"]
    assert resumen["opinion"]["datos"]["folio"] == "26NA1234567"

    pdf = client.get(f"{base}/documentos/{doc['id']}/pdf", headers=headers, params={"descargar": "true"})
    assert pdf.status_code == 200
    assert pdf.content == constancia
    assert pdf.headers["content-disposition"].startswith("attachment")

    # El mismo PDF otra vez: 409, y no se duplica.
    assert _subir(client, headers, base, "constancia", constancia).status_code == 409
    assert len(client.get(f"{base}/documentos", headers=headers, params={"tipo": "constancia"}).json()) == 1

    # Otro RFC: 422 sin guardar.
    r = _subir(client, headers, base, "constancia", constancia_sintetica(rfc="XYZ990101AB2"))
    assert r.status_code == 422
    assert len(client.get(f"{base}/documentos", headers=headers).json()) == 2

    # Auditoría de la carga.
    fila = db.query_one(
        "SELECT COUNT(*) AS n FROM auditoria WHERE accion = 'informacion_fiscal.subir' AND entidad_id = %s",
        (doc["id"],),
    )
    assert fila["n"] == 1

    assert client.delete(f"{base}/documentos/{doc['id']}", headers=headers).status_code == 204
    assert client.get(base, headers=headers).json()["constancia"] is None
    assert client.get(f"{base}/documentos/{doc['id']}/pdf", headers=headers).status_code == 404


def test_otro_usuario_no_ve_ni_sube(entorno):
    db, client, headers, base = entorno
    ajeno = headers_usuario_e2e(db, EMAIL_AJENO)
    assert client.get(base, headers=ajeno).status_code == 403
    assert _subir(client, ajeno, base, "constancia", constancia_sintetica(rfc=RFC)).status_code == 403
