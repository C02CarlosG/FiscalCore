"""
Router «Reiniciar datos» (carril D): previsualizar y confirmar el borrado de los datos
operativos de una empresa. Solo administradores de la empresa o de la plataforma, con
doble confirmación (token de un solo uso, frase con el RFC y contraseña) y auditoría.
Spec: docs/superpowers/specs/2026-10-06-reinicio-datos-design.md.

Sin `from __future__ import annotations`: slowapi lee las anotaciones del endpoint.
"""
import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from .. import db
from .. import reinicio_empresa as re_
from .. import usuarios_empresa as ue
from ..auditoria import registrar_evento
from ..deps import get_current_user, limiter, verify_password
from .cuenta import _SQL_MIEMBROS, _clave_usuario, _empresa_visible, _metadata, _rol_plataforma

router = APIRouter(prefix="/api/v1/reinicio/empresas/{empresa_id}", tags=["Reinicio"])


def _administrador(empresa_id: uuid.UUID, current_user: dict) -> tuple[str, bool, str]:
    """(empresa_id, vía admin de plataforma, RFC). 403 si no administra la empresa."""
    eid, via_admin = _empresa_visible(empresa_id, current_user)
    roles = ue.roles_efectivos(db.query_all(_SQL_MIEMBROS, (eid,)))
    if not ue.puede_administrar(current_user["user_id"], roles, _rol_plataforma(current_user)):
        raise HTTPException(status_code=403, detail="Solo un administrador de la empresa puede reiniciar sus datos")
    rfc = db.query_one("SELECT rfc FROM empresas WHERE id = %s", (eid,))["rfc"]
    return eid, via_admin, rfc


@router.post("/previsualizar")
async def previsualizar(empresa_id: uuid.UUID, cuerpo: dict = Body(...),
                        current_user: dict = Depends(get_current_user)):
    """Paso 1: conteos de lo que se borraría, la frase a teclear y el token (10 minutos)."""
    eid, via_admin, rfc = _administrador(empresa_id, current_user)
    try:
        re_.validar_alcance(cuerpo.get("alcance"))
        resultado = re_.previsualizar(eid, current_user["user_id"])
    except re_.ReinicioInvalido as e:
        raise HTTPException(status_code=422, detail=str(e))
    except re_.EmpresaDemasiadoGrande as e:
        raise HTTPException(status_code=409, detail=str(e))
    registrar_evento(current_user["user_id"], "empresa.reiniciar_previsualizar", empresa_id=eid, entidad="empresa",
                     entidad_id=eid, metadata=_metadata(via_admin, {"alcance": "todo", "conteos": resultado["conteos"]}))
    return {**resultado, "frase": re_.frase(rfc)}


@router.post("/confirmar")
@limiter.limit("5/minute", key_func=_clave_usuario)  # exige la contraseña: se limita como un login
async def confirmar(request: Request, empresa_id: uuid.UUID, cuerpo: dict = Body(...),
                    current_user: dict = Depends(get_current_user)):
    """Paso 2: con el token, la frase exacta y la contraseña actual, borra en una transacción."""
    eid, via_admin, rfc = _administrador(empresa_id, current_user)
    token, contrasena = cuerpo.get("token"), cuerpo.get("contrasena")
    if not isinstance(token, str) or not token:
        raise HTTPException(status_code=400, detail="Falta el token de confirmación: vuelve a previsualizar")
    if not re_.frase_correcta(cuerpo.get("frase"), rfc):
        raise HTTPException(status_code=400, detail=f"Escribe exactamente «{re_.frase(rfc)}» para confirmar")
    usuario = db.query_one("SELECT password_hash FROM usuarios WHERE id = %s", (current_user["user_id"],))
    if not isinstance(contrasena, str) or not usuario or not verify_password(contrasena, usuario["password_hash"]):
        raise HTTPException(status_code=403, detail="Contraseña incorrecta")
    try:
        resultado = re_.ejecutar(eid, current_user["user_id"], token)
    except re_.ReinicioInvalido as e:
        raise HTTPException(status_code=400, detail=str(e))
    except re_.TokenYaUsado as e:
        raise HTTPException(status_code=409, detail=str(e))
    registrar_evento(current_user["user_id"], "empresa.reiniciar", empresa_id=eid, entidad="empresa", entidad_id=eid,
                     metadata=_metadata(via_admin, {"alcance": "todo", **resultado}))
    return resultado
