"""
M2: Generador del papel de trabajo mensual (XLSX).
Consolida IVA, ISR, DIOT, conciliación y riesgos en un Excel descargable.
"""

from io import BytesIO
from decimal import Decimal
from datetime import datetime
from uuid import UUID

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from . import db


# Colores y estilos
ESTILOS = {
    'encabezado_iva': PatternFill(start_color='D9E8F5', end_color='D9E8F5', fill_type='solid'),
    'encabezado_isr': PatternFill(start_color='E8F5E9', end_color='E8F5E9', fill_type='solid'),
    'encabezado_diot': PatternFill(start_color='FFF3E0', end_color='FFF3E0', fill_type='solid'),
    'encabezado_riesgos': PatternFill(start_color='FFEBEE', end_color='FFEBEE', fill_type='solid'),
    'texto_encabezado': Font(bold=True, color='1F497D', size=11),
    'texto_normal': Font(size=10),
    'borde': Border(
        left=Side(style='thin', color='000000'),
        right=Side(style='thin', color='000000'),
        top=Side(style='thin', color='000000'),
        bottom=Side(style='thin', color='000000')
    ),
    'alineacion_centro': Alignment(horizontal='center', vertical='center', wrap_text=True),
    'alineacion_derecha': Alignment(horizontal='right', vertical='center'),
}


def _formato_moneda(ws, columna, fila_inicio, fila_fin):
    """Aplica formato de moneda a un rango de celdas."""
    for fila in range(fila_inicio, fila_fin + 1):
        celda = ws[f'{columna}{fila}']
        celda.number_format = '#,##0.00'


def _agregar_encabezado(ws, fila, encabezados, estilo_fill):
    """Agrega una fila de encabezado con estilo."""
    for col, texto in enumerate(encabezados, 1):
        celda = ws.cell(row=fila, column=col, value=texto)
        celda.fill = estilo_fill
        celda.font = ESTILOS['texto_encabezado']
        celda.border = ESTILOS['borde']
        celda.alignment = ESTILOS['alineacion_centro']


def generar_papel_trabajo(empresa_id: UUID, periodo: str) -> BytesIO:
    """
    Genera el XLSX con todas las hojas: resumen, IVA, ISR, DIOT, conciliación, riesgos.

    Args:
        empresa_id: UUID de la empresa
        periodo: Formato AAAA-MM

    Returns:
        BytesIO con el XLSX listo para descargar
    """
    wb = openpyxl.Workbook()
    wb.remove(wb.active)  # Elimina la hoja vacía por defecto

    # Obtener datos de la empresa
    cur = db.get_conn().cursor()
    empresa = db.query_one("SELECT * FROM empresas WHERE id = %s", (empresa_id,))
    usuario_actual = db.query_one("SELECT email FROM usuarios LIMIT 1")  # Placeholder

    # Crear hojas
    _crear_hoja_portada(wb, empresa, periodo)
    _crear_hoja_resumen(wb, empresa_id, periodo)
    _crear_hoja_iva(wb, empresa_id, periodo)
    _crear_hoja_isr(wb, empresa_id, periodo)
    _crear_hoja_diot(wb, empresa_id, periodo)
    _crear_hoja_conciliacion(wb, empresa_id, periodo)
    _crear_hoja_riesgos(wb, empresa_id, periodo)

    # Guardar en BytesIO
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def _crear_hoja_portada(wb, empresa, periodo):
    """Portada con datos de la empresa y período."""
    ws = wb.create_sheet('Portada', 0)
    ws.column_dimensions['A'].width = 50

    fila = 2
    ws[f'A{fila}'] = 'PAPEL DE TRABAJO — CIERRE MENSUAL'
    ws[f'A{fila}'].font = Font(bold=True, size=16)

    fila += 2
    ws[f'A{fila}'] = f"Empresa: {empresa['razon_social']}"
    ws[f'A{fila}'].font = Font(size=11)

    fila += 1
    ws[f'A{fila}'] = f"RFC: {empresa['rfc']}"
    ws[f'A{fila}'].font = Font(size=11)

    fila += 1
    ws[f'A{fila}'] = f"Régimen: {empresa.get('regimen_fiscal', 'No especificado')}"
    ws[f'A{fila}'].font = Font(size=11)

    fila += 2
    ws[f'A{fila}'] = f"Período: {periodo}"
    ws[f'A{fila}'].font = Font(size=12, bold=True)

    fila += 1
    ws[f'A{fila}'] = f"Fecha de descarga: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    ws[f'A{fila}'].font = Font(size=10)


def _crear_hoja_resumen(wb, empresa_id: UUID, periodo: str):
    """Hoja de resumen ejecutivo con cifras principales."""
    ws = wb.create_sheet('Resumen')
    ws.column_dimensions['A'].width = 40
    ws.column_dimensions['B'].width = 18

    fila = 1
    ws[f'A{fila}'] = 'RESUMEN EJECUTIVO'
    ws[f'A{fila}'].font = Font(bold=True, size=12)

    fila += 2
    _agregar_encabezado(ws, fila, ['Concepto', 'Importe'], ESTILOS['encabezado_iva'])

    empresa = db.query_one("SELECT rfc FROM empresas WHERE id = %s", (empresa_id,))
    rfc = empresa['rfc'] if empresa else ''

    fila += 1
    ingresos = db.query_one(
        """
        SELECT COALESCE(SUM(c.total), 0)::numeric as total
        FROM cfdi c
        WHERE c.empresa_id = %s AND c.rfc_emisor = %s AND c.tipo_comprobante = 'I'
          AND c.estado = 'vigente'
          AND DATE_TRUNC('month', c.fecha_emision)::date = %s::date
        """,
        (empresa_id, rfc, f'{periodo}-01')
    )
    ws[f'A{fila}'] = 'Ingresos netos del mes'
    ws[f'B{fila}'] = Decimal(str(ingresos['total'] or 0))
    ws[f'B{fila}'].number_format = '#,##0.00'

    fila += 1
    gastos = db.query_one(
        """
        SELECT COALESCE(SUM(c.total), 0)::numeric as total
        FROM cfdi c
        WHERE c.empresa_id = %s AND c.rfc_receptor = %s AND c.tipo_comprobante IN ('E', 'T')
          AND c.estado = 'vigente'
          AND DATE_TRUNC('month', c.fecha_emision)::date = %s::date
        """,
        (empresa_id, rfc, f'{periodo}-01')
    )
    ws[f'A{fila}'] = 'Gastos y compras netos del mes'
    ws[f'B{fila}'] = Decimal(str(gastos['total'] or 0))
    ws[f'B{fila}'].number_format = '#,##0.00'

    fila += 2
    iva_trasladado = db.query_one(
        """
        SELECT COALESCE(SUM(ci.importe), 0)::numeric as total
        FROM cfdi_impuestos ci
        JOIN cfdi c ON c.id = ci.cfdi_id
        WHERE c.empresa_id = %s AND c.rfc_emisor = %s
          AND ci.impuesto = '002' AND ci.tipo_factor = 'Traslado'
          AND DATE_TRUNC('month', c.fecha_emision)::date = %s::date
        """,
        (empresa_id, rfc, f'{periodo}-01')
    )
    ws[f'A{fila}'] = 'IVA trasladado cobrado'
    ws[f'B{fila}'] = Decimal(str(iva_trasladado['total'] or 0))
    ws[f'B{fila}'].number_format = '#,##0.00'

    fila += 1
    iva_acreditable = db.query_one(
        """
        SELECT COALESCE(SUM(ci.importe), 0)::numeric as total
        FROM cfdi_impuestos ci
        JOIN cfdi c ON c.id = ci.cfdi_id
        WHERE c.empresa_id = %s AND c.rfc_receptor = %s
          AND ci.impuesto = '002' AND ci.tipo_factor = 'Traslado'
          AND DATE_TRUNC('month', c.fecha_emision)::date = %s::date
        """,
        (empresa_id, rfc, f'{periodo}-01')
    )
    ws[f'A{fila}'] = 'IVA acreditable pagado'
    ws[f'B{fila}'] = Decimal(str(iva_acreditable['total'] or 0))
    ws[f'B{fila}'].number_format = '#,##0.00'

    fila += 1
    iva_cargo = (Decimal(str(iva_trasladado['total'] or 0)) -
                 Decimal(str(iva_acreditable['total'] or 0)))
    ws[f'A{fila}'] = 'IVA a cargo / a favor'
    ws[f'B{fila}'] = iva_cargo
    ws[f'B{fila}'].number_format = '#,##0.00'

    fila += 2
    ingresos_isr = db.query_one(
        """
        SELECT COALESCE(SUM(c.total), 0)::numeric as total
        FROM cfdi c
        WHERE c.empresa_id = %s AND c.rfc_emisor = %s AND c.tipo_comprobante = 'I'
          AND c.estado = 'vigente'
          AND DATE_TRUNC('month', c.fecha_emision)::date = %s::date
        """,
        (empresa_id, rfc, f'{periodo}-01')
    )
    ws[f'A{fila}'] = 'Ingresos acumulables (ISR)'
    ws[f'B{fila}'] = Decimal(str(ingresos_isr['total'] or 0))
    ws[f'B{fila}'].number_format = '#,##0.00'

    fila += 1
    deducciones_isr = db.query_one(
        """
        SELECT COALESCE(SUM(c.total), 0)::numeric as total
        FROM cfdi c
        WHERE c.empresa_id = %s AND c.rfc_receptor = %s AND c.tipo_comprobante IN ('E', 'T')
          AND c.estado = 'vigente'
          AND DATE_TRUNC('month', c.fecha_emision)::date = %s::date
        """,
        (empresa_id, rfc, f'{periodo}-01')
    )
    ws[f'A{fila}'] = 'Deducciones autorizadas (ISR)'
    ws[f'B{fila}'] = Decimal(str(deducciones_isr['total'] or 0))
    ws[f'B{fila}'].number_format = '#,##0.00'


def _crear_hoja_iva(wb, empresa_id: UUID, periodo: str):
    """Hoja con detalles de IVA (bases por tasa, desglose de CFDI)."""
    ws = wb.create_sheet('IVA')
    ws.column_dimensions['A'].width = 12
    ws.column_dimensions['B'].width = 18
    ws.column_dimensions['C'].width = 18
    ws.column_dimensions['D'].width = 15
    ws.column_dimensions['E'].width = 15
    ws.column_dimensions['F'].width = 15
    ws.column_dimensions['G'].width = 15

    fila = 1
    ws[f'A{fila}'] = 'IVA BASE FLUJO'
    ws[f'A{fila}'].font = Font(bold=True, size=12)

    fila += 2
    _agregar_encabezado(ws, fila, ['Tasa', 'Base trasladado', 'Base acreditable'], ESTILOS['encabezado_iva'])

    empresa = db.query_one("SELECT rfc FROM empresas WHERE id = %s", (empresa_id,))
    rfc = empresa['rfc'] if empresa else ''

    tasas_map = {'0.16': '16%', '0.08': '8%', '0': '0%'}
    bases_por_tasa = db.query_all(
        """
        SELECT
            CAST(COALESCE(ci.tasa_o_cuota, 0) AS TEXT) as tasa,
            SUM(CASE WHEN c.rfc_emisor = %s THEN ci.base ELSE 0 END)::numeric as base_trasladado,
            SUM(CASE WHEN c.rfc_receptor = %s THEN ci.base ELSE 0 END)::numeric as base_acreditable
        FROM cfdi_impuestos ci
        JOIN cfdi c ON c.id = ci.cfdi_id
        WHERE c.empresa_id = %s AND ci.impuesto = '002' AND ci.tipo_factor = 'Traslado'
          AND DATE_TRUNC('month', c.fecha_emision)::date = %s::date
        GROUP BY ci.tasa_o_cuota
        ORDER BY ci.tasa_o_cuota DESC
        """,
        (rfc, rfc, empresa_id, f'{periodo}-01')
    )

    fila += 1
    for fila_base in bases_por_tasa:
        tasa = tasas_map.get(str(fila_base['tasa']), f"{fila_base['tasa']}%")
        ws[f'A{fila}'] = tasa
        ws[f'B{fila}'] = Decimal(str(fila_base['base_trasladado'] or 0))
        ws[f'C{fila}'] = Decimal(str(fila_base['base_acreditable'] or 0))
        ws[f'B{fila}'].number_format = '#,##0.00'
        ws[f'C{fila}'].number_format = '#,##0.00'
        fila += 1

    fila += 2
    _agregar_encabezado(
        ws, fila,
        ['UUID', 'Fecha', 'Contraparte', 'Base', 'IVA', 'Retención', 'Ajuste'],
        ESTILOS['encabezado_iva']
    )

    fila += 1
    cfdis = db.query_all(
        """
        SELECT c.uuid, c.fecha_emision, c.nombre_emisor, c.nombre_receptor,
               COALESCE(SUM(CASE WHEN ci.tipo_factor = 'Traslado' THEN ci.base ELSE 0 END), 0)::numeric as base,
               COALESCE(SUM(CASE WHEN ci.tipo_factor = 'Traslado' THEN ci.importe ELSE 0 END), 0)::numeric as iva,
               COALESCE(SUM(CASE WHEN ci.tipo_factor = 'Retencion' THEN ci.importe ELSE 0 END), 0)::numeric as retencion,
               CASE WHEN ia.accion IS NOT NULL THEN ia.accion ELSE 'Normal' END as ajuste
        FROM cfdi c
        LEFT JOIN cfdi_impuestos ci ON ci.cfdi_id = c.id AND ci.impuesto = '002'
        LEFT JOIN iva_ajustes ia ON ia.empresa_id = c.empresa_id AND UPPER(ia.cfdi_uuid) = UPPER(c.uuid)
        WHERE c.empresa_id = %s AND c.estado = 'vigente'
          AND DATE_TRUNC('month', c.fecha_emision)::date = %s::date
        GROUP BY c.id, c.uuid, c.fecha_emision, c.nombre_emisor, c.nombre_receptor, ia.accion
        LIMIT 100
        """,
        (empresa_id, f'{periodo}-01')
    )

    for cfdi in cfdis:
        ws[f'A{fila}'] = cfdi['uuid'][:8] if cfdi['uuid'] else ''
        ws[f'B{fila}'] = cfdi['fecha_emision'].strftime('%d/%m/%Y') if cfdi['fecha_emision'] else ''
        ws[f'C{fila}'] = cfdi['nombre_emisor'] or cfdi['nombre_receptor'] or ''
        ws[f'D{fila}'] = Decimal(str(cfdi['base'] or 0))
        ws[f'E{fila}'] = Decimal(str(cfdi['iva'] or 0))
        ws[f'F{fila}'] = Decimal(str(cfdi['retencion'] or 0))
        ws[f'G{fila}'] = cfdi['ajuste']
        for col in ['D', 'E', 'F']:
            ws[f'{col}{fila}'].number_format = '#,##0.00'
        fila += 1


def _crear_hoja_isr(wb, empresa_id: UUID, periodo: str):
    """Hoja con detalles de ISR (ingresos, deducciones, bases)."""
    ws = wb.create_sheet('ISR')
    ws.column_dimensions['A'].width = 40
    ws.column_dimensions['B'].width = 18

    fila = 1
    ws[f'A{fila}'] = 'ISR BASE FLUJO'
    ws[f'A{fila}'].font = Font(bold=True, size=12)

    fila += 2
    _agregar_encabezado(ws, fila, ['Concepto', 'Importe'], ESTILOS['encabezado_isr'])

    empresa = db.query_one("SELECT rfc FROM empresas WHERE id = %s", (empresa_id,))
    rfc = empresa['rfc'] if empresa else ''

    fila += 1
    ingresos_contado = db.query_one(
        """
        SELECT COALESCE(SUM(c.total), 0)::numeric as total
        FROM cfdi c
        WHERE c.empresa_id = %s AND c.rfc_emisor = %s AND c.tipo_comprobante = 'I'
          AND c.metodo_pago = 'PUE' AND c.estado = 'vigente'
          AND DATE_TRUNC('month', c.fecha_emision)::date = %s::date
        """,
        (empresa_id, rfc, f'{periodo}-01')
    )
    ws[f'A{fila}'] = 'Ingresos cobrados (contado)'
    ws[f'B{fila}'] = Decimal(str(ingresos_contado['total'] or 0))
    ws[f'B{fila}'].number_format = '#,##0.00'

    fila += 1
    ingresos_rep = db.query_one(
        """
        SELECT COALESCE(SUM(c.total), 0)::numeric as total
        FROM cfdi c
        WHERE c.empresa_id = %s AND c.rfc_emisor = %s AND c.tipo_comprobante = 'I'
          AND c.metodo_pago = 'PPD' AND c.estado = 'vigente'
          AND DATE_TRUNC('month', c.fecha_emision)::date = %s::date
        """,
        (empresa_id, rfc, f'{periodo}-01')
    )
    ws[f'A{fila}'] = 'Ingresos cobrados (REP)'
    ws[f'B{fila}'] = Decimal(str(ingresos_rep['total'] or 0))
    ws[f'B{fila}'].number_format = '#,##0.00'

    fila += 1
    compras_contado = db.query_one(
        """
        SELECT COALESCE(SUM(c.total), 0)::numeric as total
        FROM cfdi c
        WHERE c.empresa_id = %s AND c.rfc_receptor = %s AND c.tipo_comprobante = 'E'
          AND c.metodo_pago = 'PUE' AND c.estado = 'vigente'
          AND DATE_TRUNC('month', c.fecha_emision)::date = %s::date
        """,
        (empresa_id, rfc, f'{periodo}-01')
    )
    ws[f'A{fila}'] = 'Compras contado'
    ws[f'B{fila}'] = Decimal(str(compras_contado['total'] or 0))
    ws[f'B{fila}'].number_format = '#,##0.00'

    fila += 1
    ws[f'A{fila}'] = 'Pagos con REP'
    ws[f'B{fila}'] = Decimal('0.00')
    ws[f'B{fila}'].number_format = '#,##0.00'

    fila += 1
    ws[f'A{fila}'] = 'Nómina gravada'
    ws[f'B{fila}'] = Decimal('0.00')
    ws[f'B{fila}'].number_format = '#,##0.00'

    fila += 1
    ws[f'A{fila}'] = 'Nómina exenta (%)'
    ws[f'B{fila}'] = Decimal('0.00')
    ws[f'B{fila}'].number_format = '0.00%'

    fila += 1
    base_isr = (Decimal(str(ingresos_contado['total'] or 0)) +
                Decimal(str(ingresos_rep['total'] or 0)) -
                Decimal(str(compras_contado['total'] or 0)))
    ws[f'A{fila}'] = 'ISR base calculado'
    ws[f'B{fila}'].font = Font(bold=True)
    ws[f'B{fila}'] = base_isr
    ws[f'B{fila}'].number_format = '#,##0.00'


def _crear_hoja_diot(wb, empresa_id: UUID, periodo: str):
    """Hoja con DIOT por tercero, tasa e IVA."""
    ws = wb.create_sheet('DIOT')
    ws.column_dimensions['A'].width = 12
    ws.column_dimensions['B'].width = 30
    ws.column_dimensions['C'].width = 12
    ws.column_dimensions['D'].width = 12
    ws.column_dimensions['E'].width = 12
    ws.column_dimensions['F'].width = 12
    ws.column_dimensions['G'].width = 12

    fila = 1
    ws[f'A{fila}'] = 'DIOT POR FLUJO'
    ws[f'A{fila}'].font = Font(bold=True, size=12)

    fila += 2
    _agregar_encabezado(
        ws, fila,
        ['RFC', 'Nombre', 'Tipo Tercero', 'Base 16%', 'IVA Acred.', 'IVA No Acred.', 'Retenciones'],
        ESTILOS['encabezado_diot']
    )

    fila += 1
    proveedores = db.query_all(
        """
        SELECT DISTINCT c.rfc_emisor as rfc, c.nombre_emisor as nombre,
               SUM(CASE WHEN ci.tasa_o_cuota = 0.16 THEN ci.base ELSE 0 END)::numeric as base_16,
               SUM(CASE WHEN ci.tasa_o_cuota = 0.16 THEN ci.importe ELSE 0 END)::numeric as iva_acred,
               SUM(CASE WHEN ci.tipo_factor = 'Retencion' THEN ci.importe ELSE 0 END)::numeric as retenciones
        FROM cfdi c
        LEFT JOIN cfdi_impuestos ci ON ci.cfdi_id = c.id AND ci.impuesto = '002'
        WHERE c.empresa_id = %s AND c.rfc_receptor = %s AND c.estado = 'vigente'
          AND DATE_TRUNC('month', c.fecha_emision)::date = %s::date
        GROUP BY c.rfc_emisor, c.nombre_emisor
        LIMIT 50
        """,
        (empresa_id, db.query_one("SELECT rfc FROM empresas WHERE id = %s", (empresa_id,))['rfc'],
         f'{periodo}-01')
    )

    for proveedor in proveedores:
        ws[f'A{fila}'] = proveedor['rfc']
        ws[f'B{fila}'] = proveedor['nombre'] or ''
        ws[f'C{fila}'] = 'Persona Física' if proveedor['rfc'][0] != 'X' else 'Persona Moral'
        ws[f'D{fila}'] = Decimal(str(proveedor['base_16'] or 0))
        ws[f'E{fila}'] = Decimal(str(proveedor['iva_acred'] or 0))
        ws[f'F{fila}'] = Decimal('0.00')
        ws[f'G{fila}'] = Decimal(str(proveedor['retenciones'] or 0))
        for col in ['D', 'E', 'F', 'G']:
            ws[f'{col}{fila}'].number_format = '#,##0.00'
        fila += 1


def _crear_hoja_conciliacion(wb, empresa_id: UUID, periodo: str):
    """Hoja con conciliación bancaria."""
    ws = wb.create_sheet('Conciliación')
    ws.column_dimensions['A'].width = 12
    ws.column_dimensions['B'].width = 40
    ws.column_dimensions['C'].width = 18

    fila = 1
    ws[f'A{fila}'] = 'CONCILIACIÓN BANCARIA'
    ws[f'A{fila}'].font = Font(bold=True, size=12)

    fila += 2
    _agregar_encabezado(
        ws, fila,
        ['Fecha', 'Descripción', 'Monto'],
        PatternFill(start_color='E8E8E8', end_color='E8E8E8', fill_type='solid')
    )

    fila += 1
    movimientos = db.query_all(
        """
        SELECT m.fecha, m.descripcion, m.monto
        FROM movimientos m
        WHERE m.empresa_id = %s
          AND DATE_TRUNC('month', m.fecha)::date = %s::date
        ORDER BY m.fecha
        LIMIT 100
        """,
        (empresa_id, f'{periodo}-01')
    )

    total_movimientos = Decimal('0.00')
    for mov in movimientos:
        ws[f'A{fila}'] = mov['fecha'].strftime('%d/%m/%Y') if mov['fecha'] else ''
        ws[f'B{fila}'] = mov['descripcion'] or ''
        ws[f'C{fila}'] = Decimal(str(mov['monto'] or 0))
        ws[f'C{fila}'].number_format = '#,##0.00'
        total_movimientos += Decimal(str(mov['monto'] or 0))
        fila += 1

    fila += 1
    ws[f'A{fila}'] = 'Total bancario'
    ws[f'C{fila}'] = total_movimientos
    ws[f'C{fila}'].number_format = '#,##0.00'

    total_cfdis = db.query_one(
        """
        SELECT COALESCE(SUM(c.total), 0)::numeric as total
        FROM cfdi c
        WHERE c.empresa_id = %s AND c.estado = 'vigente'
          AND DATE_TRUNC('month', c.fecha_emision)::date = %s::date
        """,
        (empresa_id, f'{periodo}-01')
    )

    fila += 1
    ws[f'A{fila}'] = 'Total conciliado'
    ws[f'C{fila}'] = Decimal(str(total_cfdis['total'] or 0))
    ws[f'C{fila}'].number_format = '#,##0.00'


def _crear_hoja_riesgos(wb, empresa_id: UUID, periodo: str):
    """Hoja con riesgos y validaciones detectadas."""
    ws = wb.create_sheet('Riesgos')
    ws.column_dimensions['A'].width = 20
    ws.column_dimensions['B'].width = 50
    ws.column_dimensions['C'].width = 12

    fila = 1
    ws[f'A{fila}'] = 'RIESGOS Y VALIDACIONES'
    ws[f'A{fila}'].font = Font(bold=True, size=12)

    fila += 2
    _agregar_encabezado(
        ws, fila,
        ['Tipo', 'Descripción', 'Bloquea'],
        ESTILOS['encabezado_riesgos']
    )

    riesgos = []

    # V1: Ingresos > 0
    ingresos = db.query_one(
        """
        SELECT COALESCE(SUM(c.total), 0)::numeric as total
        FROM cfdi c
        WHERE c.empresa_id = %s AND c.rfc_emisor = (SELECT rfc FROM empresas WHERE id = %s)
          AND c.tipo_comprobante = 'I' AND c.estado = 'vigente'
          AND DATE_TRUNC('month', c.fecha_emision)::date = %s::date
        """,
        (empresa_id, empresa_id, f'{periodo}-01')
    )
    if (ingresos['total'] or 0) == 0:
        riesgos.append(('Sin ingresos', 'El período no tiene CFDI de ingreso', 'Sí'))

    # V2: Sin CFDI cancelados posteriores
    cancelados = db.query_one(
        """
        SELECT COUNT(*) as cantidad
        FROM cfdi c
        WHERE c.empresa_id = %s AND c.estado = 'cancelado'
          AND c.fecha_cancelacion > %s::date + INTERVAL '1 month'
          AND DATE_TRUNC('month', c.fecha_emision)::date = %s::date
        """,
        (empresa_id, f'{periodo}-01', f'{periodo}-01')
    )
    if (cancelados['cantidad'] or 0) > 0:
        riesgos.append(('CFDI cancelado', f"{cancelados['cantidad']} CFDI cancelado(s) después de la fecha de cierre", 'Sí'))

    # V3: Scoring bajo
    scoring_bajo = db.query_one(
        """
        SELECT COUNT(*) as cantidad
        FROM cfdi c
        LEFT JOIN scoring s ON s.cfdi_id = c.id
        WHERE c.empresa_id = %s AND c.estado = 'vigente'
          AND (s.score IS NULL OR s.score < 30)
          AND DATE_TRUNC('month', c.fecha_emision)::date = %s::date
        """,
        (empresa_id, f'{periodo}-01')
    )
    if (scoring_bajo['cantidad'] or 0) > 0:
        riesgos.append(('Score bajo', f"{scoring_bajo['cantidad']} CFDI con score <= 30", 'No'))

    fila += 1
    for tipo, descripcion, bloquea in riesgos:
        ws[f'A{fila}'] = tipo
        ws[f'B{fila}'] = descripcion
        ws[f'C{fila}'] = bloquea
        fila += 1

    if not riesgos:
        ws[f'A{fila}'] = 'Sin riesgos'
        ws[f'B{fila}'] = 'El período está validado sin problemas'
        ws[f'C{fila}'] = 'No'
