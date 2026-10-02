"""Listado unificado de CFDI (emitidos y recibidos, cualquier tipo): paginado,
filtrado y ordenado en el servidor. La lógica vive en ``cfdi_listado``; aquí
solo se validan permisos y se traducen los errores de validación a 422."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from .. import cfdi_listado
from ..cfdi_columnas import columnas, columnas_concepto
from ..deps import empresa_or_404, get_current_user, validar_acceso_empresa

router = APIRouter(tags=["CFDI"])

_BASE = "/api/v1/empresas/{empresa_id}/cfdis"


def _consulta(**parametros) -> cfdi_listado.Consulta:
    try:
        return cfdi_listado.validar(**parametros)
    except cfdi_listado.FiltroInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get(_BASE + "/columnas")
async def columnas_cfdi(
    empresa_id: str,
    direccion: str = Query(..., description="emitidos | recibidos"),
    tipo: str = Query("I", description="Tipo de comprobante: I, E, T, N o P"),
    current_user: dict = Depends(get_current_user),
):
    """Catálogo de columnas del listado: qué se puede mostrar, ordenar y filtrar."""
    validar_acceso_empresa(empresa_id, current_user)
    if direccion not in cfdi_listado.DIRECCIONES or tipo not in cfdi_listado.TIPOS:
        raise HTTPException(status_code=422, detail="direccion o tipo inválido")
    return {
        "encabezado": [c.publica() for c in columnas(direccion, tipo)],
        "concepto": [c.publica() for c in columnas_concepto()],
    }


@router.get(_BASE + "/resumen")
async def resumen_cfdi(
    empresa_id: str,
    direccion: str = Query(...),
    periodo: str = Query(..., description="YYYY-MM"),
    tipo: str = Query("I"),
    estado: str = Query("vigente"),
    metodo: str = Query("todos"),
    pago: str = Query("todos"),
    q: Optional[str] = Query(None),
    filtros: Optional[str] = Query(None, description="JSON: lista de {campo, op, valor}"),
    current_user: dict = Depends(get_current_user),
):
    """Conteos por tipo de comprobante y totales (periodo y acumulado del ejercicio)."""
    validar_acceso_empresa(empresa_id, current_user)
    consulta = _consulta(direccion=direccion, periodo=periodo, tipo=tipo, estado=estado,
                         metodo=metodo, pago=pago, q=q, filtros=filtros)
    empresa = empresa_or_404(empresa_id)
    return cfdi_listado.resumen(empresa_id, empresa["rfc"], consulta)


@router.get(_BASE)
async def listar_cfdi(
    empresa_id: str,
    direccion: str = Query(...),
    periodo: str = Query(..., description="YYYY-MM"),
    tipo: str = Query("I"),
    estado: str = Query("vigente"),
    metodo: str = Query("todos"),
    pago: str = Query("todos"),
    q: Optional[str] = Query(None),
    filtros: Optional[str] = Query(None, description="JSON: lista de {campo, op, valor}"),
    orden: str = Query("fecha_emision"),
    direccion_orden: str = Query("asc", alias="dir"),
    pagina: int = Query(1),
    por_pagina: int = Query(30),
    current_user: dict = Depends(get_current_user),
):
    """Una página del listado de CFDI con todas las columnas del catálogo."""
    validar_acceso_empresa(empresa_id, current_user)
    consulta = _consulta(direccion=direccion, periodo=periodo, tipo=tipo, estado=estado,
                         metodo=metodo, pago=pago, q=q, filtros=filtros, orden=orden,
                         dir=direccion_orden, pagina=pagina, por_pagina=por_pagina)
    empresa = empresa_or_404(empresa_id)
    return cfdi_listado.listar(empresa_id, empresa["rfc"], consulta)
