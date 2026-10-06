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


@router.get("/planes")
async def planes_activos(current_user: dict = Depends(get_current_user)):
    return [datos.plan_publico(p) for p in datos.planes().values() if p["activo"]]


@router.get("/admin/cuentas")
async def cuentas(q: str = Query("", max_length=100), admin: dict = Depends(require_admin)):
    return [
        {
            "usuario_id": str(f["usuario_id"]), "email": f["email"], "nombre": f.get("nombre"),
            "es_admin_plataforma": f.get("rol") == "admin",
            "plan_clave": f.get("plan_clave"), "estado": f.get("estado"),
            "vigente_hasta": f["vigente_hasta"].isoformat() if f.get("vigente_hasta") else None,
            "notas": f.get("notas"), "uso_rfc": int(f["uso_rfc"]),
        }
        for f in datos.cuentas(q)
    ]


@router.get("/admin/cuentas/{usuario_id}/historial")
async def historial_de_cuenta(usuario_id: uuid.UUID, _admin: dict = Depends(require_admin)):
    if not db.query_one("SELECT id FROM usuarios WHERE id = %s", (str(usuario_id),)):
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    return datos.historial(str(usuario_id), con_notas=True)


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
