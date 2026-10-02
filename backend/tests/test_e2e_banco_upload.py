"""E2E de la subida de estados de cuenta contra un Postgres real.

Regresiones cubiertas:
- volver a subir el mismo archivo duplicaba todos los movimientos;
- un XLSX con celdas de fecha reales se "procesaba" con 0 movimientos.

Se salta automáticamente si no hay DB disponible.
"""
from datetime import datetime
from io import BytesIO

import pytest

from backend.tests.conftest import db_disponible, headers_usuario_e2e

RFC = "BAN010101E2E"
EMAIL = "e2e-banco-upload@test.local"
PERIODO = "2026-01"

CSV_ENERO = (
    "Fecha,Concepto,Referencia,Deposito,Cargo,Saldo\n"
    "2026-01-05,SPEI RECIBIDO CLIENTE UNO,R1,11600.00,,21600.00\n"
    "2026-01-07,COMISION,,,10.00,\n"
    "2026-01-07,COMISION,,,10.00,\n"      # dos comisiones idénticas legítimas
    "2026-01-09,PAGO PROVEEDOR,R2,,2320.00,19260.00\n"
).encode()

# Segundo archivo que se traslapa con el primero (repite el día 9) y agrega el 12.
CSV_TRASLAPE = (
    "Fecha,Concepto,Referencia,Deposito,Cargo,Saldo\n"
    "2026-01-09,PAGO PROVEEDOR,R2,,2320.00,19260.00\n"
    "2026-01-12,SPEI RECIBIDO CLIENTE DOS,R3,5800.00,,25060.00\n"
).encode()

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


def _limpiar(db):
    db.execute("DELETE FROM empresas WHERE rfc = %s", (RFC,))  # movimientos caen por CASCADE
    db.execute("DELETE FROM usuarios WHERE email = %s", (EMAIL,))


@pytest.fixture
def entorno():
    from fastapi.testclient import TestClient

    import backend.main_api as main
    from backend import db

    db.init_db()
    _limpiar(db)
    client = TestClient(main.app)
    try:
        headers = headers_usuario_e2e(db, EMAIL)
        r = client.post("/api/v1/mis-empresas", headers=headers,
                        json={"rfc": RFC, "razon_social": "Banco E2E"})
        assert r.status_code == 201, r.text
        yield db, client, headers, r.json()["empresa_id"]
    finally:
        _limpiar(db)


def _subir(client, headers, empresa_id, nombre, contenido, content_type="text/csv", banco="bbva"):
    r = client.post(
        f"/api/v1/empresas/{empresa_id}/banco/upload", headers=headers,
        data={"periodo": PERIODO, "banco": banco},
        files={"archivo": (nombre, contenido, content_type)},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _total(db, empresa_id):
    return db.query_one(
        "SELECT COUNT(*) AS n FROM movimientos_bancarios WHERE empresa_id = %s", (empresa_id,))["n"]


def test_resubir_el_mismo_estado_de_cuenta_no_duplica_movimientos(entorno):
    db, client, headers, empresa_id = entorno

    primera = _subir(client, headers, empresa_id, "enero.csv", CSV_ENERO)
    assert primera["registros_procesados"] == 4  # incluye las dos comisiones idénticas
    assert _total(db, empresa_id) == 4

    segunda = _subir(client, headers, empresa_id, "enero.csv", CSV_ENERO)
    assert segunda["registros_procesados"] == 0
    assert "4 ya estaban cargados" in segunda["mensaje"]
    assert _total(db, empresa_id) == 4


def test_archivo_que_se_traslapa_solo_agrega_lo_nuevo(entorno):
    db, client, headers, empresa_id = entorno
    _subir(client, headers, empresa_id, "enero.csv", CSV_ENERO)

    r = _subir(client, headers, empresa_id, "enero-b.csv", CSV_TRASLAPE)

    assert r["registros_procesados"] == 1
    assert _total(db, empresa_id) == 5


def test_mismo_movimiento_en_otro_banco_no_se_considera_duplicado(entorno):
    db, client, headers, empresa_id = entorno
    _subir(client, headers, empresa_id, "enero.csv", CSV_ENERO, banco="bbva")

    r = _subir(client, headers, empresa_id, "enero.csv", CSV_ENERO, banco="santander")

    assert r["registros_procesados"] == 4
    assert _total(db, empresa_id) == 8


def test_xlsx_con_celdas_de_fecha_y_extension_en_mayusculas(entorno):
    import openpyxl

    db, client, headers, empresa_id = entorno
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Fecha", "Concepto", "Deposito", "Cargo", "Saldo"])
    ws.append([datetime(2026, 1, 15), "SPEI RECIBIDO", 1500.50, None, 10000])
    ws.append([datetime(2026, 1, 16), "PAGO PROVEEDOR", None, 300, 9700])
    buf = BytesIO()
    wb.save(buf)

    r = _subir(client, headers, empresa_id, "ESTADO.XLSX", buf.getvalue(),
               content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    assert r["registros_procesados"] == 2, r
    filas = db.query_all(
        "SELECT fecha::text AS fecha, monto::text AS monto FROM movimientos_bancarios "
        "WHERE empresa_id = %s ORDER BY fecha", (empresa_id,))
    assert filas == [
        {"fecha": "2026-01-15", "monto": "1500.50"},
        {"fecha": "2026-01-16", "monto": "-300.00"},
    ]
