"""Listado unificado de CFDI (emitidos y recibidos, cualquier tipo): paginado,
filtrado y ordenado en el servidor. La lógica vive en ``cfdi_listado``; aquí
solo se validan permisos y se traducen los errores de validación a 422."""
from __future__ import annotations

from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from .. import auditoria, cfdi_exportacion, cfdi_listado
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


@router.get(_BASE + "/exportar")
async def exportar_cfdi(
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
    columnas: Optional[str] = Query(None, description="Claves separadas por coma, en el orden deseado"),
    current_user: dict = Depends(get_current_user),
):
    """Excel con todas las filas que cumplen los filtros (sin paginar), las columnas
    pedidas en su orden y una hoja de totales. Máximo 50,000 filas."""
    validar_acceso_empresa(empresa_id, current_user)
    consulta = _consulta(direccion=direccion, periodo=periodo, tipo=tipo, estado=estado,
                         metodo=metodo, pago=pago, q=q, filtros=filtros, orden=orden, dir=direccion_orden)
    claves = [k.strip() for k in columnas.split(",") if k.strip()] if columnas else None
    empresa = empresa_or_404(empresa_id)
    try:
        datos = cfdi_listado.exportar(empresa_id, empresa["rfc"], consulta, claves)
    except cfdi_listado.FiltroInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    contenido = cfdi_exportacion.construir(
        datos["columnas"], datos["items"], cfdi_listado.resumen(empresa_id, empresa["rfc"], consulta))
    auditoria.registrar_evento(
        current_user["user_id"], "cfdi_exportado", empresa_id=empresa_id,
        metadata={"direccion": direccion, "periodo": periodo, "tipo": tipo, "filas": datos["total"],
                  "columnas": [c.clave for c in datos["columnas"]]},
    )
    nombre = f"cfdi_{direccion}_{tipo}_{periodo}.xlsx"
    return StreamingResponse(
        BytesIO(contenido),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


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
