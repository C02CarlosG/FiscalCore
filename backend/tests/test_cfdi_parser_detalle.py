"""Detalle fiscal del CFDI en backend/cfdi_parser.py: impuestos por tasa,
conceptos, encabezados, impuestos de cada pago y nómina. Lógica pura (sin DB)."""
from decimal import Decimal

from backend.cfdi_parser import CFDIParser

D = Decimal


def _cfdi(cuerpo, *, version="4.0", tipo="I", subtotal="1000.00", total="1128.00", extra_attrs="", complemento=""):
    ns = "http://www.sat.gob.mx/cfd/4" if version == "4.0" else "http://www.sat.gob.mx/cfd/3"
    return f'''<cfdi:Comprobante xmlns:cfdi="{ns}" xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
        Version="{version}" Fecha="2026-01-15T12:00:00" TipoDeComprobante="{tipo}" SubTotal="{subtotal}"
        Total="{total}" Moneda="MXN" MetodoPago="PUE" FormaPago="03" LugarExpedicion="01000"
        Exportacion="01" {extra_attrs}>
      <cfdi:Emisor Rfc="PROV010101AAA" Nombre="Proveedor SA" RegimenFiscal="601"/>
      <cfdi:Receptor Rfc="EMP010101AAA" Nombre="Empresa SA" UsoCFDI="G03"
          DomicilioFiscalReceptor="01000" RegimenFiscalReceptor="601"/>
      {cuerpo}
      <cfdi:Complemento>{complemento}<tfd:TimbreFiscalDigital
          UUID="AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE" FechaTimbrado="2026-01-15T12:05:00"/></cfdi:Complemento>
    </cfdi:Comprobante>'''


# Tres conceptos: 16 %, 0 % y exento. SubTotal 1000, IVA 128, Total 1128.
CUERPO_MIXTO = '''
<cfdi:Conceptos>
  <cfdi:Concepto ClaveProdServ="43211500" NoIdentificacion="SKU-1" Cantidad="2" ClaveUnidad="H87"
      Unidad="Pieza" Descripcion="Laptop" ValorUnitario="400.00" Importe="800.00" Descuento="0.00" ObjetoImp="02">
    <cfdi:Impuestos><cfdi:Traslados>
      <cfdi:Traslado Base="800.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="128.00"/>
    </cfdi:Traslados></cfdi:Impuestos>
  </cfdi:Concepto>
  <cfdi:Concepto ClaveProdServ="50161500" Cantidad="1" ClaveUnidad="KGM" Descripcion="Alimento"
      ValorUnitario="150.00" Importe="150.00" ObjetoImp="02">
    <cfdi:Impuestos><cfdi:Traslados>
      <cfdi:Traslado Base="150.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.000000" Importe="0.00"/>
    </cfdi:Traslados></cfdi:Impuestos>
  </cfdi:Concepto>
  <cfdi:Concepto ClaveProdServ="85121600" Cantidad="1" ClaveUnidad="E48" Descripcion="Consulta"
      ValorUnitario="50.00" Importe="50.00" ObjetoImp="02">
    <cfdi:Impuestos><cfdi:Traslados>
      <cfdi:Traslado Base="50.00" Impuesto="002" TipoFactor="Exento"/>
    </cfdi:Traslados></cfdi:Impuestos>
    <cfdi:CuentaPredial Numero="PRED-9"/>
  </cfdi:Concepto>
</cfdi:Conceptos>
<cfdi:Impuestos TotalImpuestosTrasladados="128.00"><cfdi:Traslados>
  <cfdi:Traslado Base="800.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="128.00"/>
  <cfdi:Traslado Base="150.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.000000" Importe="0.00"/>
  <cfdi:Traslado Base="50.00" Impuesto="002" TipoFactor="Exento"/>
</cfdi:Traslados></cfdi:Impuestos>'''

# CFDI 3.3: el nodo raíz no trae Base; dos conceptos al 16 %.
CUERPO_33 = '''
<cfdi:Conceptos>
  <cfdi:Concepto ClaveProdServ="01010101" Cantidad="1" ClaveUnidad="ACT" Descripcion="A" ValorUnitario="300.00" Importe="300.00">
    <cfdi:Impuestos><cfdi:Traslados>
      <cfdi:Traslado Base="300.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="48.00"/>
    </cfdi:Traslados></cfdi:Impuestos>
  </cfdi:Concepto>
  <cfdi:Concepto ClaveProdServ="01010101" Cantidad="1" ClaveUnidad="ACT" Descripcion="B" ValorUnitario="200.00" Importe="200.00">
    <cfdi:Impuestos><cfdi:Traslados>
      <cfdi:Traslado Base="200.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="32.00"/>
    </cfdi:Traslados></cfdi:Impuestos>
  </cfdi:Concepto>
</cfdi:Conceptos>
<cfdi:Impuestos TotalImpuestosTrasladados="80.00"><cfdi:Traslados>
  <cfdi:Traslado Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="80.00"/>
</cfdi:Traslados></cfdi:Impuestos>'''

# Honorarios: IVA 16 % trasladado, retención de ISR 10 % y de IVA 10.6667 %.
CUERPO_HONORARIOS = '''
<cfdi:Conceptos>
  <cfdi:Concepto ClaveProdServ="80111600" Cantidad="1" ClaveUnidad="E48" Descripcion="Honorarios"
      ValorUnitario="1000.00" Importe="1000.00" ObjetoImp="02">
    <cfdi:Impuestos>
      <cfdi:Traslados>
        <cfdi:Traslado Base="1000.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="160.00"/>
      </cfdi:Traslados>
      <cfdi:Retenciones>
        <cfdi:Retencion Base="1000.00" Impuesto="001" TipoFactor="Tasa" TasaOCuota="0.100000" Importe="100.00"/>
        <cfdi:Retencion Base="1000.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.106667" Importe="106.67"/>
      </cfdi:Retenciones>
    </cfdi:Impuestos>
  </cfdi:Concepto>
</cfdi:Conceptos>
<cfdi:Impuestos TotalImpuestosTrasladados="160.00" TotalImpuestosRetenidos="206.67">
  <cfdi:Retenciones>
    <cfdi:Retencion Impuesto="001" Importe="100.00"/>
    <cfdi:Retencion Impuesto="002" Importe="106.67"/>
  </cfdi:Retenciones>
  <cfdi:Traslados>
    <cfdi:Traslado Base="1000.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="160.00"/>
  </cfdi:Traslados>
</cfdi:Impuestos>'''

# Retención declarada solo en el nodo raíz (sin impuestos por concepto).
CUERPO_RETENCION_SOLO_RAIZ = '''
<cfdi:Conceptos>
  <cfdi:Concepto ClaveProdServ="80111600" Cantidad="1" ClaveUnidad="E48" Descripcion="Servicio"
      ValorUnitario="1000.00" Importe="1000.00"/>
</cfdi:Conceptos>
<cfdi:Impuestos TotalImpuestosRetenidos="100.00">
  <cfdi:Retenciones><cfdi:Retencion Impuesto="001" Importe="100.00"/></cfdi:Retenciones>
</cfdi:Impuestos>'''


def _mapa(impuestos):
    return {(i.ambito, i.impuesto, i.tipo_factor, i.tasa_o_cuota): (i.base, i.importe) for i in impuestos}


def test_resumen_separa_tasa_16_tasa_0_y_exento():
    p = CFDIParser().parse_xml(_cfdi(CUERPO_MIXTO))

    assert _mapa(p.resumen_impuestos) == {
        ("traslado", "002", "Tasa", D("0.160000")): (D("800.00"), D("128.00")),
        ("traslado", "002", "Tasa", D("0.000000")): (D("150.00"), D("0.00")),
        ("traslado", "002", "Exento", None): (D("50.00"), D("0.00")),
    }
    assert p.iva_trasladado == D("128.00")  # el total de siempre no cambia


def test_resumen_cfdi_33_toma_la_base_de_los_conceptos():
    p = CFDIParser().parse_xml(_cfdi(CUERPO_33, version="3.3", subtotal="500.00", total="580.00"))

    assert _mapa(p.resumen_impuestos) == {
        ("traslado", "002", "Tasa", D("0.160000")): (D("500.00"), D("80.00")),
    }


def test_resumen_incluye_retenciones_con_base_y_tasa():
    p = CFDIParser().parse_xml(_cfdi(CUERPO_HONORARIOS, total="953.33"))

    mapa = _mapa(p.resumen_impuestos)
    assert mapa[("retencion", "001", "Tasa", D("0.100000"))] == (D("1000.00"), D("100.00"))
    assert mapa[("retencion", "002", "Tasa", D("0.106667"))] == (D("1000.00"), D("106.67"))
    assert mapa[("traslado", "002", "Tasa", D("0.160000"))] == (D("1000.00"), D("160.00"))
    assert len(mapa) == 3


def test_retencion_solo_en_raiz_queda_sin_tasa_ni_base():
    p = CFDIParser().parse_xml(_cfdi(CUERPO_RETENCION_SOLO_RAIZ, total="900.00"))

    assert _mapa(p.resumen_impuestos) == {
        ("retencion", "001", "Tasa", None): (D("0.00"), D("100.00")),
    }


def test_conceptos_se_extraen_en_orden_con_sus_impuestos():
    p = CFDIParser().parse_xml(_cfdi(CUERPO_MIXTO))

    assert [c.linea for c in p.conceptos] == [1, 2, 3]
    primero = p.conceptos[0]
    assert (primero.clave_prod_serv, primero.no_identificacion, primero.clave_unidad, primero.unidad) == (
        "43211500", "SKU-1", "H87", "Pieza")
    assert (primero.cantidad, primero.valor_unitario, primero.importe, primero.descuento) == (
        D("2"), D("400.00"), D("800.00"), D("0.00"))
    assert (primero.descripcion, primero.objeto_imp) == ("Laptop", "02")
    assert _mapa(primero.impuestos) == {("traslado", "002", "Tasa", D("0.160000")): (D("800.00"), D("128.00"))}
    assert p.conceptos[1].no_identificacion is None
    assert p.conceptos[2].cuenta_predial == "PRED-9"


def test_encabezados_certificado_e_informacion_global():
    cuerpo = '<cfdi:InformacionGlobal Periodicidad="04" Meses="09" Año="2026"/>' + CUERPO_MIXTO
    p = CFDIParser().parse_xml(_cfdi(
        cuerpo, extra_attrs='NoCertificado="00001000000504465028" CondicionesDePago="30 días"'))

    assert p.no_certificado == "00001000000504465028"
    assert p.condiciones_pago == "30 días"
    assert (p.periodicidad, p.meses, p.anio_global) == ("04", "09", 2026)
    assert p.regimen_emisor == "601"


def test_sin_informacion_global_los_campos_quedan_vacios():
    p = CFDIParser().parse_xml(_cfdi(CUERPO_MIXTO))

    assert (p.no_certificado, p.periodicidad, p.meses, p.anio_global) == (None, None, None, None)


def _rep(nodo_pagos):
    return f'''<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
        xmlns:pago20="http://www.sat.gob.mx/Pagos20" xmlns:pago10="http://www.sat.gob.mx/Pagos"
        xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
        Version="4.0" Fecha="2026-01-20T10:00:00" TipoDeComprobante="P" SubTotal="0" Total="0"
        Moneda="XXX" LugarExpedicion="01000" Exportacion="01">
      <cfdi:Emisor Rfc="PROV010101AAA" Nombre="Proveedor SA" RegimenFiscal="601"/>
      <cfdi:Receptor Rfc="EMP010101AAA" Nombre="Empresa SA" UsoCFDI="CP01"/>
      <cfdi:Complemento>{nodo_pagos}<tfd:TimbreFiscalDigital
          UUID="99999999-8888-7777-6666-555555555555" FechaTimbrado="2026-01-20T10:05:00"/></cfdi:Complemento>
    </cfdi:Comprobante>'''


PAGOS_20 = '''<pago20:Pagos Version="2.0">
  <pago20:Totales MontoTotalPagos="6150.00"/>
  <pago20:Pago FechaPago="2026-01-20T12:00:00" FormaDePagoP="03" MonedaP="MXN" TipoCambioP="1" Monto="6150.00">
    <pago20:DoctoRelacionado IdDocumento="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee" MonedaDR="MXN"
        EquivalenciaDR="1" NumParcialidad="1" ImpSaldoAnt="12300.00" ImpPagado="6150.00"
        ImpSaldoInsoluto="6150.00" ObjetoImpDR="02">
      <pago20:ImpuestosDR>
        <pago20:RetencionesDR>
          <pago20:RetencionDR BaseDR="5000.00" ImpuestoDR="001" TipoFactorDR="Tasa" TasaOCuotaDR="0.100000" ImporteDR="500.00"/>
        </pago20:RetencionesDR>
        <pago20:TrasladosDR>
          <pago20:TrasladoDR BaseDR="5000.00" ImpuestoDR="002" TipoFactorDR="Tasa" TasaOCuotaDR="0.160000" ImporteDR="800.00"/>
          <pago20:TrasladoDR BaseDR="250.00" ImpuestoDR="002" TipoFactorDR="Tasa" TasaOCuotaDR="0.000000" ImporteDR="0.00"/>
          <pago20:TrasladoDR BaseDR="100.00" ImpuestoDR="002" TipoFactorDR="Exento"/>
        </pago20:TrasladosDR>
      </pago20:ImpuestosDR>
    </pago20:DoctoRelacionado>
  </pago20:Pago>
</pago20:Pagos>'''

PAGOS_10 = '''<pago10:Pagos Version="1.0">
  <pago10:Pago FechaPago="2021-03-20T12:00:00" FormaDePagoP="03" MonedaP="MXN" Monto="580.00">
    <pago10:DoctoRelacionado IdDocumento="33333333-3333-3333-3333-333333333333" MonedaDR="MXN"
        NumParcialidad="1" ImpSaldoAnt="580.00" ImpPagado="580.00" ImpSaldoInsoluto="0.00"/>
  </pago10:Pago>
</pago10:Pagos>'''


def test_rep_20_trae_los_impuestos_de_cada_documento():
    p = CFDIParser().parse_xml(_rep(PAGOS_20))

    pago = p.pagos[0]
    docto = pago.doctos_relacionados[0]
    assert pago.version == "2.0"
    assert (docto.moneda_dr, docto.equivalencia_dr) == ("MXN", D("1"))
    assert _mapa(docto.impuestos) == {
        ("retencion", "001", "Tasa", D("0.100000")): (D("5000.00"), D("500.00")),
        ("traslado", "002", "Tasa", D("0.160000")): (D("5000.00"), D("800.00")),
        ("traslado", "002", "Tasa", D("0.000000")): (D("250.00"), D("0.00")),
        ("traslado", "002", "Exento", None): (D("100.00"), D("0.00")),
    }


def test_rep_10_no_trae_impuestos_y_se_marca_como_version_1():
    p = CFDIParser().parse_xml(_rep(PAGOS_10))

    pago = p.pagos[0]
    assert pago.version == "1.0"
    assert pago.doctos_relacionados[0].impuestos == []
    assert pago.doctos_relacionados[0].equivalencia_dr == D("1")
