"""E2E de la Cédula de IVA contra un Postgres real (docker compose).

Se salta automáticamente si no hay DB disponible, para no romper la suite en
entornos sin Postgres. Levantar la DB con: `docker compose up -d db`.
"""
import pytest

from backend.tests.conftest import db_disponible

RFC = "COE010101E2E"
EMAIL = "e2e-cedula-iva@test.local"
PERIODO = "2026-01"


pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


def _limpiar(db):
    db.execute(
        "DELETE FROM cfdi WHERE empresa_id IN (SELECT id FROM empresas WHERE rfc = %s)", (RFC,))
    db.execute(
        "DELETE FROM usuario_empresas WHERE empresa_id IN (SELECT id FROM empresas WHERE rfc = %s)", (RFC,))
    db.execute("DELETE FROM empresas WHERE rfc = %s", (RFC,))
    db.execute("DELETE FROM usuarios WHERE email = %s", (EMAIL,))


def _insertar_cfdi(db, empresa_id, uuid, emisor, receptor, subtotal, total, iva):
    db.execute(
        """
        INSERT INTO cfdi (empresa_id, uuid, tipo_comprobante, metodo_pago, forma_pago,
                          estado, rfc_emisor, rfc_receptor, fecha_emision,
                          subtotal, total, iva_trasladado)
        VALUES (%s, %s, 'I', 'PUE', '03', 'vigente', %s, %s, '2026-01-10',
                %s, %s, %s)
        """,
        (empresa_id, uuid, emisor, receptor, subtotal, total, iva),
    )


def test_e2e_cedula_iva_consultora():
    from backend import db

    db.init_db()
    _limpiar(db)

    from fastapi.testclient import TestClient
    import backend.main_api as main

    client = TestClient(main.app)
    try:
        # 1. Registrar contador
        r = client.post("/api/v1/auth/register",
                        json={"email": EMAIL, "password": "Test1234!", "nombre": "E2E"})
        assert r.status_code == 201, r.text
        headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

        # 2. Alta de empresa
        r = client.post("/api/v1/mis-empresas", headers=headers,
                        json={"rfc": RFC, "razon_social": "Consultora E2E"})
        assert r.status_code == 201, r.text
        empresa_id = r.json()["empresa_id"]

        # 3. Insertar CFDIs del caso consultora: 1 ingreso ($1,600) + 6 gastos ($736)
        _insertar_cfdi(db, empresa_id, "E2E-ING", RFC, "XAXX010101000", "10000", "11600", "1600")
        for i, iva in enumerate(["320", "80", "80", "96", "80", "80"]):
            _insertar_cfdi(db, empresa_id, f"E2E-GAS-{i}", "PROV010101AAA", RFC,
                           "1000", "1160", iva)

        # 4. Consultar la cédula (DB real, sin mocks)
        r = client.get(f"/api/v1/empresas/{empresa_id}/cedula-iva/{PERIODO}", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()

        assert body["trasladado"]["total"] == 1600.0
        assert body["acreditable"]["bruto"] == 736.0
        assert body["resultado"]["iva_por_pagar"] == 864.0
        assert body["resultado"]["saldo_a_cargo"] == 864.0
    finally:
        _limpiar(db)
