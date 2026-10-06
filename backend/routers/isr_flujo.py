"""ISR base flujo (F7.1): flujo del mes y acumulado, detalle de lo que compone cada cifra, porcentaje de nómina exenta y
ajustes manuales (no considerar) con auditoría. El cálculo vive en ``isr_flujo`` (puro) e ``isr_flujo_datos`` (SQL)."""
from __future__ import annotations

import re
from decimal import Decimal
from io import BytesIO
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from .. import db, isr_flujo, isr_flujo_datos, isr_flujo_exportacion, isr_pago_provisional
from ..auditoria import registrar_evento
from ..deps import empresa_or_404, get_current_user, validar_acceso_empresa

router = APIRouter(tags=["ISR por flujo"])

_BASE = "/api/v1/empresas/{empresa_id}/isr-flujo"
_PERIODO_RE = re.compile(r"20[0-9]{2}-(0[1-9]|1[0-2])")
_UUID_MAX = 36
MAX_FILAS_EXPORTACION = 50_000


class AjusteIn(BaseModel):
    uuid: str = Field(..., min_length=1, max_length=_UUID_MAX)
    lado: Literal["ingreso", "deduccion"]
    motivo: str = Field(..., max_length=500, description="Obligatorio: queda en la auditoría")

    @field_validator("motivo")
    @classmethod
    def _motivo_con_texto(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("el motivo es obligatorio")
        return valor


class ConfigIn(BaseModel):
    pct_nomina_exenta: Decimal = Field(..., description="0.47 por defecto; 0.53 si se acredita la no disminución")
    ptu_pagada: Optional[Decimal] = Field(None, ge=0, le=Decimal("9999999999999.99"), description="PTU pagada en el ejercicio")
    perdidas_pendientes: Optional[Decimal] = Field(None, ge=0, le=Decimal("9999999999999.99"),
                                                   description="Pérdidas fiscales de ejercicios anteriores por aplicar")

    arrendamiento_periodicidad: Optional[Literal["mensual", "trimestral"]] = Field(
        None, description="606: pago provisional mensual o trimestral (ingresos de hasta 10 UMA mensuales)")
    deduccion_opcional_35: Optional[bool] = Field(None, description="606: deducción opcional del 35 % (Art. 115), sin comprobantes")

    @field_validator("ptu_pagada", "perdidas_pendientes")
    @classmethod
    def _centavos(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v != v.quantize(Decimal("0.01")):
            raise ValueError("máximo dos decimales")
        return v

    @field_validator("pct_nomina_exenta")
    @classmethod
    def _solo_47_o_53(cls, v: Decimal) -> Decimal:
        if v not in (Decimal("0.47"), Decimal("0.53")):
            raise ValueError("Solo se admite 0.47 o 0.53")
        return v


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


def _ejercicio_o_422(ejercicio: int) -> int:
    if not 2000 <= ejercicio <= 2099:
        raise HTTPException(status_code=422, detail="ejercicio inválido")
    return ejercicio


# Las rutas fijas (config, ajustes) van antes que /{periodo}.

@router.get(_BASE + "/config/{ejercicio}")
async def leer_config(empresa_id: str, ejercicio: int, current_user: dict = Depends(get_current_user)):
    validar_acceso_empresa(empresa_id, current_user)
    _ejercicio_o_422(ejercicio)
    return _json({"ejercicio": ejercicio, "pct_nomina_exenta": isr_flujo_datos.porcentaje_nomina_exenta(empresa_id, ejercicio),
                  **isr_flujo_datos.parametros_provisional(empresa_id, ejercicio)})


@router.put(_BASE + "/config/{ejercicio}")
async def guardar_config(empresa_id: str, ejercicio: int, datos: ConfigIn, current_user: dict = Depends(get_current_user)):
    """Cambia el porcentaje deducible de la nómina exenta del ejercicio y lo audita."""
    validar_acceso_empresa(empresa_id, current_user)
    _ejercicio_o_422(ejercicio)
    pct = datos.pct_nomina_exenta
    isr_flujo_datos.guardar_porcentaje(empresa_id, ejercicio, pct, current_user["user_id"], datos.ptu_pagada, datos.perdidas_pendientes,
                                       datos.arrendamiento_periodicidad, datos.deduccion_opcional_35)
    return _json({"ejercicio": ejercicio, "pct_nomina_exenta": pct, **isr_flujo_datos.parametros_provisional(empresa_id, ejercicio)})


@router.get(_BASE + "/ajustes")
async def listar_ajustes(empresa_id: str, current_user: dict = Depends(get_current_user)):
    validar_acceso_empresa(empresa_id, current_user)
    filas = db.query_all(
        """SELECT cfdi_uuid AS uuid, lado, motivo, created_at, updated_at
           FROM isr_ajustes WHERE empresa_id = %s ORDER BY updated_at DESC LIMIT 500""",
        (empresa_id,),
    )
    return {"items": [{**f, "created_at": f["created_at"].isoformat(), "updated_at": f["updated_at"].isoformat()} for f in filas]}


@router.put(_BASE + "/ajustes")
async def guardar_ajuste(empresa_id: str, datos: AjusteIn, current_user: dict = Depends(get_current_user)):
    """«No considerar ISR» en un CFDI y lado: sale de las sumas y queda auditado."""
    validar_acceso_empresa(empresa_id, current_user)
    empresa = empresa_or_404(empresa_id)
    cfdi = db.query_one(
        """SELECT uuid, tipo_comprobante, rfc_emisor, rfc_receptor
           FROM cfdi WHERE empresa_id = %s AND UPPER(uuid) = UPPER(%s) AND estado = 'vigente'""",
        (empresa_id, datos.uuid),
    )
    rfc = empresa["rfc"]
    propio = cfdi and (
        (datos.lado == "ingreso" and cfdi["rfc_emisor"] == rfc and cfdi["tipo_comprobante"] in ("I", "E"))
        or (datos.lado == "deduccion" and cfdi["tipo_comprobante"] in ("I", "E", "N")
            and (cfdi["rfc_receptor"] == rfc or (cfdi["tipo_comprobante"] == "N" and cfdi["rfc_emisor"] == rfc)))
    )
    if not propio:
        raise HTTPException(status_code=404, detail="CFDI no encontrado para ese ajuste")
    uuid = cfdi["uuid"].upper()
    isr_flujo_datos.guardar_ajuste(empresa_id, uuid, datos.lado, datos.motivo, current_user["user_id"])
    return {"uuid": uuid, "lado": datos.lado, "accion": "excluir", "motivo": datos.motivo}


@router.delete(_BASE + "/ajustes/{lado}/{uuid}", status_code=204)
async def quitar_ajuste(empresa_id: str, lado: Literal["ingreso", "deduccion"], uuid: str,
                        current_user: dict = Depends(get_current_user)):
    validar_acceso_empresa(empresa_id, current_user)
    if len(uuid) > _UUID_MAX or not isr_flujo_datos.quitar_ajuste(empresa_id, uuid, lado, current_user["user_id"]):
        raise HTTPException(status_code=404, detail="Ajuste no encontrado")


@router.get(_BASE + "/{periodo}")
async def resumen_isr_flujo(empresa_id: str, periodo: str, current_user: dict = Depends(get_current_user)):
    """Flujo de ISR del mes y acumulado del ejercicio: ingresos, deducciones, nómina, retenciones y utilidad fiscal estimada."""
    validar_acceso_empresa(empresa_id, current_user)
    _periodo_o_422(periodo)
    empresa = empresa_or_404(empresa_id)
    ajustes = isr_flujo_datos.cargar_ajustes(empresa_id)
    pct = isr_flujo_datos.porcentaje_nomina_exenta(empresa_id, int(periodo[:4]))
    eventos = isr_flujo_datos.cargar_eventos(empresa_id, empresa["rfc"], periodo)
    resultado = isr_flujo.resumen(eventos, periodo, ajustes, pct)
    registrar_evento(current_user["user_id"], "reporte_generado", empresa_id=empresa_id,
                     metadata={"tipo": "isr_flujo", "periodo": periodo})
    return _json({"empresa_id": empresa_id, "regimen": isr_flujo.aplicabilidad(empresa.get("regimen_fiscal")), **resultado})


@router.get(_BASE + "/{periodo}/pago-provisional")
async def pago_provisional(
    empresa_id: str,
    periodo: str,
    predial: Decimal = Query(Decimal("0"), ge=0, le=Decimal("9999999999999.99"), decimal_places=2,
                             description="606 con la deducción opcional del 35 %: predial pagado en el periodo, que se suma"),
    current_user: dict = Depends(get_current_user),
):
    """Pago provisional del ISR por flujo de efectivo con la tarifa del Anexo 8: 612 (Art. 106, acumulado) y 606
    (Art. 116, del periodo, con deducción opcional del 35 % y retención del 10 %). El 601 usa el coeficiente de utilidad
    (``/isr-provisional/{periodo}``); otros regímenes no se calculan."""
    validar_acceso_empresa(empresa_id, current_user)
    _periodo_o_422(periodo)
    empresa = empresa_or_404(empresa_id)
    regimen = isr_flujo.aplicabilidad(empresa.get("regimen_fiscal"))
    base = {"empresa_id": empresa_id, "periodo": periodo, "regimen": regimen}
    codigo = regimen["codigo"]
    if codigo == "601":
        return _json({**base, "calculado": False, "motivo": "coeficiente",
                      "mensaje": "El régimen 601 calcula el pago provisional con el coeficiente de utilidad (Art. 14 LISR).",
                      "ruta": f"/api/v1/empresas/{empresa_id}/isr-provisional/{periodo}"})
    ejercicio = int(periodo[:4])
    ajustes = isr_flujo_datos.cargar_ajustes(empresa_id)
    pct = isr_flujo_datos.porcentaje_nomina_exenta(empresa_id, ejercicio)
    parametros = isr_flujo_datos.parametros_provisional(empresa_id, ejercicio)
    if codigo == "606":
        eventos = isr_flujo_datos.cargar_eventos(empresa_id, empresa["rfc"], periodo)
        resultado = isr_pago_provisional.pago_provisional_arrendamiento(
            periodo, lambda p: isr_flujo.resumen(eventos, p, ajustes, pct), parametros["arrendamiento_periodicidad"],
            parametros["deduccion_opcional_35"], predial)
        registrar_evento(current_user["user_id"], "reporte_generado", empresa_id=empresa_id,
                         metadata={"tipo": "isr_pago_provisional_arrendamiento", "periodo": periodo})
        return _json({**base, **resultado})
    if codigo != "612":
        return _json({**base, "calculado": False, "motivo": "regimen_no_soportado",
                      "mensaje": "El régimen de la empresa no está soportado para el pago provisional por flujo."})
    eventos = isr_flujo_datos.cargar_eventos(empresa_id, empresa["rfc"], periodo)
    resultado = isr_pago_provisional.pago_provisional_flujo(
        periodo, lambda p: isr_flujo.resumen(eventos, p, ajustes, pct), parametros["ptu_pagada"], parametros["perdidas_pendientes"])
    registrar_evento(current_user["user_id"], "reporte_generado", empresa_id=empresa_id,
                     metadata={"tipo": "isr_pago_provisional", "periodo": periodo})
    return _json({**base, **resultado})


@router.get(_BASE + "/{periodo}/detalle")
async def detalle_isr_flujo(
    empresa_id: str,
    periodo: str,
    lado: Literal["ingreso", "deduccion"] = Query(...),
    bloque: Literal["contado", "credito", "devoluciones", "nomina", "inversiones", "no_considerados"] = Query(...),
    acumulado: bool = Query(False, description="true = acumulado del ejercicio hasta el periodo"),
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(50, ge=1, le=isr_flujo.MAX_POR_PAGINA),
    current_user: dict = Depends(get_current_user),
):
    """Los CFDI que componen una cifra del flujo, con sus marcas y motivo."""
    validar_acceso_empresa(empresa_id, current_user)
    _periodo_o_422(periodo)
    empresa = empresa_or_404(empresa_id)
    ajustes = isr_flujo_datos.cargar_ajustes(empresa_id)
    eventos = isr_flujo_datos.cargar_eventos(empresa_id, empresa["rfc"], periodo)
    return _json(isr_flujo.detalle(eventos, periodo, lado, bloque, ajustes, pagina, por_pagina, acumulado))


@router.get(_BASE + "/{periodo}/exportar")
async def exportar_isr_flujo(
    empresa_id: str,
    periodo: str,
    lado: Literal["ingreso", "deduccion"] = Query(...),
    bloque: Literal["contado", "credito", "devoluciones", "nomina", "inversiones", "no_considerados"] = Query(...),
    acumulado: bool = Query(False),
    current_user: dict = Depends(get_current_user),
):
    """Excel con todos los renglones de una cifra y el resumen del mes y del acumulado. Queda en la auditoría."""
    validar_acceso_empresa(empresa_id, current_user)
    _periodo_o_422(periodo)
    empresa = empresa_or_404(empresa_id)
    ajustes = isr_flujo_datos.cargar_ajustes(empresa_id)
    pct = isr_flujo_datos.porcentaje_nomina_exenta(empresa_id, int(periodo[:4]))
    eventos = isr_flujo_datos.cargar_eventos(empresa_id, empresa["rfc"], periodo)
    filas = isr_flujo.renglones(eventos, periodo, lado, bloque, ajustes, acumulado)
    if len(filas) > MAX_FILAS_EXPORTACION:
        raise HTTPException(status_code=422, detail=f"son {len(filas)} renglones; el máximo es {MAX_FILAS_EXPORTACION}")
    contenido = isr_flujo_exportacion.construir(
        periodo, lado, bloque, filas, isr_flujo.resumen(eventos, periodo, ajustes, pct),
        isr_flujo.aplicabilidad(empresa.get("regimen_fiscal")))
    registrar_evento(current_user["user_id"], "isr_flujo_exportado", empresa_id=empresa_id,
                     metadata={"periodo": periodo, "lado": lado, "bloque": bloque, "acumulado": acumulado, "filas": len(filas)})
    return StreamingResponse(
        BytesIO(contenido),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="isr_{lado}_{bloque}_{periodo}.xlsx"'},
    )
