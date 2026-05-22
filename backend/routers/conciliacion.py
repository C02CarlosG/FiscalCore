from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends

from .. import db
from ..deps import get_current_user, validar_acceso_empresa, empresa_or_404, serializar

_log = logging.getLogger(__name__)

router = APIRouter(tags=["Conciliación"])


@router.get("/api/v1/empresas/{empresa_id}/periodos", tags=["Cierre"])
async def listar_periodos(empresa_id: str, current_user: dict = Depends(get_current_user)):
    """Lista los períodos YYYY-MM que tienen datos cargados para la empresa."""
    validar_acceso_empresa(empresa_id, current_user)
    empresa_or_404(empresa_id)
    rows = db.query_all(
        """
        SELECT DISTINCT periodo FROM (
            SELECT TO_CHAR(fecha_emision, 'YYYY-MM') AS periodo
            FROM cfdi WHERE empresa_id = %s AND fecha_emision IS NOT NULL
            UNION
            SELECT TO_CHAR(fecha, 'YYYY-MM') AS periodo
            FROM movimientos_bancarios WHERE empresa_id = %s AND fecha IS NOT NULL
            UNION
            SELECT periodo FROM scoring_fiscal WHERE empresa_id = %s
        ) sub WHERE periodo IS NOT NULL ORDER BY periodo DESC LIMIT 24
        """,
        (empresa_id, empresa_id, empresa_id),
    )
    return {"periodos": [r["periodo"] for r in rows]}


@router.get("/api/v1/empresas/{empresa_id}/cierre/{periodo}", tags=["Cierre"])
async def vista_cierre(empresa_id: str, periodo: str, current_user: dict = Depends(get_current_user)):
    """
    Vista consolidada para el cierre mensual.
    Responde: ¿Puedo cerrar? / ¿Qué me falta? / ¿Qué hago hoy?
    """
    validar_acceso_empresa(empresa_id, current_user)
    empresa_or_404(empresa_id)

    # Detecciones accionables (abierto, pendiente, en_revision, en_espera_cfdi)
    detecciones_rows = db.query_all(
        """
        SELECT
            d.id, d.estado, d.monto_afectado, d.descripcion, d.periodo,
            d.cfdi_id, d.movimiento_id, d.created_at,
            r.codigo, r.nombre, r.severidad, r.accion_sugerida,
            c.uuid        AS cfdi_uuid,
            c.fecha_emision AS cfdi_fecha,
            c.rfc_emisor  AS cfdi_rfc_emisor,
            c.rfc_receptor AS cfdi_rfc_receptor,
            c.total       AS cfdi_total,
            m.fecha       AS mov_fecha,
            m.concepto    AS mov_concepto,
            m.monto       AS mov_monto,
            m.rfc_detectado AS mov_rfc
        FROM detecciones d
        JOIN riesgos r ON r.id = d.riesgo_id
        LEFT JOIN cfdi c ON c.id = d.cfdi_id
        LEFT JOIN movimientos_bancarios m ON m.id = d.movimiento_id
        WHERE d.empresa_id = %s
          AND d.periodo = %s
          AND d.estado IN ('abierto','pendiente','en_revision','en_espera_cfdi')
        ORDER BY
            CASE r.severidad WHEN 'critico' THEN 1 WHEN 'alto' THEN 2
                             WHEN 'medio' THEN 3 ELSE 4 END,
            d.monto_afectado DESC NULLS LAST
        """,
        (empresa_id, periodo),
    )

    acciones = []
    for row in detecciones_rows:
        item = serializar(row)
        # Contexto mínimo para el ítem de acción
        item["contexto"] = {}
        if row["cfdi_uuid"]:
            item["contexto"] = {
                "tipo": "cfdi",
                "uuid":  row["cfdi_uuid"],
                "fecha": row["cfdi_fecha"].isoformat() if row["cfdi_fecha"] else None,
                "rfc":   row["cfdi_rfc_emisor"] or row["cfdi_rfc_receptor"],
                "total": float(row["cfdi_total"] or 0),
            }
        elif row["mov_fecha"]:
            item["contexto"] = {
                "tipo":    "movimiento",
                "fecha":   row["mov_fecha"].isoformat() if row["mov_fecha"] else None,
                "concepto": (row["mov_concepto"] or "")[:80],
                "monto":   float(row["mov_monto"] or 0),
                "rfc":     row["mov_rfc"],
            }
        acciones.append(item)

    bloqueadores = [a for a in acciones if a["severidad"] in ("critico", "alto")]

    # Conciliación del período
    conc_rows = db.query_all(
        """
        SELECT tipo_match, COUNT(*) AS total
        FROM conciliaciones
        WHERE empresa_id = %s AND periodo = %s
        GROUP BY tipo_match
        """,
        (empresa_id, periodo),
    )
    conc = {r["tipo_match"]: r["total"] for r in conc_rows}
    total_mov = sum(conc.values())

    # Heurísticos de alta confianza: consulta separada porque necesitamos filtrar por confianza
    heur_alta = db.query_one(
        """
        SELECT COUNT(*) AS total FROM conciliaciones
        WHERE empresa_id = %s AND periodo = %s
          AND tipo_match = 'heuristico' AND confianza = 'alta'
        """,
        (empresa_id, periodo),
    )
    conciliados = (
        conc.get("exacto", 0)
        + conc.get("parcial", 0)
        + conc.get("complemento_pago", 0)
        + conc.get("agrupado", 0)
        + conc.get("parcial_multiple", 0)
        + (heur_alta["total"] if heur_alta else 0)
    )
    pct_conciliado = round(conciliados / total_mov * 100, 1) if total_mov else 0.0
    matches_debiles = conc.get("parcial", 0) + conc.get("parcial_multiple", 0)

    # Score más reciente del período
    score_row = db.query_one(
        "SELECT score_total FROM scoring_fiscal WHERE empresa_id = %s AND periodo = %s",
        (empresa_id, periodo),
    )
    score = float(score_row["score_total"]) if score_row else None

    puede_cerrar = len(bloqueadores) == 0 and pct_conciliado >= 80.0

    razon_bloqueo = None
    if not puede_cerrar:
        razones = []
        if bloqueadores:
            razones.append(f"{len(bloqueadores)} riesgo{'s' if len(bloqueadores)>1 else ''} crítico{'s' if len(bloqueadores)>1 else ''}/alto{'s' if len(bloqueadores)>1 else ''} abierto{'s' if len(bloqueadores)>1 else ''}")
        if pct_conciliado < 80.0:
            razones.append(f"conciliación al {pct_conciliado}% (mínimo 80%)")
        razon_bloqueo = " · ".join(razones)

    return {
        "periodo": periodo,
        "puede_cerrar": puede_cerrar,
        "razon_bloqueo": razon_bloqueo,
        "score": score,
        "bloqueadores": bloqueadores,
        "acciones": acciones,
        "conciliacion": {
            "sin_cfdi":       conc.get("sin_cfdi", 0),
            "sin_movimiento": conc.get("sin_movimiento", 0),
            "matches_debiles": matches_debiles,
            "pct_conciliado": pct_conciliado,
            "total":          total_mov,
        },
    }


@router.get("/api/v1/empresas/{empresa_id}/conciliaciones/accionables")
async def conciliaciones_accionables(empresa_id: str, periodo: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Pares sin_cfdi y parciales con contexto del movimiento bancario."""
    validar_acceso_empresa(empresa_id, current_user)
    empresa_or_404(empresa_id)

    sql = """
        SELECT
            con.id, con.tipo_match, con.monto_movimiento, con.monto_cfdi,
            con.diferencia, con.porcentaje_match, con.periodo,
            m.id    AS movimiento_id,
            m.fecha AS mov_fecha,
            m.concepto,
            m.monto AS mov_monto,
            m.tipo  AS mov_tipo,
            m.rfc_detectado
        FROM conciliaciones con
        LEFT JOIN movimientos_bancarios m ON m.id = con.movimiento_id
        WHERE con.empresa_id = %s
          AND con.tipo_match IN ('sin_cfdi','parcial')
    """
    params: list = [empresa_id]
    if periodo:
        sql += " AND con.periodo = %s"
        params.append(periodo)
    sql += " ORDER BY con.monto_movimiento DESC NULLS LAST LIMIT 100"

    rows = db.query_all(sql, tuple(params))
    return {"total": len(rows), "pares": [serializar(r) for r in rows]}


@router.get("/api/v1/empresas/{empresa_id}/conciliaciones")
async def listar_conciliaciones(empresa_id: str, periodo: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    validar_acceso_empresa(empresa_id, current_user)
    empresa_or_404(empresa_id)

    sql = "SELECT tipo_match, COUNT(*) AS total FROM conciliaciones WHERE empresa_id = %s"
    params: list = [empresa_id]
    if periodo:
        sql += " AND periodo = %s"
        params.append(periodo)
    sql += " GROUP BY tipo_match"

    rows = db.query_all(sql, tuple(params))
    conteos = {r["tipo_match"]: r["total"] for r in rows}

    total = sum(conteos.values())
    conciliados = conteos.get("exacto", 0) + conteos.get("parcial", 0)
    pct = round(conciliados / total * 100, 1) if total > 0 else 0.0

    return {
        "total": total,
        "exacto": conteos.get("exacto", 0),
        "parcial": conteos.get("parcial", 0),
        "sin_cfdi": conteos.get("sin_cfdi", 0),
        "sin_movimiento": conteos.get("sin_movimiento", 0),
        "pct_conciliado": pct,
    }
