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
import re
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, time
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


class SolicitudRechazada(FIELError):
    """El SAT recibió la solicitud de descarga y la rechazó.

    ``codigo`` es el CodEstatus del SAT: 5002 (límite de por vida para los mismos
    parámetros), 5003 (tope máximo de CFDI o metadatos por solicitud), 5005
    (solicitud duplicada), etc.
    """

    def __init__(self, mensaje: str, codigo: str | None = None):
        super().__init__(mensaje)
        self.codigo = codigo


class SolicitudesAgotadasError(SolicitudRechazada):
    """CodEstatus 5002: el SAT agotó las solicitudes "de por vida" con esos
    mismos parámetros (fecha inicial, fecha final y RFC). Con otras fechas
    todavía se puede pedir."""

    def __init__(self, mensaje: str, codigo: str | None = "5002"):
        super().__init__(mensaje, codigo)


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
        if "password" in str(exc).lower() or "decrypt" in str(exc).lower():
            raise FIELError("la contraseña de la llave privada es incorrecta") from exc
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

    # El SAT filtra por fecha y hora de emisión. Una fecha sin hora se toma como
    # las 00:00:00, lo que dejaba fuera todo el último día del periodo.
    if not isinstance(fecha_inicio, datetime):
        fecha_inicio = datetime.combine(fecha_inicio, time.min)
    if not isinstance(fecha_fin, datetime):
        fecha_fin = datetime.combine(fecha_fin, time(23, 59, 59))

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
    cod_estatus = respuesta.get("CodEstatus")
    # 5000 = solicitud recibida con éxito; cualquier otro código es un rechazo
    # (5002 solicitudes agotadas, 5005 duplicada, …) aunque venga un IdSolicitud.
    if cod_estatus == "5002":
        raise SolicitudesAgotadasError(
            f"El SAT ya no acepta más solicitudes de {tipo_lower} con estas mismas fechas "
            "(código 5002: se agotaron las solicitudes de por vida)."
        )
    if not id_solicitud or (cod_estatus and cod_estatus != "5000"):
        raise SolicitudRechazada(
            f"El SAT rechazó la solicitud de {tipo_lower} "
            f"(código {cod_estatus}): {respuesta.get('Mensaje') or respuesta}",
            codigo=str(cod_estatus) if cod_estatus else None,
        )

    _log.info(
        "Solicitud de descarga de %s registrada. IdSolicitud=%s CodEstatus=%s Mensaje=%s",
        tipo_lower, id_solicitud, cod_estatus, respuesta.get("Mensaje"),
    )
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
        - ``codigo_estado``: código de estado de la solicitud (str, opcional).
        - ``cod_estatus``: código de estatus de la consulta misma (str, opcional).
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
        "cod_estatus": respuesta.get("CodEstatus"),          # str | None (estatus de la consulta)
        "mensaje": respuesta.get("Mensaje"),                 # str | None
    }


# ---------------------------------------------------------------------------
# Función 4: Descargar paquete y extraer XMLs
# ---------------------------------------------------------------------------

def descargar_paquete(creds: "Signer", id_paquete: str, extensiones: tuple[str, ...] = (".xml",)) -> list[bytes]:
    """Descarga un paquete ZIP del SAT y retorna la lista de XMLs que contiene.

    Args:
        creds: Signer con la FIEL cargada.
        id_paquete: ID de paquete (uno de los devueltos por ``verificar_solicitud``).

        extensiones: extensiones de los archivos que se extraen. Por defecto solo
            XML (paquetes de CFDI); los paquetes de metadatos traen un ``.txt``.

    Returns:
        Lista de ``bytes``, uno por cada archivo con esas extensiones dentro del
        paquete ZIP. Si el paquete no contiene ninguno, retorna lista vacía.

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
                if name.lower().endswith(tuple(e.lower() for e in extensiones))
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


# ---------------------------------------------------------------------------
# Metadatos de CFDI (descarga masiva con tipo_solicitud="Metadata")
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MetadataCFDI:
    """Una fila del archivo de metadatos: lo justo para saber si un CFDI sigue vigente."""
    uuid: str
    rfc_emisor: str
    rfc_receptor: str
    efecto: str                       # I, E, T, N, P
    estatus: str                      # 'vigente' | 'cancelado'
    fecha_cancelacion: Optional[datetime]


_UUID_RE = re.compile(r"^[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}$")
_ESTATUS_METADATA = {"0": "cancelado", "cancelado": "cancelado", "1": "vigente", "vigente": "vigente"}


def _fecha_metadata(valor: str) -> Optional[datetime]:
    valor = valor.strip()
    if not valor:
        return None
    try:
        return datetime.fromisoformat(valor)
    except ValueError:
        return None


def parsear_metadata(contenido: bytes) -> list[MetadataCFDI]:
    """Lee el ``.txt`` de un paquete de metadatos del SAT (columnas separadas por ``~``).

    El formato sale de descripciones públicas del SAT, así que el lector se guía por el
    **encabezado** (no por la posición de las columnas) y tolera BOM, mayúsculas distintas,
    columnas extra y UTF-8 o Latin-1. Si el encabezado no trae ``Uuid`` y ``Estatus``
    levanta ``FIELError`` y no devuelve nada: más vale no marcar nada que marcar mal.
    Las filas con UUID mal formado, estatus desconocido o columnas faltantes se omiten.
    """
    try:
        texto = contenido.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = contenido.decode("latin-1")
    lineas = texto.splitlines()
    if not lineas or not lineas[0].strip():
        return []

    columnas = [c.strip().lower() for c in lineas[0].split("~")]
    if "uuid" not in columnas or "estatus" not in columnas:
        raise FIELError(
            "Formato de metadatos no reconocido: el encabezado debe incluir Uuid y Estatus "
            f"(se recibió {lineas[0][:80]!r})."
        )
    idx = {nombre: i for i, nombre in enumerate(columnas)}
    minimo = max(idx["uuid"], idx["estatus"])

    def _campo(fila: list[str], nombre: str) -> str:
        i = idx.get(nombre)
        return fila[i].strip() if i is not None and i < len(fila) else ""

    registros: list[MetadataCFDI] = []
    omitidas = 0
    for linea in lineas[1:]:
        if not linea.strip():
            continue
        fila = linea.split("~")
        uuid = _campo(fila, "uuid").upper() if len(fila) > minimo else ""
        estatus = _ESTATUS_METADATA.get(_campo(fila, "estatus").lower()) if len(fila) > minimo else None
        if not _UUID_RE.match(uuid) or estatus is None:
            omitidas += 1
            continue
        registros.append(MetadataCFDI(
            uuid=uuid,
            rfc_emisor=_campo(fila, "rfcemisor").upper(),
            rfc_receptor=_campo(fila, "rfcreceptor").upper(),
            efecto=_campo(fila, "efectocomprobante").upper(),
            estatus=estatus,
            fecha_cancelacion=_fecha_metadata(_campo(fila, "fechacancelacion")),
        ))
    if omitidas:
        _log.warning("Metadatos: %d fila(s) omitida(s) por UUID o estatus inválidos", omitidas)
    return registros
