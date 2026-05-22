"""
Background tasks para el módulo SAT FIEL.

Contiene las funciones que se ejecutan asíncronamente después de
solicitar/descargar CFDIs del SAT.
"""
from __future__ import annotations

import json
import logging

from .. import db
from ..sat_fiel import FIELError, descargar_paquete, verificar_solicitud

_log = logging.getLogger(__name__)


def importar_paquetes_bg(
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

    estado_final = "descargado" if total_importados > 0 else "fallo"
    error_final = None if total_importados > 0 else "Ningún CFDI pudo importarse correctamente"
    db.execute(
        "UPDATE sat_solicitudes SET cfdi_importados=%s, estado=%s, error_msg=%s, updated_at=NOW() WHERE id=%s",
        (total_importados, estado_final, error_final, solicitud_id),
    )

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


def sync_completo_bg(empresa_id: str, periodo: str, solicitudes: list[dict]) -> None:
    """
    Background task: verifica en loop y descarga automáticamente.
    Reintenta cada 30 segundos por hasta 30 minutos.
    """
    import time
    from ..fiel_store import obtener_signer

    MAX_INTENTOS = 60
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
            row = db.query_one("SELECT id_solicitud_sat, estado FROM sat_solicitudes WHERE id = %s", (sol_id,))
            if not row or not row.get("id_solicitud_sat"):
                continue

            try:
                resultado = verificar_solicitud(creds, row["id_solicitud_sat"])
            except FIELError as exc:
                _log.warning("Error verificando %s: %s", sol_id, exc)
                continue

            estado_raw = resultado.get("estado")
            estado_str = (
                str(estado_raw.value).lower().strip()
                if hasattr(estado_raw, "value")
                else str(estado_raw or "").lower().strip()
            )
            id_paquetes = resultado.get("id_paquetes", [])
            num_cfdi    = resultado.get("num_cfdi", 0)

            if estado_str in ("terminada", "terminado"):
                db.execute(
                    "UPDATE sat_solicitudes SET estado='terminado', num_cfdi=%s, num_paquetes=%s, updated_at=NOW() WHERE id=%s",
                    (num_cfdi, len(id_paquetes), sol_id),
                )
                if id_paquetes:
                    importar_paquetes_bg(
                        creds=creds,
                        solicitud_id=sol_id,
                        empresa_id=empresa_id,
                        periodo=periodo,
                        paquetes=id_paquetes,
                    )
                del pendientes[sol_id]

            elif estado_str in ("error", "rechazada", "fallo", "falla", "vencida"):
                db.execute(
                    "UPDATE sat_solicitudes SET estado='fallo', error_msg=%s, updated_at=NOW() WHERE id=%s",
                    (f"SAT reportó estado: {estado_str}", sol_id),
                )
                del pendientes[sol_id]
            else:
                db.execute(
                    "UPDATE sat_solicitudes SET estado='en_proceso', num_cfdi=%s, updated_at=NOW() WHERE id=%s",
                    (num_cfdi, sol_id),
                )

    for sol_id in pendientes:
        db.execute(
            "UPDATE sat_solicitudes SET estado='fallo', error_msg='Timeout: el SAT tardó más de 30 minutos', updated_at=NOW() WHERE id=%s",
            (sol_id,),
        )
