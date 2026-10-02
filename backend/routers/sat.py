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

from .. import cfdi_store, db
from ..auditoria import registrar_evento
from ..deps import get_current_user, validar_acceso_empresa, serializar, limiter
from ..sat_fiel import FIELError, cargar_fiel, descargar_paquete, solicitar_descarga, verificar_solicitud

_log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/sat", tags=["SAT FIEL"])

# EstadoSolicitud del servicio de Descarga Masiva, por su valor numérico.
_ESTADOS_SAT = {
    1: "aceptada", 2: "en proceso", 3: "terminada",
    4: "error", 5: "rechazada", 6: "vencida",
}


def _estado_sat(resultado: dict) -> str:
    """Nombre en minúsculas del EstadoSolicitud que devolvió el SAT.

    satcfdi lo entrega como entero (1=Aceptada … 6=Vencida); se aceptan también
    el enum y el nombre en texto.
    """
    raw = resultado.get("estado")
    raw = getattr(raw, "value", raw)
    if isinstance(raw, int) or (isinstance(raw, str) and raw.strip().isdigit()):
        return _ESTADOS_SAT.get(int(raw), "")
    return str(raw or "").lower().strip()


# CodigoEstadoSolicitud 5004: la solicitud no generó paquetes por falta de
# información, es decir, no hay CFDI en el periodo. No es un error.
_SIN_INFORMACION = "5004"


def _sin_informacion(resultado: dict) -> bool:
    """True si el SAT dice que la solicitud no encontró CFDI que descargar."""
    return str(resultado.get("codigo_estado") or "").strip() == _SIN_INFORMACION


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


# ---------------------------------------------------------------------------
# Background task: descarga paquetes + importa XMLs
# ---------------------------------------------------------------------------

def _importar_paquetes_bg(
    creds,
    solicitud_id: str,
    empresa_id: str,
    periodo: str,
    paquetes: list[str],
    desde: int = 0,
) -> str:
    """Descarga paquetes ZIP del SAT, parsea XMLs e importa a la DB.

    Empieza en el paquete ``desde`` (los anteriores ya se importaron en una
    pasada que se cortó). El avance y los CFDI importados se guardan paquete
    por paquete, así que una pasada interrumpida se retoma donde se quedó.

    Si un paquete no se puede descargar, la solicitud se queda en 'terminado'
    para reintentarlo después: saltarlo dejaría la descarga incompleta sin
    que nadie se entere. Al terminar se cuadran los CFDI importados contra los
    que reportó el SAT y la diferencia queda en ``error_msg``.

    Al finalizar, corre el pipeline de conciliación/riesgos/scoring.
    Devuelve el estado en que queda la solicitud ('descargado', 'fallo', o
    'terminado' si falta reintentar un paquete).
    """
    from ..cfdi_parser import CFDIParser

    parser = CFDIParser()

    for num_paq, id_paq in enumerate(paquetes[desde:], start=desde + 1):
        try:
            xmls = descargar_paquete(creds, id_paq)
        except FIELError as e:
            _log.error("Error descargando paquete %s: %s", id_paq, e)
            db.execute(
                "UPDATE sat_solicitudes SET error_msg=%s, updated_at=NOW() WHERE id=%s",
                (f"No se pudo descargar el paquete {num_paq} de {len(paquetes)}: {e}. "
                 "Se reintentará en unos minutos.", solicitud_id),
            )
            return "terminado"

        importados_paq = 0
        for xml_bytes in xmls:
            try:
                resultado = parser.parse_xml(xml_bytes)
                # Solo importar si no hay errores bloqueantes
                errores_bloqueantes = [e for e in resultado.errores if not e.startswith("AVISO:")]
                if errores_bloqueantes:
                    _log.warning(
                        "CFDI %s ignorado — errores: %s",
                        resultado.uuid, errores_bloqueantes,
                    )
                    continue
                _insertar_cfdi(empresa_id, resultado, periodo, xml_bytes)
                importados_paq += 1
            except Exception as e:
                _log.warning("Error parseando XML del paquete %s: %s", id_paq, e)

        db.execute(
            """UPDATE sat_solicitudes
               SET paquetes_descargados=%s, cfdi_importados=COALESCE(cfdi_importados, 0) + %s,
                   updated_at=NOW()
               WHERE id=%s""",
            (num_paq, importados_paq, solicitud_id),
        )

    fila = db.query_one(
        "SELECT num_cfdi, cfdi_importados FROM sat_solicitudes WHERE id=%s", (solicitud_id,),
    ) or {}
    total_importados = fila.get("cfdi_importados") or 0
    esperados = fila.get("num_cfdi") or 0

    if total_importados == 0:
        estado_final = "fallo"
        error_final = "Ningún CFDI pudo importarse correctamente"
    else:
        estado_final = "descargado"
        error_final = None
        if total_importados < esperados:
            error_final = (
                f"Descarga incompleta: se importaron {total_importados} de los {esperados} CFDI "
                f"que reportó el SAT; {esperados - total_importados} no se pudieron importar."
            )
    db.execute(
        "UPDATE sat_solicitudes SET estado=%s, error_msg=%s, updated_at=NOW() WHERE id=%s",
        (estado_final, error_final, solicitud_id),
    )

    # Correr pipeline conciliación/riesgos/scoring si se importaron CFDIs
    if total_importados > 0:
        empresa = db.query_one("SELECT rfc FROM empresas WHERE id=%s", (empresa_id,))
        if empresa:
            try:
                from ..routers.ingesta import _correr_pipeline
                _correr_pipeline(empresa_id, periodo, empresa["rfc"])
            except Exception as e:
                _log.error("Error en pipeline post-descarga FIEL: %s", e)

    _log.info("Solicitud %s: %d CFDIs importados de %d paquetes", solicitud_id, total_importados, len(paquetes))
    return estado_final


def _insertar_cfdi(empresa_id: str, resultado, periodo: str, xml_raw_bytes: bytes) -> None:
    """Inserta un CFDIParsed en la DB (idempotente por UUID).

    Delega en cfdi_store para compartir la lógica con la subida manual: además
    del INSERT, registra los Complementos de Pago (tipo P) y recalcula lo
    cobrado de los CFDIs relacionados.
    """
    cfdi_store.insertar_cfdi(empresa_id, resultado, xml_raw_bytes)


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
    return {"eliminada": eliminada}


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

    # Crear registros de solicitud
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
    }


# Estados en los que el SAT todavía está preparando la solicitud.
_ESTADOS_EN_SAT = ("solicitado", "en_proceso")
# Los anteriores más 'terminado' (lista en el SAT, importación sin terminar).
_ESTADOS_PENDIENTES = _ESTADOS_EN_SAT + ("terminado",)
_ESTADOS_FALLO_SAT = ("error", "rechazada", "fallo", "falla", "vencida")


def _avanzar_solicitud(creds, solicitud: dict) -> str:
    """Da un paso a una solicitud: la verifica en el SAT y, si ya está lista,
    descarga e importa sus paquetes. Devuelve el estado en que queda.

    Es segura ante pasadas concurrentes (loop en background y /fiel/sync/avanzar):
    solo quien logra el UPDATE condicional hace la descarga.
    """
    sol_id = str(solicitud["id"])
    try:
        resultado = verificar_solicitud(creds, solicitud["id_solicitud_sat"])
    except FIELError as exc:
        _log.warning("Error verificando %s: %s", sol_id, exc)
        return solicitud["estado"]

    estado_str = _estado_sat(resultado)
    id_paquetes = resultado.get("id_paquetes") or []
    num_cfdi    = resultado.get("num_cfdi") or 0
    _log.info(
        "Solicitud %s (SAT %s): el SAT reporta '%s' (estado=%r, código=%s, estatus=%s, %s CFDI, %d paquetes) %s",
        sol_id, solicitud["id_solicitud_sat"], estado_str, resultado.get("estado"),
        resultado.get("codigo_estado"), resultado.get("cod_estatus"),
        num_cfdi, len(id_paquetes), resultado.get("mensaje") or "",
    )

    if estado_str in ("terminada", "terminado"):
        if solicitud["estado"] == "terminado":
            # Importación interrumpida (el proceso murió a media descarga, o un
            # paquete falló): se retoma desde el primer paquete sin importar.
            # Si el SAT cambió la lista de paquetes, el avance guardado no
            # aplica y se empieza de cero (reimportar un CFDI es idempotente).
            tomada = db.execute(
                """UPDATE sat_solicitudes
                   SET paquetes_descargados = CASE WHEN num_paquetes = %s
                                                   THEN COALESCE(paquetes_descargados, 0) ELSE 0 END,
                       cfdi_importados      = CASE WHEN num_paquetes = %s
                                                   THEN COALESCE(cfdi_importados, 0) ELSE 0 END,
                       num_paquetes=%s, updated_at=NOW()
                   WHERE id=%s AND estado='terminado'
                     AND updated_at < NOW() - INTERVAL '10 minutes'
                   RETURNING id, paquetes_descargados""",
                (len(id_paquetes), len(id_paquetes), len(id_paquetes), sol_id), returning=True,
            )
        else:
            tomada = db.execute(
                """UPDATE sat_solicitudes
                   SET estado='terminado', num_cfdi=%s, num_paquetes=%s,
                       paquetes_descargados=0, cfdi_importados=0, updated_at=NOW()
                   WHERE id=%s AND estado IN ('solicitado', 'en_proceso')
                   RETURNING id, paquetes_descargados""",
                (num_cfdi, len(id_paquetes), sol_id), returning=True,
            )
        if not tomada:
            return "terminado"  # otra pasada ya la está importando
        if not id_paquetes:
            db.execute(
                "UPDATE sat_solicitudes SET estado='descargado', cfdi_importados=0, updated_at=NOW() WHERE id=%s",
                (sol_id,),
            )
            return "descargado"
        return _importar_paquetes_bg(
            creds=creds,
            solicitud_id=sol_id,
            empresa_id=str(solicitud["empresa_id"]),
            periodo=solicitud["periodo_inicio"],
            paquetes=id_paquetes,
            desde=tomada.get("paquetes_descargados") or 0,
        ) or "terminado"

    # El SAT procesó la solicitud y no encontró CFDI en el periodo: es una
    # descarga terminada con cero comprobantes, no un fallo.
    if _sin_informacion(resultado):
        db.execute(
            """UPDATE sat_solicitudes
               SET estado='descargado', num_cfdi=0, num_paquetes=0, cfdi_importados=0,
                   error_msg=NULL, updated_at=NOW()
               WHERE id=%s AND estado IN ('solicitado', 'en_proceso')""",
            (sol_id,),
        )
        return "descargado"

    # Sin un estado reconocible (el SAT manda 0 cuando rechaza la consulta, p. ej.
    # "No se encontró la información") tampoco hay nada que esperar.
    # Salvo el 404 ("Error no controlado"), que el SAT pide reintentar.
    reintentable = not estado_str and resultado.get("cod_estatus") == "404"
    if (estado_str in _ESTADOS_FALLO_SAT or not estado_str) and not reintentable:
        motivo = f"SAT reportó estado: {estado_str}." if estado_str else "El SAT respondió:"
        db.execute(
            "UPDATE sat_solicitudes SET estado='fallo', error_msg=%s, updated_at=NOW() WHERE id=%s",
            (f"{motivo} {resultado.get('mensaje') or 'sin detalle'}", sol_id),
        )
        return "fallo"

    # En proceso — actualizar contadores y seguir esperando
    db.execute(
        """UPDATE sat_solicitudes SET estado='en_proceso', num_cfdi=%s, updated_at=NOW()
           WHERE id=%s AND estado IN ('solicitado', 'en_proceso')""",
        (num_cfdi, sol_id),
    )
    return "en_proceso"


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
