# backend/schemas.py
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, field_validator


class EmpresaCreate(BaseModel):
    rfc: str
    razon_social: str
    regimen_fiscal: Optional[str] = None
    email: Optional[str] = None

    @field_validator("rfc")
    @classmethod
    def rfc_upper(cls, v: str) -> str:
        return v.strip().upper()


class IngestaResponse(BaseModel):
    mensaje: str
    registros_procesados: int
    errores: list[str]
    periodo: Optional[str]


class RegisterRequest(BaseModel):
    email: str
    password: str
    nombre: Optional[str] = None


class AgregarEmpresaRequest(BaseModel):
    rfc: str
    razon_social: str
    regimen_fiscal: Optional[str] = None
    cp_fiscal: Optional[str] = None
    curp: Optional[str] = None
    obligaciones: Optional[list] = None
    representante_legal: Optional[str] = None
    rfc_representante: Optional[str] = None

    @field_validator("rfc")
    @classmethod
    def rfc_upper(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("rfc_representante", mode="before")
    @classmethod
    def rfc_rep_upper(cls, v):
        return v.strip().upper() if v else v


class LoginRequest(BaseModel):
    email: str
    password: str


class ActualizarPerfilRequest(BaseModel):
    nombre:             Optional[str] = None
    telefono:           Optional[str] = None
    rfc:                Optional[str] = None
    nombre_despacho:    Optional[str] = None
    cedula_profesional: Optional[str] = None

    @field_validator("rfc", mode="before")
    @classmethod
    def rfc_upper(cls, v):
        return v.strip().upper() if v else v


class AccionRequest(BaseModel):
    tipo: str
    notas: Optional[str] = None
