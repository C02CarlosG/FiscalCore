"""E2E de Complementos de Pago (REP) contra un Postgres real.

Cubre el ciclo factura PPD ↔ REP por las dos rutas de ingesta (subida manual y
Descarga Masiva del SAT) y las regresiones que inflaban o perdían lo cobrado:

- re-subir el mismo REP duplicaba el pago (pagos_relaciones sin UNIQUE);
- un REP que llegaba antes que su factura nunca se aplicaba;
- la descarga del SAT no procesaba complementos de pago;
- el UUID del timbre y el IdDocumento del REP con distinta caja no cruzaban.

Se salta automáticamente si no hay DB disponible.
"""
from decimal import Decimal

import pytest

from backend.tests.conftest import db_disponible, headers_usuario_e2e

RFC = "REP010101E2E"
CLIENTE = "XAXX010101000"
EMAIL = "e2e-pagos-rep@test.local"
PERIODO = "2026-01"

# A propósito con caja distinta: timbre en minúsculas, IdDocumento en mayúsculas.
UUID_FACTURA_XML = "0a1b2c3d-1111-2222-3333-44445555e2e0"
UUID_FACTURA = UUID_FACTURA_XML.upper()
UUID_REP = "0A1B2C3D-9999-8888-7777-66665555E2E0"

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


def _xml_factura_ppd() -> bytes:
    """Factura PPD emitida por la empresa: $10,000 + IVA $1,600 = $11,600."""
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
    Version="4.0" Fecha="2026-01-10T10:00:00" TipoDeComprobante="I" SubTotal="10000.00" Total="11600.00"
    Moneda="MXN" MetodoPago="PPD" FormaPago="99" Exportacion="01" LugarExpedicion="01000">
  <cfdi:Emisor Rfc="{RFC}" Nombre="Emisora E2E" RegimenFiscal="601"/>
  <cfdi:Receptor Rfc="{CLIENTE}" Nombre="Cliente" UsoCFDI="G03" DomicilioFiscalReceptor="01000" RegimenFiscalReceptor="616"/>
  <cfdi:Impuestos TotalImpuestosTrasladados="1600.00"><cfdi:Traslados>
    <cfdi:Traslado Base="10000.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="1600.00"/>
  </cfdi:Traslados></cfdi:Impuestos>
  <cfdi:Complemento><tfd:TimbreFiscalDigital UUID="{UUID_FACTURA_XML}" FechaTimbrado="2026-01-10T10:01:00"/></cfdi:Complemento>
</cfdi:Comprobante>'''.encode()


def _xml_rep() -> bytes:
    """REP (Pagos 2.0) que cobra la mitad de la factura: $5,800."""
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" xmlns:pago20="http://www.sat.gob.mx/Pagos20"
    xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
    Version="4.0" Fecha="2026-01-20T10:00:00" TipoDeComprobante="P" SubTotal="0" Total="0" Moneda="XXX"
    Exportacion="01" LugarExpedicion="01000">
  <cfdi:Emisor Rfc="{RFC}" Nombre="Emisora E2E" RegimenFiscal="601"/>
  <cfdi:Receptor Rfc="{CLIENTE}" Nombre="Cliente" UsoCFDI="CP01" DomicilioFiscalReceptor="01000" RegimenFiscalReceptor="616"/>
  <cfdi:Complemento>
    <pago20:Pagos Version="2.0">
      <pago20:Totales MontoTotalPagos="5800.00"/>
      <pago20:Pago FechaPago="2026-01-20T12:00:00" FormaDePagoP="03" MonedaP="MXN" TipoCambioP="1" Monto="5800.00">
        <pago20:DoctoRelacionado IdDocumento="{UUID_FACTURA}" MonedaDR="MXN" NumParcialidad="1"
            ImpSaldoAnt="11600.00" ImpPagado="5800.00" ImpSaldoInsoluto="5800.00"/>
      </pago20:Pago>
    </pago20:Pagos>
    <tfd:TimbreFiscalDigital UUID="{UUID_REP}" FechaTimbrado="2026-01-20T10:01:00"/>
  </cfdi:Complemento>
</cfdi:Comprobante>'''.encode()


def _limpiar(db):
    # pagos_cfdi/pagos_relaciones/conciliaciones/detecciones caen por CASCADE.
    db.execute("DELETE FROM empresas WHERE rfc = %s", (RFC,))
    db.execute("DELETE FROM cfdi WHERE uuid IN (%s, %s, %s)", (UUID_FACTURA, UUID_FACTURA_XML, UUID_REP))
    db.execute("DELETE FROM usuarios WHERE email = %s", (EMAIL,))


@pytest.fixture
def entorno():
    """Empresa + contador registrados por la API; limpia antes y después."""
    from fastapi.testclient import TestClient

    import backend.main_api as main
    from backend import db

    db.init_db()
    _limpiar(db)
    client = TestClient(main.app)
    try:
        headers = headers_usuario_e2e(db, EMAIL)
        r = client.post("/api/v1/mis-empresas", headers=headers,
                        json={"rfc": RFC, "razon_social": "Emisora E2E"})
        assert r.status_code == 201, r.text
        yield db, client, headers, r.json()["empresa_id"]
    finally:
        _limpiar(db)


def _subir(client, headers, empresa_id, nombre, xml):
    r = client.post(
        f"/api/v1/empresas/{empresa_id}/cfdi/upload", headers=headers,
        data={"periodo": PERIODO}, files=[("archivos", (nombre, xml, "text/xml"))],
    )
    assert r.status_code == 200, r.text
    assert r.json()["registros_procesados"] == 1, r.json()
    return r.json()


def _estado_factura(db):
    row = db.query_one("SELECT monto_cobrado, estado_pago FROM cfdi WHERE uuid = %s", (UUID_FACTURA,))
    assert row is not None, "la factura debe guardarse con el UUID en mayúsculas"
    return Decimal(str(row["monto_cobrado"])), row["estado_pago"]


def _num_relaciones(db):
    return db.query_one(
        "SELECT COUNT(*) AS n FROM pagos_relaciones WHERE cfdi_uuid = %s", (UUID_FACTURA,))["n"]


def _iva_ppd_cedula(client, headers, empresa_id):
    r = client.get(f"/api/v1/empresas/{empresa_id}/cedula-iva/{PERIODO}", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["trasladado"]["ppd"]


def test_rep_subido_registra_el_pago_y_resubirlo_no_lo_duplica(entorno):
    db, client, headers, empresa_id = entorno

    _subir(client, headers, empresa_id, "factura.xml", _xml_factura_ppd())
    assert _estado_factura(db) == (Decimal("0.00"), "pendiente")

    _subir(client, headers, empresa_id, "rep.xml", _xml_rep())
    assert _estado_factura(db) == (Decimal("5800.00"), "pagado_parcial")
    assert _num_relaciones(db) == 1
    assert _iva_ppd_cedula(client, headers, empresa_id) == {"cobrado": 5800.0, "iva": 800.0}

    # Re-subir el mismo REP (dos veces) no debe cambiar nada.
    _subir(client, headers, empresa_id, "rep.xml", _xml_rep())
    _subir(client, headers, empresa_id, "rep.xml", _xml_rep())
    assert _estado_factura(db) == (Decimal("5800.00"), "pagado_parcial")
    assert _num_relaciones(db) == 1
    assert _iva_ppd_cedula(client, headers, empresa_id) == {"cobrado": 5800.0, "iva": 800.0}


def test_rep_que_llega_antes_que_su_factura_se_aplica_al_llegar_la_factura(entorno):
    db, client, headers, empresa_id = entorno

    _subir(client, headers, empresa_id, "rep.xml", _xml_rep())
    assert _num_relaciones(db) == 1

    _subir(client, headers, empresa_id, "factura.xml", _xml_factura_ppd())
    assert _estado_factura(db) == (Decimal("5800.00"), "pagado_parcial")
    assert _iva_ppd_cedula(client, headers, empresa_id) == {"cobrado": 5800.0, "iva": 800.0}


def test_descarga_sat_tambien_procesa_complementos_de_pago(entorno):
    db, _client, _headers, empresa_id = entorno
    from backend.cfdi_parser import CFDIParser
    from backend import sat_sync

    parser = CFDIParser()
    for xml in (_xml_factura_ppd(), _xml_rep(), _xml_rep()):  # el paquete puede repetirse
        sat_sync._insertar_cfdi(empresa_id, parser.parse_xml(xml), PERIODO, xml)

    assert _estado_factura(db) == (Decimal("5800.00"), "pagado_parcial")
    assert _num_relaciones(db) == 1


def test_migracion_027_corrige_pagos_duplicados_y_uuids_en_minusculas(entorno):
    """Estado heredado de la versión anterior: UUID de la factura en minúsculas,
    relación de pago duplicada por re-ingesta y monto_cobrado inflado."""
    db, client, headers, empresa_id = entorno
    _subir(client, headers, empresa_id, "factura.xml", _xml_factura_ppd())
    _subir(client, headers, empresa_id, "rep.xml", _xml_rep())

    db.execute("DROP INDEX uq_pagos_rel_pago_cfdi_parcialidad")
    db.execute(
        """INSERT INTO pagos_relaciones (pago_id, cfdi_uuid, parcialidad, importe_pagado, saldo_anterior, saldo_restante)
           SELECT pago_id, LOWER(cfdi_uuid), parcialidad, importe_pagado, saldo_anterior, saldo_restante
           FROM pagos_relaciones WHERE cfdi_uuid = %s""",
        (UUID_FACTURA,),
    )
    db.execute(
        "UPDATE cfdi SET uuid = LOWER(uuid), monto_cobrado = 11600, estado_pago = 'pagado_total' WHERE uuid = %s",
        (UUID_FACTURA,),
    )

    db.init_db()  # el arranque aplica la 027

    assert _num_relaciones(db) == 1
    assert _estado_factura(db) == (Decimal("5800.00"), "pagado_parcial")
    assert _iva_ppd_cedula(client, headers, empresa_id) == {"cobrado": 5800.0, "iva": 800.0}


def test_migracion_027_solo_corrige_datos_en_el_primer_arranque(entorno):
    """Con el índice único ya creado, el arranque no vuelve a recorrer las tablas:
    la app normaliza los UUID al parsear, así que la corrección no se repite."""
    db, client, headers, empresa_id = entorno
    _subir(client, headers, empresa_id, "factura.xml", _xml_factura_ppd())
    db.init_db()  # ya aplicó la 027 (el índice existe)
    db.execute("UPDATE cfdi SET uuid = LOWER(uuid) WHERE uuid = %s", (UUID_FACTURA,))

    db.init_db()  # segundo arranque: la corrección no se ejecuta otra vez

    fila = db.query_one("SELECT uuid FROM cfdi WHERE empresa_id = %s", (empresa_id,))
    assert fila["uuid"] == UUID_FACTURA.lower()
