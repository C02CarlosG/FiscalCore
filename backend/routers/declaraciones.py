"""Comparativo contra lo declarado (M5): captura de las declaraciones presentadas y su diferencia contra lo calculado
por los motores de flujo. El cálculo vive en ``declaraciones`` (puro); aquí permisos, validación y delegación."""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from .. import declaraciones, declaraciones_datos, isr_flujo, isr_flujo_datos, iva_flujo, iva_flujo_datos
from ..deps import empresa_or_404, get_current_user, validar_acceso_empresa
from .iva_flujo import _factor_o_422

router = APIRouter(tags=["Declaraciones"])

_BASE = "/api/v1/empresas/{empresa_id}/declaraciones"
_PERIODO_RE = re.compile(r"20[0-9]{2}-(0[1-9]|1[0-2])")
_MAXIMO = Decimal("9999999999999.99")
_CON_SIGNO = dict(default=None, ge=-_MAXIMO, le=_MAXIMO)
_POSITIVO = dict(default=None, ge=0, le=_MAXIMO)


class DeclaracionIn(BaseModel):
    tipo: Literal["normal", "complementaria"] = "normal"
    fecha_presentacion: Optional[date] = None
    numero_operacion: Optional[str] = Field(None, max_length=40)
    ingresos: Optional[Decimal] = Field(**_POSITIVO)
    deducciones: Optional[Decimal] = Field(**_POSITIVO)
    impuesto_trasladado: Optional[Decimal] = Field(**_POSITIVO)
    impuesto_acreditable: Optional[Decimal] = Field(**_POSITIVO)
    retenciones: Optional[Decimal] = Field(**_POSITIVO)
    retenciones_a_terceros: Optional[Decimal] = Field(**_POSITIVO, description="Impuesto retenido a terceros por enterar")
    saldo_a_favor_aplicado: Optional[Decimal] = Field(**_POSITIVO, description="Solo IVA: saldo a favor de periodos anteriores")
    impuesto_a_cargo: Optional[Decimal] = Field(**_CON_SIGNO, description="A cargo (+) o a favor (−)")
    monto_pagado: Optional[Decimal] = Field(**_POSITIVO)
    notas: str = Field("", max_length=500)

    @field_validator("ingresos", "deducciones", "impuesto_trasladado", "impuesto_acreditable", "retenciones",
                     "retenciones_a_terceros", "saldo_a_favor_aplicado", "impuesto_a_cargo", "monto_pagado")
    @classmethod
    def _centavos(cls, valor: Optional[Decimal]) -> Optional[Decimal]:
        if valor is not None and valor != valor.quantize(Decimal("0.01")):
            raise ValueError("máximo dos decimales")
        return valor


def _json(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json(v) for v in obj]
    return obj


def _periodo_o_422(periodo: str) -> str:
    if not _PERIODO_RE.fullmatch(periodo):
        raise HTTPException(status_code=422, detail="periodo inválido; formato esperado YYYY-MM")
    return periodo


def _impuesto_o_422(impuesto: str) -> str:
    if impuesto not in declaraciones.IMPUESTOS:
        raise HTTPException(status_code=422, detail="impuesto inválido; use iva o isr")
    return impuesto


@router.get(_BASE)
async def estado_del_ejercicio(empresa_id: str, ejercicio: int = Query(..., ge=2000, le=2099),
                               current_user: dict = Depends(get_current_user)):
    """Las declaraciones capturadas del ejercicio (sin recalcular): qué meses e impuestos ya tienen captura."""
    validar_acceso_empresa(empresa_id, current_user)
    return _json({"ejercicio": ejercicio, "items": declaraciones_datos.del_ejercicio(empresa_id, ejercicio)})


@router.get(_BASE + "/{periodo}")
async def comparativo(empresa_id: str, periodo: str,
                      factor: float = Query(1.0, description="Factor de prorrateo del IVA (LIVA 5-V)"),
                      current_user: dict = Depends(get_current_user)):
    """Lo declarado contra lo calculado de IVA e ISR del periodo, con la diferencia por renglón."""
    validar_acceso_empresa(empresa_id, current_user)
    _periodo_o_422(periodo)
    factor_dec = _factor_o_422(factor)
    empresa = empresa_or_404(empresa_id)
    rfc = empresa["rfc"]

    ajustes_iva = iva_flujo_datos.cargar_ajustes(empresa_id)
    iva = iva_flujo.resumen(iva_flujo_datos.cargar_eventos(empresa_id, rfc, periodo, ajustes_iva), periodo, ajustes_iva, factor_dec)
    ajustes_isr = isr_flujo_datos.cargar_ajustes(empresa_id)
    pct = isr_flujo_datos.porcentaje_nomina_exenta(empresa_id, int(periodo[:4]))
    isr = isr_flujo.resumen(isr_flujo_datos.cargar_eventos(empresa_id, rfc, periodo), periodo, ajustes_isr, pct)

    return _json({
        "empresa_id": empresa_id, "periodo": periodo, "factor_prorrateo": factor_dec,
        "iva": declaraciones.comparar("iva", declaraciones_datos.cadena(empresa_id, periodo, "iva"),
                                      declaraciones.calculado_de_iva(iva)),
        "isr": declaraciones.comparar("isr", declaraciones_datos.cadena(empresa_id, periodo, "isr"),
                                      declaraciones.calculado_de_isr(isr)),
        "aviso": "El pago provisional del ISR no se calcula: se muestra solo lo declarado.",
    })


@router.put(_BASE + "/{periodo}/{impuesto}")
async def guardar_declaracion(empresa_id: str, periodo: str, impuesto: str, datos: DeclaracionIn,
                              current_user: dict = Depends(get_current_user)):
    """Captura la declaración normal o agrega una complementaria (la vigente es la última). Queda auditado.
    409 si una normal llega con complementarias ya capturadas o una complementaria sin normal."""
    validar_acceso_empresa(empresa_id, current_user)
    empresa_or_404(empresa_id)
    _periodo_o_422(periodo)
    _impuesto_o_422(impuesto)
    if impuesto == "isr" and datos.saldo_a_favor_aplicado is not None:
        raise HTTPException(status_code=422, detail="saldo_a_favor_aplicado solo aplica al IVA")
    try:
        declaraciones_datos.guardar(empresa_id, periodo, impuesto, datos.tipo, datos.model_dump(), current_user["user_id"])
    except declaraciones_datos.ConflictoDeclaracion as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _json(declaraciones_datos.cadena(empresa_id, periodo, impuesto)[-1])


@router.delete(_BASE + "/{periodo}/{impuesto}", status_code=204)
async def eliminar_declaracion(empresa_id: str, periodo: str, impuesto: str,
                               current_user: dict = Depends(get_current_user)):
    """Borra la declaración vigente (la última); la anterior, si hay, vuelve a ser la vigente."""
    validar_acceso_empresa(empresa_id, current_user)
    _periodo_o_422(periodo)
    _impuesto_o_422(impuesto)
    if not declaraciones_datos.eliminar_ultima(empresa_id, periodo, impuesto, current_user["user_id"]):
        raise HTTPException(status_code=404, detail="Declaración no encontrada")
