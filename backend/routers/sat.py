# backend/routers/sat.py
"""
Router SAT FIEL — Descarga Masiva de CFDIs.

Expone 4 endpoints para gestionar el ciclo completo de solicitud, verificación
y descarga de CFDIs directamente del SAT usando la e.firma (FIEL) del contribuyente.
"""
from __future__ import annotations

import json as _json
import logging
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile

from .. import db
from ..deps import get_current_user, validar_acceso_empresa, serializar
from ..sat_fiel import FIELError, cargar_fiel, descargar_paquete, solicitar_descarga, verificar_solicitud

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
        id_sat = solicitar_descarga(creds, empresa["rfc"], tipo, fecha_ini, fecha_fin_d)
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

    # Mapear código de estado SAT a estado interno.
    # verificar_solicitud retorna "estado" como int del enum EstadoSolicitud:
    #   1=Aceptada, 2=EnProceso, 3=Terminada, 4=Error, 5=Rechazada, 6=Vencida
    codigo_int = resultado.get("estado", 0)
    ESTADO_MAP = {1: "en_proceso", 2: "en_proceso", 3: "terminado", 4: "fallo", 5: "fallo", 6: "fallo"}
    nuevo_estado = ESTADO_MAP.get(codigo_int, "en_proceso")

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
) -> None:
    """Descarga paquetes ZIP del SAT, parsea XMLs e importa a la DB.

    Se ejecuta en background — no bloquea la respuesta HTTP.
    Al finalizar, corre el pipeline de conciliación/riesgos/scoring.
    """
    from ..cfdi_parser import CFDIParser

    parser = CFDIParser()
    total_importados = 0

    for id_paq in paquetes:
        try:
            xmls = descargar_paquete(creds, id_paq)
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
                    total_importados += 1
                except Exception as e:
                    _log.warning("Error parseando XML del paquete %s: %s", id_paq, e)

            db.execute(
                "UPDATE sat_solicitudes SET paquetes_descargados = paquetes_descargados + 1, updated_at=NOW() WHERE id=%s",
                (solicitud_id,),
            )
        except FIELError as e:
            _log.error("Error descargando paquete %s: %s", id_paq, e)

    db.execute(
        "UPDATE sat_solicitudes SET cfdi_importados=%s, estado='descargado', updated_at=NOW() WHERE id=%s",
        (total_importados, solicitud_id),
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


def _insertar_cfdi(empresa_id: str, resultado, periodo: str, xml_raw_bytes: bytes) -> None:
    """Inserta un CFDIParsed en la DB. ON CONFLICT (uuid) DO NOTHING para idempotencia."""
    import json

    xml_raw_str = xml_raw_bytes.decode("utf-8", errors="replace")

    db.execute(
        """
        INSERT INTO cfdi (
            empresa_id, uuid, tipo_comprobante, serie, folio, version,
            rfc_emisor, nombre_emisor, rfc_receptor, nombre_receptor,
            fecha_emision, fecha_timbrado,
            subtotal, descuento, iva_trasladado, iva_retenido, isr_retenido, total,
            metodo_pago, forma_pago, uso_cfdi, moneda, tipo_cambio, xml_raw,
            exportacion, lugar_expedicion,
            domicilio_fiscal_receptor, regimen_fiscal_receptor,
            cfdi_relacionados, es_anticipo_sat
        ) VALUES (
            %s,%s,%s,%s,%s,%s,
            %s,%s,%s,%s,
            %s,%s,
            %s,%s,%s,%s,%s,%s,
            %s,%s,%s,%s,%s,%s,
            %s,%s,%s,%s,
            %s,%s
        )
        ON CONFLICT (uuid) DO NOTHING
        """,
        (
            empresa_id, resultado.uuid, resultado.tipo_comprobante,
            resultado.serie, resultado.folio, resultado.version,
            resultado.rfc_emisor, resultado.nombre_emisor,
            resultado.rfc_receptor, resultado.nombre_receptor,
            resultado.fecha_emision, resultado.fecha_timbrado,
            str(resultado.subtotal), str(resultado.descuento),
            str(resultado.iva_trasladado), str(resultado.iva_retenido),
            str(resultado.isr_retenido), str(resultado.total),
            resultado.metodo_pago, resultado.forma_pago,
            resultado.uso_cfdi, resultado.moneda,
            str(resultado.tipo_cambio),
            xml_raw_str,
            resultado.exportacion,
            resultado.lugar_expedicion,
            resultado.domicilio_fiscal_receptor,
            resultado.regimen_fiscal_receptor,
            json.dumps(resultado.cfdi_relacionados),
            resultado.es_anticipo_sat,
        ),
    )
