"""E2E: el régimen de la constancia se guarda en la empresa (F8) y ISR deja de avisar
«régimen no soportado». Constancias sintéticas; se salta sin DB."""
import pytest

from backend.tests.conftest import db_disponible, headers_usuario_e2e
from backend.tests.pdf_sintetico import pdf_con_texto

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]

RFC = "GOHC800101AB1"  # persona física
EMAIL = "e2e-regimen-constancia@test.local"


def _constancia(dia: int, *regimenes: str) -> bytes:
    return pdf_con_texto([
        "CÉDULA DE IDENTIFICACIÓN FISCAL",
        "CONSTANCIA DE SITUACIÓN FISCAL",
        f"RFC: {RFC}",
        "Lugar y Fecha de Emisión",
        f"OAXACA DE JUAREZ , OAXACA A {dia:02d} DE OCTUBRE DE 2026",
        "Nombre (s): CARLOS",
        "Código Postal: 68000",
        "Regímenes:",
        *regimenes,
    ])


def _limpiar(db):
    db.execute("DELETE FROM empresas WHERE rfc = %s", (RFC,))
    db.execute("DELETE FROM usuarios WHERE email = %s", (EMAIL,))


@pytest.fixture
def entorno():
    from fastapi.testclient import TestClient

    import backend.main_api as main
    from backend import db
    from backend.deps import limiter

    db.init_db()
    _limpiar(db)
    limiter.reset()
    client = TestClient(main.app)
    try:
        headers = headers_usuario_e2e(db, EMAIL)
        r = client.post("/api/v1/mis-empresas", headers=headers, json={"rfc": RFC, "razon_social": "Régimen E2E"})
        assert r.status_code == 201, r.text
        empresa_id = r.json()["empresa_id"]
        yield db, client, headers, empresa_id
    finally:
        limiter.reset()
        _limpiar(db)


def _subir(client, headers, empresa_id, pdf):
    from backend.deps import limiter
    limiter.reset()
    return client.post(f"/api/v1/informacion-fiscal/empresas/{empresa_id}/documentos/constancia", headers=headers,
                       files={"archivo": ("constancia.pdf", pdf, "application/pdf")})


def _modulo_isr(client, headers, empresa_id):
    r = client.get(f"/api/v1/empresas/{empresa_id}/isr-flujo/2026-09", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["regimen"]["modulo"]


def test_la_constancia_guarda_el_regimen_y_quita_el_aviso_de_isr(entorno):
    db, client, headers, empresa_id = entorno
    base = f"/api/v1/informacion-fiscal/empresas/{empresa_id}/regimen"
    assert _modulo_isr(client, headers, empresa_id) == "no_soportado"
    assert client.get(base, headers=headers).json() == {"actual": None, "constancia_id": None, "detectados": [],
                                                        "sugerido": None}

    # 612 con sueldos (605, secundario): se guarda 612 solo.
    r = _subir(client, headers, empresa_id, _constancia(
        1, "Régimen de las Personas Físicas con Actividades Empresariales y Profesionales",
        "Sueldos y Salarios e Ingresos Asimilados a Salarios"))
    assert r.status_code == 201, r.text
    assert r.json()["regimen_guardado"] == "612"
    assert db.query_one("SELECT regimen_fiscal FROM empresas WHERE id = %s", (empresa_id,))["regimen_fiscal"] == (
        "612 - Personas Físicas con Actividades Empresariales y Profesionales")
    assert _modulo_isr(client, headers, empresa_id) == "flujo"
    estado = client.get(base, headers=headers).json()
    assert estado["actual"]["codigo"] == "612" and estado["sugerido"] is None
    assert {d["codigo"] for d in estado["detectados"]} == {"612", "605"}

    # Una constancia posterior con otro régimen no sobrescribe: se sugiere y una persona decide.
    r = _subir(client, headers, empresa_id, _constancia(5, "Régimen Simplificado de Confianza"))
    assert r.json()["regimen_guardado"] is None
    estado = client.get(base, headers=headers).json()
    assert (estado["actual"]["codigo"], estado["sugerido"]) == ("612", "626")
    r = client.put(base, headers=headers, json={"codigo": "626"})
    assert r.status_code == 200, r.text
    assert r.json()["actual"] == {"codigo": "626", "texto": "626 - Régimen Simplificado de Confianza"}
    assert client.get(base, headers=headers).json()["sugerido"] is None
    assert _modulo_isr(client, headers, empresa_id) == "no_soportado"  # RESICO no es flujo ni coeficiente

    for cuerpo in ({"codigo": "999"}, {"codigo": 612}, {}):
        assert client.put(base, headers=headers, json=cuerpo).status_code == 422
    origenes = [f["metadata"]["origen"] for f in db.query_all(
        "SELECT metadata FROM auditoria WHERE accion = 'informacion_fiscal.regimen' AND empresa_id = %s "
        "ORDER BY creado_en", (empresa_id,))]
    assert origenes == ["constancia", "manual"]


def test_dos_regimenes_principales_no_se_guardan_solos(entorno):
    _db, client, headers, empresa_id = entorno
    r = _subir(client, headers, empresa_id, _constancia(
        1, "Régimen de las Personas Físicas con Actividades Empresariales y Profesionales", "Régimen de Arrendamiento"))
    assert r.json()["regimen_guardado"] is None
    estado = client.get(f"/api/v1/informacion-fiscal/empresas/{empresa_id}/regimen", headers=headers).json()
    assert estado["actual"] is None and estado["sugerido"] is None
    assert {d["codigo"] for d in estado["detectados"]} == {"612", "606"}


def test_otra_cuenta_no_ve_ni_cambia_el_regimen(entorno):
    db, client, _headers, empresa_id = entorno
    ajeno = headers_usuario_e2e(db, "e2e-regimen-ajeno@test.local")
    try:
        base = f"/api/v1/informacion-fiscal/empresas/{empresa_id}/regimen"
        assert client.get(base, headers=ajeno).status_code == 403
        assert client.put(base, headers=ajeno, json={"codigo": "612"}).status_code == 403
    finally:
        db.execute("DELETE FROM usuarios WHERE email = 'e2e-regimen-ajeno@test.local'")
