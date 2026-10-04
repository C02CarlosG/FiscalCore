"""IVA base flujo (F5.1): resumen por tasa y origen, detalle de lo que compone cada cifra y
ajustes manuales (no considerar / reasignar periodo) con auditoría. El cálculo vive en
``iva_flujo`` (puro) e ``iva_flujo_datos`` (SQL); aquí solo se validan permisos y entradas."""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Literal, Optional

from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from .. import db, iva_flujo, iva_flujo_datos, iva_flujo_exportacion
from ..auditoria import registrar_evento
from ..deps import empresa_or_404, get_current_user, validar_acceso_empresa

router = APIRouter(tags=["IVA por flujo"])

_BASE = "/api/v1/empresas/{empresa_id}/iva-flujo"
_PERIODO_RE = re.compile(r"20[0-9]{2}-(0[1-9]|1[0-2])")
_UUID_MAX = 36
MAX_FILAS_EXPORTACION = 50_000


class AjusteIn(BaseModel):
    uuid: str = Field(..., min_length=1, max_length=_UUID_MAX)
    direccion: Literal["trasladado", "acreditable"]
    accion: Literal["excluir", "reasignar"]
    periodo_destino: Optional[str] = None
    motivo: str = Field(..., max_length=500, description="Obligatorio: queda en la auditoría")

    @field_validator("motivo")
    @classmethod
    def _motivo_con_texto(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("el motivo es obligatorio")
        return valor


def _json(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json(v) for v in obj]
    return obj


def _periodo_o_422(periodo: str) -> str:
    if not _PERIODO_RE.fullmatch(periodo):
        raise HTTPException(status_code=422, detail="periodo inválido; formato esperado YYYY-MM")
    return periodo


def _factor_o_422(factor: float) -> Decimal:
    if not 0 <= factor <= 1:
        raise HTTPException(status_code=422, detail="el factor de prorrateo debe estar entre 0 y 1")
    return Decimal(str(factor))


# Las rutas de ajustes van primero: "ajustes" no debe leerse como un periodo.

@router.get(_BASE + "/ajustes")
async def listar_ajustes(empresa_id: str, current_user: dict = Depends(get_current_user)):
    """Ajustes vigentes de la empresa, del más reciente al más antiguo."""
    validar_acceso_empresa(empresa_id, current_user)
    filas = db.query_all(
        """SELECT cfdi_uuid AS uuid, direccion, accion, periodo_destino, motivo, created_at, updated_at
           FROM iva_ajustes WHERE empresa_id = %s ORDER BY updated_at DESC LIMIT 500""",
        (empresa_id,),
    )
    return {"items": [{**f, "created_at": f["created_at"].isoformat(), "updated_at": f["updated_at"].isoformat()} for f in filas]}


@router.put(_BASE + "/ajustes")
async def guardar_ajuste(empresa_id: str, datos: AjusteIn, current_user: dict = Depends(get_current_user)):
    """Crea o reemplaza el ajuste de un CFDI en una dirección y lo audita."""
    validar_acceso_empresa(empresa_id, current_user)
    empresa = empresa_or_404(empresa_id)

    if datos.accion == "reasignar":
        if not datos.periodo_destino or not _PERIODO_RE.fullmatch(datos.periodo_destino):
            raise HTTPException(status_code=422, detail="reasignar requiere periodo_destino con formato YYYY-MM")
    elif datos.periodo_destino is not None:
        raise HTTPException(status_code=422, detail="excluir no lleva periodo_destino")

    cfdi = db.query_one(
        """SELECT uuid, tipo_comprobante, metodo_pago, fecha_emision, rfc_emisor, rfc_receptor
           FROM cfdi WHERE empresa_id = %s AND UPPER(uuid) = UPPER(%s) AND estado = 'vigente'""",
        (empresa_id, datos.uuid),
    )
    propio = cfdi and (
        (datos.direccion == "trasladado" and cfdi["rfc_emisor"] == empresa["rfc"])
        or (datos.direccion == "acreditable" and cfdi["rfc_receptor"] == empresa["rfc"])
    )
    if not propio or cfdi["tipo_comprobante"] not in ("I", "E"):
        raise HTTPException(status_code=404, detail="CFDI no encontrado para ese ajuste")

    # Un PUE tiene un solo mes de efecto: reasignarlo a ese mismo mes no hace nada.
    un_solo_mes = cfdi["tipo_comprobante"] == "E" or cfdi["metodo_pago"] == "PUE"
    if datos.accion == "reasignar" and un_solo_mes and datos.periodo_destino == cfdi["fecha_emision"].strftime("%Y-%m"):
        raise HTTPException(status_code=422, detail="el periodo destino es el mismo de la emisión")

    uuid = cfdi["uuid"].upper()
    iva_flujo_datos.guardar_ajuste(
        empresa_id, uuid, datos.direccion, datos.accion, datos.periodo_destino, datos.motivo, current_user["user_id"])
    return {"uuid": uuid, "direccion": datos.direccion, "accion": datos.accion,
            "periodo_destino": datos.periodo_destino, "motivo": datos.motivo}


@router.delete(_BASE + "/ajustes/{direccion}/{uuid}", status_code=204)
async def quitar_ajuste(empresa_id: str, direccion: Literal["trasladado", "acreditable"], uuid: str,
                        current_user: dict = Depends(get_current_user)):
    """Retira un ajuste (el CFDI vuelve a considerarse según las reglas) y lo audita."""
    validar_acceso_empresa(empresa_id, current_user)
    if len(uuid) > _UUID_MAX:
        raise HTTPException(status_code=404, detail="Ajuste no encontrado")
    if iva_flujo_datos.quitar_ajuste(empresa_id, uuid, direccion, current_user["user_id"]) is None:
        raise HTTPException(status_code=404, detail="Ajuste no encontrado")


@router.get(_BASE + "/{periodo}")
async def resumen_iva_flujo(
    empresa_id: str,
    periodo: str,
    factor: float = Query(1.0, description="Factor de prorrateo (LIVA 5-V); 1 = actividad 100 % gravada"),
    current_user: dict = Depends(get_current_user),
):
    """IVA del mes por flujo de efectivo: por tasa y origen, con resultado y advertencias."""
    validar_acceso_empresa(empresa_id, current_user)
    _periodo_o_422(periodo)
    factor_dec = _factor_o_422(factor)
    empresa = empresa_or_404(empresa_id)
    ajustes = iva_flujo_datos.cargar_ajustes(empresa_id)
    eventos = iva_flujo_datos.cargar_eventos(empresa_id, empresa["rfc"], periodo, ajustes)
    return _json({"empresa_id": empresa_id, **iva_flujo.resumen(eventos, periodo, ajustes, factor_dec)})


@router.get(_BASE + "/{periodo}/detalle")
async def detalle_iva_flujo(
    empresa_id: str,
    periodo: str,
    direccion: str = Query(..., description="trasladado | acreditable"),
    origen: str = Query(..., description="contado | credito | notas_credito | no_considerados | reasignados"),
    pagina: int = Query(1),
    por_pagina: int = Query(50),
    current_user: dict = Depends(get_current_user),
):
    """Lo que compone una cifra del resumen, renglón por CFDI (o por pago)."""
    validar_acceso_empresa(empresa_id, current_user)
    _periodo_o_422(periodo)
    empresa = empresa_or_404(empresa_id)
    ajustes = iva_flujo_datos.cargar_ajustes(empresa_id)
    eventos = iva_flujo_datos.cargar_eventos(empresa_id, empresa["rfc"], periodo, ajustes)
    try:
        return iva_flujo.detalle(eventos, periodo, direccion, origen, ajustes, pagina, por_pagina)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get(_BASE + "/{periodo}/exportar")
async def exportar_iva_flujo(
    empresa_id: str,
    periodo: str,
    direccion: str = Query(..., description="trasladado | acreditable"),
    origen: str = Query(..., description="contado | credito | notas_credito | no_considerados | reasignados"),
    factor: float = Query(1.0),
    current_user: dict = Depends(get_current_user),
):
    """Excel con el detalle de una cifra (todos sus renglones) y el resumen del periodo.
    Si pasa de 50,000 renglones se pide acotar. Queda en la auditoría."""
    validar_acceso_empresa(empresa_id, current_user)
    _periodo_o_422(periodo)
    factor_dec = _factor_o_422(factor)
    empresa = empresa_or_404(empresa_id)
    ajustes = iva_flujo_datos.cargar_ajustes(empresa_id)
    eventos = iva_flujo_datos.cargar_eventos(empresa_id, empresa["rfc"], periodo, ajustes)
    try:
        filas = iva_flujo.renglones(eventos, periodo, direccion, origen, ajustes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if len(filas) > MAX_FILAS_EXPORTACION:
        raise HTTPException(status_code=422, detail=f"son {len(filas)} renglones; el máximo es {MAX_FILAS_EXPORTACION}")
    contenido = iva_flujo_exportacion.construir(
        periodo, direccion, origen, filas, iva_flujo.resumen(eventos, periodo, ajustes, factor_dec))
    registrar_evento(
        current_user["user_id"], "iva_flujo_exportado", empresa_id=empresa_id,
        metadata={"periodo": periodo, "direccion": direccion, "origen": origen, "filas": len(filas)},
    )
    return StreamingResponse(
        BytesIO(contenido),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="iva_{direccion}_{origen}_{periodo}.xlsx"'},
    )
