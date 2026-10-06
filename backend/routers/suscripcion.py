"""
Router de suscripción (M7.1, carril D): plan de la cuenta, catálogo de planes y, para el
administrador de la plataforma, asignación manual y edición de planes. Sin cobro en
línea (decisión de Carlos, 2026-10-04).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from .. import db
from .. import suscripcion as s
from .. import suscripcion_datos as datos
from .. import suscripcion_pagos as sp
from ..auditoria import registrar_evento
from ..deps import get_current_user, require_admin


async def configuracion_invalida(_request: Request, exc: s.ConfiguracionInvalida) -> JSONResponse:
    """Un catálogo sin plan por defecto es un problema de configuración, no un 500.
    Se registra en `main_api` para todas las rutas (también cuenta.py al aprobar)."""
    return JSONResponse(status_code=409, content={"detail": f"Configuración de planes inválida: {exc}"})


router = APIRouter(prefix="/api/v1/suscripcion", tags=["Suscripción"])


def _422(e: Exception):
    return HTTPException(status_code=422, detail=str(e))


@router.get("")
async def mi_suscripcion(current_user: dict = Depends(get_current_user)):
    return datos.resumen(current_user["user_id"])


@router.get("/historial")
async def mi_historial(current_user: dict = Depends(get_current_user)):
    """Mis asignaciones de plan (sin las notas internas ni quién las hizo)."""
    return datos.historial(current_user["user_id"], con_notas=False)


@router.get("/datos-fiscales")
async def mis_datos_fiscales(current_user: dict = Depends(get_current_user)):
    """Datos con los que se emite el CFDI de mi suscripción (los captura el administrador)."""
    return datos.datos_fiscales(current_user["user_id"])


@router.put("/datos-fiscales")
async def editar_mis_datos_fiscales(cuerpo: dict = Body(...), current_user: dict = Depends(get_current_user)):
    """La cuenta captura o corrige los datos con los que se emite el CFDI de su suscripción."""
    try:
        fiscales = sp.validar_datos_fiscales(cuerpo)
    except s.DatoInvalido as e:
        raise _422(e)
    guardado = datos.guardar_datos_fiscales(current_user["user_id"], fiscales, current_user["user_id"])
    registrar_evento(current_user["user_id"], "suscripcion.datos_fiscales", entidad="usuario",
                     entidad_id=current_user["user_id"],
                     metadata={"rfc": fiscales["rfc"], "regimen_fiscal": fiscales["regimen_fiscal"], "por": "cuenta"})
    return guardado


@router.get("/pagos")
async def mis_pagos(current_user: dict = Depends(get_current_user)):
    """Pagos de mi suscripción que registró el administrador (también los anulados, con su
    estado), del más reciente al más antiguo; sin quién los registró ni el motivo de anulación."""
    return datos.pagos(current_user["user_id"], con_internos=False)


@router.get("/planes")
async def planes_activos(current_user: dict = Depends(get_current_user)):
    return [datos.plan_publico(p) for p in datos.planes().values() if p["activo"]]


@router.get("/admin/cuentas")
async def cuentas(q: str = Query("", max_length=100), admin: dict = Depends(require_admin)):
    hoy = datos.hoy()
    return [
        {
            "usuario_id": str(f["usuario_id"]), "email": f["email"], "nombre": f.get("nombre"),
            "es_admin_plataforma": f.get("rol") == "admin",
            "plan_clave": f.get("plan_clave"), "estado": f.get("estado"),
            "vigente_hasta": f["vigente_hasta"].isoformat() if f.get("vigente_hasta") else None,
            "notas": f.get("notas"), "uso_rfc": int(f["uso_rfc"]),
            "dias_para_vencer": sp.aviso_vencimiento(
                f.get("vigente_hasta"), None if f.get("estado") == "activa" else (f.get("estado") or "sin_suscripcion"),
                hoy),  # negativo si ya venció
        }
        for f in datos.cuentas(q)
    ]


def _cuenta_existe(usuario_id: uuid.UUID) -> str:
    if not db.query_one("SELECT id FROM usuarios WHERE id = %s", (str(usuario_id),)):
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    return str(usuario_id)


@router.get("/admin/cuentas/{usuario_id}/historial")
async def historial_de_cuenta(usuario_id: uuid.UUID, _admin: dict = Depends(require_admin)):
    return datos.historial(_cuenta_existe(usuario_id), con_notas=True)


@router.get("/admin/cuentas/{usuario_id}/datos-fiscales")
async def datos_fiscales_de_cuenta(usuario_id: uuid.UUID, _admin: dict = Depends(require_admin)):
    return datos.datos_fiscales(_cuenta_existe(usuario_id))


@router.put("/admin/cuentas/{usuario_id}/datos-fiscales")
async def editar_datos_fiscales(usuario_id: uuid.UUID, cuerpo: dict = Body(...), admin: dict = Depends(require_admin)):
    uid = _cuenta_existe(usuario_id)
    try:
        fiscales = sp.validar_datos_fiscales(cuerpo)
    except s.DatoInvalido as e:
        raise _422(e)
    guardado = datos.guardar_datos_fiscales(uid, fiscales, admin["user_id"])
    registrar_evento(admin["user_id"], "suscripcion.datos_fiscales", entidad="usuario", entidad_id=uid,
                     metadata={"rfc": fiscales["rfc"], "regimen_fiscal": fiscales["regimen_fiscal"], "por": "admin"})
    return guardado


@router.get("/admin/cuentas/{usuario_id}/pagos")
async def pagos_de_cuenta(usuario_id: uuid.UUID, _admin: dict = Depends(require_admin)):
    return datos.pagos(_cuenta_existe(usuario_id), con_internos=True)


@router.post("/admin/cuentas/{usuario_id}/pagos", status_code=201)
async def registrar_pago(usuario_id: uuid.UUID, cuerpo: dict = Body(...), admin: dict = Depends(require_admin)):
    """Registra un pago recibido fuera de la plataforma (D10: sin cobro en línea) y extiende
    la vigencia ``meses`` meses en la misma transacción."""
    uid = _cuenta_existe(usuario_id)
    try:
        pago = sp.validar_pago(cuerpo, datos.hoy())
    except s.DatoInvalido as e:
        raise _422(e)
    try:
        fila = datos.registrar_pago(uid, pago, admin["user_id"])
    except datos.SinSuscripcion as e:
        raise HTTPException(status_code=409, detail=str(e))
    registrar_evento(admin["user_id"], "suscripcion.registrar_pago", entidad="usuario", entidad_id=uid,
                     metadata={"pago": fila["id"], "fecha": fila["fecha"], "monto": fila["monto"], "meses": fila["meses"],
                               "vigente_hasta": fila["vigente_hasta_nueva"], "folio_cfdi": fila["folio_cfdi"],
                               "uuid_cfdi": fila["uuid_cfdi"]})
    return fila


@router.post("/admin/cuentas/{usuario_id}/pagos/{pago_id}/anular")
async def anular_pago(usuario_id: uuid.UUID, pago_id: uuid.UUID, cuerpo: dict = Body(...),
                      admin: dict = Depends(require_admin)):
    """Anula un pago (no se borra) y revierte la vigencia si nada la cambió después."""
    uid = _cuenta_existe(usuario_id)
    try:
        motivo = sp.validar_anulacion(cuerpo)
    except s.DatoInvalido as e:
        raise _422(e)
    try:
        resultado = datos.anular_pago(uid, str(pago_id), motivo, admin["user_id"])
    except datos.PagoNoEncontrado:
        raise HTTPException(status_code=404, detail="Pago no encontrado o ya anulado")
    registrar_evento(admin["user_id"], "suscripcion.anular_pago", entidad="usuario", entidad_id=uid,
                     metadata={"pago": str(pago_id), "motivo": motivo, **resultado})
    return resultado


@router.get("/admin/vencimientos")
async def vencimientos(_admin: dict = Depends(require_admin)):
    """Cuentas activas por vencer (15 días o menos) o ya vencidas."""
    return datos.vencimientos(datos.hoy())


@router.put("/admin/cuentas/{usuario_id}")
async def asignar(usuario_id: uuid.UUID, cuerpo: dict = Body(...), admin: dict = Depends(require_admin)):
    if not db.query_one("SELECT id FROM usuarios WHERE id = %s", (str(usuario_id),)):
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    try:
        asignacion = s.validar_asignacion(cuerpo, datos.planes())
    except s.DatoInvalido as e:
        raise _422(e)
    datos.asignar(str(usuario_id), asignacion, admin["user_id"])
    registrar_evento(
        admin["user_id"], "suscripcion.asignar", entidad="usuario", entidad_id=str(usuario_id),
        metadata={**asignacion, "vigente_hasta": asignacion["vigente_hasta"].isoformat() if asignacion["vigente_hasta"] else None},
    )
    return datos.resumen(str(usuario_id))


@router.put("/admin/planes/{clave}")
async def editar_plan(clave: str, cuerpo: dict = Body(...), admin: dict = Depends(require_admin)):
    """Edita un plan (o lo crea si la clave no existe)."""
    try:
        plan = s.validar_plan(clave, cuerpo)
    except s.DatoInvalido as e:
        raise _422(e)
    fila = datos.guardar_plan(plan)
    registrar_evento(
        admin["user_id"], "suscripcion.editar_plan", entidad="plan", entidad_id=clave,
        metadata={**plan, "precio_mensual": str(plan["precio_mensual"])},
    )
    return datos.plan_publico(fila)
