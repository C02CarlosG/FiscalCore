# backend/routers/sat.py
"""
Router SAT FIEL — Descarga Masiva de CFDIs.

Expone endpoints para gestionar el ciclo completo de solicitud, verificación
y descarga de CFDIs directamente del SAT usando la e.firma (FIEL) del contribuyente.

Las funciones de background se encuentran en sat_tasks.py.
"""
from __future__ import annotations

import json as _json
import logging
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile

from .. import db
from ..deps import get_current_user, validar_acceso_empresa, serializar
from ..sat_fiel import FIELError, cargar_fiel, solicitar_descarga, verificar_solicitud
from .sat_tasks import importar_paquetes_bg, sync_completo_bg

_log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/sat", tags=["SAT FIEL"])


# ---------------------------------------------------------------------------
# POST /api/v1/sat/solicitar
# ---------------------------------------------------------------------------

@router.post("/solicitar")
async def solicitar_descarga_cfdi(
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

    registro = db.execute(
        """INSERT INTO sat_solicitudes
           (empresa_id, usuario_id, tipo, periodo_inicio, periodo_fin, estado)
           VALUES (%s, %s, %s, %s, %s, 'pendiente') RETURNING *""",
        (
            empresa_id,
            current_user["user_id"],
            tipo,
            fecha_inicio[:7],
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
async def verificar_solicitud_endpoint(
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

    # satcfdi puede devolver EstadoSolicitud como enum Python o como string.
    estado_raw = resultado.get("estado")
    estado_str = (
        str(estado_raw.value).lower().strip()
        if hasattr(estado_raw, "value")
        else str(estado_raw or "").lower().strip()
    )
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

    id_paquetes = resultado.get("id_paquetes", [])
    num_cfdi = resultado.get("num_cfdi", 0)

    db.execute(
        """UPDATE sat_solicitudes
           SET estado=%s, num_cfdi=%s, num_paquetes=%s, updated_at=NOW()
           WHERE id=%s""",
        (nuevo_estado, num_cfdi, len(id_paquetes), solicitud_id),
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
async def descargar_cfdi_endpoint(
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

    background_tasks.add_task(
        importar_paquetes_bg,
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
async def guardar_fiel_empresa(
    empresa_id: str,
    cer_file: UploadFile = File(...),
    key_file: UploadFile = File(...),
    password: str = Form(...),
    current_user: dict = Depends(get_current_user),
):
    """Guarda la FIEL cifrada para una empresa. Reemplaza cualquier FIEL previa."""
    validar_acceso_empresa(empresa_id, current_user)

    empresa = db.query_one("SELECT id FROM empresas WHERE id = %s", (empresa_id,))
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
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

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
    return {"eliminada": eliminada}


@router.post("/empresas/{empresa_id}/fiel/sync")
async def sync_completo_fiel(
    empresa_id: str,
    background_tasks: BackgroundTasks,
    tipo: str = Form(...),     # "emitidos" | "recibidos" | "ambos"
    periodo: str = Form(...),  # YYYY-MM
    current_user: dict = Depends(get_current_user),
):
    """
    Ciclo completo automatizado usando la FIEL guardada:
    1. Solicitar descarga al SAT
    2. Verificar en loop hasta que esté lista (máx 30 min)
    3. Descargar paquetes e importar CFDIs
    4. Correr pipeline (conciliación + riesgos + scoring)
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

    tipos = ["emitidos", "recibidos"] if tipo == "ambos" else [tipo]
    if not all(t in ("emitidos", "recibidos") for t in tipos):
        raise HTTPException(status_code=400, detail="tipo debe ser 'emitidos', 'recibidos' o 'ambos'")

    import calendar
    año, mes = periodo.split("-")
    fecha_inicio = date(int(año), int(mes), 1)
    ultimo_dia = calendar.monthrange(int(año), int(mes))[1]
    fecha_fin = date(int(año), int(mes), ultimo_dia)

    solicitud_ids = []
    try:
        creds = obtener_signer(db, empresa_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    for t in tipos:
        registro = db.execute(
            """INSERT INTO sat_solicitudes
               (empresa_id, usuario_id, tipo, periodo_inicio, periodo_fin, estado)
               VALUES (%s, %s, %s, %s, %s, 'pendiente') RETURNING *""",
            (empresa_id, current_user["user_id"], t, periodo, periodo),
            returning=True,
        )
        solicitud_ids.append({"id": str(registro["id"]), "tipo": t})

        try:
            id_sat = solicitar_descarga(creds, empresa["rfc"], t, fecha_inicio, fecha_fin,
                                    estado_comprobante="Vigente")
            db.execute(
                "UPDATE sat_solicitudes SET id_solicitud_sat=%s, estado='solicitado', updated_at=NOW() WHERE id=%s",
                (id_sat, str(registro["id"])),
            )
        except FIELError as exc:
            db.execute(
                "UPDATE sat_solicitudes SET estado='fallo', error_msg=%s, updated_at=NOW() WHERE id=%s",
                (str(exc), str(registro["id"])),
            )
            raise HTTPException(status_code=502, detail=f"Error SAT al solicitar {t}: {exc}")

    background_tasks.add_task(
        sync_completo_bg,
        empresa_id=empresa_id,
        periodo=periodo,
        solicitudes=solicitud_ids,
    )

    return {
        "mensaje": f"Sync iniciado para {len(tipos)} tipo(s). Se verificará y descargará automáticamente.",
        "solicitudes": solicitud_ids,
        "periodo": periodo,
        "tipos": tipos,
    }
