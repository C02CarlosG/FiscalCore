"""E2E de deducciones autorizadas contra un Postgres real (docker compose).

Levanta el flujo real (register -> alta empresa -> insertar CFDIs y pagos ->
GET deducciones) y lo cruza contra el cálculo a mano del caso "Ferretería El
Tornillo" de la spec (docs/modulo-cogs-deducciones-spec.md):

- Enero (Caso A): gasto 33,000 (renta 20,000 + honorarios PPD pagados 15,000
  - NC 2,000), costo identificado 80,000 (mercancía G01), inversión
  identificada 18,000 (equipo I04), excluido por efectivo 3,000 (papelería
  pagada en efectivo > $2,000).
- Febrero (Caso B, acumulado del ejercicio): + mercancía G01 40,000 (costo)
  y servicios 10,000 (gasto) -> acumulado gasto 43,000, costo 120,000.

Se salta automáticamente si no hay DB disponible. Levantar la DB con:
`docker compose up -d db`.
"""
from decimal import Decimal

import pytest

from backend.tests.conftest import db_disponible

RFC = "COE010101E2D"
PROV = "PROV010101AAA"
EMAIL = "e2e-deducciones@test.local"


pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


def _limpiar(db):
    db.execute(
        "DELETE FROM pagos_relaciones WHERE pago_id IN "
        "(SELECT id FROM pagos_cfdi WHERE empresa_id IN (SELECT id FROM empresas WHERE rfc = %s))", (RFC,))
    db.execute(
        "DELETE FROM pagos_cfdi WHERE empresa_id IN (SELECT id FROM empresas WHERE rfc = %s)", (RFC,))
    db.execute(
        "DELETE FROM cfdi WHERE empresa_id IN (SELECT id FROM empresas WHERE rfc = %s)", (RFC,))
    db.execute(
        "DELETE FROM usuario_empresas WHERE empresa_id IN (SELECT id FROM empresas WHERE rfc = %s)", (RFC,))
    db.execute("DELETE FROM empresas WHERE rfc = %s", (RFC,))
    db.execute("DELETE FROM usuarios WHERE email = %s", (EMAIL,))


def _insertar_cfdi(db, empresa_id, uuid, **kw):
    base = {
        "tipo_comprobante": "I",
        "metodo_pago": "PUE",
        "forma_pago": "03",
        "uso_cfdi": "G03",
        "estado": "vigente",
        "fecha_emision": "2026-01-15",
        "subtotal": Decimal("0"),
        "total": Decimal("0"),
    }
    base.update(kw)
    db.execute(
        """
        INSERT INTO cfdi (empresa_id, uuid, tipo_comprobante, metodo_pago, forma_pago,
                          uso_cfdi, estado, rfc_emisor, rfc_receptor, fecha_emision,
                          subtotal, total)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (empresa_id, uuid, base["tipo_comprobante"], base["metodo_pago"], base["forma_pago"],
         base["uso_cfdi"], base["estado"], PROV, RFC, base["fecha_emision"],
         base["subtotal"], base["total"]),
    )


def _insertar_pago(db, empresa_id, cfdi_uuid, importe, fecha_pago):
    row = db.execute("SELECT id FROM cfdi WHERE uuid = %s", (cfdi_uuid,), returning=True)
    pago = db.execute(
        """
        INSERT INTO pagos_cfdi (empresa_id, cfdi_id, uuid_cfdi_pago, fecha_pago, monto)
        VALUES (%s, %s, %s, %s, %s) RETURNING id
        """,
        (empresa_id, row["id"], "PAGO-" + cfdi_uuid, fecha_pago, importe),
        returning=True,
    )
    db.execute(
        "INSERT INTO pagos_relaciones (pago_id, cfdi_uuid, importe_pagado) VALUES (%s, %s, %s)",
        (pago["id"], cfdi_uuid, importe),
    )


def test_e2e_deducciones_ferreteria_caso_a_y_b():
    from backend import db

    db.init_db()
    _limpiar(db)

    from fastapi.testclient import TestClient
    import backend.main_api as main

    client = TestClient(main.app)
    try:
        # 1. Registrar contador
        r = client.post("/api/v1/auth/register",
                        json={"email": EMAIL, "password": "Test1234!", "nombre": "E2E Deducciones"})
        assert r.status_code == 201, r.text
        headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

        # 2. Alta de empresa
        r = client.post("/api/v1/mis-empresas", headers=headers,
                        json={"rfc": RFC, "razon_social": "Ferretería El Tornillo"})
        assert r.status_code == 201, r.text
        empresa_id = r.json()["empresa_id"]

        # 3. Caso A (enero): gasto, costo, inversión, excluido por efectivo
        _insertar_cfdi(db, empresa_id, "RENTA", subtotal=Decimal("20000"), total=Decimal("20000"))
        _insertar_cfdi(db, empresa_id, "HON", metodo_pago="PPD",
                       subtotal=Decimal("15000"), total=Decimal("15000"))
        _insertar_pago(db, empresa_id, "HON", Decimal("15000"), "2026-01-20")
        _insertar_cfdi(db, empresa_id, "NC-RENTA", tipo_comprobante="E",
                       subtotal=Decimal("2000"), total=Decimal("2000"))
        _insertar_cfdi(db, empresa_id, "PAPEL", forma_pago="01",
                       subtotal=Decimal("3000"), total=Decimal("3000"))
        _insertar_cfdi(db, empresa_id, "MERCANCIA", uso_cfdi="G01",
                       subtotal=Decimal("80000"), total=Decimal("80000"))
        _insertar_cfdi(db, empresa_id, "EQUIPO", uso_cfdi="I04",
                       subtotal=Decimal("18000"), total=Decimal("18000"))

        # 4. Caso B (febrero): amplía el acumulado del ejercicio
        _insertar_cfdi(db, empresa_id, "MERCANCIA-FEB", uso_cfdi="G01", fecha_emision="2026-02-10",
                       subtotal=Decimal("40000"), total=Decimal("40000"))
        _insertar_cfdi(db, empresa_id, "SERVICIOS-FEB", fecha_emision="2026-02-10",
                       subtotal=Decimal("10000"), total=Decimal("10000"))

        # 5. Consultar cada periodo (DB real, sin mocks) y cruzar contra el cálculo a mano
        r_ene = client.get(f"/api/v1/empresas/{empresa_id}/deducciones/2026-01", headers=headers)
        r_feb = client.get(f"/api/v1/empresas/{empresa_id}/deducciones/2026-02", headers=headers)

        assert r_ene.status_code == 200, r_ene.text
        assert r_feb.status_code == 200, r_feb.text

        ene, feb = r_ene.json(), r_feb.json()

        # Caso A: enero == acumulado del ejercicio a ese corte
        assert ene["del_mes"]["gasto"] == 33000.0
        assert ene["del_mes"]["costo_identificado"] == 80000.0
        assert ene["del_mes"]["inversion_identificada"] == 18000.0
        assert ene["del_mes"]["excluido_efectivo"] == 3000.0
        assert ene["total_deducible_mes"] == 33000.0
        assert ene["acumulado_ejercicio"]["gasto"] == 33000.0
        assert ene["total_deducible_acumulado"] == 33000.0

        # Caso B: del mes de febrero solo lo nuevo; acumulado suma enero + febrero
        assert feb["del_mes"]["gasto"] == 10000.0
        assert feb["del_mes"]["costo_identificado"] == 40000.0
        assert feb["total_deducible_mes"] == 10000.0
        assert feb["acumulado_ejercicio"]["gasto"] == 43000.0
        assert feb["acumulado_ejercicio"]["costo_identificado"] == 120000.0
        assert feb["acumulado_ejercicio"]["inversion_identificada"] == 18000.0
        assert feb["acumulado_ejercicio"]["excluido_efectivo"] == 3000.0
        assert feb["total_deducible_acumulado"] == 43000.0
    finally:
        _limpiar(db)


def test_e2e_deducciones_sin_cfdis_devuelve_ceros():
    from backend import db

    db.init_db()
    _limpiar(db)

    from fastapi.testclient import TestClient
    import backend.main_api as main

    client = TestClient(main.app)
    try:
        r = client.post("/api/v1/auth/register",
                        json={"email": EMAIL, "password": "Test1234!", "nombre": "E2E Deducciones"})
        headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
        r = client.post("/api/v1/mis-empresas", headers=headers,
                        json={"rfc": RFC, "razon_social": "Ferretería Sin Movimientos"})
        empresa_id = r.json()["empresa_id"]

        r = client.get(f"/api/v1/empresas/{empresa_id}/deducciones/2026-01", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total_deducible_mes"] == 0.0
        assert body["total_deducible_acumulado"] == 0.0
    finally:
        _limpiar(db)
