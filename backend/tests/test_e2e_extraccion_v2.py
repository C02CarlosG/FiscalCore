"""E2E de la extracción v2 contra un Postgres real: lo que se sube por la API (REP con
Totales e ImpuestosP, nómina por percepción, ACuentaTerceros) queda guardado, el
reproceso rellena lo que se guardó con la versión 1, y repetir no duplica."""
from datetime import date
from decimal import Decimal

import pytest

from backend import cfdi_store
from backend.tests.conftest import db_disponible, headers_usuario_e2e

D = Decimal
RFC = "EXT010101E2E"
CLIENTE = "XAXX010101000"
TRABAJADOR = "TRAB010101ABC"
EMAIL = "e2e-extraccion-v2@test.local"
PERIODO = "2026-12"
UUID_FACTURA = "0E0E0E0E-1111-2222-3333-44445555EE20"
UUID_REP = "0E0E0E0E-9999-8888-7777-66665555EE20"
UUID_NOMINA = "0E0E0E0E-5555-6666-7777-88889999EE20"
UUID_REP_DOBLE = "0E0E0E0E-AAAA-BBBB-CCCC-DDDDEEEEEE20"

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


def _xml_factura_terceros() -> bytes:
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
    Version="4.0" Fecha="2026-12-10T10:00:00" TipoDeComprobante="I" SubTotal="1500.00" Total="1660.00"
    Moneda="MXN" MetodoPago="PPD" FormaPago="99" Exportacion="01" LugarExpedicion="01000">
  <cfdi:Emisor Rfc="{RFC}" Nombre="Emisora E2E" RegimenFiscal="601"/>
  <cfdi:Receptor Rfc="{CLIENTE}" Nombre="Cliente" UsoCFDI="G03" DomicilioFiscalReceptor="01000" RegimenFiscalReceptor="616"/>
  <cfdi:Conceptos>
    <cfdi:Concepto ClaveProdServ="80101500" Cantidad="1" ClaveUnidad="E48" Descripcion="Cobro por cuenta de terceros"
        ValorUnitario="1000.00" Importe="1000.00" ObjetoImp="02">
      <cfdi:Impuestos><cfdi:Traslados>
        <cfdi:Traslado Base="1000.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="160.00"/>
      </cfdi:Traslados></cfdi:Impuestos>
      <cfdi:ACuentaTerceros RfcACuentaTerceros="TTE010101ABC" NombreACuentaTerceros="TERCERO SA"
          RegimenFiscalACuentaTerceros="601" DomicilioFiscalACuentaTerceros="68000"/>
    </cfdi:Concepto>
    <cfdi:Concepto ClaveProdServ="80101500" Cantidad="1" ClaveUnidad="E48" Descripcion="Propio"
        ValorUnitario="500.00" Importe="500.00" ObjetoImp="01"/>
  </cfdi:Conceptos>
  <cfdi:Impuestos TotalImpuestosTrasladados="160.00"><cfdi:Traslados>
    <cfdi:Traslado Base="1000.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="160.00"/>
  </cfdi:Traslados></cfdi:Impuestos>
  <cfdi:Complemento><tfd:TimbreFiscalDigital UUID="{UUID_FACTURA}" FechaTimbrado="2026-12-10T10:01:00"/></cfdi:Complemento>
</cfdi:Comprobante>'''.encode()


def _xml_rep() -> bytes:
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" xmlns:pago20="http://www.sat.gob.mx/Pagos20"
    xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
    Version="4.0" Fecha="2026-12-20T10:00:00" TipoDeComprobante="P" SubTotal="0" Total="0" Moneda="XXX"
    Exportacion="01" LugarExpedicion="01000">
  <cfdi:Emisor Rfc="{RFC}" Nombre="Emisora E2E" RegimenFiscal="601"/>
  <cfdi:Receptor Rfc="{CLIENTE}" Nombre="Cliente" UsoCFDI="CP01" DomicilioFiscalReceptor="01000" RegimenFiscalReceptor="616"/>
  <cfdi:Complemento>
    <pago20:Pagos Version="2.0">
      <pago20:Totales TotalTrasladosBaseIVA16="1000.00" TotalTrasladosImpuestoIVA16="160.00" MontoTotalPagos="1160.00"/>
      <pago20:Pago FechaPago="2026-12-20T12:00:00" FormaDePagoP="03" MonedaP="MXN" TipoCambioP="1" Monto="1160.00">
        <pago20:DoctoRelacionado IdDocumento="{UUID_FACTURA}" MonedaDR="MXN" EquivalenciaDR="1" NumParcialidad="1"
            ImpSaldoAnt="1660.00" ImpPagado="1160.00" ImpSaldoInsoluto="500.00" ObjetoImpDR="02">
          <pago20:ImpuestosDR><pago20:TrasladosDR>
            <pago20:TrasladoDR BaseDR="1000.00" ImpuestoDR="002" TipoFactorDR="Tasa" TasaOCuotaDR="0.160000" ImporteDR="160.00"/>
          </pago20:TrasladosDR></pago20:ImpuestosDR>
        </pago20:DoctoRelacionado>
        <pago20:ImpuestosP><pago20:TrasladosP>
          <pago20:TrasladoP BaseP="1000.00" ImpuestoP="002" TipoFactorP="Tasa" TasaOCuotaP="0.160000" ImporteP="160.00"/>
        </pago20:TrasladosP></pago20:ImpuestosP>
      </pago20:Pago>
    </pago20:Pagos>
    <tfd:TimbreFiscalDigital UUID="{UUID_REP}" FechaTimbrado="2026-12-20T10:01:00"/>
  </cfdi:Complemento>
</cfdi:Comprobante>'''.encode()


def _xml_nomina() -> bytes:
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" xmlns:nomina12="http://www.sat.gob.mx/nomina12"
    xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
    Version="4.0" Fecha="2026-12-21T10:00:00" TipoDeComprobante="N" SubTotal="21200.00" Descuento="2500.00" Total="18700.00"
    Moneda="MXN" MetodoPago="PUE" FormaPago="99" Exportacion="01" LugarExpedicion="01000">
  <cfdi:Emisor Rfc="{RFC}" Nombre="Emisora E2E" RegimenFiscal="601"/>
  <cfdi:Receptor Rfc="{TRABAJADOR}" Nombre="Trabajador" UsoCFDI="CN01" DomicilioFiscalReceptor="01000" RegimenFiscalReceptor="605"/>
  <cfdi:Conceptos>
    <cfdi:Concepto ClaveProdServ="84111505" Cantidad="1" ClaveUnidad="ACT" Descripcion="Pago de nómina"
        ValorUnitario="21200.00" Importe="21200.00" Descuento="2500.00" ObjetoImp="01"/>
  </cfdi:Conceptos>
  <cfdi:Complemento>
    <nomina12:Nomina Version="1.2" TipoNomina="E" FechaPago="2026-12-20" FechaInicialPago="2026-12-01"
        FechaFinalPago="2026-12-31" NumDiasPagados="31" TotalPercepciones="21000.00" TotalDeducciones="2500.00"
        TotalOtrosPagos="200.00">
      <nomina12:Receptor Curp="AAAA010101HDFXXX01" TipoContrato="01" TipoRegimen="02" NumEmpleado="E-0042" PeriodicidadPago="04"/>
      <nomina12:Percepciones TotalSueldos="10000.00" TotalSeparacionIndemnizacion="5000.00"
          TotalJubilacionPensionRetiro="6000.00" TotalGravado="14000.00" TotalExento="7000.00">
        <nomina12:Percepcion TipoPercepcion="001" Clave="P01" Concepto="Sueldo" ImporteGravado="10000.00" ImporteExento="0.00"/>
        <nomina12:Percepcion TipoPercepcion="003" Clave="P03" Concepto="PTU" ImporteGravado="4000.00" ImporteExento="7000.00"/>
        <nomina12:JubilacionPensionRetiro TotalUnaExhibicion="6000.00" IngresoAcumulable="1000.00" IngresoNoAcumulable="5000.00"/>
        <nomina12:SeparacionIndemnizacion TotalPagado="5000.00" NumAñosServicio="7" UltimoSueldoMensOrd="9000.00"
            IngresoAcumulable="3000.00" IngresoNoAcumulable="2000.00"/>
      </nomina12:Percepciones>
      <nomina12:Deducciones TotalOtrasDeducciones="300.00" TotalImpuestosRetenidos="2200.00">
        <nomina12:Deduccion TipoDeduccion="001" Clave="D01" Concepto="IMSS" Importe="300.00"/>
        <nomina12:Deduccion TipoDeduccion="002" Clave="D02" Concepto="ISR" Importe="2200.00"/>
      </nomina12:Deducciones>
      <nomina12:OtrosPagos>
        <nomina12:OtroPago TipoOtroPago="002" Clave="O01" Concepto="Subsidio para el empleo" Importe="200.00">
          <nomina12:SubsidioAlEmpleo SubsidioCausado="200.00"/>
        </nomina12:OtroPago>
        <nomina12:OtroPago TipoOtroPago="004" Clave="O02" Concepto="Compensación" Importe="0.00">
          <nomina12:CompensacionSaldosAFavor SaldoAFavor="400.00" Año="2025" RemanenteSalFav="250.00"/>
        </nomina12:OtroPago>
      </nomina12:OtrosPagos>
    </nomina12:Nomina>
    <tfd:TimbreFiscalDigital UUID="{UUID_NOMINA}" FechaTimbrado="2026-12-21T10:01:00"/>
  </cfdi:Complemento>
</cfdi:Comprobante>'''.encode()


def _limpiar(db):
    db.execute("DELETE FROM empresas WHERE rfc = %s", (RFC,))
    db.execute("DELETE FROM cfdi WHERE uuid IN (%s, %s, %s, %s)", (UUID_FACTURA, UUID_REP, UUID_NOMINA, UUID_REP_DOBLE))
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
        r = client.post("/api/v1/mis-empresas", headers=headers, json={"rfc": RFC, "razon_social": "Emisora E2E"})
        assert r.status_code == 201, r.text
        empresa_id = r.json()["empresa_id"]
        for nombre, xml in (("factura.xml", _xml_factura_terceros()), ("rep.xml", _xml_rep()), ("nomina.xml", _xml_nomina())):
            r = client.post(f"/api/v1/empresas/{empresa_id}/cfdi/upload", headers=headers, data={"periodo": PERIODO},
                            files=[("archivos", (nombre, xml, "text/xml"))])
            assert r.status_code == 200 and r.json()["registros_procesados"] == 1, r.text
        yield db, client, headers, empresa_id
    finally:
        _limpiar(db)


def _uno(db, sql, *params):
    return db.query_one(sql, params)


def _conteos(db):
    """Filas v2 de los tres CFDI de la prueba."""
    return {
        "terceros": _uno(db, "SELECT COUNT(*) AS n FROM cfdi_conceptos k JOIN cfdi c ON c.id = k.cfdi_id "
                             "WHERE c.uuid = %s AND k.rfc_a_cuenta_terceros IS NOT NULL", UUID_FACTURA)["n"],
        "totales": _uno(db, "SELECT COUNT(*) AS n FROM cfdi_pagos_totales t JOIN cfdi c ON c.id = t.cfdi_id WHERE c.uuid = %s", UUID_REP)["n"],
        "impuestos_p": _uno(db, "SELECT COUNT(*) AS n FROM pagos_impuestos i JOIN pagos_cfdi p ON p.id = i.pago_id "
                                "JOIN cfdi c ON c.id = p.cfdi_id WHERE c.uuid = %s", UUID_REP)["n"],
        "nominas": _uno(db, "SELECT COUNT(*) AS n FROM cfdi_nominas n JOIN cfdi c ON c.id = n.cfdi_id WHERE c.uuid = %s", UUID_NOMINA)["n"],
        "nomina_conceptos": _uno(db, "SELECT COUNT(*) AS n FROM cfdi_nomina_conceptos k JOIN cfdi_nominas n ON n.id = k.nomina_id "
                                     "JOIN cfdi c ON c.id = n.cfdi_id WHERE c.uuid = %s", UUID_NOMINA)["n"],
    }


ESPERADO = {"terceros": 1, "totales": 1, "impuestos_p": 1, "nominas": 1, "nomina_conceptos": 6}


def test_subir_guarda_la_extraccion_v2(entorno):
    db, *_ = entorno

    assert _conteos(db) == ESPERADO
    assert {_uno(db, "SELECT detalle_version AS v FROM cfdi WHERE uuid = %s", u)["v"]
            for u in (UUID_FACTURA, UUID_REP, UUID_NOMINA)} == {cfdi_store.DETALLE_VERSION}

    ajeno = _uno(db, "SELECT k.rfc_a_cuenta_terceros AS rfc, k.nombre_a_cuenta_terceros AS nombre, k.regimen_a_cuenta_terceros AS reg "
                     "FROM cfdi_conceptos k JOIN cfdi c ON c.id = k.cfdi_id WHERE c.uuid = %s AND k.linea = 1", UUID_FACTURA)
    assert ajeno == {"rfc": "TTE010101ABC", "nombre": "TERCERO SA", "reg": "601"}
    propio = _uno(db, "SELECT k.rfc_a_cuenta_terceros AS rfc FROM cfdi_conceptos k JOIN cfdi c ON c.id = k.cfdi_id "
                      "WHERE c.uuid = %s AND k.linea = 2", UUID_FACTURA)
    assert propio["rfc"] is None


def test_rep_totales_impuestos_p_y_objeto_imp_dr(entorno):
    db, *_ = entorno

    t = _uno(db, "SELECT t.* FROM cfdi_pagos_totales t JOIN cfdi c ON c.id = t.cfdi_id WHERE c.uuid = %s", UUID_REP)
    assert (t["monto_total_pagos"], t["total_traslados_base_iva16"], t["total_traslados_iva16"]) == (D("1160.00"), D("1000.00"), D("160.00"))
    assert t["total_retenciones_isr"] is None and t["total_traslados_base_iva8"] is None   # no vienen: NULL, no 0

    p = _uno(db, "SELECT i.ambito, i.impuesto, i.tasa_o_cuota, i.base, i.importe FROM pagos_impuestos i "
                 "JOIN pagos_cfdi p ON p.id = i.pago_id JOIN cfdi c ON c.id = p.cfdi_id WHERE c.uuid = %s", UUID_REP)
    assert p == {"ambito": "traslado", "impuesto": "002", "tasa_o_cuota": D("0.160000"), "base": D("1000.000000"), "importe": D("160.000000")}

    rel = _uno(db, "SELECT objeto_imp_dr FROM pagos_relaciones WHERE cfdi_uuid = %s", UUID_FACTURA)
    assert rel["objeto_imp_dr"] == "02"


def test_nomina_encabezado_y_conceptos_por_tipo(entorno):
    db, *_ = entorno

    n = _uno(db, "SELECT n.* FROM cfdi_nominas n JOIN cfdi c ON c.id = n.cfdi_id WHERE c.uuid = %s", UUID_NOMINA)
    assert (n["nodo"], n["tipo_nomina"], n["tipo_regimen"], n["num_empleado"]) == (1, "E", "02", "E-0042")
    assert (n["fecha_pago"], n["fecha_inicial_pago"], n["fecha_final_pago"]) == (date(2026, 12, 20), date(2026, 12, 1), date(2026, 12, 31))
    assert (n["total_sueldos"], n["total_gravado"], n["total_exento"], n["total_impuestos_retenidos"]) == (
        D("10000.00"), D("14000.00"), D("7000.00"), D("2200.00"))
    assert (n["sep_total_pagado"], n["sep_anios_servicio"], n["jub_total_una_exhibicion"], n["jub_total_parcialidad"]) == (
        D("5000.00"), 7, D("6000.00"), None)

    filas = db.query_all(
        "SELECT k.categoria, k.linea, k.tipo, k.importe_gravado, k.importe_exento, k.importe, k.subsidio_causado "
        "FROM cfdi_nomina_conceptos k JOIN cfdi_nominas n ON n.id = k.nomina_id JOIN cfdi c ON c.id = n.cfdi_id "
        "WHERE c.uuid = %s ORDER BY k.categoria, k.linea", (UUID_NOMINA,))
    assert [(f["categoria"], f["tipo"], f["importe_gravado"], f["importe_exento"], f["importe"], f["subsidio_causado"]) for f in filas] == [
        ("deduccion", "001", None, None, D("300.00"), None),
        ("deduccion", "002", None, None, D("2200.00"), None),
        ("otro_pago", "002", None, None, D("200.00"), D("200.00")),
        ("otro_pago", "004", None, None, D("0.00"), None),
        ("percepcion", "001", D("10000.00"), D("0.00"), None, None),
        ("percepcion", "003", D("4000.00"), D("7000.00"), None, None),
    ]
    comp = _uno(db, "SELECT k.saldo_a_favor, k.anio_saldo_a_favor, k.remanente_saldo_a_favor FROM cfdi_nomina_conceptos k "
                    "JOIN cfdi_nominas n ON n.id = k.nomina_id JOIN cfdi c ON c.id = n.cfdi_id "
                    "WHERE c.uuid = %s AND k.tipo = '004'", UUID_NOMINA)
    assert comp == {"saldo_a_favor": D("400.00"), "anio_saldo_a_favor": 2025, "remanente_saldo_a_favor": D("250.00")}
    # Los totales de v1 en cfdi siguen ahí.
    cfdi = _uno(db, "SELECT nomina_gravado, nomina_exento, nomina_isr_retenido FROM cfdi WHERE uuid = %s", UUID_NOMINA)
    assert cfdi == {"nomina_gravado": D("14000.00"), "nomina_exento": D("7000.00"), "nomina_isr_retenido": D("2200.00")}


def _simular_cfdi_de_la_version_1(db):
    """Estado de un CFDI guardado antes de F3.5a: sin nada de v2 y con detalle_version 1."""
    db.execute("DELETE FROM cfdi_nominas WHERE cfdi_id IN (SELECT id FROM cfdi WHERE uuid = %s)", (UUID_NOMINA,))
    db.execute("DELETE FROM cfdi_pagos_totales WHERE cfdi_id IN (SELECT id FROM cfdi WHERE uuid = %s)", (UUID_REP,))
    db.execute("DELETE FROM pagos_impuestos WHERE pago_id IN (SELECT p.id FROM pagos_cfdi p JOIN cfdi c ON c.id = p.cfdi_id WHERE c.uuid = %s)", (UUID_REP,))
    db.execute("UPDATE pagos_relaciones SET objeto_imp_dr = NULL WHERE cfdi_uuid = %s", (UUID_FACTURA,))
    db.execute("UPDATE cfdi_conceptos SET rfc_a_cuenta_terceros = NULL, nombre_a_cuenta_terceros = NULL, "
               "regimen_a_cuenta_terceros = NULL WHERE cfdi_id IN (SELECT id FROM cfdi WHERE uuid = %s)", (UUID_FACTURA,))
    db.execute("UPDATE cfdi SET detalle_version = 1 WHERE uuid IN (%s, %s, %s)", (UUID_FACTURA, UUID_REP, UUID_NOMINA))
    assert sum(_conteos(db).values()) == 0


def test_el_reproceso_rellena_los_cfdi_guardados_con_la_version_1(entorno):
    db, _client, _headers, empresa_id = entorno
    from backend import reproceso

    _simular_cfdi_de_la_version_1(db)

    resultado = reproceso.reprocesar_detalle(empresa_id=empresa_id)

    assert resultado == {"procesados": 3, "errores": [], "pendientes": 0}
    assert _conteos(db) == ESPERADO
    assert _uno(db, "SELECT objeto_imp_dr FROM pagos_relaciones WHERE cfdi_uuid = %s", UUID_FACTURA)["objeto_imp_dr"] == "02"
    assert {_uno(db, "SELECT detalle_version AS v FROM cfdi WHERE uuid = %s", u)["v"]
            for u in (UUID_FACTURA, UUID_REP, UUID_NOMINA)} == {cfdi_store.DETALLE_VERSION}


def test_reprocesar_dos_veces_no_duplica(entorno):
    db, _client, _headers, empresa_id = entorno
    from backend import reproceso

    for _ in range(2):
        db.execute("UPDATE cfdi SET detalle_version = 1 WHERE empresa_id = %s", (empresa_id,))
        resultado = reproceso.reprocesar_detalle(empresa_id=empresa_id)
        assert resultado["errores"] == [] and resultado["pendientes"] == 0
        assert _conteos(db) == ESPERADO


def test_re_subir_el_mismo_xml_no_duplica(entorno):
    db, client, headers, empresa_id = entorno

    for nombre, xml in (("factura.xml", _xml_factura_terceros()), ("rep.xml", _xml_rep()), ("nomina.xml", _xml_nomina())):
        client.post(f"/api/v1/empresas/{empresa_id}/cfdi/upload", headers=headers, data={"periodo": PERIODO},
                    files=[("archivos", (nombre, xml, "text/xml"))])

    assert _conteos(db) == ESPERADO


def test_el_detalle_v2_se_va_con_la_empresa(entorno):
    """Borrar la empresa (y sus CFDI) no deja renglones huérfanos de nómina."""
    db, *_ = entorno

    db.execute("DELETE FROM conciliaciones WHERE empresa_id IN (SELECT id FROM empresas WHERE rfc = %s)", (RFC,))
    db.execute("DELETE FROM cfdi WHERE uuid IN (%s, %s, %s)", (UUID_FACTURA, UUID_REP, UUID_NOMINA))

    assert _conteos(db) == {k: 0 for k in ESPERADO}


def _xml_rep_con_dos_pagos_identicos() -> bytes:
    """REP con dos pago20:Pago de la misma fecha y monto, cada uno con sus ImpuestosP.
    Comparten fila en pagos_cfdi (UNIQUE cfdi_id, fecha_pago, monto)."""
    pago = """<pago20:Pago FechaPago="2026-12-22T12:00:00" FormaDePagoP="03" MonedaP="USD" TipoCambioP="17.5" Monto="1160.00">
        <pago20:ImpuestosP><pago20:TrasladosP>
          <pago20:TrasladoP BaseP="1000.00" ImpuestoP="002" TipoFactorP="Tasa" TasaOCuotaP="0.160000" ImporteP="160.00"/>
        </pago20:TrasladosP></pago20:ImpuestosP>
      </pago20:Pago>"""
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" xmlns:pago20="http://www.sat.gob.mx/Pagos20"
    xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
    Version="4.0" Fecha="2026-12-22T10:00:00" TipoDeComprobante="P" SubTotal="0" Total="0" Moneda="XXX"
    Exportacion="01" LugarExpedicion="01000">
  <cfdi:Emisor Rfc="{RFC}" Nombre="Emisora E2E" RegimenFiscal="601"/>
  <cfdi:Receptor Rfc="{CLIENTE}" Nombre="Cliente" UsoCFDI="CP01" DomicilioFiscalReceptor="01000" RegimenFiscalReceptor="616"/>
  <cfdi:Complemento>
    <pago20:Pagos Version="2.0">
      <pago20:Totales TotalTrasladosBaseIVA16="35000.123456" TotalTrasladosImpuestoIVA16="5600.019753" MontoTotalPagos="40600.50"/>
      {pago}{pago}
    </pago20:Pagos>
    <tfd:TimbreFiscalDigital UUID="{UUID_REP_DOBLE}" FechaTimbrado="2026-12-22T10:01:00"/>
  </cfdi:Complemento>
</cfdi:Comprobante>'''.encode()


def test_dos_pagos_identicos_tienen_cada_uno_su_fila_y_sus_impuestos(entorno):
    db, client, headers, empresa_id = entorno

    for _ in range(2):    # subirlo dos veces tampoco duplica
        client.post(f"/api/v1/empresas/{empresa_id}/cfdi/upload", headers=headers, data={"periodo": PERIODO},
                    files=[("archivos", ("rep2.xml", _xml_rep_con_dos_pagos_identicos(), "text/xml"))])
    from backend import reproceso
    db.execute("UPDATE cfdi SET detalle_version = 1 WHERE uuid = %s", (UUID_REP_DOBLE,))
    reproceso.reprocesar_detalle(empresa_id=empresa_id)             # y reprocesarlo, igual

    pagos = db.query_all("SELECT p.id, p.nodo, p.forma_pago FROM pagos_cfdi p JOIN cfdi c ON c.id = p.cfdi_id "
                         "WHERE c.uuid = %s ORDER BY p.nodo", (UUID_REP_DOBLE,))
    assert [(p["nodo"], p["forma_pago"]) for p in pagos] == [(1, "03"), (2, "03")]   # una fila por nodo
    for p in pagos:
        filas = db.query_all("SELECT ambito, impuesto, base, importe FROM pagos_impuestos WHERE pago_id = %s", (p["id"],))
        assert [(f["ambito"], f["impuesto"], f["base"], f["importe"]) for f in filas] == [
            ("traslado", "002", D("1000.000000"), D("160.000000"))]       # el IVA de cada pago, completo


def test_totales_del_rep_conservan_seis_decimales_en_la_base(entorno):
    db, client, headers, empresa_id = entorno
    client.post(f"/api/v1/empresas/{empresa_id}/cfdi/upload", headers=headers, data={"periodo": PERIODO},
                files=[("archivos", ("rep2.xml", _xml_rep_con_dos_pagos_identicos(), "text/xml"))])

    t = _uno(db, "SELECT t.* FROM cfdi_pagos_totales t JOIN cfdi c ON c.id = t.cfdi_id WHERE c.uuid = %s", UUID_REP_DOBLE)
    assert (t["total_traslados_base_iva16"], t["total_traslados_iva16"], t["monto_total_pagos"]) == (
        D("35000.123456"), D("5600.019753"), D("40600.500000"))


def test_un_rep_guardado_antes_de_la_041_reclama_su_fila_y_agrega_la_que_faltaba(entorno):
    """Antes de la 041 los dos pagos idénticos compartían una fila (nodo 0, sin asignar). El
    reproceso la reclama para el nodo 1 (conserva su id y sus relaciones) y crea la del nodo 2."""
    db, client, headers, empresa_id = entorno
    from backend import reproceso

    client.post(f"/api/v1/empresas/{empresa_id}/cfdi/upload", headers=headers, data={"periodo": PERIODO},
                files=[("archivos", ("rep2.xml", _xml_rep_con_dos_pagos_identicos(), "text/xml"))])
    cfdi_id = _uno(db, "SELECT id FROM cfdi WHERE uuid = %s", UUID_REP_DOBLE)["id"]
    db.execute("DELETE FROM pagos_cfdi WHERE cfdi_id = %s AND nodo = 2", (cfdi_id,))        # estado anterior: una sola fila
    db.execute("UPDATE pagos_cfdi SET nodo = 0, forma_pago = NULL WHERE cfdi_id = %s", (cfdi_id,))
    db.execute("DELETE FROM pagos_impuestos WHERE pago_id IN (SELECT id FROM pagos_cfdi WHERE cfdi_id = %s)", (cfdi_id,))
    db.execute("UPDATE cfdi SET detalle_version = 2 WHERE id = %s", (cfdi_id,))
    fila_vieja = _uno(db, "SELECT id FROM pagos_cfdi WHERE cfdi_id = %s", cfdi_id)["id"]

    resultado = reproceso.reprocesar_detalle(empresa_id=empresa_id)

    assert resultado["errores"] == [] and resultado["pendientes"] == 0
    pagos = db.query_all("SELECT id, nodo, forma_pago FROM pagos_cfdi WHERE cfdi_id = %s ORDER BY nodo", (cfdi_id,))
    assert [(p["nodo"], p["forma_pago"]) for p in pagos] == [(1, "03"), (2, "03")]
    assert pagos[0]["id"] == fila_vieja                                       # reclamó la fila anterior
    assert _uno(db, "SELECT COUNT(*) AS n FROM pagos_impuestos i JOIN pagos_cfdi p ON p.id = i.pago_id WHERE p.cfdi_id = %s", cfdi_id)["n"] == 2


# ─── Un REP cancelado ya no es un cobro (pedido del carril B) ─────────────────

def _cobrado_de_la_factura(db):
    return _uno(db, "SELECT monto_cobrado AS m, estado_pago AS e FROM cfdi WHERE uuid = %s", UUID_FACTURA)


def test_un_rep_cancelado_ya_no_cuenta_como_cobro(entorno):
    db, *_ = entorno
    from backend import cfdi_store

    assert _cobrado_de_la_factura(db) == {"m": D("1160.00"), "e": "pagado_parcial"}     # el REP vigente cobra 1,160

    db.execute("UPDATE cfdi SET estado = 'cancelado' WHERE uuid = %s", (UUID_REP,))
    recalculados = cfdi_store.recalcular_cobrado_de_rep(_empresa(db), UUID_REP)

    assert recalculados == 1
    assert _cobrado_de_la_factura(db) == {"m": D("0.00"), "e": "pendiente"}


def _empresa(db):
    return str(_uno(db, "SELECT id FROM empresas WHERE rfc = %s", RFC)["id"])


def test_recalcular_directo_tampoco_cuenta_un_rep_cancelado(entorno):
    """Aunque nadie llame al recálculo por REP, cualquier recálculo posterior de la factura
    (otro REP, reproceso) ya excluye al cancelado."""
    db, *_ = entorno
    from backend import cfdi_store

    db.execute("UPDATE cfdi SET estado = 'cancelado' WHERE uuid = %s", (UUID_REP,))
    cfdi_store.recalcular_cobrado(_empresa(db), UUID_FACTURA)

    assert _cobrado_de_la_factura(db) == {"m": D("0.00"), "e": "pendiente"}


def test_reprocesar_un_rep_cancelado_no_vuelve_a_inflar_lo_cobrado(entorno):
    db, _client, _headers, empresa_id = entorno
    from backend import reproceso

    db.execute("UPDATE cfdi SET estado = 'cancelado' WHERE uuid = %s", (UUID_REP,))
    db.execute("UPDATE cfdi SET detalle_version = 1 WHERE empresa_id = %s", (empresa_id,))
    reproceso.reprocesar_detalle(empresa_id=empresa_id)

    assert _cobrado_de_la_factura(db) == {"m": D("0.00"), "e": "pendiente"}


def test_con_dos_rep_solo_el_cancelado_deja_de_contar(entorno):
    """La factura de 1,660 cobrada por dos REP (1,160 y 500): al cancelar uno queda el otro."""
    db, client, headers, empresa_id = entorno
    from backend import cfdi_store

    uuid_rep2 = "0E0E0E0E-BBBB-CCCC-DDDD-EEEEFFFFEE20"
    xml = _xml_rep().replace(UUID_REP.encode(), uuid_rep2.encode()) \
        .replace(b'Monto="1160.00"', b'Monto="500.00"').replace(b'ImpPagado="1160.00"', b'ImpPagado="500.00"') \
        .replace(b'FechaPago="2026-12-20T12:00:00"', b'FechaPago="2026-12-21T12:00:00"')
    try:
        r = client.post(f"/api/v1/empresas/{empresa_id}/cfdi/upload", headers=headers, data={"periodo": PERIODO},
                        files=[("archivos", ("rep_b.xml", xml, "text/xml"))])
        assert r.status_code == 200, r.text
        assert _cobrado_de_la_factura(db)["m"] == D("1660.00")

        db.execute("UPDATE cfdi SET estado = 'cancelado' WHERE uuid = %s", (UUID_REP,))
        cfdi_store.recalcular_cobrado_de_rep(empresa_id, UUID_REP)

        assert _cobrado_de_la_factura(db) == {"m": D("500.00"), "e": "pagado_parcial"}
    finally:
        db.execute("DELETE FROM cfdi WHERE uuid = %s", (uuid_rep2,))


# ─── Reproceso de un REP anterior a la 041 con relaciones en varios nodos ─────

def _xml_rep_dos_nodos_con_documentos() -> bytes:
    """REP con dos pago:Pago de la misma fecha y monto; cada uno paga una parcialidad distinta de
    la misma factura (580 y 580 de 1,660)."""
    def pago(parcialidad: int, saldo_ant: str, saldo: str) -> str:
        return f"""<pago20:Pago FechaPago="2026-12-23T12:00:00" FormaDePagoP="03" MonedaP="MXN" TipoCambioP="1" Monto="580.00">
        <pago20:DoctoRelacionado IdDocumento="{UUID_FACTURA}" MonedaDR="MXN" EquivalenciaDR="1" NumParcialidad="{parcialidad}"
            ImpSaldoAnt="{saldo_ant}" ImpPagado="580.00" ImpSaldoInsoluto="{saldo}" ObjetoImpDR="01"/>
      </pago20:Pago>"""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" xmlns:pago20="http://www.sat.gob.mx/Pagos20"
    xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
    Version="4.0" Fecha="2026-12-23T10:00:00" TipoDeComprobante="P" SubTotal="0" Total="0" Moneda="XXX"
    Exportacion="01" LugarExpedicion="01000">
  <cfdi:Emisor Rfc="{RFC}" Nombre="Emisora E2E" RegimenFiscal="601"/>
  <cfdi:Receptor Rfc="{CLIENTE}" Nombre="Cliente" UsoCFDI="CP01" DomicilioFiscalReceptor="01000" RegimenFiscalReceptor="616"/>
  <cfdi:Complemento>
    <pago20:Pagos Version="2.0">
      <pago20:Totales MontoTotalPagos="1160.00"/>
      {pago(1, "1660.00", "1080.00")}{pago(2, "1080.00", "500.00")}
    </pago20:Pagos>
    <tfd:TimbreFiscalDigital UUID="{UUID_REP_DOBLE}" FechaTimbrado="2026-12-23T10:01:00"/>
  </cfdi:Complemento>
</cfdi:Comprobante>""".encode()


def _relaciones(db, cfdi_id):
    return db.query_all(
        "SELECT p.nodo, pr.parcialidad FROM pagos_relaciones pr JOIN pagos_cfdi p ON p.id = pr.pago_id "
        "WHERE p.cfdi_id = %s ORDER BY p.nodo, pr.parcialidad", (cfdi_id,))


def test_reprocesar_un_rep_antiguo_con_relaciones_en_varios_nodos_no_las_duplica(entorno):
    """Antes de la 041 los dos nodos compartían una fila (nodo 0) con las relaciones de ambos. El nodo 1
    reclama esa fila sin las del nodo 2, que viven en la suya: la parcialidad 2 no se cuenta dos veces."""
    db, client, headers, empresa_id = entorno
    from backend import reproceso

    r = client.post(f"/api/v1/empresas/{empresa_id}/cfdi/upload", headers=headers, data={"periodo": PERIODO},
                    files=[("archivos", ("rep3.xml", _xml_rep_dos_nodos_con_documentos(), "text/xml"))])
    assert r.status_code == 200, r.text
    cfdi_id = _uno(db, "SELECT id FROM cfdi WHERE uuid = %s", UUID_REP_DOBLE)["id"]
    assert [(x["nodo"], x["parcialidad"]) for x in _relaciones(db, cfdi_id)] == [(1, 1), (2, 2)]

    # Estado anterior a la 041: una sola fila, sin nodo, con las relaciones de los dos nodos.
    fila_unica = _uno(db, "SELECT id FROM pagos_cfdi WHERE cfdi_id = %s AND nodo = 1", cfdi_id)["id"]
    otra = _uno(db, "SELECT id FROM pagos_cfdi WHERE cfdi_id = %s AND nodo = 2", cfdi_id)["id"]
    db.execute("UPDATE pagos_relaciones SET pago_id = %s WHERE pago_id = %s", (fila_unica, otra))
    db.execute("DELETE FROM pagos_cfdi WHERE id = %s", (otra,))
    db.execute("UPDATE pagos_cfdi SET nodo = 0 WHERE id = %s", (fila_unica,))
    db.execute("UPDATE cfdi SET detalle_version = 2 WHERE id = %s", (cfdi_id,))

    resultado = reproceso.reprocesar_detalle(empresa_id=empresa_id)

    assert resultado["errores"] == [] and resultado["pendientes"] == 0
    assert [(x["nodo"], x["parcialidad"]) for x in _relaciones(db, cfdi_id)] == [(1, 1), (2, 2)]   # cada una, una vez
    assert _uno(db, "SELECT id FROM pagos_cfdi WHERE cfdi_id = %s AND nodo = 1", cfdi_id)["id"] == fila_unica   # conservó su id
    # y lo cobrado de la factura no se infla: 580 + 580 (más el REP vigente de la fixture, 1,160) tope 1,660
    assert _uno(db, "SELECT monto_cobrado AS m FROM cfdi WHERE uuid = %s", UUID_FACTURA)["m"] == D("1660.00")


def test_dos_copias_simultaneas_de_un_rep_antiguo_no_crean_dos_filas(entorno):
    """El candado por REP serializa la resolución de la fila: dos hilos reprocesando el mismo REP
    antiguo terminan con una fila por nodo, no con dos para el mismo."""
    import threading

    db, client, headers, empresa_id = entorno
    from backend import cfdi_store
    from backend.cfdi_parser import CFDIParser

    client.post(f"/api/v1/empresas/{empresa_id}/cfdi/upload", headers=headers, data={"periodo": PERIODO},
                files=[("archivos", ("rep3.xml", _xml_rep_dos_nodos_con_documentos(), "text/xml"))])
    cfdi_id = str(_uno(db, "SELECT id FROM cfdi WHERE uuid = %s", UUID_REP_DOBLE)["id"])
    db.execute("DELETE FROM pagos_cfdi WHERE cfdi_id = %s AND nodo = 2", (cfdi_id,))
    db.execute("UPDATE pagos_cfdi SET nodo = 0 WHERE cfdi_id = %s", (cfdi_id,))
    resultado = CFDIParser().parse_xml(_xml_rep_dos_nodos_con_documentos())
    errores = []

    def correr():
        try:
            cfdi_store.persistir_complemento_pago(empresa_id, resultado)
        except Exception as exc:     # pragma: no cover - solo si el candado falla
            errores.append(exc)

    hilos = [threading.Thread(target=correr) for _ in range(4)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    assert errores == []
    assert [f["nodo"] for f in db.query_all("SELECT nodo FROM pagos_cfdi WHERE cfdi_id = %s ORDER BY nodo", (cfdi_id,))] == [1, 2]
    assert [(x["nodo"], x["parcialidad"]) for x in _relaciones(db, cfdi_id)] == [(1, 1), (2, 2)]
