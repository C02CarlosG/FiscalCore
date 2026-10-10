"""
M2: Lógica de cierre de períodos contables.
Validaciones bloqueantes y reaperturas auditadas.
"""
from decimal import Decimal
from uuid import UUID

from . import db
from .auditoria import registrar_evento


class PeriodoNoPuedeCerrar(Exception):
    """Levantada cuando las validaciones bloqueantes no pasaron."""
    pass


def validaciones_bloqueantes(empresa_id: UUID, periodo: str) -> list[dict]:
    """
    Ejecuta todas las validaciones bloqueantes del cierre.
    Devuelve lista de dicts con {nombre, pasó, bloquea, mensaje}.
    """
    empresa = db.query_one("SELECT rfc FROM empresas WHERE id = %s", (empresa_id,))
    rfc = empresa['rfc'] if empresa else ''

    validaciones = []

    # V1: Al menos 1 CFDI de ingreso
    ingresos = db.query_one(
        """
        SELECT COUNT(*) as cantidad
        FROM cfdi c
        WHERE c.empresa_id = %s AND c.rfc_emisor = %s AND c.tipo_comprobante = 'I'
          AND c.estado = 'vigente'
          AND DATE_TRUNC('month', c.fecha_emision)::date = %s::date
        """,
        (empresa_id, rfc, f'{periodo}-01')
    )
    pasó = (ingresos.get('cantidad') or 0) > 0
    validaciones.append({
        'nombre': 'Al menos 1 CFDI de ingreso',
        'pasó': pasó,
        'bloquea': True,
        'mensaje': 'El período debe tener al menos 1 CFDI de ingreso del propio mes'
    })

    # V2: Ingresos > 0
    total_ingresos = db.query_one(
        """
        SELECT COALESCE(SUM(c.total), 0)::numeric as total
        FROM cfdi c
        WHERE c.empresa_id = %s AND c.rfc_emisor = %s AND c.tipo_comprobante = 'I'
          AND c.estado = 'vigente'
          AND DATE_TRUNC('month', c.fecha_emision)::date = %s::date
        """,
        (empresa_id, rfc, f'{periodo}-01')
    )
    pasó = Decimal(str(total_ingresos.get('total') or 0)) > 0
    validaciones.append({
        'nombre': 'Ingresos superiores a $0',
        'pasó': pasó,
        'bloquea': True,
        'mensaje': 'Los ingresos del período deben ser mayores a $0.00'
    })

    # V3: Sin CFDI cancelados posteriores al inicio del período
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
    pasó = (cancelados.get('cantidad') or 0) == 0
    validaciones.append({
        'nombre': 'Sin CFDI cancelados después de la fecha de cierre',
        'pasó': pasó,
        'bloquea': True,
        'mensaje': 'No se pueden cerrar períodos con CFDI cancelados después de la fecha de cierre'
    })

    return validaciones


def validaciones_recomendadas(empresa_id: UUID, periodo: str) -> list[dict]:
    """
    Ejecuta validaciones recomendadas (no bloqueantes).
    Devuelve lista de dicts con {nombre, pasó, bloquea, mensaje}.
    """
    empresa = db.query_one("SELECT rfc FROM empresas WHERE id = %s", (empresa_id,))
    rfc = empresa['rfc'] if empresa else ''

    validaciones = []

    # R1: Bancarización >= 90%
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
    total_ingresos = Decimal(str(ingresos.get('total') or 0))

    if total_ingresos > 0:
        ingresos_conciliados = db.query_one(
            """
            SELECT COALESCE(SUM(m.monto), 0)::numeric as total
            FROM movimientos m
            JOIN cfdi_conciliaciones cc ON cc.movimiento_id = m.id
            WHERE m.empresa_id = %s
              AND DATE_TRUNC('month', m.fecha)::date = %s::date
            """,
            (empresa_id, f'{periodo}-01')
        )
        total_conciliados = Decimal(str(ingresos_conciliados.get('total') or 0))
        porcentaje = (total_conciliados / total_ingresos * 100) if total_ingresos > 0 else 0
        pasó = porcentaje >= 90
    else:
        pasó = True
        porcentaje = 0

    validaciones.append({
        'nombre': 'Bancarización >= 90%',
        'pasó': pasó,
        'bloquea': False,
        'mensaje': f'Actualmente {porcentaje:.0f}% de los ingresos están bancarizados'
    })

    # R2: Sin scoring bajo (<= 30)
    scoring_bajo = db.query_one(
        """
        SELECT COUNT(*) as cantidad
        FROM cfdi c
        LEFT JOIN scoring s ON s.cfdi_id = c.id
        WHERE c.empresa_id = %s AND c.estado = 'vigente'
          AND (s.score IS NULL OR s.score <= 30)
          AND DATE_TRUNC('month', c.fecha_emision)::date = %s::date
        """,
        (empresa_id, f'{periodo}-01')
    )
    pasó = (scoring_bajo.get('cantidad') or 0) == 0
    validaciones.append({
        'nombre': 'Sin CFDI con scoring bajo',
        'pasó': pasó,
        'bloquea': False,
        'mensaje': f"{scoring_bajo.get('cantidad') or 0} CFDI(s) con score <= 30"
    })

    return validaciones


def puede_cerrar(empresa_id: UUID, periodo: str) -> bool:
    """True si todas las validaciones bloqueantes pasaron."""
    validaciones = validaciones_bloqueantes(empresa_id, periodo)
    return all(v['pasó'] for v in validaciones if v['bloquea'])


def cerrar_periodo(empresa_id: UUID, periodo: str, usuario_id: UUID) -> None:
    """
    Intenta cerrar el período. Levanta excepción si no puede.
    Registra en auditoría.
    """
    if not puede_cerrar(empresa_id, periodo):
        bloqueantes = validaciones_bloqueantes(empresa_id, periodo)
        sin_pasar = [v for v in bloqueantes if v['bloquea'] and not v['pasó']]
        mensaje = ', '.join(v['nombre'] for v in sin_pasar)
        raise PeriodoNoPuedeCerrar(f"Validaciones bloqueantes sin pasar: {mensaje}")

    validaciones_json = {
        'bloqueantes': validaciones_bloqueantes(empresa_id, periodo),
        'recomendadas': validaciones_recomendadas(empresa_id, periodo)
    }

    db.execute(
        """
        INSERT INTO periodos_cerrados (empresa_id, periodo, cerrado_por, validaciones_pasadas)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (empresa_id, periodo) DO NOTHING
        """,
        (empresa_id, periodo, usuario_id, str(validaciones_json))
    )

    registrar_evento(
        tipo='periodo_cerrado',
        origen='cierre',
        usuario_id=usuario_id,
        empresa_id=empresa_id,
        detalles={
            'periodo': periodo,
            'validaciones': validaciones_json
        }
    )


def reabrir_periodo(empresa_id: UUID, periodo: str, usuario_id: UUID) -> None:
    """
    Reabre un período (solo admin). Registra en auditoría.
    """
    db.execute(
        """
        UPDATE periodos_cerrados
        SET reabierto_por = %s, fecha_reapertura = NOW()
        WHERE empresa_id = %s AND periodo = %s
        """,
        (usuario_id, empresa_id, periodo)
    )

    registrar_evento(
        tipo='periodo_reabierto',
        origen='cierre',
        usuario_id=usuario_id,
        empresa_id=empresa_id,
        detalles={'periodo': periodo}
    )


def periodo_esta_cerrado(empresa_id: UUID, periodo: str) -> bool:
    """True si el período está cerrado y no reabierto."""
    cierre = db.query_one(
        """
        SELECT id FROM periodos_cerrados
        WHERE empresa_id = %s AND periodo = %s AND reabierto_por IS NULL
        """,
        (empresa_id, periodo)
    )
    return bool(cierre)
