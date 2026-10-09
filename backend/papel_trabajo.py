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

    # Datos de F4 (Inicio)
    fila += 1
    ingresos = db.query_one(
        """
        SELECT COALESCE(SUM(monto), 0) as total
        FROM iva
        WHERE empresa_id = %s AND periodo = %s AND lado = 'propio' AND tipo = 'trasladado'
        """,
        (empresa_id, periodo)
    )
    ws[f'A{fila}'] = 'Ingresos netos del mes'
    ws[f'B{fila}'] = ingresos['total']
    ws[f'B{fila}'].number_format = '#,##0.00'

    fila += 1
    gastos = db.query_one(
        """
        SELECT COALESCE(SUM(monto), 0) as total
        FROM iva
        WHERE empresa_id = %s AND periodo = %s AND lado = 'propio' AND tipo = 'acreditable'
        """,
        (empresa_id, periodo)
    )
    ws[f'A{fila}'] = 'Gastos y compras netos del mes'
    ws[f'B{fila}'] = gastos['total']
    ws[f'B{fila}'].number_format = '#,##0.00'

    fila += 2
    ws[f'A{fila}'] = 'IVA trasladado cobrado'
    ws[f'B{fila}'] = Decimal('0.00')  # Placeholder; en producción vendría de F5
    ws[f'B{fila}'].number_format = '#,##0.00'

    fila += 1
    ws[f'A{fila}'] = 'IVA acreditable pagado'
    ws[f'B{fila}'] = Decimal('0.00')
    ws[f'B{fila}'].number_format = '#,##0.00'

    fila += 1
    ws[f'A{fila}'] = 'IVA a cargo / a favor'
    ws[f'B{fila}'] = Decimal('0.00')
    ws[f'B{fila}'].number_format = '#,##0.00'

    fila += 2
    ws[f'A{fila}'] = 'Ingresos acumulables (ISR)'
    ws[f'B{fila}'] = Decimal('0.00')
    ws[f'B{fila}'].number_format = '#,##0.00'

    fila += 1
    ws[f'A{fila}'] = 'Deducciones autorizadas (ISR)'
    ws[f'B{fila}'] = Decimal('0.00')
    ws[f'B{fila}'].number_format = '#,##0.00'


def _crear_hoja_iva(wb, empresa_id: UUID, periodo: str):
    """Hoja con detalles de IVA (bases por tasa, desglose de CFDI)."""
    ws = wb.create_sheet('IVA')
    ws.column_dimensions['A'].width = 12
    ws.column_dimensions['B'].width = 18
    ws.column_dimensions['C'].width = 18

    fila = 1
    ws[f'A{fila}'] = 'IVA BASE FLUJO'
    ws[f'A{fila}'].font = Font(bold=True, size=12)

    fila += 2
    _agregar_encabezado(ws, fila, ['Tasa', 'Base trasladado', 'Base acreditable'], ESTILOS['encabezado_iva'])

    # Datos por tasa
    tasas = ['16%', '8%', '0%', 'Exento']
    fila += 1
    for tasa in tasas:
        ws[f'A{fila}'] = tasa
        ws[f'B{fila}'] = Decimal('0.00')
        ws[f'C{fila}'] = Decimal('0.00')
        ws[f'B{fila}'].number_format = '#,##0.00'
        ws[f'C{fila}'].number_format = '#,##0.00'
        fila += 1

    # Listado de CFDI
    fila += 2
    _agregar_encabezado(
        ws, fila,
        ['UUID', 'Fecha', 'Contraparte', 'Base', 'IVA', 'Retención', 'Ajuste'],
        ESTILOS['encabezado_iva']
    )


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

    # Secciones
    ingresos_label = ['Ingresos cobrados (contado)', 'Ingresos cobrados (REP)']
    deducciones_label = ['Compras contado', 'Pagos con REP', 'Nómina gravada', 'Nómina exenta (%)']

    fila += 1
    for label in ingresos_label:
        ws[f'A{fila}'] = label
        ws[f'B{fila}'] = Decimal('0.00')
        ws[f'B{fila}'].number_format = '#,##0.00'
        fila += 1

    fila += 1
    for label in deducciones_label:
        ws[f'A{fila}'] = label
        ws[f'B{fila}'] = Decimal('0.00')
        ws[f'B{fila}'].number_format = '#,##0.00'
        fila += 1

    fila += 1
    ws[f'A{fila}'] = 'ISR base calculado'
    ws[f'B{fila}'].font = Font(bold=True)
    ws[f'B{fila}'] = Decimal('0.00')
    ws[f'B{fila}'].number_format = '#,##0.00'


def _crear_hoja_diot(wb, empresa_id: UUID, periodo: str):
    """Hoja con DIOT por tercero, tasa e IVA."""
    ws = wb.create_sheet('DIOT')
    ws.column_dimensions['A'].width = 12
    ws.column_dimensions['B'].width = 30
    ws.column_dimensions['C'].width = 12

    fila = 1
    ws[f'A{fila}'] = 'DIOT POR FLUJO'
    ws[f'A{fila}'].font = Font(bold=True, size=12)

    fila += 2
    _agregar_encabezado(
        ws, fila,
        ['RFC', 'Nombre', 'Tipo Tercero', 'Base 16%', 'IVA Acred.', 'IVA No Acred.', 'Retenciones'],
        ESTILOS['encabezado_diot']
    )


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

    fila += 2
    ws[f'A{fila}'] = 'Total bancario'
    ws[f'C{fila}'] = Decimal('0.00')
    ws[f'C{fila}'].number_format = '#,##0.00'

    fila += 1
    ws[f'A{fila}'] = 'Total conciliado'
    ws[f'C{fila}'] = Decimal('0.00')
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

    fila += 1
    ws[f'A{fila}'] = 'Ejemplo'
    ws[f'B{fila}'] = 'CFDI cancelado después del cierre'
    ws[f'C{fila}'] = 'Sí'
