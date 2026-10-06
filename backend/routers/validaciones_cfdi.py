"""
Router de validaciones de CFDI (V1, carril D): tarjetas con conteo del periodo y del
acumulado, lista de CFDI de cada tarjeta y configuración por empresa.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from .. import db
from .. import validaciones_cfdi as v
from .. import validaciones_cfdi_datos as datos
from ..auditoria import registrar_evento
from ..deps import get_current_user, serializar, validar_acceso_empresa

router = APIRouter(
    prefix="/api/v1/validaciones-cfdi/empresas/{empresa_id}",
    tags=["Validaciones de CFDI"],
)


def _empresa(empresa_id: uuid.UUID, current_user: dict) -> dict:
    validar_acceso_empresa(str(empresa_id), current_user)
    empresa = db.query_one("SELECT id, rfc FROM empresas WHERE id = %s", (str(empresa_id),))
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    return empresa


def _o_422(funcion, *args):
    try:
        return funcion(*args)
    except v.ValidacionInvalida as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("")
async def resumen(
    empresa_id: uuid.UUID,
    periodo: str = Query(..., description="YYYY-MM"),
    current_user: dict = Depends(get_current_user),
):
    """Una tarjeta por validación y dirección; las inactivas traen conteos null."""
    empresa = _empresa(empresa_id, current_user)
    _o_422(v.rangos, periodo)
    config = datos.leer_configuracion(str(empresa_id))
    resultado = {"periodo": periodo, "configuracion": config.a_json()}
    for direccion in v.DIRECCIONES:
        conteos = datos.contar(str(empresa_id), empresa["rfc"], direccion, periodo, config)
        resultado[direccion] = [
            {
                "clave": x.clave, "titulo": x.titulo, "descripcion": x.descripcion, "tipo": x.tipo,
                "activa": config.activa(x.clave),
                "periodo": conteos.get(x.clave, (None, None))[0],
                "acumulado": conteos.get(x.clave, (None, None))[1],
            }
            for x in v.de_direccion(direccion)
        ]
    return resultado


@router.get("/cfdis")
async def cfdis(
    empresa_id: uuid.UUID,
    periodo: str = Query(..., description="YYYY-MM"),
    direccion: str = Query(...),
    validacion: str = Query(...),
    alcance: str = Query("periodo"),
    current_user: dict = Depends(get_current_user),
):
    """CFDI que componen una tarjeta (hasta 500, por fecha de emisión)."""
    empresa = _empresa(empresa_id, current_user)
    _o_422(v.rangos, periodo)
    _o_422(v.validar_direccion, direccion)
    _o_422(v.validar_validacion, validacion, direccion)
    _o_422(v.validar_alcance, alcance)
    config = datos.leer_configuracion(str(empresa_id))
    resultado = datos.listar(str(empresa_id), empresa["rfc"], direccion, validacion, alcance, periodo, config)
    return {"cfdis": [serializar(f) for f in resultado["cfdis"]], "total_filas": resultado["total_filas"]}


@router.get("/configuracion")
async def leer_configuracion(empresa_id: uuid.UUID, current_user: dict = Depends(get_current_user)):
    _empresa(empresa_id, current_user)
    return datos.leer_configuracion(str(empresa_id)).a_json()


@router.put("/configuracion")
async def guardar_configuracion(
    empresa_id: uuid.UUID,
    cuerpo: dict = Body(...),
    current_user: dict = Depends(get_current_user),
):
    """Validaciones apagadas y umbral de efectivo. Lo que no se manda vuelve al valor por defecto."""
    _empresa(empresa_id, current_user)
    config = _o_422(v.validar_cambio, cuerpo)
    datos.guardar_configuracion(str(empresa_id), config, current_user["user_id"])
    registrar_evento(
        current_user["user_id"], "validaciones_cfdi.configurar", empresa_id=str(empresa_id),
        entidad="validaciones_cfdi_config", entidad_id=str(empresa_id), metadata=config.a_json(),
    )
    return config.a_json()
