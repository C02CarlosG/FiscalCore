from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from .. import db
from ..deps import get_current_user, validar_acceso_empresa, empresa_or_404, serializar
from ..schemas import AccionRequest

_log = logging.getLogger(__name__)

router = APIRouter(tags=["Riesgos"])

ACCION_ESTADO = {
    "marcar_revisado": "en_revision",
    "solicitar_cfdi":  "en_espera_cfdi",
    "emitir_cfdi":     "en_espera_cfdi",
    "confirmar_match": "confirmado",
    "descartar":       "descartado",
    "resolver":        "resuelto",
}


@router.get("/api/v1/empresas/{empresa_id}/riesgos")
async def listar_riesgos(
    empresa_id: str,
    periodo: Optional[str] = None,
    severidad: Optional[str] = None,
    estado: str = "abierto",
    current_user: dict = Depends(get_current_user),
):
    validar_acceso_empresa(empresa_id, current_user)
    empresa_or_404(empresa_id)

    sql = """
        SELECT d.id, r.codigo, r.nombre, r.severidad,
               d.monto_afectado, d.descripcion,
               d.cfdi_id, d.movimiento_id, d.estado, d.periodo, d.created_at
        FROM detecciones d
        JOIN riesgos r ON r.id = d.riesgo_id
        WHERE d.empresa_id = %s
    """
    params: list = [empresa_id]

    if estado:
        sql += " AND d.estado = %s"
        params.append(estado)
    if periodo:
        sql += " AND d.periodo = %s"
        params.append(periodo)
    if severidad:
        sql += " AND r.severidad = %s"
        params.append(severidad)

    sql += """
        ORDER BY CASE r.severidad WHEN 'critico' THEN 1 WHEN 'alto' THEN 2
                                   WHEN 'medio' THEN 3 ELSE 4 END, d.created_at DESC
    """

    rows = db.query_all(sql, tuple(params))
    riesgos = [serializar(r) for r in rows]
    return {"total": len(riesgos), "riesgos": riesgos}


@router.patch("/api/v1/riesgos/{riesgo_id}/resolver")
async def resolver_riesgo(riesgo_id: str, notas: str = ""):
    row = db.execute(
        """
        UPDATE detecciones
        SET estado = 'resuelto', resuelto_en = NOW(), notas_resolucion = %s
        WHERE id = %s
        RETURNING id, estado
        """,
        (notas, riesgo_id),
        returning=True,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Riesgo no encontrado")
    return {"mensaje": "Riesgo marcado como resuelto", "riesgo_id": riesgo_id, "estado": "resuelto"}


@router.post("/api/v1/acciones/{deteccion_id}/ejecutar", tags=["Acciones"])
async def ejecutar_accion(deteccion_id: str, body: AccionRequest):
    """Ejecuta una acción sobre una detección y actualiza su estado."""
    det = db.query_one("SELECT estado FROM detecciones WHERE id = %s", (deteccion_id,))
    if not det:
        raise HTTPException(status_code=404, detail="Detección no encontrada")

    nuevo_estado = ACCION_ESTADO.get(body.tipo)
    if not nuevo_estado:
        raise HTTPException(status_code=400, detail=f"Tipo de acción desconocido: {body.tipo}")

    db.execute(
        """
        UPDATE detecciones
        SET estado = %s, updated_at = NOW(), notas_resolucion = %s,
            resuelto_en = CASE WHEN %s IN ('resuelto','descartado','confirmado') THEN NOW() ELSE resuelto_en END
        WHERE id = %s
        """,
        (nuevo_estado, body.notas or "", nuevo_estado, deteccion_id),
    )

    return {
        "deteccion_id": deteccion_id,
        "estado_anterior": det["estado"],
        "estado_nuevo": nuevo_estado,
    }
