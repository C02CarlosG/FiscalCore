"""Pruebas de _cargar_datos_deducciones contra un Postgres real (docker compose).

A diferencia del motor puro (test_deducciones.py) y del endpoint mockeado
(test_reportes_deducciones.py), estas pruebas validan que la query SQL del
loader trae los candidatos correctos (casos borde del filtrado, mismo patrón
que el Día 9 de ISR en test_isr_cargar_datos.py). Se salta si no hay DB.

A diferencia del loader de ISR, este NO filtra `es_anticipo_sat` ni
`rfc_receptor` en SQL: esos filtros son responsabilidad de la función pura
`deducciones_periodo` (ver backend/deducciones.py), que también decide qué
cubeta corresponde a cada CFDI vía `uso_cfdi`. El loader solo acota por
`estado = 'vigente'` y por fecha (con la excepción deliberada de que los PPD
se traen sin importar su `fecha_emision`, porque su deducibilidad depende de
la fecha del REP, no de la fecha de emisión).

Alcance NO cubierto por este módulo (documentado también en
docs/modulo-cogs-deducciones-spec.md): depreciación de inversiones
(Art. 31-36 LISR) y costeo absorbente/histórico de mercancías (Art. 39-43
LISR). El MVP solo identifica los montos de "inversión" y "costo" por
`uso_cfdi`, pero no los deduce — ver `inversion_identificada` /
`costo_identificado` en el resultado de `deducciones_periodo`, que
deliberadamente no se suman a `total_deducible`.
"""
import os
from decimal import Decimal

import psycopg2
import pytest

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/fiscalcore"
)

RFC = "COD010101DED"
OTRO_RFC = "COD020202DE2"
PROV = "PROV010101AAA"
EJERCICIO = "2026"


def _db_disponible() -> bool:
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=2)
        conn.close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_disponible(), reason="Postgres no disponible (docker compose up -d db)")


def _limpiar(db, empresa_ids):
    for empresa_id in empresa_ids:
        db.execute("DELETE FROM pagos_relaciones WHERE pago_id IN (SELECT id FROM pagos_cfdi WHERE empresa_id = %s)", (empresa_id,))
        db.execute("DELETE FROM pagos_cfdi WHERE empresa_id = %s", (empresa_id,))
        db.execute("DELETE FROM cfdi WHERE empresa_id = %s", (empresa_id,))
    db.execute("DELETE FROM empresas WHERE rfc IN (%s, %s)", (RFC, OTRO_RFC))


def _crear_empresa(db, rfc, nombre):
    row = db.execute(
        "INSERT INTO empresas (rfc, razon_social) VALUES (%s, %s) RETURNING id",
        (rfc, nombre),
        returning=True,
    )
    return str(row["id"])


def _cfdi(db, empresa_id, uuid, **kw):
    base = {
        "tipo_comprobante": "I",
        "metodo_pago": "PUE",
        "estado": "vigente",
        "es_anticipo_sat": False,
        "uso_cfdi": "G03",
        "rfc_emisor": PROV,
        "rfc_receptor": RFC,
        "forma_pago": "03",
        "fecha_emision": "2026-01-15",
        "subtotal": Decimal("0"),
        "total": Decimal("0"),
    }
    base.update(kw)
    db.execute(
        """
        INSERT INTO cfdi (empresa_id, uuid, tipo_comprobante, metodo_pago, estado,
                          es_anticipo_sat, uso_cfdi, rfc_emisor, rfc_receptor,
                          forma_pago, fecha_emision, subtotal, total)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (empresa_id, uuid, base["tipo_comprobante"], base["metodo_pago"], base["estado"],
         base["es_anticipo_sat"], base["uso_cfdi"], base["rfc_emisor"], base["rfc_receptor"],
         base["forma_pago"], base["fecha_emision"], base["subtotal"], base["total"]),
    )


def _pago(db, empresa_id, cfdi_id, cfdi_uuid, importe, fecha_pago):
    row = db.execute(
        """
        INSERT INTO pagos_cfdi (empresa_id, cfdi_id, uuid_cfdi_pago, fecha_pago, monto)
        VALUES (%s, %s, %s, %s, %s) RETURNING id
        """,
        (empresa_id, cfdi_id, "PAGO-" + cfdi_uuid, fecha_pago, importe),
        returning=True,
    )
    db.execute(
        """
        INSERT INTO pagos_relaciones (pago_id, cfdi_uuid, importe_pagado)
        VALUES (%s, %s, %s)
        """,
        (row["id"], cfdi_uuid, importe),
    )


def _cfdi_id(db, uuid):
    row = db.execute("SELECT id FROM cfdi WHERE uuid = %s", (uuid,), returning=True)
    return row["id"]


@pytest.fixture
def empresa_ded():
    from backend import db
    db.init_db()
    empresa_id = _crear_empresa(db, RFC, "E2E Deducciones")
    otra_empresa_id = _crear_empresa(db, OTRO_RFC, "Otra Empresa")
    yield db, empresa_id, otra_empresa_id
    _limpiar(db, [empresa_id, otra_empresa_id])


def test_estado_vigente_filtra_cancelados(empresa_ded):
    from backend.routers.reportes import _cargar_datos_deducciones

    db, empresa_id, _ = empresa_ded
    _cfdi(db, empresa_id, "CANC-1", estado="cancelado", subtotal=Decimal("9000"), total=Decimal("9000"))

    _, cfdis, _ = _cargar_datos_deducciones(empresa_id, "2026-01")
    assert cfdis == []


def test_ppd_se_incluye_sin_importar_fecha_emision(empresa_ded):
    from backend.routers.reportes import _cargar_datos_deducciones

    db, empresa_id, _ = empresa_ded
    _cfdi(db, empresa_id, "PPD-VIEJO", metodo_pago="PPD", fecha_emision="2025-11-01",
          subtotal=Decimal("10000"), total=Decimal("11600"))

    _, cfdis, _ = _cargar_datos_deducciones(empresa_id, "2026-01")
    assert [c["uuid"] for c in cfdis] == ["PPD-VIEJO"]


def test_pue_fuera_de_rango_no_se_incluye(empresa_ded):
    from backend.routers.reportes import _cargar_datos_deducciones

    db, empresa_id, _ = empresa_ded
    _cfdi(db, empresa_id, "PUE-DIC", fecha_emision="2025-12-31",
          subtotal=Decimal("5000"), total=Decimal("5000"))

    _, cfdis, _ = _cargar_datos_deducciones(empresa_id, "2026-01")
    assert cfdis == []


def test_nota_de_credito_se_incluye_en_el_rango(empresa_ded):
    from backend.routers.reportes import _cargar_datos_deducciones

    db, empresa_id, _ = empresa_ded
    _cfdi(db, empresa_id, "NC-1", tipo_comprobante="E",
          subtotal=Decimal("2000"), total=Decimal("2000"))

    _, cfdis, _ = _cargar_datos_deducciones(empresa_id, "2026-01")
    assert [c["uuid"] for c in cfdis] == ["NC-1"]


def test_cfdis_de_otra_empresa_no_se_incluyen(empresa_ded):
    from backend.routers.reportes import _cargar_datos_deducciones

    db, empresa_id, otra_empresa_id = empresa_ded
    _cfdi(db, otra_empresa_id, "AJENO-1", rfc_receptor=OTRO_RFC,
          subtotal=Decimal("7000"), total=Decimal("7000"))

    _, cfdis, _ = _cargar_datos_deducciones(empresa_id, "2026-01")
    assert cfdis == []


def test_pagos_filtrados_por_fecha_pago(empresa_ded):
    from backend.routers.reportes import _cargar_datos_deducciones

    db, empresa_id, _ = empresa_ded
    _cfdi(db, empresa_id, "PPD-1", metodo_pago="PPD", subtotal=Decimal("10000"), total=Decimal("11600"))
    cfdi_id = _cfdi_id(db, "PPD-1")
    _pago(db, empresa_id, cfdi_id, "PPD-1", Decimal("11600"), "2026-01-20")
    _pago(db, empresa_id, cfdi_id, "PPD-1", Decimal("5000"), "2026-03-05")

    _, _, pagos = _cargar_datos_deducciones(empresa_id, "2026-01")
    assert len(pagos) == 1
    assert pagos[0]["importe_pagado"] == Decimal("11600.00")


def test_pagos_de_otra_empresa_no_se_incluyen(empresa_ded):
    from backend.routers.reportes import _cargar_datos_deducciones

    db, empresa_id, otra_empresa_id = empresa_ded
    _cfdi(db, otra_empresa_id, "PPD-AJENO", metodo_pago="PPD", rfc_receptor=OTRO_RFC,
          subtotal=Decimal("8000"), total=Decimal("8000"))
    cfdi_id = _cfdi_id(db, "PPD-AJENO")
    _pago(db, otra_empresa_id, cfdi_id, "PPD-AJENO", Decimal("8000"), "2026-01-10")

    _, _, pagos = _cargar_datos_deducciones(empresa_id, "2026-01")
    assert pagos == []


def test_sin_cfdis_devuelve_listas_vacias(empresa_ded):
    from backend.routers.reportes import _cargar_datos_deducciones

    db, empresa_id, _ = empresa_ded

    rfc, cfdis, pagos = _cargar_datos_deducciones(empresa_id, "2026-01")
    assert rfc == RFC
    assert cfdis == []
    assert pagos == []
