"""Tests de backend/cfdi_parser.py — parser de CFDI XML (Día 20).

Lógica pura (sin DB): parsea XML CFDI 3.3/4.0 con `xml.etree.ElementTree`.
Los fixtures construyen XML mínimo pero válido respetando los namespaces
oficiales del SAT (cfdi 3.3/4.0, TimbreFiscalDigital, Pagos 2.0) para
ejercitar el parser tal como lo haría un XML real.
"""
from decimal import Decimal

import pytest

from backend.cfdi_parser import CFDIParseError, CFDIParser, validar_rfc

RFC_PROV = "PROV010101AAA"
RFC_EMPRESA = "EMP010101AAA"


def _xml_ingreso(
    comprobante_attrs=None,
    emisor_attrs=None,
    receptor_attrs=None,
    clave_prod_serv="01010101",
    incluir_timbre=True,
    cfdi_relacionados_xml="",
    impuestos_xml=None,
):
    """CFDI 4.0 tipo Ingreso, PUE, $1000 + 16% IVA = $1160, con timbre."""
    attrs = {
        "Version": "4.0", "Fecha": "2026-01-15T12:00:00", "TipoDeComprobante": "I",
        "SubTotal": "1000.00", "Descuento": "0", "Total": "1160.00", "Moneda": "MXN",
        "MetodoPago": "PUE", "FormaPago": "03", "LugarExpedicion": "01000", "Exportacion": "01",
    }
    attrs.update(comprobante_attrs or {})
    e_attrs = {"Rfc": RFC_PROV, "Nombre": "Proveedor SA", "RegimenFiscal": "601"}
    e_attrs.update(emisor_attrs or {})
    r_attrs = {"Rfc": RFC_EMPRESA, "Nombre": "Empresa SA", "UsoCFDI": "G03",
               "DomicilioFiscalReceptor": "01000", "RegimenFiscalReceptor": "601"}
    r_attrs.update(receptor_attrs or {})

    if impuestos_xml is None:
        impuestos_xml = (
            '<cfdi:Impuestos TotalImpuestosTrasladados="160.00"><cfdi:Traslados>'
            '<cfdi:Traslado Impuesto="002" TasaOCuota="0.160000" TipoFactor="Tasa" Importe="160.00"/>'
            '</cfdi:Traslados></cfdi:Impuestos>'
        )
    timbre_xml = (
        '<cfdi:Complemento><tfd:TimbreFiscalDigital '
        'UUID="AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE" FechaTimbrado="2026-01-15T12:05:00"/></cfdi:Complemento>'
        if incluir_timbre else ""
    )

    attrs_str = " ".join(f'{k}="{v}"' for k, v in attrs.items() if v is not None)
    emisor_str = " ".join(f'{k}="{v}"' for k, v in e_attrs.items() if v is not None)
    receptor_str = " ".join(f'{k}="{v}"' for k, v in r_attrs.items() if v is not None)

    return f'''<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
        xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" {attrs_str}>
      <cfdi:Emisor {emisor_str}/>
      <cfdi:Receptor {receptor_str}/>
      {cfdi_relacionados_xml}
      <cfdi:Conceptos>
        <cfdi:Concepto ClaveProdServ="{clave_prod_serv}" Importe="1000.00"/>
      </cfdi:Conceptos>
      {impuestos_xml}
      {timbre_xml}
    </cfdi:Comprobante>'''


def _xml_pago():
    """Complemento de Pago 2.0 (tipo P), un REP que liquida un CFDI PPD."""
    return '''<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" xmlns:pago20="http://www.sat.gob.mx/Pagos20"
        Version="4.0" Fecha="2026-01-20T10:00:00" TipoDeComprobante="P" SubTotal="0" Total="0" Moneda="XXX"
        LugarExpedicion="01000" Exportacion="01">
      <cfdi:Emisor Rfc="PROV010101AAA" Nombre="Proveedor SA" RegimenFiscal="601"/>
      <cfdi:Receptor Rfc="EMP010101AAA" Nombre="Empresa SA" UsoCFDI="CP01"/>
      <cfdi:Complemento>
        <pago20:Pagos Version="2.0">
          <pago20:Totales MontoTotalPagos="1000.00"/>
          <pago20:Pago FechaPago="2026-01-20T10:00:00" FormaDePagoP="03" Monto="1000.00" MonedaP="MXN" TipoCambioP="1">
            <pago20:DoctoRelacionado IdDocumento="AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE" NumParcialidad="1"
                ImpPagado="1000.00" ImpSaldoAnt="1000.00" ImpSaldoInsoluto="0.00"/>
          </pago20:Pago>
        </pago20:Pagos>
        <tfd:TimbreFiscalDigital xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
            UUID="99999999-8888-7777-6666-555555555555" FechaTimbrado="2026-01-20T10:05:00"/>
      </cfdi:Complemento>
    </cfdi:Comprobante>'''


def _xml_33_ppd():
    """CFDI 3.3 (namespace cfd/3), Ingreso PPD — no debe generar AVISOs de campos 4.0."""
    return '''<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/3"
        xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
        Version="3.3" Fecha="2025-06-01T09:00:00" TipoDeComprobante="I" SubTotal="500.00"
        Total="580.00" Moneda="MXN" MetodoPago="PPD" FormaPago="99">
      <cfdi:Emisor Rfc="PROV010101AAA" Nombre="Proveedor SA" RegimenFiscal="601"/>
      <cfdi:Receptor Rfc="EMP010101AAA" Nombre="Empresa SA" UsoCFDI="G03"/>
      <cfdi:Impuestos TotalImpuestosTrasladados="80.00">
        <cfdi:Traslados>
          <cfdi:Traslado Impuesto="002" TasaOCuota="0.160000" TipoFactor="Tasa" Importe="80.00"/>
        </cfdi:Traslados>
      </cfdi:Impuestos>
      <cfdi:Complemento><tfd:TimbreFiscalDigital
          UUID="33333333-3333-3333-3333-333333333333" FechaTimbrado="2025-06-01T09:05:00"/></cfdi:Complemento>
    </cfdi:Comprobante>'''


def _parser():
    return CFDIParser()


# ─── Caso feliz: CFDI 4.0 ingreso PUE típico ────────────────────────────────


def test_cfdi_4_0_ingreso_pue_completo():
    p = _parser().parse_xml(_xml_ingreso())
    assert p.version == "4.0"
    assert p.tipo_comprobante == "I"
    assert p.es_ingreso is True
    assert p.rfc_emisor == RFC_PROV
    assert p.rfc_emisor_valido is True
    assert p.subtotal == p.total - p.iva_trasladado
    assert p.iva_trasladado == Decimal("160.00")
    assert p.uuid == "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
    assert p.fecha_timbrado is not None
    assert p.errores == []
    assert p.es_anticipo_sat is False


# ─── XML malformado ──────────────────────────────────────────────────────────


def test_xml_malformado_levanta_cfdi_parse_error():
    with pytest.raises(CFDIParseError, match="XML inválido"):
        _parser().parse_xml("<cfdi:Comprobante><no cierra")


def test_xml_vacio_levanta_cfdi_parse_error():
    with pytest.raises(CFDIParseError):
        _parser().parse_xml("")


# ─── Timbre fiscal ────────────────────────────────────────────────────────


def test_sin_timbre_es_error_bloqueante_y_no_inventa_uuid():
    """Un XML sin Timbre Fiscal Digital no es un CFDI válido (borrador o
    prefactura). Antes se le asignaba un UUID aleatorio y se ingería como si
    estuviera timbrado; re-subirlo creaba además un registro nuevo cada vez."""
    p = _parser().parse_xml(_xml_ingreso(incluir_timbre=False))
    assert p.uuid == ""
    assert p.fecha_timbrado is None
    bloqueantes = [e for e in p.errores if not e.startswith("AVISO:")]
    assert any("Timbre Fiscal Digital" in e for e in bloqueantes)


# ─── Anticipo SAT (ClaveProdServ 84111506) ──────────────────────────────────


def test_clave_anticipo_en_ingreso_pue_sin_relacionados_marca_anticipo():
    p = _parser().parse_xml(_xml_ingreso(clave_prod_serv="84111506"))
    assert p.es_anticipo_sat is True


def test_clave_anticipo_no_activa_si_ppd():
    """La definición SAT exige MetodoPago=PUE; con PPD no debe marcarse."""
    p = _parser().parse_xml(_xml_ingreso(
        clave_prod_serv="84111506", comprobante_attrs={"MetodoPago": "PPD"}))
    assert p.es_anticipo_sat is False


def test_clave_anticipo_no_activa_con_cfdi_relacionados():
    """Un anticipo real no debe traer CfdiRelacionados (eso es la aplicación posterior)."""
    p = _parser().parse_xml(_xml_ingreso(
        clave_prod_serv="84111506",
        cfdi_relacionados_xml=(
            '<cfdi:CfdiRelacionados TipoRelacion="07">'
            '<cfdi:CfdiRelacionado UUID="11111111-1111-1111-1111-111111111111"/>'
            '</cfdi:CfdiRelacionados>'
        ),
    ))
    assert p.es_anticipo_sat is False


def test_clave_normal_no_es_anticipo():
    p = _parser().parse_xml(_xml_ingreso(clave_prod_serv="01010101"))
    assert p.es_anticipo_sat is False


# ─── CfdiRelacionados (notas de crédito, aplicación de anticipo) ───────────


def test_cfdi_relacionados_nota_credito():
    p = _parser().parse_xml(_xml_ingreso(cfdi_relacionados_xml=(
        '<cfdi:CfdiRelacionados TipoRelacion="01">'
        '<cfdi:CfdiRelacionado UUID="11111111-1111-1111-1111-111111111111"/>'
        '</cfdi:CfdiRelacionados>'
    )))
    assert p.cfdi_relacionados == [{
        "tipo_relacion": "01",
        "uuids": ["11111111-1111-1111-1111-111111111111"],
    }]


def test_sin_cfdi_relacionados_da_lista_vacia():
    p = _parser().parse_xml(_xml_ingreso())
    assert p.cfdi_relacionados == []


# ─── PUE vs PPD ──────────────────────────────────────────────────────────


def test_metodo_pago_pue():
    p = _parser().parse_xml(_xml_ingreso(comprobante_attrs={"MetodoPago": "PUE"}))
    assert p.metodo_pago == "PUE"


def test_metodo_pago_ppd():
    p = _parser().parse_xml(_xml_ingreso(comprobante_attrs={"MetodoPago": "PPD"}))
    assert p.metodo_pago == "PPD"


# ─── Complemento de Pago (tipo P) ───────────────────────────────────────────


def test_complemento_de_pago_extrae_pagos_y_doctos_relacionados():
    p = _parser().parse_xml(_xml_pago())
    assert p.tipo_comprobante == "P"
    assert p.es_pago is True
    assert len(p.pagos) == 1

    pago = p.pagos[0]
    assert pago.monto == Decimal("1000.00")
    assert pago.moneda == "MXN"
    assert len(pago.doctos_relacionados) == 1

    docto = pago.doctos_relacionados[0]
    assert docto.uuid == "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
    assert docto.imp_pagado == Decimal("1000.00")
    assert docto.imp_saldo_insoluto == Decimal("0.00")


def test_complemento_de_pago_lee_monto_del_nodo_pago_no_de_totales():
    """Pagos20.xsd: el importe del pago es el atributo `Monto` del nodo Pago.
    `MontoTotalPagos` (en pago20:Totales) es la suma de todos los pagos del REP.
    Antes se leía un atributo inexistente (`MontoTotal`), el monto quedaba en 0
    y la ingesta descartaba el pago."""
    xml = _xml_pago().replace('MontoTotalPagos="1000.00"', 'MontoTotalPagos="9999.00"')
    p = _parser().parse_xml(xml)
    assert p.pagos[0].monto == Decimal("1000.00")


def test_uuid_de_timbre_y_de_docto_relacionado_se_normalizan_a_mayusculas():
    """El mismo UUID llega con distinta caja según el emisor; se guarda siempre
    en mayúsculas para que el cruce REP ↔ factura no dependa de eso."""
    factura = _parser().parse_xml(
        _xml_ingreso().replace("AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"))
    rep = _parser().parse_xml(
        _xml_pago().replace("AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"))
    assert factura.uuid == "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
    assert rep.pagos[0].doctos_relacionados[0].uuid == factura.uuid


def test_complemento_de_pago_no_genera_error_por_total_cero():
    """Un CFDI tipo P legítimamente tiene Total=0 — la validación de cuadre no debe aplicar."""
    p = _parser().parse_xml(_xml_pago())
    assert p.errores == []


def test_cfdi_no_pago_no_extrae_pagos():
    p = _parser().parse_xml(_xml_ingreso())
    assert p.pagos == []


# ─── Cuadre fiscal con impuestos distintos de IVA/ISR ─────────────────────


def _bloqueantes(p):
    return [e for e in p.errores if not e.startswith("AVISO:")]


def test_cuadre_acepta_cfdi_con_ieps_trasladado():
    """Gasolina, bebidas, etc.: Total = SubTotal + IVA + IEPS. Antes el cuadre
    solo sumaba IVA y rechazaba el CFDI como error bloqueante."""
    impuestos = (
        '<cfdi:Impuestos TotalImpuestosTrasladados="240.00"><cfdi:Traslados>'
        '<cfdi:Traslado Impuesto="002" TasaOCuota="0.160000" TipoFactor="Tasa" Importe="160.00"/>'
        '<cfdi:Traslado Impuesto="003" TasaOCuota="0.080000" TipoFactor="Tasa" Importe="80.00"/>'
        '</cfdi:Traslados></cfdi:Impuestos>'
    )
    p = _parser().parse_xml(_xml_ingreso(comprobante_attrs={"Total": "1240.00"}, impuestos_xml=impuestos))
    assert _bloqueantes(p) == []
    assert p.iva_trasladado == Decimal("160.00")  # el IEPS no se mezcla con el IVA
    assert p.total_traslados == Decimal("240.00")


def test_cuadre_acepta_retenciones_de_iva_isr_e_ieps():
    impuestos = (
        '<cfdi:Impuestos TotalImpuestosTrasladados="160.00" TotalImpuestosRetenidos="216.67">'
        '<cfdi:Retenciones>'
        '<cfdi:Retencion Impuesto="001" Importe="100.00"/>'
        '<cfdi:Retencion Impuesto="002" Importe="106.67"/>'
        '<cfdi:Retencion Impuesto="003" Importe="10.00"/>'
        '</cfdi:Retenciones><cfdi:Traslados>'
        '<cfdi:Traslado Impuesto="002" TasaOCuota="0.160000" TipoFactor="Tasa" Importe="160.00"/>'
        '</cfdi:Traslados></cfdi:Impuestos>'
    )
    p = _parser().parse_xml(_xml_ingreso(comprobante_attrs={"Total": "943.33"}, impuestos_xml=impuestos))
    assert _bloqueantes(p) == []
    assert p.isr_retenido == Decimal("100.00")
    assert p.iva_retenido == Decimal("106.67")
    assert p.total_retenciones == Decimal("216.67")


def test_cuadre_acepta_impuestos_locales_del_complemento_implocal():
    """Hospedaje (ISH): el impuesto local va en el complemento implocal y forma
    parte del Total, pero no aparece en cfdi:Impuestos."""
    xml = _xml_ingreso(comprobante_attrs={"Total": "1190.00"}).replace(
        "<cfdi:Complemento>",
        '<cfdi:Complemento><implocal:ImpuestosLocales xmlns:implocal="http://www.sat.gob.mx/implocal" '
        'version="1.0" TotaldeRetenciones="0.00" TotaldeTraslados="30.00">'
        '<implocal:TrasladosLocales ImpLocTrasladado="ISH" TasadeTraslado="3.00" Importe="30.00"/>'
        '</implocal:ImpuestosLocales>',
    )
    p = _parser().parse_xml(xml)
    assert _bloqueantes(p) == []
    assert p.total_traslados == Decimal("190.00")


def test_cuadre_sigue_detectando_total_que_no_cuadra():
    impuestos = (
        '<cfdi:Impuestos TotalImpuestosTrasladados="240.00"><cfdi:Traslados>'
        '<cfdi:Traslado Impuesto="002" TasaOCuota="0.160000" TipoFactor="Tasa" Importe="160.00"/>'
        '<cfdi:Traslado Impuesto="003" TasaOCuota="0.080000" TipoFactor="Tasa" Importe="80.00"/>'
        '</cfdi:Traslados></cfdi:Impuestos>'
    )
    p = _parser().parse_xml(_xml_ingreso(comprobante_attrs={"Total": "1160.00"}, impuestos_xml=impuestos))
    assert any("Cuadre fiscal" in e for e in _bloqueantes(p))


# ─── CFDI 3.3 ────────────────────────────────────────────────────────────


def test_cfdi_3_3_detecta_version_y_namespace():
    p = _parser().parse_xml(_xml_33_ppd())
    assert p.version == "3.3"
    assert p.metodo_pago == "PPD"
    assert p.errores == []  # los AVISOs de campos 4.0 no aplican a 3.3


# ─── Validaciones: RFC, cuadre fiscal, campos requeridos 4.0 ───────────────


def test_rfc_emisor_invalido_genera_error():
    p = _parser().parse_xml(_xml_ingreso(emisor_attrs={"Rfc": "MAL"}))
    assert p.rfc_emisor_valido is False
    assert any("RFC emisor inválido" in e for e in p.errores)


def test_cuadre_fiscal_incorrecto_genera_error():
    p = _parser().parse_xml(_xml_ingreso(comprobante_attrs={"Total": "99999.00"}))
    assert any("Cuadre fiscal" in e for e in p.errores)


def test_total_cero_en_ingreso_no_bloquea():
    # El SAT timbra ingresos en cero (descuento del 100 %, bonificaciones):
    # descartarlos dejaba fuera CFDI recibidos válidos en la descarga masiva.
    p = _parser().parse_xml(_xml_ingreso(
        comprobante_attrs={"Total": "0", "SubTotal": "0"},
        impuestos_xml='<cfdi:Impuestos TotalImpuestosTrasladados="0"/>',
    ))
    assert [e for e in p.errores if not e.startswith("AVISO:")] == []


def test_traslado_con_total_cero_no_bloquea():
    # Anexo 20: en un comprobante tipo T el Total siempre es cero.
    p = _parser().parse_xml(_xml_ingreso(
        comprobante_attrs={"TipoDeComprobante": "T", "Total": "0", "SubTotal": "0",
                           "Moneda": "XXX", "MetodoPago": None, "FormaPago": None},
        impuestos_xml="",
    ))
    assert [e for e in p.errores if not e.startswith("AVISO:")] == []


def test_total_negativo_genera_error():
    p = _parser().parse_xml(_xml_ingreso(
        comprobante_attrs={"Total": "-1160.00", "SubTotal": "-1000.00"},
        impuestos_xml='<cfdi:Impuestos TotalImpuestosTrasladados="-160.00"/>',
    ))
    assert any("Total no puede ser negativo" in e for e in p.errores)


def test_cfdi_4_0_sin_campos_requeridos_genera_avisos():
    p = _parser().parse_xml(_xml_ingreso(
        comprobante_attrs={"Exportacion": None, "LugarExpedicion": None},
        receptor_attrs={"DomicilioFiscalReceptor": None, "RegimenFiscalReceptor": None},
    ))
    assert any("Exportacion" in e for e in p.errores)
    assert any("LugarExpedicion" in e for e in p.errores)
    assert any("DomicilioFiscalReceptor" in e for e in p.errores)
    assert any("RegimenFiscalReceptor" in e for e in p.errores)


# ─── validar_rfc (función pura, usada también por MotorRiesgos) ────────────


@pytest.mark.parametrize("rfc", ["PROV010101AAA", "EMP010101AAA", "XAXX010101000"])
def test_validar_rfc_formatos_validos(rfc):
    assert validar_rfc(rfc) is True


@pytest.mark.parametrize("rfc", ["ABC123", "", None, "DEMASIADOLARGO0101AAAA"])
def test_validar_rfc_formatos_invalidos(rfc):
    assert validar_rfc(rfc) is False


def test_validar_rfc_normaliza_espacios_y_minusculas():
    assert validar_rfc(" prov010101aaa ") is True
