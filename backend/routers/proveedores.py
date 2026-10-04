"""Catálogo de proveedores (F6.1): lista alimentada de los CFDI recibidos, alta manual y edición.
La lógica vive en ``proveedores`` y ``diot_catalogos``; aquí solo se validan permisos y entradas."""
from __future__ import annotations

import re
import uuid as _uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from .. import diot_catalogos, proveedores
from ..deps import empresa_or_404, get_current_user, validar_acceso_empresa

router = APIRouter(tags=["Proveedores"])

_BASE = "/api/v1/empresas/{empresa_id}/proveedores"
_PAIS_RE = re.compile(r"[A-Z]{3}")


def _codigo(valor: Optional[str]) -> Optional[str]:
    if valor is None or valor == "":
        return None
    if not (len(valor) == 2 and valor.isdigit()):
        raise ValueError("debe ser un código de dos dígitos")
    return valor


def _pais(valor: Optional[str]) -> Optional[str]:
    if valor is None or valor == "":
        return None
    valor = valor.strip().upper()
    if not _PAIS_RE.fullmatch(valor):
        raise ValueError("debe ser una clave ISO 3166-1 de tres letras")
    return valor


class _Campos(BaseModel):
    tipo_tercero: Optional[str] = None
    tipo_operacion: Optional[str] = None
    pais: Optional[str] = None
    jurisdiccion_detalle: Optional[str] = Field(None, max_length=300)
    id_fiscal: Optional[str] = Field(None, max_length=40)
    efectos_fiscales: Optional[bool] = None

    @field_validator("tipo_tercero", "tipo_operacion")
    @classmethod
    def _codigos(cls, valor: Optional[str]) -> Optional[str]:
        return _codigo(valor)

    @field_validator("pais")
    @classmethod
    def _clave_pais(cls, valor: Optional[str]) -> Optional[str]:
        return _pais(valor)


class ProveedorIn(_Campos):
    rfc: str = Field(..., min_length=1, max_length=30)
    nombre: str = Field("", max_length=300)


class ProveedorPatch(_Campos):
    nombre: Optional[str] = Field(None, max_length=300)
    nombre_editado: Optional[bool] = Field(None, description="false devuelve el nombre a la alimentación automática")

    @field_validator("nombre", "nombre_editado", mode="before")
    @classmethod
    def _no_nulo(cls, valor, info):
        if valor is None:
            raise ValueError("no puede ser nulo; omite el campo para no cambiarlo")
        return valor


def _rfc_o_422(rfc: str) -> str:
    rfc = proveedores.rfc_normalizado(rfc)
    if not diot_catalogos.es_rfc_valido(rfc):
        raise HTTPException(status_code=422, detail="RFC inválido")
    return rfc


def _errores_o_422(prov: dict) -> None:
    errores = diot_catalogos.validar(prov)
    if errores:
        raise HTTPException(status_code=422, detail="; ".join(errores))


def _id_o_404(proveedor_id: str) -> str:
    try:
        return str(_uuid.UUID(proveedor_id))
    except ValueError:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")


@router.get(_BASE)
async def listar_proveedores(
    empresa_id: str,
    q: Optional[str] = Query(None, max_length=100, description="Busca en RFC, nombre e ID fiscal"),
    current_user: dict = Depends(get_current_user),
):
    """Proveedores de la empresa. **Escribe**: antes de listar agrega los emisores de los CFDI recibidos que falten
    (`agregados`) y lo deja en la auditoría; un RFC con formato inválido no entra (`omitidos`)."""
    validar_acceso_empresa(empresa_id, current_user)
    empresa = empresa_or_404(empresa_id)
    sincronizado = proveedores.sincronizar(empresa_id, empresa["rfc"], current_user["user_id"])
    items = proveedores.listar(empresa_id, q)
    return {"total": len(items), **sincronizado, "items": items}


@router.post(_BASE, status_code=201)
async def crear_proveedor(empresa_id: str, datos: ProveedorIn, current_user: dict = Depends(get_current_user)):
    validar_acceso_empresa(empresa_id, current_user)
    rfc = _rfc_o_422(datos.rfc)
    campos = datos.model_dump(exclude={"rfc"})
    _errores_o_422({"rfc": rfc, **campos})
    campos["tipo_operacion"] = campos["tipo_operacion"] or diot_catalogos.OPERACION_POR_DEFECTO
    try:
        return proveedores.crear(empresa_id, rfc, campos, current_user["user_id"])
    except proveedores.Duplicado:
        raise HTTPException(status_code=409, detail="El proveedor ya existe")


@router.patch(_BASE + "/{proveedor_id}")
async def editar_proveedor(empresa_id: str, proveedor_id: str, datos: ProveedorPatch,
                           current_user: dict = Depends(get_current_user)):
    validar_acceso_empresa(empresa_id, current_user)
    proveedor_id = _id_o_404(proveedor_id)
    cambios = datos.model_dump(exclude_unset=True)
    if set(cambios) & {"tipo_tercero", "tipo_operacion", "pais", "id_fiscal"}:
        resultante = proveedores.estado_para_validar(empresa_id, proveedor_id, cambios)
        if resultante is None:
            raise HTTPException(status_code=404, detail="Proveedor no encontrado")
        _errores_o_422(resultante)
    try:
        actualizado = proveedores.actualizar(empresa_id, proveedor_id, cambios, current_user["user_id"])
    except proveedores.Duplicado:
        raise HTTPException(status_code=409, detail="Ya existe un proveedor extranjero con ese ID fiscal")
    if actualizado is None:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    return actualizado
