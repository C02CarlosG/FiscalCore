"""
Router de cuenta (U1, carril D): cambio de contraseña, usuarios de una empresa con su
rol e invitaciones. El perfil se edita con `GET /auth/me` y `PATCH /usuarios/perfil`
(carril B). Las reglas viven en `backend/usuarios_empresa.py`.

El acceso de otra persona a una empresa se da **por invitación**: el administrador
invita un correo y la persona la acepta desde su perfil. La respuesta es la misma
exista o no una cuenta con ese correo (no se revela ni su nombre) y nadie queda
vinculado a una empresa sin su consentimiento.

NOTA: sin `from __future__ import annotations`: hay endpoints envueltos por
@limiter.limit (slowapi) y FastAPI no resolvería los forward-refs (ver routers/sat.py).
"""
import uuid
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .. import db
from .. import usuarios_empresa as ue
from .. import suscripcion_datos
from ..auditoria import registrar_evento
from ..deps import get_current_user, hash_password, limiter, validar_acceso_empresa, verificar_token, verify_password

router = APIRouter(prefix="/api/v1/cuenta", tags=["Cuenta"])


def _clave_usuario(request: Request) -> str:
    """Clave del límite de frecuencia: el usuario autenticado, no la IP (varias personas
    de un despacho comparten IP y una sola cuenta no debe esquivarlo cambiando de red)."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        try:
            return "usuario:" + str(verificar_token(auth[7:]).get("user_id"))
        except Exception:
            pass
    return "ip:" + (request.client.host if request.client else "desconocida")


class CambioContrasena(BaseModel):
    actual: str = Field(..., max_length=128)
    nueva: str = Field(..., max_length=128)


class Invitacion(BaseModel):
    email: str = Field(..., max_length=320)
    rol: str


class CambioRol(BaseModel):
    rol: str


def _422(e: Exception):
    return HTTPException(status_code=422, detail=str(e))


def _404_miembro():
    return HTTPException(status_code=404, detail="Ese usuario no tiene acceso a la empresa")


# ─── Contraseña ──────────────────────────────────────────────────────────────

@router.post("/contrasena", status_code=204)
@limiter.limit("5/minute", key_func=_clave_usuario)  # exige la contraseña actual: mismo cuidado que el login
async def cambiar_contrasena(
    request: Request,
    cuerpo: CambioContrasena,
    current_user: dict = Depends(get_current_user),
):
    usuario = db.query_one("SELECT password_hash FROM usuarios WHERE id = %s", (current_user["user_id"],))
    if not usuario or not verify_password(cuerpo.actual, usuario["password_hash"]):
        raise HTTPException(status_code=400, detail="La contraseña actual no es correcta")
    try:
        ue.validar_contrasena(cuerpo.nueva, actual=cuerpo.actual)
    except ue.DatoInvalido as e:
        raise _422(e)
    db.execute(
        "UPDATE usuarios SET password_hash = %s, updated_at = NOW() WHERE id = %s",
        (hash_password(cuerpo.nueva), current_user["user_id"]),
    )
    registrar_evento(current_user["user_id"], "cuenta.cambiar_contrasena", entidad="usuario",
                     entidad_id=current_user["user_id"])
    return Response(status_code=204)


# ─── Contexto de una empresa ─────────────────────────────────────────────────

_SQL_MIEMBROS = """
    SELECT ue.usuario_id, ue.rol, ue.created_at, u.email, u.nombre
    FROM usuario_empresas ue
    JOIN usuarios u ON u.id = ue.usuario_id
    WHERE ue.empresa_id = %s
    ORDER BY ue.created_at NULLS LAST, ue.usuario_id
"""


def _rol_plataforma(current_user: dict) -> str:
    return (db.query_one("SELECT rol FROM usuarios WHERE id = %s", (current_user["user_id"],)) or {}).get("rol")


def _empresa_visible(empresa_id: uuid.UUID, current_user: dict) -> tuple[str, bool]:
    """Valida el acceso: miembro de la empresa o administrador de la plataforma.

    Devuelve (empresa_id, actúa como administrador de plataforma sin ser miembro).
    """
    eid = str(empresa_id)
    es_admin_plataforma = _rol_plataforma(current_user) == "admin"
    if not es_admin_plataforma:
        validar_acceso_empresa(eid, current_user)
    if not db.query_one("SELECT id FROM empresas WHERE id = %s", (eid,)):
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    es_miembro = bool(db.query_one(
        "SELECT 1 AS x FROM usuario_empresas WHERE empresa_id = %s AND usuario_id = %s",
        (eid, current_user["user_id"]),
    ))
    return eid, es_admin_plataforma and not es_miembro


def _metadata(via_admin: bool, extra: dict = None) -> dict:
    datos = dict(extra or {})
    if via_admin:
        datos["via_admin_plataforma"] = True
    return datos


@contextmanager
def _miembros_bloqueados(eid: str):
    """Lee los vínculos de la empresa con ``FOR UPDATE`` dentro de una transacción.

    Dos administradores que se quitan o degradan al mismo tiempo se serializan: el
    segundo vuelve a leer los vínculos ya cambiados y la regla del último
    administrador se evalúa sobre ellos.
    """
    with db.get_conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT usuario_id, rol, created_at FROM usuario_empresas WHERE empresa_id = %s "
            "ORDER BY created_at NULLS LAST, usuario_id FOR UPDATE",
            (eid,),
        )
        miembros = [dict(f) for f in cur.fetchall()]
        yield cur, miembros, ue.roles_efectivos(miembros)


def _fijar_administradores(cur, eid: str, miembros: list, roles: dict) -> list:
    """Guarda como explícito al administrador implícito (primer vinculado sin marcar).

    Sin esto, al nombrar a otro administrador el creador dejaría de serlo: la regla del
    primer vinculado solo aplica cuando no hay ninguno marcado. Devuelve a quién promovió.
    """
    promovidos = []
    for m in miembros:
        uid = str(m["usuario_id"])
        if roles.get(uid) == "administrador" and m["rol"] != "administrador":
            cur.execute("UPDATE usuario_empresas SET rol = 'administrador' WHERE empresa_id = %s AND usuario_id = %s",
                        (eid, uid))
            promovidos.append(uid)
    return promovidos


def _verificar_plan(cur, usuario_id: str, current_user: dict) -> None:
    """Quien pasa a administrar la empresa la suma a su uso de RFC (M7.1): se revisa su
    plan con el candado por cuenta, en la misma transacción que crea o cambia el vínculo."""
    try:
        suscripcion_datos.verificar_alta_rfc(cur, usuario_id, de_tercero=str(usuario_id) != str(current_user["user_id"]))
    except suscripcion_datos.LimiteRfcAlcanzado as e:
        raise HTTPException(status_code=403, detail=str(e))


def _exigir_administrador(current_user: dict, roles: dict, rol_plataforma: str) -> None:
    if not ue.puede_administrar(current_user["user_id"], roles, rol_plataforma):
        raise HTTPException(status_code=403, detail="Solo un administrador de la empresa puede gestionar usuarios")


def _usuario(m: dict, roles: dict, yo: str) -> dict:
    uid = str(m["usuario_id"])
    return {
        "usuario_id": uid, "email": m["email"], "nombre": m.get("nombre"),
        "rol": roles.get(uid, m.get("rol")), "desde": m["created_at"].isoformat() if m.get("created_at") else None,
        "soy_yo": uid == str(yo),
    }


def _invitacion(f: dict) -> dict:
    return {
        "id": str(f["id"]), "email": f["email"], "rol": f["rol"], "estado": f["estado"],
        "creada": f["created_at"].isoformat() if f.get("created_at") else None,
    }


# ─── Usuarios de una empresa ─────────────────────────────────────────────────

@router.get("/empresas/{empresa_id}/usuarios")
async def listar_usuarios(empresa_id: uuid.UUID, current_user: dict = Depends(get_current_user)):
    eid, _via_admin = _empresa_visible(empresa_id, current_user)
    miembros = db.query_all(_SQL_MIEMBROS, (eid,))
    roles = ue.roles_efectivos(miembros)
    yo = current_user["user_id"]
    puede = ue.puede_administrar(yo, roles, _rol_plataforma(current_user))
    invitaciones, por_aprobar = [], []
    if puede:
        invitaciones = db.query_all(
            "SELECT id, email, rol, estado, created_at FROM invitaciones_empresa "
            "WHERE empresa_id = %s AND estado = 'pendiente' AND expires_at > NOW() ORDER BY created_at",
            (eid,),
        )
        # Aceptaciones que esperan la aprobación de un administrador: se muestran el
        # nombre y el correo de la cuenta que aceptó y cuándo se creó esa cuenta, para
        # reconocer a quien se registró con un correo ajeno.
        por_aprobar = db.query_all(
            """
            SELECT i.id, i.email AS email_invitado, i.rol, i.respondida_at, u.nombre, u.email AS email_cuenta,
                   u.created_at AS cuenta_creada
            FROM invitaciones_empresa i
            JOIN usuarios u ON u.id = i.respondida_por
            WHERE i.empresa_id = %s AND i.estado = 'aceptada_pendiente' AND i.expires_at > NOW()
            ORDER BY i.respondida_at
            """,
            (eid,),
        )
    return {
        "mi_rol": roles.get(str(yo)),
        "puede_administrar": puede,
        "usuarios": [_usuario(m, roles, yo) for m in miembros],
        "invitaciones": [_invitacion(f) for f in invitaciones],
        "por_aprobar": [
            {
                "id": str(f["id"]), "email": f["email_cuenta"], "email_invitado": f["email_invitado"],
                "nombre": f.get("nombre"), "rol": f["rol"],
                "cuenta_creada": f["cuenta_creada"].isoformat() if f.get("cuenta_creada") else None,
                "aceptada": f["respondida_at"].isoformat() if f.get("respondida_at") else None,
            }
            for f in por_aprobar
        ],
    }


@router.patch("/empresas/{empresa_id}/usuarios/{usuario_id}")
async def cambiar_rol(
    empresa_id: uuid.UUID,
    usuario_id: uuid.UUID,
    cuerpo: CambioRol,
    current_user: dict = Depends(get_current_user),
):
    eid, via_admin = _empresa_visible(empresa_id, current_user)
    rol_plataforma = _rol_plataforma(current_user)
    try:
        rol = ue.validar_rol(cuerpo.rol)
    except ue.DatoInvalido as e:
        raise _422(e)
    with _miembros_bloqueados(eid) as (cur, miembros, roles):
        _exigir_administrador(current_user, roles, rol_plataforma)
        try:
            ue.validar_cambio_rol(roles, str(usuario_id), rol)
        except ue.NoEsMiembro:
            raise _404_miembro()
        except ue.UltimoAdministrador as e:
            raise HTTPException(status_code=409, detail=str(e))
        if rol == "administrador" and roles.get(str(usuario_id)) != "administrador":
            _verificar_plan(cur, str(usuario_id), current_user)
        promovidos = _fijar_administradores(cur, eid, miembros, roles)
        cur.execute("UPDATE usuario_empresas SET rol = %s WHERE empresa_id = %s AND usuario_id = %s",
                    (rol, eid, str(usuario_id)))
        anterior = roles.get(str(usuario_id))
    registrar_evento(
        current_user["user_id"], "cuenta.cambiar_rol", empresa_id=eid, entidad="usuario",
        entidad_id=str(usuario_id),
        metadata=_metadata(via_admin, {"de": anterior, "a": rol, "administradores_fijados": promovidos}),
    )
    miembro = next((m for m in db.query_all(_SQL_MIEMBROS, (eid,)) if str(m["usuario_id"]) == str(usuario_id)), None)
    if miembro is None:  # lo quitaron entre la escritura y esta lectura
        raise _404_miembro()
    return _usuario(miembro, {str(usuario_id): rol}, current_user["user_id"])


@router.delete("/empresas/{empresa_id}/usuarios/{usuario_id}", status_code=204)
async def quitar_usuario(
    empresa_id: uuid.UUID,
    usuario_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
):
    """Quita el acceso a la empresa; la cuenta de la persona no se borra."""
    eid, via_admin = _empresa_visible(empresa_id, current_user)
    rol_plataforma = _rol_plataforma(current_user)
    with _miembros_bloqueados(eid) as (cur, miembros, roles):
        _exigir_administrador(current_user, roles, rol_plataforma)
        try:
            ue.validar_baja(roles, str(usuario_id))
        except ue.NoEsMiembro:
            raise _404_miembro()
        except ue.UltimoAdministrador as e:
            raise HTTPException(status_code=409, detail=str(e))
        promovidos = _fijar_administradores(cur, eid, miembros, roles)
        cur.execute("DELETE FROM usuario_empresas WHERE empresa_id = %s AND usuario_id = %s", (eid, str(usuario_id)))
    registrar_evento(
        current_user["user_id"], "cuenta.quitar_usuario", empresa_id=eid, entidad="usuario",
        entidad_id=str(usuario_id), metadata=_metadata(via_admin, {"administradores_fijados": promovidos}),
    )
    return Response(status_code=204)


# ─── Invitaciones (lado de la empresa) ───────────────────────────────────────

@router.post("/empresas/{empresa_id}/invitaciones", status_code=201)
@limiter.limit("20/hour", key_func=_clave_usuario)  # evita barrer correos aunque la respuesta no revele nada
async def invitar(
    request: Request,
    empresa_id: uuid.UUID,
    cuerpo: Invitacion,
    current_user: dict = Depends(get_current_user),
):
    """Invita un correo. Misma respuesta exista o no una cuenta con ese correo."""
    eid, via_admin = _empresa_visible(empresa_id, current_user)
    rol_plataforma = _rol_plataforma(current_user)
    try:
        email = ue.normalizar_correo(cuerpo.email)
        rol = ue.validar_rol(cuerpo.rol)
    except ue.DatoInvalido as e:
        raise _422(e)
    mio = (db.query_one("SELECT email FROM usuarios WHERE id = %s", (current_user["user_id"],)) or {}).get("email")
    with _miembros_bloqueados(eid) as (cur, miembros, roles):
        # El permiso se revisa sobre los vínculos bloqueados: si otro administrador le
        # quita el rol al mismo tiempo, esta invitación espera y luego se rechaza.
        _exigir_administrador(current_user, roles, rol_plataforma)
        if mio and mio.strip().lower() == email:
            # También impide que un administrador de la plataforma se dé acceso a sí mismo.
            raise HTTPException(status_code=422, detail="No puedes invitarte a ti mismo")
        cur.execute(
            "SELECT 1 FROM usuario_empresas ue JOIN usuarios u ON u.id = ue.usuario_id "
            "WHERE ue.empresa_id = %s AND lower(btrim(u.email)) = %s",
            (eid, email),
        )
        if cur.fetchone():
            raise HTTPException(status_code=409, detail="Esa persona ya tiene acceso a la empresa")
        cur.execute(
            """
            INSERT INTO invitaciones_empresa (empresa_id, email, rol, invitada_por)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (empresa_id, email) WHERE estado IN ('pendiente', 'aceptada_pendiente')
            DO UPDATE SET rol = EXCLUDED.rol, invitada_por = EXCLUDED.invitada_por,
                          created_at = NOW(), expires_at = NOW() + INTERVAL '7 days'
            WHERE invitaciones_empresa.estado = 'pendiente'
            RETURNING id, email, rol, estado, created_at
            """,
            (eid, email, rol, current_user["user_id"]),
        )
        fila = cur.fetchone()
        if fila is None:
            # Ya la aceptaron: re-invitar no cambia el rol ni renueva el plazo de lo que
            # el administrador está por aprobar.
            raise HTTPException(
                status_code=409,
                detail="Esa persona ya aceptó una invitación que espera aprobación: apruébala o recházala",
            )
        fila = dict(fila)
    registrar_evento(
        current_user["user_id"], "cuenta.invitar", empresa_id=eid, entidad="invitacion",
        entidad_id=str(fila["id"]), metadata=_metadata(via_admin, {"email": email, "rol": rol}),
    )
    return _invitacion(fila)


@router.delete("/empresas/{empresa_id}/invitaciones/{invitacion_id}", status_code=204)
async def cancelar_invitacion(
    empresa_id: uuid.UUID,
    invitacion_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
):
    eid, via_admin = _empresa_visible(empresa_id, current_user)
    rol_plataforma = _rol_plataforma(current_user)
    with _miembros_bloqueados(eid) as (cur, _miembros, roles):
        _exigir_administrador(current_user, roles, rol_plataforma)
        cur.execute(
            "UPDATE invitaciones_empresa SET estado = 'cancelada', resuelta_at = NOW(), resuelta_por = %s "
            "WHERE id = %s AND empresa_id = %s AND estado = 'pendiente' RETURNING id",
            (current_user["user_id"], str(invitacion_id), eid),
        )
        fila = cur.fetchone()
    if not fila:
        raise HTTPException(status_code=404, detail="Invitación no encontrada")
    registrar_evento(current_user["user_id"], "cuenta.cancelar_invitacion", empresa_id=eid, entidad="invitacion",
                     entidad_id=str(invitacion_id), metadata=_metadata(via_admin))
    return Response(status_code=204)


def _resolver(empresa_id: uuid.UUID, invitacion_id: uuid.UUID, current_user: dict, aprobar: bool) -> None:
    """Un administrador aprueba o rechaza una aceptación. Todo ocurre en la transacción
    que bloquea los vínculos de la empresa: permiso, invitación y alta del vínculo."""
    eid, via_admin = _empresa_visible(empresa_id, current_user)
    rol_plataforma = _rol_plataforma(current_user)
    with _miembros_bloqueados(eid) as (cur, miembros, roles):
        _exigir_administrador(current_user, roles, rol_plataforma)
        cur.execute(
            "SELECT i.id, i.rol, i.respondida_por, i.email, u.email AS email_cuenta FROM invitaciones_empresa i "
            "JOIN usuarios u ON u.id = i.respondida_por AND u.activo IS NOT FALSE "
            "WHERE i.id = %s AND i.empresa_id = %s AND i.estado = 'aceptada_pendiente' AND i.expires_at > NOW() "
            "FOR UPDATE OF i",
            (str(invitacion_id), eid),
        )
        inv = cur.fetchone()
        if not inv:
            raise HTTPException(status_code=404, detail="Invitación no encontrada")
        promovidos = []
        if aprobar:
            # B1 otra vez al aprobar: si desde que aceptó apareció otra cuenta con el mismo
            # correo en minúsculas (o el de la cuenta ya no es el invitado), no se aprueba.
            correo = inv["email_cuenta"].strip().lower()
            cur.execute("SELECT COUNT(*) AS n FROM usuarios WHERE lower(btrim(email)) = %s", (correo,))
            if correo != inv["email"] or cur.fetchone()["n"] > 1:
                registrar_evento(current_user["user_id"], "cuenta.correo_ambiguo", empresa_id=eid,
                                 entidad="invitacion", entidad_id=str(invitacion_id),
                                 metadata=_metadata(via_admin, {"usuario": str(inv["respondida_por"])}))
                raise HTTPException(
                    status_code=409,
                    detail="El correo de esa cuenta ya no identifica a una sola persona; no se puede aprobar",
                )
            # Administra la empresa si se le invitó como administrador o si es el primer
            # vínculo (administrador implícito): eso suma un RFC a su plan (M7.1).
            if inv["rol"] == "administrador" or not miembros:
                _verificar_plan(cur, str(inv["respondida_por"]), current_user)
            promovidos = _fijar_administradores(cur, eid, miembros, roles)
            cur.execute(
                "INSERT INTO usuario_empresas (usuario_id, empresa_id, rol) VALUES (%s, %s, %s) "
                "ON CONFLICT (usuario_id, empresa_id) DO NOTHING",
                (inv["respondida_por"], eid, inv["rol"]),
            )
        cur.execute(
            "UPDATE invitaciones_empresa SET estado = %s, resuelta_por = %s, resuelta_at = NOW() WHERE id = %s",
            ("aprobada" if aprobar else "rechazada_admin", current_user["user_id"], inv["id"]),
        )
        nuevo = str(inv["respondida_por"])
    registrar_evento(
        current_user["user_id"], "cuenta.aprobar_invitacion" if aprobar else "cuenta.rechazar_aceptacion",
        empresa_id=eid, entidad="invitacion", entidad_id=str(invitacion_id),
        metadata=_metadata(via_admin, {"usuario": nuevo, "administradores_fijados": promovidos}),
    )


@router.post("/empresas/{empresa_id}/invitaciones/{invitacion_id}/aprobar", status_code=204)
async def aprobar_invitacion(
    empresa_id: uuid.UUID,
    invitacion_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
):
    """Da acceso a quien aceptó la invitación, con el rol invitado."""
    _resolver(empresa_id, invitacion_id, current_user, aprobar=True)
    return Response(status_code=204)


@router.post("/empresas/{empresa_id}/invitaciones/{invitacion_id}/rechazar", status_code=204)
async def rechazar_aceptacion(
    empresa_id: uuid.UUID,
    invitacion_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
):
    """No da acceso a quien aceptó (por ejemplo, alguien que se registró con un correo ajeno)."""
    _resolver(empresa_id, invitacion_id, current_user, aprobar=False)
    return Response(status_code=204)


# ─── Invitaciones (lado de la persona invitada) ──────────────────────────────

def _mi_correo(current_user: dict):
    """Correo de la cuenta en minúsculas, o None si es ambiguo.

    `usuarios.email` distingue mayúsculas: dos cuentas pueden tener el mismo correo
    escrito distinto. En ese caso nadie puede ver ni aceptar invitaciones a ese correo
    (lo contrario dejaría a un tercero tomar la invitación registrándose como
    «Victima@…»). Se audita y se resuelve cuando el carril B haga único lower(email).
    """
    fila = db.query_one("SELECT email FROM usuarios WHERE id = %s AND activo = TRUE", (current_user["user_id"],))
    if not fila:
        raise HTTPException(status_code=403, detail="Cuenta inactiva")
    email = fila["email"].strip().lower()
    cuentas = db.query_one("SELECT COUNT(*) AS n FROM usuarios WHERE lower(btrim(email)) = %s", (email,))["n"]
    if cuentas > 1:
        registrar_evento(current_user["user_id"], "cuenta.correo_ambiguo", entidad="usuario",
                         entidad_id=current_user["user_id"], metadata={"cuentas": int(cuentas)})
        return None
    return email


@router.get("/invitaciones")
async def mis_invitaciones(current_user: dict = Depends(get_current_user)):
    """Invitaciones pendientes y vigentes al correo de la cuenta."""
    email = _mi_correo(current_user)
    if email is None:
        return []
    filas = db.query_all(
        """
        SELECT i.id, i.rol, i.estado, i.created_at, e.rfc, e.razon_social, u.nombre AS invitada_por
        FROM invitaciones_empresa i
        JOIN empresas e ON e.id = i.empresa_id AND e.activo IS NOT FALSE
        LEFT JOIN usuarios u ON u.id = i.invitada_por
        WHERE i.email = %s AND i.expires_at > NOW()
          AND (i.estado = 'pendiente' OR (i.estado = 'aceptada_pendiente' AND i.respondida_por = %s))
        ORDER BY i.created_at
        """,
        (email, current_user["user_id"]),
    )
    return [
        {"id": str(f["id"]), "rol": f["rol"], "estado": f["estado"], "creada": f["created_at"].isoformat(), "rfc": f["rfc"],
         "razon_social": f["razon_social"], "invitada_por": f["invitada_por"]}
        for f in filas
    ]


def _responder(invitacion_id: uuid.UUID, current_user: dict, aceptar: bool) -> str:
    """La persona invitada acepta o rechaza. Aceptar NO da acceso: deja la invitación
    por aprobar (doble confirmación, decisión de Carlos del 2026-10-04) y abre un plazo
    de 7 días para que un administrador la apruebe."""
    email = _mi_correo(current_user)
    if email is None:
        raise HTTPException(status_code=404, detail="Invitación no encontrada")
    with db.get_conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT i.id, i.empresa_id FROM invitaciones_empresa i "
            "JOIN empresas e ON e.id = i.empresa_id AND e.activo IS NOT FALSE "
            "WHERE i.id = %s AND i.email = %s AND i.estado = 'pendiente' AND i.expires_at > NOW() "
            "FOR UPDATE OF i",
            (str(invitacion_id), email),
        )
        inv = cur.fetchone()
        if not inv:
            # Igual si no existe, es de otro correo o ya se respondió: no se revela cuál.
            raise HTTPException(status_code=404, detail="Invitación no encontrada")
        if aceptar:
            cur.execute(
                "UPDATE invitaciones_empresa SET estado = 'aceptada_pendiente', respondida_por = %s, "
                "respondida_at = NOW(), expires_at = NOW() + INTERVAL '7 days' WHERE id = %s",
                (current_user["user_id"], inv["id"]),
            )
        else:
            cur.execute(
                "UPDATE invitaciones_empresa SET estado = 'rechazada', respondida_por = %s, respondida_at = NOW() "
                "WHERE id = %s",
                (current_user["user_id"], inv["id"]),
            )
        empresa_id = str(inv["empresa_id"])
    registrar_evento(
        current_user["user_id"], "cuenta.aceptar_invitacion" if aceptar else "cuenta.rechazar_invitacion",
        empresa_id=empresa_id, entidad="invitacion", entidad_id=str(invitacion_id),
    )
    return empresa_id


@router.post("/invitaciones/{invitacion_id}/aceptar")
async def aceptar_invitacion(invitacion_id: uuid.UUID, current_user: dict = Depends(get_current_user)):
    """Queda por aprobar: el acceso llega cuando un administrador de la empresa la aprueba."""
    _responder(invitacion_id, current_user, aceptar=True)
    return {"estado": "aceptada_pendiente"}


@router.post("/invitaciones/{invitacion_id}/rechazar", status_code=204)
async def rechazar_invitacion(invitacion_id: uuid.UUID, current_user: dict = Depends(get_current_user)):
    _responder(invitacion_id, current_user, aceptar=False)
    return Response(status_code=204)
