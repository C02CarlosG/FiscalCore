"""DIOT por flujo (F6.2): el acreditable del mes por tercero y tipo de operación, con la clasificación editable por periodo.
El cálculo vive en ``iva_flujo.por_contraparte`` y ``diot`` (puros); aquí solo se validan permisos y entradas."""
from __future__ import annotations

import re
from decimal import Decimal
from io import BytesIO
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator

from .. import db, diot, diot_catalogos, diot_datos, iva_flujo, iva_flujo_datos, proveedores
from ..auditoria import registrar_evento
from ..deps import empresa_or_404, get_current_user, validar_acceso_empresa
from .iva_flujo import _factor_o_422

router = APIRouter(tags=["DIOT"])

_BASE = "/api/v1/empresas/{empresa_id}/diot-flujo"
_PERIODO_RE = re.compile(r"20[0-9]{2}-(0[1-9]|1[0-2])")
_UUID_MAX = 36


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


def _codigo(valor: Optional[str], permitidos: tuple) -> Optional[str]:
    if valor is None or valor == "":
        return None
    if valor not in permitidos:
        raise ValueError(f"debe ser uno de: {', '.join(permitidos)}")
    return valor


class ClasificacionIn(BaseModel):
    tipo_tercero: Optional[str] = None
    tipo_operacion: Optional[str] = None

    @field_validator("tipo_tercero")
    @classmethod
    def _t(cls, v):
        return _codigo(v, diot_catalogos.TIPOS_TERCERO)

    @field_validator("tipo_operacion")
    @classmethod
    def _o(cls, v):
        return _codigo(v, diot_catalogos.TIPOS_OPERACION)


class OperacionIn(BaseModel):
    tipo_operacion: Literal["02", "03", "06", "07", "08", "85", "87"]


def _calcular(empresa_id: str, empresa: dict, periodo: str, factor: Decimal, usuario_id: str) -> dict:
    """La DIOT del periodo. Escribe: antes de calcular agrega al catálogo los proveedores que falten."""
    proveedores.sincronizar(empresa_id, empresa["rfc"], usuario_id)
    catalogo_lista = proveedores.listar(empresa_id)
    catalogo = diot.indice_de_catalogo(catalogo_lista)
    overrides = diot_datos.cargar_overrides(empresa_id, periodo)
    por_cfdi = diot_datos.cargar_operaciones_cfdi(empresa_id, periodo)
    ajustes = iva_flujo_datos.cargar_ajustes(empresa_id)
    eventos = iva_flujo_datos.cargar_eventos(empresa_id, empresa["rfc"], periodo, ajustes)

    def operacion_de(ev: dict) -> Optional[str]:
        asignada = por_cfdi.get(iva_flujo.llave(ev["uuid"]))
        if asignada:
            return asignada
        proveedor = catalogo.get(iva_flujo.clave_de_contraparte(ev["contraparte_rfc"], ev["contraparte"]))
        return diot.clasificacion(proveedor, overrides.get(proveedor["id"] if proveedor else None))[1]

    terceros = iva_flujo.por_contraparte(eventos, periodo, ajustes, factor, operacion_de)
    resumen = iva_flujo.resumen(eventos, periodo, ajustes, factor)
    resultado = diot.componer(terceros, catalogo, overrides)
    cuadre = resumen["acreditable"]["ajustado"]
    return {
        "empresa_id": empresa_id, "periodo": periodo, "factor_prorrateo": factor,
        **resultado,
        "cuadre_con_iva": {"iva_acreditable_diot": resultado["totales"]["iva_acreditable"], "iva_acreditable_resumen": cuadre,
                           "cuadra": resultado["totales"]["iva_acreditable"] == cuadre},
        "advertencias_iva": resumen["advertencias"],
        "operaciones_por_cfdi": len(por_cfdi),
    }


@router.get(_BASE + "/{periodo}")
async def diot_del_periodo(
    empresa_id: str,
    periodo: str,
    factor: float = Query(1.0, description="Factor de prorrateo (LIVA 5-V); el mismo de la cédula de IVA"),
    current_user: dict = Depends(get_current_user),
):
    """DIOT del mes por flujo: por tercero y tipo de operación, con el valor de actos por tasa, el IVA acreditable y el no
    acreditable por motivo. **Escribe**: agrega al catálogo los proveedores que falten (ver ``/proveedores``)."""
    validar_acceso_empresa(empresa_id, current_user)
    _periodo_o_422(periodo)
    factor_dec = _factor_o_422(factor)
    empresa = empresa_or_404(empresa_id)
    resultado = _calcular(empresa_id, empresa, periodo, factor_dec, current_user["user_id"])
    registrar_evento(current_user["user_id"], "reporte_generado", empresa_id=empresa_id, metadata={"tipo": "diot_flujo", "periodo": periodo})
    return _json(resultado)


def _proveedor_o_404(empresa_id: str, proveedor_id: str) -> dict:
    import uuid as _uuid
    try:
        pid = str(_uuid.UUID(proveedor_id))
    except ValueError:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    p = proveedores.obtener(empresa_id, pid)
    if p is None:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    return p


@router.put(_BASE + "/{periodo}/terceros/{proveedor_id}")
async def clasificar_tercero(empresa_id: str, periodo: str, proveedor_id: str, datos: ClasificacionIn,
                             current_user: dict = Depends(get_current_user)):
    """Tipo de tercero y de operación de un proveedor **en este periodo** (lo que no se manda cae al catálogo)."""
    validar_acceso_empresa(empresa_id, current_user)
    _periodo_o_422(periodo)
    p = _proveedor_o_404(empresa_id, proveedor_id)
    errores = diot_catalogos.validar({**p, **{k: v for k, v in datos.model_dump().items() if v is not None}})
    if errores:
        raise HTTPException(status_code=422, detail="; ".join(errores))
    diot_datos.guardar_tercero_periodo(empresa_id, periodo, p["id"], datos.tipo_tercero, datos.tipo_operacion, current_user["user_id"])
    return {"proveedor_id": p["id"], "periodo": periodo, **datos.model_dump()}


@router.delete(_BASE + "/{periodo}/terceros/{proveedor_id}", status_code=204)
async def quitar_clasificacion(empresa_id: str, periodo: str, proveedor_id: str, current_user: dict = Depends(get_current_user)):
    validar_acceso_empresa(empresa_id, current_user)
    _periodo_o_422(periodo)
    p = _proveedor_o_404(empresa_id, proveedor_id)
    if not diot_datos.quitar_tercero_periodo(empresa_id, periodo, p["id"], current_user["user_id"]):
        raise HTTPException(status_code=404, detail="Sin clasificación para ese periodo")


@router.put(_BASE + "/{periodo}/cfdi/{uuid}")
async def operacion_de_un_cfdi(empresa_id: str, periodo: str, uuid: str, datos: OperacionIn,
                               current_user: dict = Depends(get_current_user)):
    """Tipo de operación de **un CFDI** en el periodo: así un mismo tercero se declara con varias operaciones."""
    validar_acceso_empresa(empresa_id, current_user)
    _periodo_o_422(periodo)
    empresa = empresa_or_404(empresa_id)
    cfdi = None if len(uuid) > _UUID_MAX else db.query_one(
        """SELECT uuid FROM cfdi WHERE empresa_id = %s AND UPPER(uuid) = UPPER(%s) AND estado = 'vigente'
           AND tipo_comprobante IN ('I', 'E') AND rfc_receptor = %s""",
        (empresa_id, uuid, empresa["rfc"]))
    if not cfdi:
        raise HTTPException(status_code=404, detail="CFDI recibido no encontrado")
    diot_datos.guardar_operacion_cfdi(empresa_id, periodo, cfdi["uuid"], datos.tipo_operacion, current_user["user_id"])
    return {"uuid": cfdi["uuid"].upper(), "periodo": periodo, "tipo_operacion": datos.tipo_operacion}


@router.delete(_BASE + "/{periodo}/cfdi/{uuid}", status_code=204)
async def quitar_operacion_de_un_cfdi(empresa_id: str, periodo: str, uuid: str, current_user: dict = Depends(get_current_user)):
    validar_acceso_empresa(empresa_id, current_user)
    _periodo_o_422(periodo)
    if len(uuid) > _UUID_MAX or not diot_datos.quitar_operacion_cfdi(empresa_id, periodo, uuid, current_user["user_id"]):
        raise HTTPException(status_code=404, detail="Sin operación asignada a ese CFDI")


@router.get(_BASE + "/{periodo}/exportar")
async def exportar_diot(empresa_id: str, periodo: str, factor: float = Query(1.0), current_user: dict = Depends(get_current_user)):
    """Excel de la DIOT del periodo (una fila por tercero y operación, con totales)."""
    from .. import diot_exportacion

    validar_acceso_empresa(empresa_id, current_user)
    _periodo_o_422(periodo)
    factor_dec = _factor_o_422(factor)
    empresa = empresa_or_404(empresa_id)
    resultado = _calcular(empresa_id, empresa, periodo, factor_dec, current_user["user_id"])
    contenido = diot_exportacion.construir(resultado)
    registrar_evento(current_user["user_id"], "diot_exportada", empresa_id=empresa_id,
                     metadata={"periodo": periodo, "terceros": resultado["totales"]["terceros"]})
    return StreamingResponse(
        BytesIO(contenido),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="diot_{periodo}.xlsx"'},
    )
