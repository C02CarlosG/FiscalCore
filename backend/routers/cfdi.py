from __future__ import annotations

import calendar
import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query

from .. import db
from ..deps import get_current_user, validar_acceso_empresa, empresa_or_404

_log = logging.getLogger(__name__)

router = APIRouter(tags=["CFDI"])

_PERIODO_PATTERN = r"^\d{4}-\d{2}$"


def _rango_periodo(periodo: str) -> tuple[str, str]:
    try:
        año, mes = periodo.split("-")
        inicio = f"{año}-{mes}-01"
        ultimo = calendar.monthrange(int(año), int(mes))[1]
        fin = f"{año}-{mes}-{ultimo:02d}"
        return inicio, fin
    except ValueError:
        raise HTTPException(status_code=400, detail="Periodo inválido, usa formato YYYY-MM")


@router.get("/api/v1/empresas/{empresa_id}/cfdi/visor")
async def get_visor_sat(
    empresa_id: str,
    periodo: str = Query(..., pattern=_PERIODO_PATTERN, description="Período en formato YYYY-MM"),
    current_user: dict = Depends(get_current_user),
):
    """
    Visor general de CFDI: todos los comprobantes (cualquier tipo) emitidos o
    recibidos por el RFC de la empresa en el período — la vista "como en el
    portal del SAT", sin la clasificación de anticipos/notas de crédito que
    aplican los endpoints de Emitidos/Recibidos.
    """
    validar_acceso_empresa(empresa_id, current_user)
    empresa = empresa_or_404(empresa_id)
    inicio, fin = _rango_periodo(periodo)

    rows = db.query_all(
        """
        SELECT uuid, tipo_comprobante, serie, folio, fecha_emision::date AS fecha,
               rfc_emisor, nombre_emisor, rfc_receptor, nombre_receptor,
               total, iva_trasladado, estado
        FROM cfdi
        WHERE empresa_id = %s
          AND (rfc_emisor = %s OR rfc_receptor = %s)
          AND fecha_emision::date BETWEEN %s AND %s
        ORDER BY fecha_emision ASC
        """,
        (empresa_id, empresa["rfc"], empresa["rfc"], inicio, fin),
    )

    def _row(r: dict) -> dict:
        return {
            "uuid": r["uuid"],
            "tipo_comprobante": r["tipo_comprobante"],
            "serie_folio": f"{r['serie'] or ''}{r['folio'] or ''}".strip() or None,
            "fecha": str(r["fecha"]),
            "rfc_emisor": r["rfc_emisor"],
            "nombre_emisor": r["nombre_emisor"],
            "rfc_receptor": r["rfc_receptor"],
            "nombre_receptor": r["nombre_receptor"],
            "total": float(r["total"] or 0),
            "iva": float(r["iva_trasladado"] or 0),
            "estado": r["estado"],
            "direccion": "emitido" if r["rfc_emisor"] == empresa["rfc"] else "recibido",
        }

    cfdis = [_row(r) for r in rows]
    total_monto = sum(Decimal(str(c["total"])) for c in cfdis)

    return {
        "periodo": periodo,
        "empresa_rfc": empresa["rfc"],
        "resumen": {
            "total_cfdi": len(cfdis),
            "emitidos": sum(1 for c in cfdis if c["direccion"] == "emitido"),
            "recibidos": sum(1 for c in cfdis if c["direccion"] == "recibido"),
            "vigentes": sum(1 for c in cfdis if c["estado"] != "cancelado"),
            "canceladas": sum(1 for c in cfdis if c["estado"] == "cancelado"),
            "monto_total": float(total_monto),
        },
        "cfdi": cfdis,
    }


@router.get("/api/v1/empresas/{empresa_id}/cfdi/nomina")
async def get_cfdi_nomina(
    empresa_id: str,
    periodo: str = Query(..., pattern=_PERIODO_PATTERN, description="Período en formato YYYY-MM"),
    current_user: dict = Depends(get_current_user),
):
    """CFDIs de nómina (tipo_comprobante='N') emitidos por la empresa a sus empleados en el período."""
    validar_acceso_empresa(empresa_id, current_user)
    empresa = empresa_or_404(empresa_id)
    inicio, fin = _rango_periodo(periodo)

    rows = db.query_all(
        """
        SELECT uuid, serie, folio, fecha_emision::date AS fecha,
               rfc_receptor, nombre_receptor, subtotal, total, estado
        FROM cfdi
        WHERE empresa_id = %s
          AND rfc_emisor = %s
          AND tipo_comprobante = 'N'
          AND fecha_emision::date BETWEEN %s AND %s
        ORDER BY fecha_emision ASC
        """,
        (empresa_id, empresa["rfc"], inicio, fin),
    )

    def _row(r: dict) -> dict:
        return {
            "uuid": r["uuid"],
            "serie_folio": f"{r['serie'] or ''}{r['folio'] or ''}".strip() or None,
            "fecha": str(r["fecha"]),
            "rfc_receptor": r["rfc_receptor"],
            "nombre_receptor": r["nombre_receptor"],
            "subtotal": float(r["subtotal"] or 0),
            "total": float(r["total"] or 0),
            "estado": r["estado"],
        }

    recibos = [_row(r) for r in rows]
    total_nomina = sum(Decimal(str(r["total"])) for r in recibos)

    return {
        "periodo": periodo,
        "empresa_rfc": empresa["rfc"],
        "resumen": {
            "total_nomina": float(total_nomina),
            "num_recibos": len(recibos),
            "vigentes": sum(1 for r in recibos if r["estado"] != "cancelado"),
            "canceladas": sum(1 for r in recibos if r["estado"] == "cancelado"),
        },
        "recibos": recibos,
    }
