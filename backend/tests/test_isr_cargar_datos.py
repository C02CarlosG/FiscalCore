"""Pruebas de _cargar_datos_isr contra un Postgres real (docker compose).

A diferencia del motor puro (test_isr.py) y del endpoint mockeado
(test_reportes_isr.py), estas pruebas validan que las queries SQL del loader
filtran correctamente los CFDIs (casos borde §2 de la spec) y que el ingreso
nominal se acumula mes a mes. Se salta si no hay DB (Día 9).
"""
from decimal import Decimal

import pytest

from backend.tests.conftest import db_disponible

RFC = "COE010101ISR"
OTRO_RFC = "PROV010101AAA"
EJERCICIO = "2026"


pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


def _limpiar(db, empresa_id=None):
    if empresa_id:
        db.execute("DELETE FROM cfdi WHERE empresa_id = %s", (empresa_id,))
        db.execute("DELETE FROM config_isr_empresa WHERE empresa_id = %s", (empresa_id,))
    db.execute("DELETE FROM cfdi WHERE empresa_id IN (SELECT id FROM empresas WHERE rfc = %s)", (RFC,))
    db.execute("DELETE FROM config_isr_empresa WHERE empresa_id IN (SELECT id FROM empresas WHERE rfc = %s)", (RFC,))
    db.execute("DELETE FROM empresas WHERE rfc = %s", (RFC,))


def _crear_empresa(db):
    row = db.execute(
        "INSERT INTO empresas (rfc, razon_social) VALUES (%s, %s) RETURNING id",
        (RFC, "E2E ISR"),
        returning=True,
    )
    return str(row["id"])


def _cfdi(db, empresa_id, uuid, **kw):
    base = {
        "tipo_comprobante": "I",
        "metodo_pago": "PUE",
        "estado": "vigente",
        "es_anticipo_sat": False,
        "rfc_emisor": RFC,
        "rfc_receptor": "XAXX010101000",
        "fecha_emision": "2026-01-15",
        "subtotal": Decimal("0"),
        "total": Decimal("0"),
        "isr_retenido": Decimal("0"),
    }
    base.update(kw)
    db.execute(
        """
        INSERT INTO cfdi (empresa_id, uuid, tipo_comprobante, metodo_pago, estado,
                          es_anticipo_sat, rfc_emisor, rfc_receptor, fecha_emision,
                          subtotal, total, isr_retenido)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (empresa_id, uuid, base["tipo_comprobante"], base["metodo_pago"], base["estado"],
         base["es_anticipo_sat"], base["rfc_emisor"], base["rfc_receptor"], base["fecha_emision"],
         base["subtotal"], base["total"], base["isr_retenido"]),
    )


@pytest.fixture
def empresa_isr():
    from backend import db
    db.init_db()
    empresa_id = _crear_empresa(db)
    db.execute(
        """
        INSERT INTO config_isr_empresa (empresa_id, ejercicio, coeficiente_utilidad,
                                        perdidas_pendientes, ptu_pagada, tasa_isr)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (empresa_id, EJERCICIO, Decimal("0.0850"), Decimal("0"), Decimal("0"), Decimal("0.30")),
    )
    yield db, empresa_id
    _limpiar(db, empresa_id)


def test_nota_de_credito_resta_del_ingreso_nominal(empresa_isr):
    from backend.routers.reportes import _cargar_datos_isr

    db, empresa_id = empresa_isr
    _cfdi(db, empresa_id, "NC-ING", subtotal=Decimal("10000"), total=Decimal("10000"))
    _cfdi(db, empresa_id, "NC-NC", tipo_comprobante="E", subtotal=Decimal("2000"), total=Decimal("2000"))

    _, ingresos_por_mes, _ = _cargar_datos_isr(empresa_id, "2026-01")
    assert ingresos_por_mes[1] == Decimal("8000")


def test_cfdi_recibido_no_es_ingreso(empresa_isr):
    from backend.routers.reportes import _cargar_datos_isr

    db, empresa_id = empresa_isr
    _cfdi(db, empresa_id, "REC-1", rfc_emisor=OTRO_RFC, rfc_receptor=RFC,
          subtotal=Decimal("5000"), total=Decimal("5000"))

    _, ingresos_por_mes, _ = _cargar_datos_isr(empresa_id, "2026-01")
    assert ingresos_por_mes[1] == Decimal("0")


def test_ppd_sin_rep_si_acumula_isr(empresa_isr):
    from backend.routers.reportes import _cargar_datos_isr

    db, empresa_id = empresa_isr
    _cfdi(db, empresa_id, "PPD-1", metodo_pago="PPD", subtotal=Decimal("15000"), total=Decimal("15000"))

    _, ingresos_por_mes, _ = _cargar_datos_isr(empresa_id, "2026-01")
    assert ingresos_por_mes[1] == Decimal("15000")


def test_cfdi_cancelado_se_excluye(empresa_isr):
    from backend.routers.reportes import _cargar_datos_isr

    db, empresa_id = empresa_isr
    _cfdi(db, empresa_id, "CANC-1", estado="cancelado", subtotal=Decimal("9000"), total=Decimal("9000"))

    _, ingresos_por_mes, _ = _cargar_datos_isr(empresa_id, "2026-01")
    assert ingresos_por_mes[1] == Decimal("0")


def test_anticipo_sat_se_excluye(empresa_isr):
    from backend.routers.reportes import _cargar_datos_isr

    db, empresa_id = empresa_isr
    _cfdi(db, empresa_id, "ANT-1", es_anticipo_sat=True, subtotal=Decimal("3000"), total=Decimal("3000"))

    _, ingresos_por_mes, _ = _cargar_datos_isr(empresa_id, "2026-01")
    assert ingresos_por_mes[1] == Decimal("0")


def test_retencion_isr_del_mes_declarado(empresa_isr):
    from backend.routers.reportes import _cargar_datos_isr

    db, empresa_id = empresa_isr
    _cfdi(db, empresa_id, "RET-ENE", subtotal=Decimal("1000"), total=Decimal("1000"),
          isr_retenido=Decimal("100"))
    _cfdi(db, empresa_id, "RET-FEB", fecha_emision="2026-02-10",
          subtotal=Decimal("1000"), total=Decimal("1000"), isr_retenido=Decimal("50"))

    _, _, retencion_enero = _cargar_datos_isr(empresa_id, "2026-01")
    _, _, retencion_febrero = _cargar_datos_isr(empresa_id, "2026-02")
    assert retencion_enero == Decimal("100")
    assert retencion_febrero == Decimal("50")


def test_continuidad_del_acumulado_multi_mes(empresa_isr):
    from backend.routers.reportes import _cargar_datos_isr

    db, empresa_id = empresa_isr
    _cfdi(db, empresa_id, "M1", fecha_emision="2026-01-10", subtotal=Decimal("1000000"), total=Decimal("1000000"))
    _cfdi(db, empresa_id, "M2", fecha_emision="2026-02-10", subtotal=Decimal("1200000"), total=Decimal("1200000"))
    _cfdi(db, empresa_id, "M3", fecha_emision="2026-03-10", subtotal=Decimal("800000"), total=Decimal("800000"))

    _, ingresos_por_mes, _ = _cargar_datos_isr(empresa_id, "2026-03")
    assert ingresos_por_mes[1] == Decimal("1000000")
    assert ingresos_por_mes[2] == Decimal("2200000")
    assert ingresos_por_mes[3] == Decimal("3000000")


def test_sin_config_isr_devuelve_none(empresa_isr):
    from backend.routers.reportes import _cargar_datos_isr

    db, empresa_id = empresa_isr
    db.execute("DELETE FROM config_isr_empresa WHERE empresa_id = %s", (empresa_id,))

    config, ingresos_por_mes, retencion = _cargar_datos_isr(empresa_id, "2026-01")
    assert config is None
    assert ingresos_por_mes == {}
    assert retencion == Decimal("0")
