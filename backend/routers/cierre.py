"""
M2: Cierre de períodos contables — endpoints para papel de trabajo, validaciones y cierre.
"""
from io import BytesIO
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from .. import cierre as cierre_logic, papel_trabajo
from ..deps import empresa_or_404, get_current_user, validar_acceso_empresa

router = APIRouter(tags=["Cierre de período"])

_BASE = "/api/v1/empresas/{empresa_id}/periodos/{periodo}"


@router.get(_BASE + "/papel-trabajo")
async def descargar_papel_trabajo(empresa_id: str, periodo: str, current_user: dict = Depends(get_current_user)):
    """Descarga el Excel (papel de trabajo) del período."""
    validar_acceso_empresa(empresa_id, current_user)
    empresa_or_404(empresa_id)

    xlsx_bytes = papel_trabajo.generar_papel_trabajo(UUID(empresa_id), periodo)

    return StreamingResponse(
        iter([xlsx_bytes.getvalue()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=papel-trabajo-{periodo}.xlsx"}
    )


@router.get(_BASE + "/validaciones")
async def listar_validaciones(empresa_id: str, periodo: str, current_user: dict = Depends(get_current_user)):
    """Lista todas las validaciones del período sin intentar cerrar."""
    validar_acceso_empresa(empresa_id, current_user)
    empresa_or_404(empresa_id)

    bloqueantes = cierre_logic.validaciones_bloqueantes(UUID(empresa_id), periodo)
    recomendadas = cierre_logic.validaciones_recomendadas(UUID(empresa_id), periodo)

    return {
        "validaciones": bloqueantes + recomendadas,
        "puede_cerrar": cierre_logic.puede_cerrar(UUID(empresa_id), periodo)
    }


@router.post(_BASE + "/cerrar")
async def cerrar_periodo(empresa_id: str, periodo: str, current_user: dict = Depends(get_current_user)):
    """Intenta cerrar el período. 403 si hay validaciones bloqueantes sin pasar."""
    validar_acceso_empresa(empresa_id, current_user)
    empresa_or_404(empresa_id)

    try:
        cierre_logic.cerrar_periodo(UUID(empresa_id), periodo, UUID(current_user['user_id']))
        return {"mensaje": "Período cerrado exitosamente"}
    except cierre_logic.PeriodoNoPuedeCerrar as e:
        validaciones = cierre_logic.validaciones_bloqueantes(UUID(empresa_id), periodo)
        sin_pasar = [v for v in validaciones if v['bloquea'] and not v['pasó']]
        raise HTTPException(
            status_code=403,
            detail={
                "mensaje": str(e),
                "validaciones_sin_pasar": sin_pasar
            }
        )


@router.delete(_BASE + "/cierre")
async def reabrir_periodo(empresa_id: str, periodo: str, current_user: dict = Depends(get_current_user)):
    """Reabre un período (solo admin)."""
    if current_user.get('rol') != 'admin':
        raise HTTPException(status_code=403, detail="Solo admin puede reabrir períodos")

    empresa_or_404(empresa_id)

    cierre_logic.reabrir_periodo(UUID(empresa_id), periodo, UUID(current_user['user_id']))
    return {"mensaje": "Período reabierto"}


@router.get(_BASE + "/estado-cierre")
async def estado_cierre(empresa_id: str, periodo: str, current_user: dict = Depends(get_current_user)):
    """Estado actual del cierre: cerrado sí/no, quién, cuándo."""
    validar_acceso_empresa(empresa_id, current_user)
    empresa_or_404(empresa_id)

    from .. import db
    cierre_row = db.query_one(
        """
        SELECT cerrado_por, fecha_cierre, reabierto_por, fecha_reapertura
        FROM periodos_cerrados
        WHERE empresa_id = %s AND periodo = %s
        """,
        (empresa_id, periodo)
    )

    if not cierre_row:
        return {"cerrado": False}

    return {
        "cerrado": True,
        "cerrado_por": str(cierre_row['cerrado_por']) if cierre_row['cerrado_por'] else None,
        "fecha_cierre": cierre_row['fecha_cierre'].isoformat() if cierre_row['fecha_cierre'] else None,
        "reabierto": cierre_row['reabierto_por'] is not None,
        "reabierto_por": str(cierre_row['reabierto_por']) if cierre_row['reabierto_por'] else None,
        "fecha_reapertura": cierre_row['fecha_reapertura'].isoformat() if cierre_row['fecha_reapertura'] else None
    }
