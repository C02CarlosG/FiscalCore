"""
Router de suscripción (M7.1, carril D): plan de la cuenta, catálogo de planes y, para el
administrador de la plataforma, asignación manual y edición de planes. Sin cobro en
línea (decisión de Carlos, 2026-10-04).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from .. import db
from .. import suscripcion as s
from .. import suscripcion_datos as datos
from .. import suscripcion_pagos as sp
from ..auditoria import registrar_evento
from ..deps import get_current_user, require_admin

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


@router.get("/pagos")
async def mis_pagos(current_user: dict = Depends(get_current_user)):
    """Pagos de mi suscripción registrados por el administrador, del más reciente al más antiguo."""
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
                hoy),
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
                     metadata={"rfc": fiscales["rfc"], "regimen_fiscal": fiscales["regimen_fiscal"]})
    return guardado


@router.get("/admin/cuentas/{usuario_id}/pagos")
async def pagos_de_cuenta(usuario_id: uuid.UUID, _admin: dict = Depends(require_admin)):
    return datos.pagos(_cuenta_existe(usuario_id), con_internos=True)


@router.post("/admin/cuentas/{usuario_id}/pagos", status_code=201)
async def registrar_pago(usuario_id: uuid.UUID, cuerpo: dict = Body(...), admin: dict = Depends(require_admin)):
    """Registra un pago recibido fuera de la plataforma (D10: sin cobro en línea)."""
    uid = _cuenta_existe(usuario_id)
    try:
        pago = sp.validar_pago(cuerpo, datos.hoy())
    except s.DatoInvalido as e:
        raise _422(e)
    fila = datos.registrar_pago(uid, pago, admin["user_id"])
    registrar_evento(admin["user_id"], "suscripcion.registrar_pago", entidad="usuario", entidad_id=uid,
                     metadata={"pago": fila["id"], "fecha": fila["fecha"], "monto": fila["monto"],
                               "folio_cfdi": fila["folio_cfdi"]})
    return fila


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
