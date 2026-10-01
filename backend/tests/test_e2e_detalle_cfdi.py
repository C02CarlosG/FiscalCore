"""E2E del detalle fiscal del CFDI contra un Postgres real: lo que se sube por
la API queda con impuestos por tasa, conceptos, encabezados e impuestos de cada
pago, y re-subir no duplica. Se salta si no hay DB."""
from decimal import Decimal

import pytest

from backend.tests.conftest import db_disponible, headers_usuario_e2e

D = Decimal
RFC = "DET010101E2E"
CLIENTE = "XAXX010101000"
EMAIL = "e2e-detalle-cfdi@test.local"
PERIODO = "2026-01"
UUID_FACTURA = "0D0D0D0D-1111-2222-3333-44445555DE70"
UUID_REP = "0D0D0D0D-9999-8888-7777-66665555DE70"

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


def _xml_factura() -> bytes:
    """Factura PPD con tres tasas: 10,000 al 16 %, 500 al 0 % y 200 exento. Total 12,300."""
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
    Version="4.0" Fecha="2026-01-10T10:00:00" TipoDeComprobante="I" SubTotal="10700.00" Total="12300.00"
    Moneda="MXN" MetodoPago="PPD" FormaPago="99" Exportacion="01" LugarExpedicion="01000"
    NoCertificado="00001000000504465028" CondicionesDePago="30 días">
  <cfdi:Emisor Rfc="{RFC}" Nombre="Emisora E2E" RegimenFiscal="601"/>
  <cfdi:Receptor Rfc="{CLIENTE}" Nombre="Cliente" UsoCFDI="G03" DomicilioFiscalReceptor="01000" RegimenFiscalReceptor="616"/>
  <cfdi:Conceptos>
    <cfdi:Concepto ClaveProdServ="43211500" Cantidad="1" ClaveUnidad="H87" Descripcion="Equipo"
        ValorUnitario="10000.00" Importe="10000.00" ObjetoImp="02">
      <cfdi:Impuestos><cfdi:Traslados>
        <cfdi:Traslado Base="10000.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="1600.00"/>
      </cfdi:Traslados></cfdi:Impuestos>
    </cfdi:Concepto>
    <cfdi:Concepto ClaveProdServ="50161500" Cantidad="1" ClaveUnidad="KGM" Descripcion="Alimento"
        ValorUnitario="500.00" Importe="500.00" ObjetoImp="02">
      <cfdi:Impuestos><cfdi:Traslados>
        <cfdi:Traslado Base="500.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.000000" Importe="0.00"/>
      </cfdi:Traslados></cfdi:Impuestos>
    </cfdi:Concepto>
    <cfdi:Concepto ClaveProdServ="85121600" Cantidad="1" ClaveUnidad="E48" Descripcion="Consulta"
        ValorUnitario="200.00" Importe="200.00" ObjetoImp="02">
      <cfdi:Impuestos><cfdi:Traslados>
        <cfdi:Traslado Base="200.00" Impuesto="002" TipoFactor="Exento"/>
      </cfdi:Traslados></cfdi:Impuestos>
    </cfdi:Concepto>
  </cfdi:Conceptos>
  <cfdi:Impuestos TotalImpuestosTrasladados="1600.00"><cfdi:Traslados>
    <cfdi:Traslado Base="10000.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="1600.00"/>
    <cfdi:Traslado Base="500.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.000000" Importe="0.00"/>
    <cfdi:Traslado Base="200.00" Impuesto="002" TipoFactor="Exento"/>
  </cfdi:Traslados></cfdi:Impuestos>
  <cfdi:Complemento><tfd:TimbreFiscalDigital UUID="{UUID_FACTURA}" FechaTimbrado="2026-01-10T10:01:00"/></cfdi:Complemento>
</cfdi:Comprobante>'''.encode()


def _xml_rep() -> bytes:
    """REP 2.0 que cobra la mitad (6,150) con sus ImpuestosDR."""
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" xmlns:pago20="http://www.sat.gob.mx/Pagos20"
    xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
    Version="4.0" Fecha="2026-01-20T10:00:00" TipoDeComprobante="P" SubTotal="0" Total="0" Moneda="XXX"
    Exportacion="01" LugarExpedicion="01000">
  <cfdi:Emisor Rfc="{RFC}" Nombre="Emisora E2E" RegimenFiscal="601"/>
  <cfdi:Receptor Rfc="{CLIENTE}" Nombre="Cliente" UsoCFDI="CP01" DomicilioFiscalReceptor="01000" RegimenFiscalReceptor="616"/>
  <cfdi:Complemento>
    <pago20:Pagos Version="2.0">
      <pago20:Totales MontoTotalPagos="6150.00"/>
      <pago20:Pago FechaPago="2026-01-20T12:00:00" FormaDePagoP="03" MonedaP="MXN" TipoCambioP="1" Monto="6150.00">
        <pago20:DoctoRelacionado IdDocumento="{UUID_FACTURA}" MonedaDR="MXN" EquivalenciaDR="1" NumParcialidad="1"
            ImpSaldoAnt="12300.00" ImpPagado="6150.00" ImpSaldoInsoluto="6150.00" ObjetoImpDR="02">
          <pago20:ImpuestosDR><pago20:TrasladosDR>
            <pago20:TrasladoDR BaseDR="5000.00" ImpuestoDR="002" TipoFactorDR="Tasa" TasaOCuotaDR="0.160000" ImporteDR="800.00"/>
            <pago20:TrasladoDR BaseDR="250.00" ImpuestoDR="002" TipoFactorDR="Tasa" TasaOCuotaDR="0.000000" ImporteDR="0.00"/>
            <pago20:TrasladoDR BaseDR="100.00" ImpuestoDR="002" TipoFactorDR="Exento"/>
          </pago20:TrasladosDR></pago20:ImpuestosDR>
        </pago20:DoctoRelacionado>
      </pago20:Pago>
    </pago20:Pagos>
    <tfd:TimbreFiscalDigital UUID="{UUID_REP}" FechaTimbrado="2026-01-20T10:01:00"/>
  </cfdi:Complemento>
</cfdi:Comprobante>'''.encode()


def _limpiar(db):
    # cfdi_impuestos, cfdi_conceptos, pagos_* caen por CASCADE.
    db.execute("DELETE FROM empresas WHERE rfc = %s", (RFC,))
    db.execute("DELETE FROM cfdi WHERE uuid IN (%s, %s)", (UUID_FACTURA, UUID_REP))
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


def _impuestos_cfdi(db):
    filas = db.query_all(
        """SELECT i.ambito, i.impuesto, i.tipo_factor, i.tasa_o_cuota, i.base, i.importe
           FROM cfdi_impuestos i JOIN cfdi c ON c.id = i.cfdi_id WHERE c.uuid = %s""",
        (UUID_FACTURA,),
    )
    return {(f["ambito"], f["impuesto"], f["tipo_factor"], f["tasa_o_cuota"], f["base"], f["importe"]) for f in filas}


IMPUESTOS_FACTURA = {
    ("traslado", "002", "Tasa", D("0.160000"), D("10000.00"), D("1600.00")),
    ("traslado", "002", "Tasa", D("0.000000"), D("500.00"), D("0.00")),
    ("traslado", "002", "Exento", None, D("200.00"), D("0.00")),
}
IMPUESTOS_PAGO = {
    ("Tasa", D("0.160000"), D("5000.00"), D("800.00")),
    ("Tasa", D("0.000000"), D("250.00"), D("0.00")),
    ("Exento", None, D("100.00"), D("0.00")),
}


def test_subir_factura_guarda_impuestos_conceptos_y_encabezados(entorno):
    db, client, headers, empresa_id = entorno

    _subir(client, headers, empresa_id, "factura.xml", _xml_factura())

    cfdi = db.query_one(
        "SELECT regimen_emisor, condiciones_pago, no_certificado, detalle_version FROM cfdi WHERE uuid = %s",
        (UUID_FACTURA,),
    )
    assert cfdi == {"regimen_emisor": "601", "condiciones_pago": "30 días",
                    "no_certificado": "00001000000504465028", "detalle_version": 1}
    assert _impuestos_cfdi(db) == IMPUESTOS_FACTURA
    conceptos = db.query_all(
        """SELECT k.linea, k.descripcion, k.importe, k.impuestos
           FROM cfdi_conceptos k JOIN cfdi c ON c.id = k.cfdi_id WHERE c.uuid = %s ORDER BY k.linea""",
        (UUID_FACTURA,),
    )
    assert [(k["linea"], k["descripcion"], k["importe"]) for k in conceptos] == [
        (1, "Equipo", D("10000.00")), (2, "Alimento", D("500.00")), (3, "Consulta", D("200.00"))]
    assert conceptos[0]["impuestos"] == [{
        "ambito": "traslado", "impuesto": "002", "tipo_factor": "Tasa",
        "tasa_o_cuota": "0.160000", "base": "10000.00", "importe": "1600.00"}]


def test_resubir_la_factura_no_duplica_el_detalle(entorno):
    db, client, headers, empresa_id = entorno

    for _ in range(3):
        _subir(client, headers, empresa_id, "factura.xml", _xml_factura())

    assert _impuestos_cfdi(db) == IMPUESTOS_FACTURA
    n = db.query_one(
        "SELECT COUNT(*) AS n FROM cfdi_conceptos k JOIN cfdi c ON c.id = k.cfdi_id WHERE c.uuid = %s",
        (UUID_FACTURA,))["n"]
    assert n == 3


def test_subir_rep_guarda_impuestos_del_documento_y_resubirlo_no_duplica(entorno):
    db, client, headers, empresa_id = entorno
    _subir(client, headers, empresa_id, "factura.xml", _xml_factura())

    for _ in range(2):
        _subir(client, headers, empresa_id, "rep.xml", _xml_rep())

    filas = db.query_all(
        """SELECT i.tipo_factor, i.tasa_o_cuota, i.base, i.importe
           FROM pagos_relaciones_impuestos i
           JOIN pagos_relaciones pr ON pr.id = i.relacion_id WHERE pr.cfdi_uuid = %s""",
        (UUID_FACTURA,),
    )
    assert len(filas) == 3
    assert {(f["tipo_factor"], f["tasa_o_cuota"], f["base"], f["importe"]) for f in filas} == IMPUESTOS_PAGO
    rel = db.query_one(
        """SELECT pr.moneda_dr, pr.equivalencia_dr, pc.version_pago
           FROM pagos_relaciones pr JOIN pagos_cfdi pc ON pc.id = pr.pago_id WHERE pr.cfdi_uuid = %s""",
        (UUID_FACTURA,),
    )
    assert (rel["moneda_dr"], rel["equivalencia_dr"], rel["version_pago"]) == ("MXN", D("1"), "2.0")


def test_reproceso_reconstruye_el_detalle_de_cfdis_anteriores(entorno):
    db, client, headers, empresa_id = entorno
    from backend import reproceso

    _subir(client, headers, empresa_id, "factura.xml", _xml_factura())
    _subir(client, headers, empresa_id, "rep.xml", _xml_rep())
    # Simular CFDI guardados antes de la migración 028: sin detalle.
    db.execute("DELETE FROM cfdi_impuestos WHERE cfdi_id IN (SELECT id FROM cfdi WHERE empresa_id = %s)", (empresa_id,))
    db.execute("DELETE FROM cfdi_conceptos WHERE cfdi_id IN (SELECT id FROM cfdi WHERE empresa_id = %s)", (empresa_id,))
    db.execute(
        """DELETE FROM pagos_relaciones_impuestos WHERE relacion_id IN (
               SELECT pr.id FROM pagos_relaciones pr JOIN pagos_cfdi pc ON pc.id = pr.pago_id
               WHERE pc.empresa_id = %s)""",
        (empresa_id,),
    )
    db.execute("UPDATE cfdi SET detalle_version = 0, regimen_emisor = NULL WHERE empresa_id = %s", (empresa_id,))

    resultado = reproceso.reprocesar_detalle(empresa_id=empresa_id)

    assert resultado == {"procesados": 2, "errores": [], "pendientes": 0}
    assert _impuestos_cfdi(db) == IMPUESTOS_FACTURA
    assert db.query_one("SELECT regimen_emisor FROM cfdi WHERE uuid = %s", (UUID_FACTURA,))["regimen_emisor"] == "601"
    n = db.query_one(
        """SELECT COUNT(*) AS n FROM pagos_relaciones_impuestos i
           JOIN pagos_relaciones pr ON pr.id = i.relacion_id WHERE pr.cfdi_uuid = %s""",
        (UUID_FACTURA,))["n"]
    assert n == 3


def test_reproceso_marca_el_xml_ilegible_y_no_lo_reintenta(entorno):
    db, client, headers, empresa_id = entorno
    from backend import reproceso

    _subir(client, headers, empresa_id, "factura.xml", _xml_factura())
    db.execute("UPDATE cfdi SET detalle_version = 0, xml_raw = '<roto' WHERE uuid = %s", (UUID_FACTURA,))

    primero = reproceso.reprocesar_detalle(empresa_id=empresa_id)
    segundo = reproceso.reprocesar_detalle(empresa_id=empresa_id)

    assert primero["procesados"] == 0
    assert [e["uuid"] for e in primero["errores"]] == [UUID_FACTURA]
    assert primero["pendientes"] == 0
    assert segundo == {"procesados": 0, "errores": [], "pendientes": 0}
    assert db.query_one("SELECT detalle_version FROM cfdi WHERE uuid = %s", (UUID_FACTURA,))["detalle_version"] == -1
