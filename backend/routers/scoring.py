from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from .. import db
from ..deps import get_current_user, validar_acceso_empresa, empresa_or_404, serializar

_log = logging.getLogger(__name__)

router = APIRouter(tags=["Scoring"])


@router.get("/api/v1/empresas/{empresa_id}/scoring")
async def obtener_scoring(empresa_id: str, periodo: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    validar_acceso_empresa(empresa_id, current_user)
    empresa_or_404(empresa_id)
    if periodo:
        row = db.query_one(
            "SELECT * FROM scoring_fiscal WHERE empresa_id = %s AND periodo = %s",
            (empresa_id, periodo),
        )
    else:
        row = db.query_one(
            "SELECT * FROM scoring_fiscal WHERE empresa_id = %s ORDER BY periodo DESC LIMIT 1",
            (empresa_id,),
        )
    if not row:
        raise HTTPException(status_code=404, detail="Sin scoring para este período")
    return serializar(row)


@router.get("/api/v1/empresas/{empresa_id}/scoring/historial")
async def historial_scoring(empresa_id: str, current_user: dict = Depends(get_current_user)):
    validar_acceso_empresa(empresa_id, current_user)
    empresa_or_404(empresa_id)
    rows = db.query_all(
        "SELECT periodo, score_total AS score, clasificacion FROM scoring_fiscal WHERE empresa_id = %s ORDER BY periodo",
        (empresa_id,),
    )
    return {"historial": rows}
