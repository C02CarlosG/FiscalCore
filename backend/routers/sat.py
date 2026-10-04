# backend/routers/sat.py
"""
Router SAT FIEL — Descarga Masiva de CFDIs.

Expone 4 endpoints para gestionar el ciclo completo de solicitud, verificación
y descarga de CFDIs directamente del SAT usando la e.firma (FIEL) del contribuyente.

NOTA: NO usar `from __future__ import annotations` aquí. Los endpoints están
envueltos por @limiter.limit (slowapi); con anotaciones diferidas, FastAPI
resuelve los forward-refs (UploadFile, Request, …) contra los __globals__ del
wrapper de slowapi y truena al importar.
"""
import json as _json
import logging
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

from .. import db
from ..auditoria import registrar_evento
from ..deps import get_current_user, validar_acceso_empresa, serializar, limiter
from ..sat_fiel import FIELError, cargar_fiel, solicitar_descarga, verificar_solicitud
from ..sat_sync import (
    ConfigSyncInvalida,
    SolicitudActiva,
    crear_solicitud_ventana,
    ESTADOS_PENDIENTES as _ESTADOS_PENDIENTES,
    configurar_sync,
    desactivar_por_fiel_eliminada,
    estado_sync,
    forzar_corrida,
    avanzar_solicitud as _avanzar_solicitud,
    estado_sat as _estado_sat,
    importar_paquetes as _importar_paquetes_bg,
    sin_informacion as _sin_informacion,
)

_log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/sat", tags=["SAT FIEL"])

# ---------------------------------------------------------------------------
# POST /api/v1/sat/solicitar
# ---------------------------------------------------------------------------

@router.post("/solicitar")
@limiter.limit("10/minute")  # límite conservador: operación costosa contra el SAT usando la FIEL
async def solicitar_descarga_cfdi(
    request: Request,
    empresa_id: str = Form(...),
    tipo: str = Form(...),
    fecha_inicio: str = Form(...),  # YYYY-MM-DD
    fecha_fin: str = Form(...),     # YYYY-MM-DD
    estado_comprobante: str = Form("Vigente"),  # "Vigente", "Cancelado", "Todos"
    cer_file: UploadFile = File(...),
    key_file: UploadFile = File(...),
    password: str = Form(...),
    current_user: dict = Depends(get_current_user),
):
    """Envía una solicitud de descarga masiva al SAT usando la FIEL del contribuyente."""
    validar_acceso_empresa(empresa_id, current_user)

    empresa = db.query_one("SELECT rfc FROM empresas WHERE id = %s", (empresa_id,))
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    if tipo not in ("emitidos", "recibidos"):
        raise HTTPException(status_code=400, detail="tipo debe ser 'emitidos' o 'recibidos'")

    try:
        fecha_ini = date.fromisoformat(fecha_inicio)
        fecha_fin_d = date.fromisoformat(fecha_fin)
    except ValueError:
        raise HTTPException(status_code=400, detail="Fechas inválidas — formato esperado: YYYY-MM-DD")

    cer_bytes = await cer_file.read()
    key_bytes = await key_file.read()

    try:
        creds = cargar_fiel(cer_bytes, key_bytes, password)
    except FIELError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Crear registro de solicitud en estado 'pendiente'
    registro = db.execute(
        """INSERT INTO sat_solicitudes
           (empresa_id, usuario_id, tipo, periodo_inicio, periodo_fin, estado)
           VALUES (%s, %s, %s, %s, %s, 'pendiente') RETURNING *""",
        (
            empresa_id,
            current_user["user_id"],
            tipo,
            fecha_inicio[:7],  # YYYY-MM
            fecha_fin[:7],
        ),
        returning=True,
    )
    solicitud_id = str(registro["id"])

    try:
        id_sat = solicitar_descarga(creds, empresa["rfc"], tipo, fecha_ini, fecha_fin_d,
                                    estado_comprobante=estado_comprobante)
        db.execute(
            "UPDATE sat_solicitudes SET id_solicitud_sat=%s, estado='solicitado', updated_at=NOW() WHERE id=%s",
            (id_sat, solicitud_id),
        )
    except FIELError as e:
        db.execute(
            "UPDATE sat_solicitudes SET estado='fallo', error_msg=%s, updated_at=NOW() WHERE id=%s",
            (str(e), solicitud_id),
        )
        raise HTTPException(status_code=502, detail=f"Error SAT: {e}")

    return {
        "solicitud_id": solicitud_id,
        "id_solicitud_sat": id_sat,
        "estado": "solicitado",
        "mensaje": "Solicitud enviada al SAT. Usa /verificar para consultar el estado.",
    }


# ---------------------------------------------------------------------------
# GET /api/v1/sat/solicitudes
# ---------------------------------------------------------------------------

@router.get("/solicitudes")
async def listar_solicitudes(
    empresa_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Lista las últimas 20 solicitudes de descarga masiva de la empresa."""
    validar_acceso_empresa(empresa_id, current_user)
    rows = db.query_all(
        "SELECT * FROM sat_solicitudes WHERE empresa_id=%s ORDER BY created_at DESC LIMIT 20",
        (empresa_id,),
    )
    return [serializar(r) for r in rows]


# ---------------------------------------------------------------------------
# POST /api/v1/sat/solicitudes/{solicitud_id}/verificar
# ---------------------------------------------------------------------------

@router.post("/solicitudes/{solicitud_id}/verificar")
@limiter.limit("10/minute")  # límite conservador: operación costosa contra el SAT usando la FIEL
async def verificar_solicitud_endpoint(
    request: Request,
    solicitud_id: str,
    cer_file: UploadFile = File(...),
    key_file: UploadFile = File(...),
    password: str = Form(...),
    current_user: dict = Depends(get_current_user),
):
    """Consulta el estado de una solicitud en el SAT y actualiza el registro local."""
    solicitud = db.query_one("SELECT * FROM sat_solicitudes WHERE id=%s", (solicitud_id,))
    if not solicitud:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    validar_acceso_empresa(str(solicitud["empresa_id"]), current_user)

    if not solicitud.get("id_solicitud_sat"):
        raise HTTPException(status_code=400, detail="La solicitud aún no tiene ID del SAT")

    cer_bytes = await cer_file.read()
    key_bytes = await key_file.read()

    try:
        creds = cargar_fiel(cer_bytes, key_bytes, password)
        resultado = verificar_solicitud(creds, solicitud["id_solicitud_sat"])
    except FIELError as e:
        raise HTTPException(status_code=502, detail=str(e))

    estado_str = _estado_sat(resultado)
    ESTADO_MAP = {
        "aceptada":   "en_proceso",
        "en proceso": "en_proceso",
        "en_proceso": "en_proceso",
        "terminada":  "terminado",
        "error":      "fallo",
        "rechazada":  "fallo",
        "falla":      "fallo",
        "vencida":    "fallo",
    }
    nuevo_estado = ESTADO_MAP.get(estado_str, "en_proceso")
    if _sin_informacion(resultado):
        nuevo_estado = "descargado"

    id_paquetes = resultado.get("id_paquetes") or []
    num_cfdi = resultado.get("num_cfdi") or 0

    db.execute(
        """UPDATE sat_solicitudes
           SET estado=%s, num_cfdi=%s, num_paquetes=%s,
               error_msg = CASE WHEN %s = 'descargado' THEN NULL ELSE error_msg END,
               updated_at=NOW()
           WHERE id=%s""",
        (nuevo_estado, num_cfdi, len(id_paquetes), nuevo_estado, solicitud_id),
    )

    return {
        "solicitud_id": solicitud_id,
        "estado": nuevo_estado,
        "num_cfdi": num_cfdi,
        "num_paquetes": len(id_paquetes),
        "id_paquetes": id_paquetes,
        "mensaje": resultado.get("mensaje") or "",
    }


# ---------------------------------------------------------------------------
# POST /api/v1/sat/solicitudes/{solicitud_id}/descargar
# ---------------------------------------------------------------------------

@router.post("/solicitudes/{solicitud_id}/descargar")
@limiter.limit("10/minute")  # límite conservador: operación costosa contra el SAT usando la FIEL
async def descargar_cfdi_endpoint(
    request: Request,
    solicitud_id: str,
    background_tasks: BackgroundTasks,
    cer_file: UploadFile = File(...),
    key_file: UploadFile = File(...),
    password: str = Form(...),
    id_paquetes: str = Form(...),  # JSON array string, ej: '["pkg1","pkg2"]'
    current_user: dict = Depends(get_current_user),
):
    """Lanza la descarga de paquetes ZIP en background e importa los XMLs a la DB."""
    solicitud = db.query_one("SELECT * FROM sat_solicitudes WHERE id=%s", (solicitud_id,))
    if not solicitud:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    validar_acceso_empresa(str(solicitud["empresa_id"]), current_user)

    cer_bytes = await cer_file.read()
    key_bytes = await key_file.read()

    try:
        creds = cargar_fiel(cer_bytes, key_bytes, password)
    except FIELError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        paquetes = _json.loads(id_paquetes)
        if not isinstance(paquetes, list):
            raise ValueError("Se esperaba un array JSON")
    except (ValueError, _json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="id_paquetes debe ser un JSON array, ej: '[\"pkg1\",\"pkg2\"]'")

    # La importación acumula el avance por paquete: se arranca de cero.
    db.execute(
        """UPDATE sat_solicitudes
           SET paquetes_descargados=0, cfdi_importados=0, updated_at=NOW()
           WHERE id=%s""",
        (solicitud_id,),
    )

    background_tasks.add_task(
        _importar_paquetes_bg,
        creds=creds,
        solicitud_id=solicitud_id,
        empresa_id=str(solicitud["empresa_id"]),
        periodo=solicitud["periodo_inicio"],
        paquetes=paquetes,
    )

    return {
        "mensaje": "Descarga iniciada en background",
        "paquetes": len(paquetes),
        "solicitud_id": solicitud_id,
    }


# ===========================================================================
# FIEL GUARDADA — endpoints para almacenar y usar FIEL por empresa
# ===========================================================================

@router.post("/empresas/{empresa_id}/fiel/guardar")
@limiter.limit("10/minute")  # límite conservador: valida FIEL contra credenciales SAT
async def guardar_fiel_empresa(
    request: Request,
    empresa_id: str,
    cer_file: UploadFile = File(...),
    key_file: UploadFile = File(...),
    password: str = Form(...),
    current_user: dict = Depends(get_current_user),
):
    """Guarda la FIEL cifrada para una empresa. Reemplaza cualquier FIEL previa."""
    validar_acceso_empresa(empresa_id, current_user)

    empresa = db.query_one("SELECT id, rfc FROM empresas WHERE id = %s", (empresa_id,))
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    from ..fiel_store import guardar_fiel
    try:
        resultado = guardar_fiel(
            db=db,
            empresa_id=empresa_id,
            cer_bytes=await cer_file.read(),
            key_bytes=await key_file.read(),
            password=password,
            rfc_esperado=empresa.get("rfc"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    registrar_evento(current_user["user_id"], "fiel_cargada", empresa_id=empresa_id)

    return resultado


@router.get("/empresas/{empresa_id}/fiel/estado")
async def estado_fiel_empresa(
    empresa_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Devuelve metadatos de la FIEL guardada (sin exponer credenciales)."""
    validar_acceso_empresa(empresa_id, current_user)
    from ..fiel_store import estado_fiel
    info = estado_fiel(db, empresa_id)
    return info if info else {"tiene_fiel": False}


@router.delete("/empresas/{empresa_id}/fiel")
async def eliminar_fiel_empresa(
    empresa_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Elimina la FIEL guardada de la empresa."""
    validar_acceso_empresa(empresa_id, current_user)
    from ..fiel_store import eliminar_fiel
    eliminada = eliminar_fiel(db, empresa_id)
    # Sin e.firma no hay descarga automática: se apaga en la misma operación.
    desactivar_por_fiel_eliminada(empresa_id, current_user["user_id"])
    return {"eliminada": eliminada}


# ---------------------------------------------------------------------------
# Descarga automática (worker): estado, activación y "actualizar ahora"
# ---------------------------------------------------------------------------

class ConfigSyncBody(BaseModel):
    activa: bool
    consentimiento: bool = False


def _o_http(resultado):
    """Ejecuta una operación de sat_sync traduciendo sus errores a HTTP."""
    try:
        return resultado()
    except ConfigSyncInvalida as exc:
        raise HTTPException(status_code=exc.codigo, detail=exc.detalle)


@router.get("/empresas/{empresa_id}/sync/estado")
async def estado_sync_empresa(
    empresa_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Estado de la descarga automática: configuración, última y próxima corrida, progreso."""
    validar_acceso_empresa(empresa_id, current_user)
    return estado_sync(empresa_id)


@router.put("/empresas/{empresa_id}/sync/config")
@limiter.limit("10/minute")
async def configurar_sync_empresa(
    request: Request,
    empresa_id: str,
    cuerpo: ConfigSyncBody,
    current_user: dict = Depends(get_current_user),
):
    """Activa (con consentimiento explícito) o desactiva la descarga automática de la empresa."""
    validar_acceso_empresa(empresa_id, current_user)
    return _o_http(lambda: configurar_sync(
        empresa_id, current_user["user_id"], activa=cuerpo.activa, consentimiento=cuerpo.consentimiento))


@router.post("/empresas/{empresa_id}/sync/ahora")
@limiter.limit("5/minute")
async def sync_ahora_empresa(
    request: Request,
    empresa_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Fuerza una corrida: el worker la toma en su siguiente ciclo."""
    validar_acceso_empresa(empresa_id, current_user)
    return _o_http(lambda: forzar_corrida(empresa_id, current_user["user_id"]))


@router.post("/empresas/{empresa_id}/fiel/sync")
@limiter.limit("10/minute")  # límite conservador: operación costosa contra el SAT usando la FIEL
async def sync_completo_fiel(
    request: Request,
    empresa_id: str,
    background_tasks: BackgroundTasks,
    tipo: str = Form(...),          # "emitidos" | "recibidos" | "ambos"
    periodo: str = Form(...),       # YYYY-MM
    current_user: dict = Depends(get_current_user),
):
    """
    Ciclo completo automatizado usando la FIEL guardada:
    1. Solicitar descarga al SAT
    2. Verificar en loop hasta que esté lista (máx 30 min)
    3. Descargar paquetes e importar CFDIs
    4. Correr pipeline (conciliación + riesgos + scoring)

    Requiere que la empresa tenga una FIEL guardada previamente.
    """
    validar_acceso_empresa(empresa_id, current_user)

    empresa = db.query_one("SELECT rfc FROM empresas WHERE id = %s", (empresa_id,))
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    from ..fiel_store import obtener_signer, estado_fiel
    info = estado_fiel(db, empresa_id)
    if not info:
        raise HTTPException(status_code=422, detail="No hay FIEL guardada para esta empresa. Guárdala primero.")
    if info.get("vencida"):
        raise HTTPException(status_code=422, detail="La FIEL guardada está vencida. Actualízala.")

    # Determinar tipos a solicitar
    tipos = ["emitidos", "recibidos"] if tipo == "ambos" else [tipo]
    if not all(t in ("emitidos", "recibidos") for t in tipos):
        raise HTTPException(status_code=400, detail="tipo debe ser 'emitidos', 'recibidos' o 'ambos'")

    # Calcular fechas del período
    import calendar
    año, mes = periodo.split("-")
    fecha_inicio = date(int(año), int(mes), 1)
    ultimo_dia = calendar.monthrange(int(año), int(mes))[1]
    fecha_fin = date(int(año), int(mes), ultimo_dia)

    try:
        creds = obtener_signer(db, empresa_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # Cada tipo se pide por separado: si el SAT rechaza uno, el otro sigue.
    solicitud_ids: list[dict] = []
    errores: list[str] = []
    en_curso: list[str] = []
    for t in tipos:
        try:
            filas = crear_solicitud_ventana(
                creds, {"id": empresa_id, "rfc": empresa["rfc"]}, t, fecha_inicio, fecha_fin,
                origen="manual", usuario_id=current_user["user_id"],
            )
        except SolicitudActiva:
            en_curso.append(t)
            errores.append(f"{t}: ya hay una descarga en curso para {periodo}")
        except FIELError as exc:
            errores.append(f"{t}: {exc}")
        else:
            solicitud_ids += [{"id": str(f["id"]), "tipo": t} for f in filas if f["estado"] == "solicitado"]
    if not solicitud_ids:
        if en_curso and len(en_curso) == len(tipos):
            raise HTTPException(
                status_code=409,
                detail=f"Ya hay una descarga en curso para {periodo}. Espera a que termine.",
            )
        raise HTTPException(status_code=502, detail="Error SAT al solicitar " + "; ".join(errores))

    # Lanzar background task que verifica y descarga automáticamente
    background_tasks.add_task(
        _sync_completo_bg,
        empresa_id=empresa_id,
        periodo=periodo,
        solicitudes=solicitud_ids,
    )

    return {
        "mensaje": f"Sync iniciado para {len(tipos)} tipo(s). Se verificará y descargará automáticamente.",
        "solicitudes": solicitud_ids,
        "periodo": periodo,
        "tipos": tipos,
        "errores": errores,
    }


@router.post("/empresas/{empresa_id}/fiel/sync/avanzar")
@limiter.limit("30/minute")
def avanzar_sync_fiel(
    request: Request,
    empresa_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Da una pasada a las descargas en curso de la empresa usando la FIEL guardada:
    verifica cada solicitud en el SAT y, si ya está lista, la descarga e importa.

    Existe para los entornos donde el proceso no sobrevive al request
    (serverless) y el loop de /fiel/sync se corta: el frontend lo llama
    mientras haya descargas en curso. Cada solicitud se verifica en el SAT como
    mucho una vez cada 20 segundos, sin importar cuántas veces se llame.
    """
    validar_acceso_empresa(empresa_id, current_user)

    pendientes = db.query_all(
        """SELECT * FROM sat_solicitudes
           WHERE empresa_id=%s AND id_solicitud_sat IS NOT NULL
             AND (proximo_intento IS NULL OR proximo_intento <= NOW())
             AND ((estado IN ('solicitado', 'en_proceso')
                   AND updated_at < NOW() - INTERVAL '20 seconds')
               OR (estado = 'terminado'
                   AND updated_at < NOW() - INTERVAL '10 minutes'))
           ORDER BY created_at""",
        (empresa_id,),
    )
    if not pendientes:
        return {"avanzadas": []}

    from ..fiel_store import obtener_signer
    try:
        creds = obtener_signer(db, empresa_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return {
        "avanzadas": [
            {"id": str(s["id"]), "estado": _avanzar_solicitud(creds, s)}
            for s in pendientes
        ]
    }


def _sync_completo_bg(empresa_id: str, periodo: str, solicitudes: list[dict]) -> None:
    """
    Background task: verifica en loop y descarga automáticamente.
    Reintenta cada 30 segundos por hasta 30 minutos.
    """
    import time
    from ..fiel_store import obtener_signer

    MAX_INTENTOS = 60       # 60 × 30s = 30 minutos
    ESPERA_SEG   = 30

    try:
        creds = obtener_signer(db, empresa_id)
    except Exception as exc:
        _log.error("sync_completo_bg: no se pudo obtener FIEL: %s", exc)
        for s in solicitudes:
            db.execute(
                "UPDATE sat_solicitudes SET estado='fallo', error_msg=%s, updated_at=NOW() WHERE id=%s",
                (f"Error FIEL: {exc}", s["id"]),
            )
        return

    empresa = db.query_one("SELECT rfc FROM empresas WHERE id = %s", (empresa_id,))
    if not empresa:
        return

    pendientes = {s["id"]: s for s in solicitudes}

    for intento in range(MAX_INTENTOS):
        if not pendientes:
            break

        time.sleep(ESPERA_SEG)
        _log.info("sync_completo_bg intento %d/%d, %d solicitudes pendientes", intento+1, MAX_INTENTOS, len(pendientes))

        for sol_id in list(pendientes.keys()):
            row = db.query_one("SELECT * FROM sat_solicitudes WHERE id = %s", (sol_id,))
            if not row or not row.get("id_solicitud_sat"):
                continue
            # Otra pasada (p. ej. /fiel/sync/avanzar) pudo haberla resuelto ya.
            # 'terminado' sigue pendiente: falta importar (o reintentar) paquetes.
            if row["estado"] not in _ESTADOS_PENDIENTES or _avanzar_solicitud(creds, row) not in _ESTADOS_PENDIENTES:
                del pendientes[sol_id]

    # Marcar como fallo las que no terminaron a tiempo
    for sol_id in pendientes:
        db.execute(
            """UPDATE sat_solicitudes
               SET estado='fallo', error_msg='Timeout: el SAT tardó más de 30 minutos', updated_at=NOW()
               WHERE id=%s AND estado IN ('solicitado', 'en_proceso')""",
            (sol_id,),
        )
