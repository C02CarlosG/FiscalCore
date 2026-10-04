"""Extracción v2 del XML (F3.5a): nómina por percepción, Totales e ImpuestosP del REP,
ObjetoImpDR y ACuentaTerceros. Lógica pura (sin DB)."""
from datetime import datetime
from decimal import Decimal

import pytest

from backend.cfdi_parser import CFDIParser
from backend.tests.test_cfdi_parser_detalle import PAGOS_10, _cfdi, _rep

D = Decimal

NOMINA_COMPLETA = '''<nomina12:Nomina xmlns:nomina12="http://www.sat.gob.mx/nomina12" Version="1.2" TipoNomina="E"
    FechaPago="2026-12-20" FechaInicialPago="2026-12-01" FechaFinalPago="2026-12-31" NumDiasPagados="30.5"
    TotalPercepciones="21000.00" TotalDeducciones="2500.00" TotalOtrosPagos="200.00">
  <nomina12:Receptor Curp="AAAA010101HDFXXX01" TipoContrato="01" TipoRegimen="02" NumEmpleado="E-0042"
      PeriodicidadPago="04" ClaveEntFed="OAX"/>
  <nomina12:Percepciones TotalSueldos="10000.00" TotalSeparacionIndemnizacion="5000.00"
      TotalJubilacionPensionRetiro="6000.00" TotalGravado="14000.00" TotalExento="7000.00">
    <nomina12:Percepcion TipoPercepcion="001" Clave="P01" Concepto="Sueldo" ImporteGravado="10000.00" ImporteExento="0.00"/>
    <nomina12:Percepcion TipoPercepcion="002" Clave="P02" Concepto="Aguinaldo" ImporteGravado="0.00" ImporteExento="2000.00"/>
    <nomina12:Percepcion TipoPercepcion="003" Clave="P03" Concepto="PTU" ImporteGravado="4000.00" ImporteExento="5000.00"/>
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
    <nomina12:OtroPago TipoOtroPago="004" Clave="O02" Concepto="Reembolso" Importe="0.00"/>
    <nomina12:OtroPago TipoOtroPago="004" Clave="O03" Concepto="Compensación" Importe="150.00">
      <nomina12:CompensacionSaldosAFavor SaldoAFavor="400.00" Año="2025" RemanenteSalFav="250.00"/>
    </nomina12:OtroPago>
  </nomina12:OtrosPagos>
</nomina12:Nomina>'''


def _nomina(nodos=NOMINA_COMPLETA):
    return CFDIParser().parse_xml(_cfdi(
        "<cfdi:Conceptos><cfdi:Concepto ClaveProdServ=\"84111505\" Cantidad=\"1\" ClaveUnidad=\"ACT\" "
        "Descripcion=\"Pago de nómina\" ValorUnitario=\"21200.00\" Importe=\"21200.00\" ObjetoImp=\"01\"/></cfdi:Conceptos>",
        tipo="N", subtotal="21200.00", total="18700.00", complemento=nodos)).nominas


def test_nomina_encabezado_y_receptor():
    (n,) = _nomina()

    assert n.nodo == 1
    assert n.tipo_nomina == "E"
    assert n.fecha_pago == datetime(2026, 12, 20)
    assert (n.fecha_inicial_pago, n.fecha_final_pago) == (datetime(2026, 12, 1), datetime(2026, 12, 31))
    assert n.num_dias_pagados == D("30.5")
    assert (n.tipo_regimen, n.num_empleado) == ("02", "E-0042")
    assert (n.total_percepciones, n.total_deducciones, n.total_otros_pagos) == (D("21000.00"), D("2500.00"), D("200.00"))
    assert (n.total_sueldos, n.total_gravado, n.total_exento) == (D("10000.00"), D("14000.00"), D("7000.00"))
    assert (n.total_otras_deducciones, n.total_impuestos_retenidos) == (D("300.00"), D("2200.00"))


def test_nomina_no_guarda_la_curp_del_trabajador():
    """La CURP es un dato personal que ningún cálculo usa: no se extrae."""
    assert "curp" not in {c.lower() for c in vars(_nomina()[0])}


def test_percepciones_por_tipo_con_gravado_y_exento():
    percepciones = [c for c in _nomina()[0].conceptos if c.categoria == "percepcion"]

    assert [(c.linea, c.tipo, c.concepto, c.importe_gravado, c.importe_exento) for c in percepciones] == [
        (1, "001", "Sueldo", D("10000.00"), D("0.00")),
        (2, "002", "Aguinaldo", D("0.00"), D("2000.00")),
        (3, "003", "PTU", D("4000.00"), D("5000.00")),
    ]
    assert all(c.importe is None for c in percepciones)


def test_deducciones_y_otros_pagos_por_tipo_con_subsidio_causado():
    conceptos = _nomina()[0].conceptos
    deducciones = [c for c in conceptos if c.categoria == "deduccion"]
    otros = [c for c in conceptos if c.categoria == "otro_pago"]

    assert [(c.tipo, c.importe) for c in deducciones] == [("001", D("300.00")), ("002", D("2200.00"))]
    assert [(c.linea, c.tipo, c.importe, c.subsidio_causado) for c in otros] == [
        (1, "002", D("200.00"), D("200.00")),
        (2, "004", D("0.00"), None),     # sin SubsidioAlEmpleo: no se inventa un causado
        (3, "004", D("150.00"), None),
    ]
    compensacion = otros[2]
    assert (compensacion.saldo_a_favor, compensacion.anio_saldo_a_favor, compensacion.remanente_saldo_a_favor) == (
        D("400.00"), 2025, D("250.00"))
    assert (otros[1].saldo_a_favor, otros[1].anio_saldo_a_favor) == (None, None)


def test_separacion_y_jubilacion():
    (n,) = _nomina()

    assert n.total_separacion_indemnizacion == D("5000.00")
    assert (n.sep_total_pagado, n.sep_anios_servicio, n.sep_ultimo_sueldo_mens_ord) == (D("5000.00"), 7, D("9000.00"))
    assert (n.sep_ingreso_acumulable, n.sep_ingreso_no_acumulable) == (D("3000.00"), D("2000.00"))
    assert n.total_jubilacion_pension_retiro == D("6000.00")
    assert (n.jub_total_una_exhibicion, n.jub_total_parcialidad, n.jub_monto_diario) == (D("6000.00"), None, None)
    assert (n.jub_ingreso_acumulable, n.jub_ingreso_no_acumulable) == (D("1000.00"), D("5000.00"))


def test_nomina_minima_deja_none_lo_que_no_viene():
    (n,) = _nomina('''<nomina12:Nomina xmlns:nomina12="http://www.sat.gob.mx/nomina12" Version="1.2" TipoNomina="O"
        FechaPago="2026-01-15" TotalPercepciones="100.00"><nomina12:Percepciones TotalGravado="100.00"/></nomina12:Nomina>''')

    assert (n.total_deducciones, n.total_otros_pagos, n.total_sueldos, n.total_exento) == (None, None, None, None)
    assert (n.tipo_regimen, n.num_empleado, n.fecha_inicial_pago, n.num_dias_pagados) == (None, None, None, None)
    assert (n.sep_total_pagado, n.sep_anios_servicio, n.jub_monto_diario) == (None, None, None)
    assert n.conceptos == []


def test_nomina_atributos_basura_no_rompen_ni_cuentan_como_cero():
    (n,) = _nomina('''<nomina12:Nomina xmlns:nomina12="http://www.sat.gob.mx/nomina12" Version="1.2" TipoNomina="O"
        FechaPago="no-es-fecha" TotalPercepciones="NaN" NumDiasPagados="abc">
        <nomina12:Percepciones><nomina12:Percepcion TipoPercepcion="001" ImporteGravado="Infinity"/></nomina12:Percepciones>
        </nomina12:Nomina>''')

    assert n.fecha_pago is None and n.total_percepciones is None and n.num_dias_pagados is None
    assert n.conceptos[0].importe_gravado is None


def test_varios_nodos_de_nomina_se_numeran_en_orden():
    dos = NOMINA_COMPLETA.replace("</nomina12:Nomina>", "</nomina12:Nomina>" + NOMINA_COMPLETA.replace("E-0042", "E-0043"))
    nominas = _nomina(dos)

    assert [(n.nodo, n.num_empleado) for n in nominas] == [(1, "E-0042"), (2, "E-0043")]


def test_el_resumen_de_nomina_de_v1_sigue_igual():
    p = CFDIParser().parse_xml(_cfdi("", tipo="N", subtotal="0", total="0", complemento=NOMINA_COMPLETA))
    assert (p.nomina.total_gravado, p.nomina.total_exento, p.nomina.isr_retenido) == (D("14000.00"), D("7000.00"), D("2200.00"))


def test_cfdi_sin_nomina_no_trae_detalle_de_nomina():
    assert CFDIParser().parse_xml(_cfdi("")).nominas == []


# ─── REP ────────────────────────────────────────────────────

PAGOS_20_V2 = '''<pago20:Pagos Version="2.0">
  <pago20:Totales TotalRetencionesISR="500.00" TotalTrasladosBaseIVA16="5000.00" TotalTrasladosImpuestoIVA16="800.00"
      TotalTrasladosBaseIVA0="250.00" TotalTrasladosImpuestoIVA0="0.00" TotalTrasladosBaseIVAExento="100.00"
      MontoTotalPagos="6150.00"/>
  <pago20:Pago FechaPago="2026-01-20T12:00:00" FormaDePagoP="03" MonedaP="MXN" TipoCambioP="1" Monto="6150.00">
    <pago20:DoctoRelacionado IdDocumento="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee" MonedaDR="MXN"
        EquivalenciaDR="1" NumParcialidad="1" ImpSaldoAnt="12300.00" ImpPagado="6150.00"
        ImpSaldoInsoluto="6150.00" ObjetoImpDR="02"/>
    <pago20:DoctoRelacionado IdDocumento="bbbbbbbb-bbbb-cccc-dddd-eeeeeeeeeeee" MonedaDR="MXN"
        EquivalenciaDR="1" NumParcialidad="1" ImpSaldoAnt="100.00" ImpPagado="100.00"
        ImpSaldoInsoluto="0.00" ObjetoImpDR="01"/>
    <pago20:ImpuestosP>
      <pago20:RetencionesP><pago20:RetencionP ImpuestoP="001" ImporteP="500.00"/></pago20:RetencionesP>
      <pago20:TrasladosP>
        <pago20:TrasladoP BaseP="5000.00" ImpuestoP="002" TipoFactorP="Tasa" TasaOCuotaP="0.160000" ImporteP="800.00"/>
        <pago20:TrasladoP BaseP="250.00" ImpuestoP="002" TipoFactorP="Tasa" TasaOCuotaP="0.000000" ImporteP="0.00"/>
        <pago20:TrasladoP BaseP="100.00" ImpuestoP="002" TipoFactorP="Exento"/>
      </pago20:TrasladosP>
    </pago20:ImpuestosP>
  </pago20:Pago>
</pago20:Pagos>'''


def test_rep_totales_oficiales_en_pesos():
    t = CFDIParser().parse_xml(_rep(PAGOS_20_V2)).pagos_totales

    assert t.monto_total_pagos == D("6150.00")
    assert (t.total_traslados_base_iva16, t.total_traslados_iva16) == (D("5000.00"), D("800.00"))
    assert (t.total_traslados_base_iva0, t.total_traslados_iva0, t.total_traslados_base_exento) == (D("250.00"), D("0.00"), D("100.00"))
    assert t.total_retenciones_isr == D("500.00")
    # Lo que el XML no trae queda en None, no en cero.
    assert (t.total_retenciones_iva, t.total_retenciones_ieps, t.total_traslados_base_iva8, t.total_traslados_iva8) == (None,) * 4


def test_rep_impuestos_p_por_pago():
    (pago,) = CFDIParser().parse_xml(_rep(PAGOS_20_V2)).pagos

    por_clave = {(i.ambito, i.impuesto, i.tipo_factor, i.tasa_o_cuota): (i.base, i.importe) for i in pago.impuestos_p}
    assert por_clave == {
        ("retencion", "001", "Tasa", None): (D("0.000000"), D("500.000000")),   # la retención no trae base ni tasa
        ("traslado", "002", "Tasa", D("0.160000")): (D("5000.000000"), D("800.000000")),
        ("traslado", "002", "Tasa", D("0.000000")): (D("250.000000"), D("0.000000")),
        ("traslado", "002", "Exento", None): (D("100.000000"), D("0.000000")),
    }


def test_rep_objeto_imp_dr_por_documento():
    (pago,) = CFDIParser().parse_xml(_rep(PAGOS_20_V2)).pagos
    assert [d.objeto_imp_dr for d in pago.doctos_relacionados] == ["02", "01"]


def test_rep_sin_impuestos_ni_totales_de_iva():
    p = CFDIParser().parse_xml(_rep('''<pago20:Pagos Version="2.0"><pago20:Totales MontoTotalPagos="100.00"/>
        <pago20:Pago FechaPago="2026-01-20T12:00:00" MonedaP="MXN" Monto="100.00">
        <pago20:DoctoRelacionado IdDocumento="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee" MonedaDR="MXN" EquivalenciaDR="1"
            NumParcialidad="1" ImpSaldoAnt="100.00" ImpPagado="100.00" ImpSaldoInsoluto="0.00" ObjetoImpDR="01"/>
        </pago20:Pago></pago20:Pagos>'''))

    assert p.pagos[0].impuestos_p == []
    assert p.pagos_totales.monto_total_pagos == D("100.00")
    assert p.pagos_totales.total_traslados_base_iva16 is None


def test_rep_10_no_trae_totales_ni_impuestos_p_ni_objeto_imp():
    p = CFDIParser().parse_xml(_rep(PAGOS_10))

    assert p.pagos_totales is None
    assert p.pagos[0].impuestos_p == []
    assert p.pagos[0].doctos_relacionados[0].objeto_imp_dr is None


def test_un_cfdi_que_no_es_rep_no_trae_totales_de_pagos():
    assert CFDIParser().parse_xml(_cfdi("")).pagos_totales is None


# ─── ACuentaTerceros ────────────────────────────────────────

def test_a_cuenta_de_terceros_por_concepto():
    p = CFDIParser().parse_xml(_cfdi('''<cfdi:Conceptos>
      <cfdi:Concepto ClaveProdServ="80101500" Cantidad="1" ClaveUnidad="E48" Descripcion="Cobro por cuenta" ValorUnitario="1000.00"
          Importe="1000.00" ObjetoImp="02">
        <cfdi:Impuestos><cfdi:Traslados>
          <cfdi:Traslado Base="1000.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="160.00"/>
        </cfdi:Traslados></cfdi:Impuestos>
        <cfdi:ACuentaTerceros RfcACuentaTerceros=" tte010101abc " NombreACuentaTerceros="TERCERO SA"
            RegimenFiscalACuentaTerceros="601" DomicilioFiscalACuentaTerceros="68000"/>
      </cfdi:Concepto>
      <cfdi:Concepto ClaveProdServ="80101500" Cantidad="1" ClaveUnidad="E48" Descripcion="Propio" ValorUnitario="500.00"
          Importe="500.00" ObjetoImp="01"/>
    </cfdi:Conceptos>''', subtotal="1500.00", total="1660.00"))

    propio, ajeno = p.conceptos[1], p.conceptos[0]
    assert (ajeno.rfc_a_cuenta_terceros, ajeno.nombre_a_cuenta_terceros, ajeno.regimen_a_cuenta_terceros) == (
        "TTE010101ABC", "TERCERO SA", "601")
    assert (propio.rfc_a_cuenta_terceros, propio.nombre_a_cuenta_terceros, propio.regimen_a_cuenta_terceros) == (None,) * 3
    # El nodo no cambia la lectura de impuestos del concepto.
    assert ajeno.impuestos[0].importe == D("160.00")


def test_cfdi_33_no_trae_a_cuenta_de_terceros():
    """En CFDI 3.3 el equivalente es el complemento Terceros 1.1, que no se lee: queda sin
    marca de terceros (limitación documentada, ver migración 040)."""
    p = CFDIParser().parse_xml(_cfdi('''<cfdi:Conceptos>
      <cfdi:Concepto ClaveProdServ="80101500" Cantidad="1" ClaveUnidad="E48" Descripcion="X" ValorUnitario="100.00" Importe="100.00">
        <cfdi:ComplementoConcepto><terceros:PorCuentadeTerceros xmlns:terceros="http://www.sat.gob.mx/terceros"
            version="1.1" rfc="TTE010101ABC" nombre="T"/></cfdi:ComplementoConcepto>
      </cfdi:Concepto></cfdi:Conceptos>''', version="3.3", subtotal="100.00", total="100.00"))
    assert p.conceptos[0].rfc_a_cuenta_terceros is None


def test_rep_totales_conservan_hasta_seis_decimales():
    """En Pagos20.xsd los Totales son t_Importe (hasta 6 decimales): el parser no los redondea."""
    t = CFDIParser().parse_xml(_rep('''<pago20:Pagos Version="2.0">
        <pago20:Totales TotalTrasladosBaseIVA16="1234.565432" TotalTrasladosImpuestoIVA16="197.530469" MontoTotalPagos="1432.095901"/>
        <pago20:Pago FechaPago="2026-01-20T12:00:00" MonedaP="MXN" Monto="1432.10"/></pago20:Pagos>''')).pagos_totales

    assert (t.total_traslados_base_iva16, t.total_traslados_iva16, t.monto_total_pagos) == (
        D("1234.565432"), D("197.530469"), D("1432.095901"))


def test_rfc_de_terceros_invalido_se_conserva_y_se_registra(caplog):
    with caplog.at_level("WARNING"):
        p = CFDIParser().parse_xml(_cfdi('''<cfdi:Conceptos>
          <cfdi:Concepto ClaveProdServ="80101500" Cantidad="1" ClaveUnidad="E48" Descripcion="X" ValorUnitario="100.00" Importe="100.00">
            <cfdi:ACuentaTerceros RfcACuentaTerceros="no-es-rfc" NombreACuentaTerceros="T"/>
          </cfdi:Concepto></cfdi:Conceptos>''', subtotal="100.00", total="100.00"))

    assert p.conceptos[0].rfc_a_cuenta_terceros == "NO-ES-RFC"      # el dato no se pierde
    assert "RfcACuentaTerceros con forma inválida" in caplog.text


def test_cada_pago_trae_su_orden_de_nodo_y_su_forma_de_pago():
    p = CFDIParser().parse_xml(_rep('''<pago20:Pagos Version="2.0">
        <pago20:Pago FechaPago="2026-01-20T12:00:00" FormaDePagoP="01" MonedaP="MXN" Monto="100.00"/>
        <pago20:Pago FechaPago="2026-01-20T12:00:00" FormaDePagoP="03" MonedaP="MXN" Monto="100.00"/>
        <pago20:Pago FechaPago="2026-01-21T12:00:00" MonedaP="MXN" Monto="50.00"/></pago20:Pagos>'''))

    assert [(x.nodo, x.forma_pago) for x in p.pagos] == [(1, "01"), (2, "03"), (3, None)]


def test_el_orden_de_nodo_cuenta_tambien_los_pagos_que_no_se_guardan():
    """Un pago sin fecha o con monto 0 no se guarda, pero su lugar no se recorre: el nodo
    siguiente conserva su número real del XML."""
    p = CFDIParser().parse_xml(_rep('''<pago20:Pagos Version="2.0">
        <pago20:Pago FechaPago="2026-01-20T12:00:00" MonedaP="MXN" Monto="0"/>
        <pago20:Pago FechaPago="2026-01-20T12:00:00" FormaDePagoP="03" MonedaP="MXN" Monto="100.00"/></pago20:Pagos>'''))

    assert [x.nodo for x in p.pagos] == [1, 2]


def test_rep_10_tambien_numera_sus_pagos():
    p = CFDIParser().parse_xml(_rep(PAGOS_10))
    assert [(x.nodo, x.forma_pago) for x in p.pagos] == [(1, "03")]
