"""Catálogo de proveedores (F6.1): lista alimentada de los CFDI recibidos, alta manual y edición.
La lógica vive en ``proveedores``; aquí solo se validan permisos y entradas."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from .. import proveedores
from ..cfdi_parser import RFC_REGEX
from ..deps import empresa_or_404, get_current_user, serializar, validar_acceso_empresa

router = APIRouter(tags=["Proveedores"])

_BASE = "/api/v1/empresas/{empresa_id}/proveedores"


def _codigo(valor: Optional[str]) -> Optional[str]:
    if valor is None or valor == "":
        return None
    if not (len(valor) == 2 and valor.isdigit()):
        raise ValueError("debe ser un código de dos dígitos")
    return valor


class ProveedorIn(BaseModel):
    rfc: str = Field(..., min_length=1, max_length=30)
    nombre: str = Field("", max_length=300)
    tipo_tercero: Optional[str] = None
    tipo_operacion: Optional[str] = None
    pais: Optional[str] = Field(None, max_length=60)
    id_fiscal: Optional[str] = Field(None, max_length=40)

    @field_validator("tipo_tercero", "tipo_operacion")
    @classmethod
    def _codigos(cls, valor: Optional[str]) -> Optional[str]:
        return _codigo(valor)


class ProveedorPatch(BaseModel):
    nombre: Optional[str] = Field(None, max_length=300)
    tipo_tercero: Optional[str] = None
    tipo_operacion: Optional[str] = None
    pais: Optional[str] = Field(None, max_length=60)
    id_fiscal: Optional[str] = Field(None, max_length=40)

    @field_validator("tipo_tercero", "tipo_operacion")
    @classmethod
    def _codigos(cls, valor: Optional[str]) -> Optional[str]:
        return _codigo(valor)


def _rfc_o_422(rfc: str) -> str:
    rfc = proveedores.rfc_normalizado(rfc)
    if not RFC_REGEX.match(rfc):
        raise HTTPException(status_code=422, detail="RFC inválido")
    return rfc


@router.get(_BASE)
async def listar_proveedores(
    empresa_id: str,
    q: Optional[str] = Query(None, max_length=100, description="Busca en RFC y nombre"),
    current_user: dict = Depends(get_current_user),
):
    """Proveedores de la empresa; antes de listar agrega los emisores de los CFDI recibidos que falten."""
    validar_acceso_empresa(empresa_id, current_user)
    empresa = empresa_or_404(empresa_id)
    agregados = proveedores.sincronizar(empresa_id, empresa["rfc"])
    items = proveedores.listar(empresa_id, q)
    return {"total": len(items), "agregados": agregados, "items": [serializar(i) for i in items]}


@router.post(_BASE, status_code=201)
async def crear_proveedor(empresa_id: str, datos: ProveedorIn, current_user: dict = Depends(get_current_user)):
    validar_acceso_empresa(empresa_id, current_user)
    rfc = _rfc_o_422(datos.rfc)
    creado = proveedores.crear(empresa_id, rfc, datos.model_dump(exclude={"rfc"}), current_user["user_id"])
    if creado is None:
        raise HTTPException(status_code=409, detail="El proveedor ya existe")
    return serializar(creado)


@router.patch(_BASE + "/{rfc}")
async def editar_proveedor(empresa_id: str, rfc: str, datos: ProveedorPatch, current_user: dict = Depends(get_current_user)):
    validar_acceso_empresa(empresa_id, current_user)
    actualizado = proveedores.actualizar(
        empresa_id, _rfc_o_422(rfc), datos.model_dump(exclude_unset=True), current_user["user_id"])
    if actualizado is None:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    return serializar(actualizado)
