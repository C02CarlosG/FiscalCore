from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends

from .. import db
from ..deps import get_current_user, validar_acceso_empresa, empresa_or_404, serializar

_log = logging.getLogger(__name__)

router = APIRouter(tags=["Dashboard"])


@router.get("/api/v1/dashboard/{empresa_id}")
async def dashboard(empresa_id: str, periodo: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    validar_acceso_empresa(empresa_id, current_user)
    empresa = empresa_or_404(empresa_id)

    # Scoring más reciente (o del período solicitado)
    if periodo:
        score_row = db.query_one(
            "SELECT * FROM scoring_fiscal WHERE empresa_id = %s AND periodo = %s",
            (empresa_id, periodo),
        )
    else:
        score_row = db.query_one(
            "SELECT * FROM scoring_fiscal WHERE empresa_id = %s ORDER BY periodo DESC LIMIT 1",
            (empresa_id,),
        )

    periodo_actual = periodo or (score_row["periodo"] if score_row else None)

    # Riesgos abiertos del período
    if periodo_actual:
        riesgos_rows = db.query_all(
            """
            SELECT d.id, r.codigo, r.nombre, r.severidad,
                   d.monto_afectado, d.descripcion,
                   d.cfdi_id, d.movimiento_id, d.estado, d.periodo, d.created_at
            FROM detecciones d
            JOIN riesgos r ON r.id = d.riesgo_id
            WHERE d.empresa_id = %s AND d.estado = 'abierto' AND d.periodo = %s
            ORDER BY
                CASE r.severidad WHEN 'critico' THEN 1 WHEN 'alto' THEN 2
                                 WHEN 'medio' THEN 3 ELSE 4 END
            """,
            (empresa_id, periodo_actual),
        )
    else:
        riesgos_rows = db.query_all(
            """
            SELECT d.id, r.codigo, r.nombre, r.severidad,
                   d.monto_afectado, d.descripcion,
                   d.cfdi_id, d.movimiento_id, d.estado, d.periodo, d.created_at
            FROM detecciones d
            JOIN riesgos r ON r.id = d.riesgo_id
            WHERE d.empresa_id = %s AND d.estado = 'abierto'
            ORDER BY
                CASE r.severidad WHEN 'critico' THEN 1 WHEN 'alto' THEN 2
                                 WHEN 'medio' THEN 3 ELSE 4 END
            LIMIT 50
            """,
            (empresa_id,),
        )

    riesgos = [serializar(r) for r in riesgos_rows]

    resumen = {
        "critico": sum(1 for r in riesgos if r["severidad"] == "critico"),
        "alto":    sum(1 for r in riesgos if r["severidad"] == "alto"),
        "medio":   sum(1 for r in riesgos if r["severidad"] == "medio"),
        "bajo":    sum(1 for r in riesgos if r["severidad"] == "bajo"),
        "monto_total_en_riesgo": sum(r.get("monto_afectado") or 0 for r in riesgos),
    }

    # Tendencia de scores
    tendencia = db.query_all(
        "SELECT periodo, score_total AS score FROM scoring_fiscal WHERE empresa_id = %s ORDER BY periodo",
        (empresa_id,),
    )

    score_out = serializar(score_row) if score_row else None
    indicadores = {}
    if score_row:
        dep = float(score_row.get("total_depositos_banco") or 0)
        car = float(score_row.get("total_cargos_banco") or 0)
        ing = float(score_row.get("total_ingresos_cfdi") or 0)
        egr = float(score_row.get("total_egresos_cfdi") or 0)
        tot = score_row.get("total_movimientos") or 0
        con = score_row.get("total_conciliados") or 0
        indicadores = {
            "ingresos_cfdi": ing,
            "egresos_cfdi": egr,
            "depositos_banco": dep,
            "cargos_banco": car,
            "brecha_ingresos": dep - ing,
            "brecha_egresos": car - egr,
            "pct_conciliacion": round(con / tot * 100, 1) if tot > 0 else 0,
        }

    return {
        "empresa": serializar(empresa),
        "score_actual": score_out,
        "riesgos_abiertos": riesgos,
        "resumen_riesgos": resumen,
        "tendencia_score": tendencia,
        "indicadores": indicadores,
    }
