"""E2E de ISR provisional contra un Postgres real (docker compose).

Levanta el flujo real (register -> alta empresa -> insertar CFDIs -> GET
isr-provisional) y lo cruza contra el cálculo a mano del Caso A de la spec
(docs/modulo-isr-provisional-spec.md §2): continuidad ene->mar 2026 con
CU=0.0850, sin PTU/pérdidas/retención -> pagos 25,500 / 30,600 / 20,400.

Se salta automáticamente si no hay DB disponible. Levantar la DB con:
`docker compose up -d db`.
"""
import os
from decimal import Decimal

import psycopg2
import pytest

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/fiscalcore"
)

RFC = "COE010101E2I"
EMAIL = "e2e-isr-provisional@test.local"
EJERCICIO = "2026"


def _db_disponible() -> bool:
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=2)
        conn.close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_disponible(), reason="Postgres no disponible (docker compose up -d db)")


def _limpiar(db):
    db.execute(
        "DELETE FROM cfdi WHERE empresa_id IN (SELECT id FROM empresas WHERE rfc = %s)", (RFC,))
    db.execute(
        "DELETE FROM config_isr_empresa WHERE empresa_id IN (SELECT id FROM empresas WHERE rfc = %s)", (RFC,))
    db.execute(
        "DELETE FROM usuario_empresas WHERE empresa_id IN (SELECT id FROM empresas WHERE rfc = %s)", (RFC,))
    db.execute("DELETE FROM empresas WHERE rfc = %s", (RFC,))
    db.execute("DELETE FROM usuarios WHERE email = %s", (EMAIL,))


def _insertar_cfdi(db, empresa_id, uuid, fecha_emision, subtotal, isr_retenido="0"):
    db.execute(
        """
        INSERT INTO cfdi (empresa_id, uuid, tipo_comprobante, metodo_pago, forma_pago,
                          estado, rfc_emisor, rfc_receptor, fecha_emision, subtotal, total,
                          isr_retenido)
        VALUES (%s, %s, 'I', 'PUE', '03', 'vigente', %s, 'XAXX010101000', %s, %s, %s, %s)
        """,
        (empresa_id, uuid, RFC, fecha_emision, subtotal, subtotal, isr_retenido),
    )


def test_e2e_isr_provisional_caso_a_continuidad_del_ejercicio():
    from backend import db

    db.init_db()
    _limpiar(db)

    from fastapi.testclient import TestClient
    import backend.main_api as main

    client = TestClient(main.app)
    try:
        # 1. Registrar contador
        r = client.post("/api/v1/auth/register",
                        json={"email": EMAIL, "password": "Test1234!", "nombre": "E2E ISR"})
        assert r.status_code == 201, r.text
        headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

        # 2. Alta de empresa
        r = client.post("/api/v1/mis-empresas", headers=headers,
                        json={"rfc": RFC, "razon_social": "E2E ISR Provisional"})
        assert r.status_code == 201, r.text
        empresa_id = r.json()["empresa_id"]

        # 3. Capturar CU del ejercicio (insumo externo, sin endpoint aún - Días 7-10)
        db.execute(
            """
            INSERT INTO config_isr_empresa (empresa_id, ejercicio, coeficiente_utilidad,
                                            perdidas_pendientes, ptu_pagada, tasa_isr)
            VALUES (%s, %s, %s, 0, 0, 0.30)
            """,
            (empresa_id, EJERCICIO, Decimal("0.0850")),
        )

        # 4. Insertar ingresos del Caso A: ene 1,000,000 / feb 1,200,000 / mar 800,000
        _insertar_cfdi(db, empresa_id, "E2E-ISR-ENE", "2026-01-15", "1000000")
        _insertar_cfdi(db, empresa_id, "E2E-ISR-FEB", "2026-02-15", "1200000")
        _insertar_cfdi(db, empresa_id, "E2E-ISR-MAR", "2026-03-15", "800000")

        # 5. Consultar cada mes (DB real, sin mocks) y cruzar contra el cálculo a mano
        r_ene = client.get(f"/api/v1/empresas/{empresa_id}/isr-provisional/2026-01", headers=headers)
        r_feb = client.get(f"/api/v1/empresas/{empresa_id}/isr-provisional/2026-02", headers=headers)
        r_mar = client.get(f"/api/v1/empresas/{empresa_id}/isr-provisional/2026-03", headers=headers)

        assert r_ene.status_code == 200, r_ene.text
        assert r_feb.status_code == 200, r_feb.text
        assert r_mar.status_code == 200, r_mar.text

        ene, feb, mar = r_ene.json(), r_feb.json(), r_mar.json()

        assert ene["ingreso_nominal_acumulado"] == 1000000.0
        assert ene["isr_acumulado"] == 25500.0
        assert ene["pagos_provisionales_anteriores"] == 0.0
        assert ene["resultado"]["pago_del_mes"] == 25500.0

        assert feb["ingreso_nominal_acumulado"] == 2200000.0
        assert feb["isr_acumulado"] == 56100.0
        assert feb["pagos_provisionales_anteriores"] == 25500.0
        assert feb["resultado"]["pago_del_mes"] == 30600.0

        assert mar["ingreso_nominal_acumulado"] == 3000000.0
        assert mar["isr_acumulado"] == 76500.0
        assert mar["pagos_provisionales_anteriores"] == 56100.0
        assert mar["resultado"]["pago_del_mes"] == 20400.0
    finally:
        _limpiar(db)


def test_e2e_isr_provisional_sin_cu_devuelve_404():
    from backend import db

    db.init_db()
    _limpiar(db)

    from fastapi.testclient import TestClient
    import backend.main_api as main

    client = TestClient(main.app)
    try:
        r = client.post("/api/v1/auth/register",
                        json={"email": EMAIL, "password": "Test1234!", "nombre": "E2E ISR"})
        headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
        r = client.post("/api/v1/mis-empresas", headers=headers,
                        json={"rfc": RFC, "razon_social": "E2E ISR Sin CU"})
        empresa_id = r.json()["empresa_id"]

        # Sin config_isr_empresa capturada -> 404 controlado (no 500)
        r = client.get(f"/api/v1/empresas/{empresa_id}/isr-provisional/2026-01", headers=headers)
        assert r.status_code == 404
    finally:
        _limpiar(db)


def test_e2e_isr_provisional_retencion_de_mes_anterior_no_subestima_el_pago():
    """Regresión Kilo Code Review (PR #4), de punta a punta contra Postgres real:
    enero retuvo $5,000 de ISR -> su pago real fue 20,500, no 25,500. El pago de
    febrero debe restar ese pago real como pagos_previos, no el ISR acumulado
    bruto de enero ignorando su retención."""
    from backend import db

    db.init_db()
    _limpiar(db)

    from fastapi.testclient import TestClient
    import backend.main_api as main

    client = TestClient(main.app)
    try:
        r = client.post("/api/v1/auth/register",
                        json={"email": EMAIL, "password": "Test1234!", "nombre": "E2E ISR"})
        assert r.status_code == 201, r.text
        headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

        r = client.post("/api/v1/mis-empresas", headers=headers,
                        json={"rfc": RFC, "razon_social": "E2E ISR Retención"})
        assert r.status_code == 201, r.text
        empresa_id = r.json()["empresa_id"]

        db.execute(
            """
            INSERT INTO config_isr_empresa (empresa_id, ejercicio, coeficiente_utilidad,
                                            perdidas_pendientes, ptu_pagada, tasa_isr)
            VALUES (%s, %s, %s, 0, 0, 0.30)
            """,
            (empresa_id, EJERCICIO, Decimal("0.0850")),
        )

        _insertar_cfdi(db, empresa_id, "E2E-RET-ENE", "2026-01-15", "1000000", isr_retenido="5000")
        _insertar_cfdi(db, empresa_id, "E2E-RET-FEB", "2026-02-15", "1200000")

        r_feb = client.get(f"/api/v1/empresas/{empresa_id}/isr-provisional/2026-02", headers=headers)
        assert r_feb.status_code == 200, r_feb.text
        feb = r_feb.json()

        assert feb["pagos_provisionales_anteriores"] == 20500.0
        assert feb["resultado"]["pago_del_mes"] == 35600.0
    finally:
        _limpiar(db)
