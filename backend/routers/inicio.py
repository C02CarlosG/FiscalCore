"""Inicio (F4): ingresos y gastos netos, serie de 12 meses e IVA del ejercicio.
Solo lectura; el cálculo vive en ``inicio`` y ``inicio_datos``."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from .. import inicio, inicio_datos
from ..deps import empresa_or_404, get_current_user, validar_acceso_empresa

router = APIRouter(tags=["Inicio"])

_BASE = "/api/v1/empresas/{empresa_id}/inicio"


def _json(obj):
    """Decimal -> float en estructuras anidadas (los importes ya van a centavos)."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json(v) for v in obj]
    return obj


def _periodo_o_422(periodo: str) -> str:
    if not inicio.periodo_valido(periodo):
        raise HTTPException(status_code=422, detail="periodo inválido; formato esperado YYYY-MM")
    return periodo


@router.get(_BASE + "/resumen")
async def resumen_inicio(
    empresa_id: str,
    periodo: str = Query(..., description="YYYY-MM"),
    current_user: dict = Depends(get_current_user),
):
    """Ingresos y gastos netos del periodo y del ejercicio, y los últimos 12 meses."""
    validar_acceso_empresa(empresa_id, current_user)
    _periodo_o_422(periodo)
    empresa = empresa_or_404(empresa_id)
    filas = inicio_datos.cargar_agregados(empresa_id, empresa["rfc"], periodo)
    return _json({"empresa_id": empresa_id, **inicio.componer_resumen(filas, periodo)})


@router.get(_BASE + "/iva-anual")
async def iva_anual_inicio(
    empresa_id: str,
    ejercicio: int = Query(..., ge=2000, le=2099),
    periodo: Optional[str] = Query(None, description="YYYY-MM; los meses posteriores salen en cero"),
    current_user: dict = Depends(get_current_user),
):
    """IVA del ejercicio mes por mes: trasladado, acreditable y resultado."""
    validar_acceso_empresa(empresa_id, current_user)
    if periodo is not None:
        _periodo_o_422(periodo)
        if int(periodo[:4]) != ejercicio:
            raise HTTPException(status_code=422, detail="el periodo no pertenece al ejercicio")
    empresa = empresa_or_404(empresa_id)
    meses, advertencias = inicio_datos.cargar_iva_ejercicio(empresa_id, empresa["rfc"], ejercicio, periodo)
    return _json({
        "empresa_id": empresa_id,
        **inicio.componer_iva_anual(ejercicio, meses, periodo),
        "advertencias": advertencias,
    })
