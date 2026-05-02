# backend/sat_fiel.py
"""
Cliente FIEL para descarga masiva de CFDIs del SAT.

Encapsula autenticación con e.firma (FIEL) y las tres operaciones del
servicio de Descarga Masiva Terceros del SAT:
  1. Solicitar descarga (emitidos o recibidos)
  2. Verificar estado de solicitud
  3. Descargar paquete ZIP y extraer XMLs
"""
from __future__ import annotations

import base64
import io
import logging
import zipfile
from datetime import date, datetime
from typing import Optional

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Importación condicional — graceful degradation si satcfdi no está instalado
# ---------------------------------------------------------------------------
try:
    from satcfdi.models.signer import Signer
    from satcfdi.pacs.sat import (
        SAT,
        CodigoEstadoSolicitud,
        EstadoSolicitud,
        TipoDescargaMasivaTerceros,
    )
    SATCFDI_OK = True
except ImportError:
    SATCFDI_OK = False
    _log.warning("satcfdi no instalado — módulo FIEL deshabilitado. Ejecutar: pip install satcfdi")


# ---------------------------------------------------------------------------
# Excepción propia del módulo
# ---------------------------------------------------------------------------

class FIELError(Exception):
    """Error relacionado con la FIEL o con el servicio SAT Descarga Masiva."""


def _check_satcfdi():
    if not SATCFDI_OK:
        raise FIELError("satcfdi no instalado. Ejecutar: pip install satcfdi")


# ---------------------------------------------------------------------------
# Función 1: Cargar FIEL localmente (sin llamada al SAT)
# ---------------------------------------------------------------------------

def cargar_fiel(cer_bytes: bytes, key_bytes: bytes, password: str | bytes) -> "Signer":
    """Carga y valida la e.firma (FIEL) a partir de los archivos .cer y .key.

    No realiza ninguna llamada al SAT — sólo verifica que el certificado y la
    llave privada sean compatibles y que la contraseña sea correcta.

    Args:
        cer_bytes: Contenido binario del archivo .cer (certificado DER).
        key_bytes: Contenido binario del archivo .key (llave privada cifrada).
        password: Contraseña del archivo .key (str o bytes).

    Returns:
        Instancia de ``Signer`` lista para usarse con el cliente SAT.

    Raises:
        FIELError: Si satcfdi no está instalado, o si los archivos/contraseña
                   son inválidos.
    """
    _check_satcfdi()
    try:
        signer = Signer.load(
            certificate=cer_bytes,
            key=key_bytes,
            password=password,
        )
        return signer
    except Exception as exc:
        raise FIELError(f"No se pudo cargar la FIEL: {exc}") from exc


# ---------------------------------------------------------------------------
# Función 2: Solicitar descarga masiva
# ---------------------------------------------------------------------------

def solicitar_descarga(
    creds: "Signer",
    rfc: str,
    tipo: str,  # "emitidos" | "recibidos"
    fecha_inicio: date,
    fecha_fin: date,
    tipo_solicitud: str = "CFDI",
    estado_comprobante: str = "Vigente",  # "Vigente", "Cancelado", "Todos"
) -> str:
    """Envía una solicitud de descarga masiva al SAT.

    Args:
        creds: Signer con la FIEL cargada (resultado de ``cargar_fiel``).
        rfc: RFC del contribuyente para el que se solicita la descarga.
        tipo: ``"emitidos"`` o ``"recibidos"``.
        fecha_inicio: Fecha inicial del período a consultar.
        fecha_fin: Fecha final del período a consultar.
        tipo_solicitud: ``"CFDI"`` (default) o ``"Metadata"``.

    Returns:
        ``id_solicitud`` asignado por el SAT (UUID string).

    Raises:
        FIELError: Si satcfdi no está instalado, si el tipo es inválido, o si
                   el SAT rechaza la solicitud.
    """
    _check_satcfdi()

    tipo_lower = tipo.lower()
    if tipo_lower not in ("emitidos", "recibidos"):
        raise FIELError(f"tipo debe ser 'emitidos' o 'recibidos', se recibió: {tipo!r}")

    try:
        tipo_desc = TipoDescargaMasivaTerceros(tipo_solicitud)
    except ValueError:
        raise FIELError(
            f"tipo_solicitud inválido: {tipo_solicitud!r}. "
            f"Valores válidos: {[e.value for e in TipoDescargaMasivaTerceros]}"
        )

    sat_client = SAT(signer=creds)

    try:
        if tipo_lower == "emitidos":
            respuesta = sat_client.recover_comprobante_emitted_request(
                fecha_inicial=fecha_inicio,
                fecha_final=fecha_fin,
                rfc_emisor=rfc,
                tipo_solicitud=tipo_desc,
                estado_comprobante=estado_comprobante or None,
            )
        else:  # recibidos
            respuesta = sat_client.recover_comprobante_received_request(
                fecha_inicial=fecha_inicio,
                fecha_final=fecha_fin,
                rfc_receptor=rfc,
                tipo_solicitud=tipo_desc,
                estado_comprobante=estado_comprobante or None,
            )
    except Exception as exc:
        raise FIELError(f"Error al solicitar descarga al SAT: {exc}") from exc

    id_solicitud = respuesta.get("IdSolicitud")
    if not id_solicitud:
        raise FIELError(
            f"El SAT no devolvió IdSolicitud. Respuesta completa: {respuesta}"
        )

    _log.info("Solicitud de descarga registrada. IdSolicitud=%s", id_solicitud)
    return id_solicitud


# ---------------------------------------------------------------------------
# Función 3: Verificar estado de una solicitud
# ---------------------------------------------------------------------------

def verificar_solicitud(creds: "Signer", id_solicitud: str) -> dict:
    """Consulta el estado de una solicitud de descarga masiva.

    Args:
        creds: Signer con la FIEL cargada.
        id_solicitud: UUID devuelto por ``solicitar_descarga``.

    Returns:
        Diccionario con al menos las claves:
        - ``estado``: valor int del enum ``EstadoSolicitud`` del SAT
          (1=Aceptada, 2=EnProceso, 3=Terminada, 4=Error, 5=Rechazada, 6=Vencida).
        - ``num_cfdi``: cantidad de CFDIs encontrados (int).
        - ``id_paquetes``: lista de strings con los IDs de paquetes disponibles.
        - ``codigo_estado``: código de estatus SAT (str, opcional).
        - ``mensaje``: descripción del estado (str, opcional).

    Raises:
        FIELError: Si satcfdi no está instalado o si el SAT devuelve error.
    """
    _check_satcfdi()

    sat_client = SAT(signer=creds)

    try:
        respuesta = sat_client.recover_comprobante_status(id_solicitud=id_solicitud)
    except Exception as exc:
        raise FIELError(f"Error al verificar solicitud {id_solicitud!r}: {exc}") from exc

    return {
        "estado": respuesta.get("EstadoSolicitud"),          # int (EstadoSolicitud enum)
        "num_cfdi": respuesta.get("NumeroCFDIs", 0),         # int
        "id_paquetes": respuesta.get("IdsPaquetes", []),     # list[str]
        "codigo_estado": respuesta.get("CodigoEstadoSolicitud"),  # str | None
        "mensaje": respuesta.get("Mensaje"),                 # str | None
    }


# ---------------------------------------------------------------------------
# Función 4: Descargar paquete y extraer XMLs
# ---------------------------------------------------------------------------

def descargar_paquete(creds: "Signer", id_paquete: str) -> list[bytes]:
    """Descarga un paquete ZIP del SAT y retorna la lista de XMLs que contiene.

    Args:
        creds: Signer con la FIEL cargada.
        id_paquete: ID de paquete (uno de los devueltos por ``verificar_solicitud``).

    Returns:
        Lista de ``bytes``, uno por cada archivo XML dentro del paquete ZIP.
        Si el paquete no contiene XMLs, retorna lista vacía.

    Raises:
        FIELError: Si satcfdi no está instalado, si el SAT devuelve error, o si
                   el contenido del paquete no es un ZIP válido.
    """
    _check_satcfdi()

    sat_client = SAT(signer=creds)

    try:
        # recover_comprobante_download devuelve (dict_respuesta, paquete_b64_text)
        _respuesta, paquete_b64 = sat_client.recover_comprobante_download(
            id_paquete=id_paquete
        )
    except Exception as exc:
        raise FIELError(f"Error al descargar paquete {id_paquete!r}: {exc}") from exc

    if not paquete_b64:
        _log.warning("El SAT devolvió un paquete vacío para id_paquete=%s", id_paquete)
        return []

    try:
        zip_bytes = base64.b64decode(paquete_b64)
    except Exception as exc:
        raise FIELError(f"El contenido del paquete no es base64 válido: {exc}") from exc

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            xmls = [
                zf.read(name)
                for name in zf.namelist()
                if name.lower().endswith(".xml")
            ]
    except zipfile.BadZipFile as exc:
        raise FIELError(f"El paquete descargado no es un ZIP válido: {exc}") from exc
    except Exception as exc:
        raise FIELError(f"Error al extraer XMLs del paquete: {exc}") from exc

    _log.info(
        "Paquete %s descargado: %d XMLs extraídos de %d bytes",
        id_paquete, len(xmls), len(zip_bytes),
    )
    return xmls
