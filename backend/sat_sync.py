# backend/sat_sync.py
"""
Núcleo compartido de la descarga masiva del SAT.

Lo usan el router (`routers/sat.py`) y el worker de descarga automática (F2):
ventanas de fechas, esperas de reintento, configuración y, en las siguientes
tareas de F2.1, el avance e importación de solicitudes.

Las funciones de este bloque son puras: no tocan la base de datos ni el SAT.
"""
from __future__ import annotations

import calendar
import logging
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from . import cfdi_store, db
from .sat_fiel import FIELError, descargar_paquete, verificar_solicitud

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ventanas de fechas
# ---------------------------------------------------------------------------


def ventanas_mensuales(desde: date, hasta: date) -> list[tuple[date, date]]:
    """Parte ``[desde, hasta]`` por mes natural.

    Una solicitud al SAT nunca cubre más de un mes: así cada una se mantiene bajo
    los límites del servicio y se puede reintentar o retomar por separado.
    """
    ventanas: list[tuple[date, date]] = []
    inicio = desde
    while inicio <= hasta:
        fin_de_mes = date(inicio.year, inicio.month, calendar.monthrange(inicio.year, inicio.month)[1])
        fin = min(fin_de_mes, hasta)
        ventanas.append((inicio, fin))
        inicio = fin + timedelta(days=1)
    return ventanas


def partir_ventana(inicio: date, fin: date) -> list[tuple[date, date]] | None:
    """Parte una ventana en dos mitades contiguas, sin hueco ni solape.

    Se usa cuando el SAT rechaza una solicitud por volumen. Devuelve ``None``
    si la ventana ya es de un solo día (no hay nada más que partir).
    """
    dias = (fin - inicio).days + 1
    if dias <= 1:
        return None
    mitad = inicio + timedelta(days=(dias // 2) - 1)
    return [(inicio, mitad), (mitad + timedelta(days=1), fin)]


# ---------------------------------------------------------------------------
# Reintentos
# ---------------------------------------------------------------------------

# Espera tras el intento N fallido (1-indexado). Al agotarse, la solicitud falla.
_ESPERAS_REINTENTO = (
    timedelta(minutes=5),
    timedelta(minutes=15),
    timedelta(hours=1),
    timedelta(hours=6),
)


def espera_reintento(intentos: int) -> timedelta | None:
    """Cuánto esperar antes de reintentar tras ``intentos`` fallos seguidos.

    ``None`` si ``intentos`` no es un número de intento válido (0 o negativo)
    o si ya se agotaron los reintentos.
    """
    if intentos < 1 or intentos > len(_ESPERAS_REINTENTO):
        return None
    return _ESPERAS_REINTENTO[intentos - 1]


# ---------------------------------------------------------------------------
# Reintentos de solicitudes
# ---------------------------------------------------------------------------

# Cuánto se difiere una solicitud cuando el SAT dice que se agotó el cupo (5002).
_ESPERA_CUPO_AGOTADO = timedelta(hours=1)


def _en_espera(solicitud: dict) -> bool:
    """True si la solicitud tiene un ``proximo_intento`` que aún no llega."""
    proximo = solicitud.get("proximo_intento")
    if not proximo:
        return False
    if proximo.tzinfo is None:
        proximo = proximo.replace(tzinfo=timezone.utc)
    return proximo > datetime.now(timezone.utc)


def registrar_solicitud_fallida(solicitud_id: str, mensaje: str, *, diferir: bool = False) -> str:
    """Anota un fallo transitorio del SAT sobre una solicitud.

    - Normal: cuenta un intento y agenda el siguiente con la espera creciente
      (5 min, 15 min, 1 h, 6 h). Al agotarse, la solicitud queda en ``fallo``
      con el mensaje del SAT.
    - ``diferir=True`` (cupo de solicitudes agotado, código 5002): espera una hora
      sin consumir intento; no es culpa de la solicitud.

    Devuelve ``'fallo'`` si se agotó, o el estado vigente de la solicitud si se
    reintentará. ``mensaje`` es solo el texto del SAT: nunca lleva la e.firma.
    """
    if diferir:
        fila = db.execute(
            """UPDATE sat_solicitudes
               SET proximo_intento = NOW() + %s, error_msg=%s, updated_at=NOW()
               WHERE id=%s RETURNING estado""",
            (_ESPERA_CUPO_AGOTADO, mensaje, solicitud_id), returning=True,
        )
        return (fila or {}).get("estado", "solicitado")

    fila = db.execute(
        """UPDATE sat_solicitudes
           SET intentos = intentos + 1, error_msg=%s, updated_at=NOW()
           WHERE id=%s RETURNING intentos, estado""",
        (mensaje, solicitud_id), returning=True,
    ) or {}
    intentos = fila.get("intentos") or 1
    espera = espera_reintento(intentos)
    if espera is None:
        db.execute(
            "UPDATE sat_solicitudes SET estado='fallo', error_msg=%s, updated_at=NOW() WHERE id=%s",
            (f"El SAT no respondió tras {intentos} intentos: {mensaje}", solicitud_id),
        )
        return "fallo"
    db.execute(
        "UPDATE sat_solicitudes SET proximo_intento = NOW() + %s, updated_at=NOW() WHERE id=%s",
        (espera, solicitud_id),
    )
    return fila.get("estado", "solicitado")


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConfigSync:
    intervalo_seg: int = 60
    hora_local: str = "03:00"
    traslape_dias: int = 7
    meses_cancelacion: int = 3
    max_en_vuelo: int = 4


_HORA_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _entero_positivo(nombre: str, defecto: int) -> int:
    crudo = os.environ.get(nombre, "").strip()
    try:
        valor = int(crudo)
    except ValueError:
        return defecto
    return valor if valor > 0 else defecto


def config_sync() -> ConfigSync:
    """Lee la configuración de las variables ``SAT_SYNC_*``.

    Un valor ausente o inválido cae al defecto (y se avisa en el log) en vez de
    impedir que el worker arranque.
    """
    base = ConfigSync()
    hora = os.environ.get("SAT_SYNC_HORA_LOCAL", "").strip() or base.hora_local
    if not _HORA_RE.match(hora):
        _log.warning("SAT_SYNC_HORA_LOCAL inválida (%r); se usa %s", hora, base.hora_local)
        hora = base.hora_local
    return ConfigSync(
        intervalo_seg=_entero_positivo("SAT_SYNC_INTERVALO_SEG", base.intervalo_seg),
        hora_local=hora,
        traslape_dias=_entero_positivo("SAT_SYNC_TRASLAPE_DIAS", base.traslape_dias),
        meses_cancelacion=_entero_positivo("SAT_SYNC_MESES_CANCELACION", base.meses_cancelacion),
        max_en_vuelo=_entero_positivo("SAT_SYNC_MAX_EN_VUELO", base.max_en_vuelo),
    )


# ---------------------------------------------------------------------------
# Estado de las solicitudes, importación de paquetes y avance
# (movido de routers/sat.py sin cambios de comportamiento)
# ---------------------------------------------------------------------------

# EstadoSolicitud del servicio de Descarga Masiva, por su valor numérico.
_ESTADOS_SAT = {
    1: "aceptada", 2: "en proceso", 3: "terminada",
    4: "error", 5: "rechazada", 6: "vencida",
}


def estado_sat(resultado: dict) -> str:
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


def sin_informacion(resultado: dict) -> bool:
    """True si el SAT dice que la solicitud no encontró CFDI que descargar."""
    return str(resultado.get("codigo_estado") or "").strip() == _SIN_INFORMACION




# ---------------------------------------------------------------------------
# Background task: descarga paquetes + importa XMLs
# ---------------------------------------------------------------------------

def importar_paquetes(
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
    que nadie se entere. Tras ``MAX_INTENTOS_PAQUETE`` intentos fallidos del
    mismo paquete la solicitud queda en 'fallo'. Al terminar se cuadran los CFDI importados contra los
    que reportó el SAT y la diferencia queda en ``error_msg``.

    Al finalizar, corre el pipeline de conciliación/riesgos/scoring.
    Devuelve el estado en que queda la solicitud ('descargado', 'fallo', o
    'terminado' si falta reintentar un paquete).
    """
    from .cfdi_parser import CFDIParser

    parser = CFDIParser()

    for num_paq, id_paq in enumerate(paquetes[desde:], start=desde + 1):
        try:
            xmls = descargar_paquete(creds, id_paq)
        except FIELError as e:
            _log.error("Error descargando paquete %s: %s", id_paq, e)
            return registrar_paquete_fallido(solicitud_id, num_paq, len(paquetes), e)

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
                from .routers.ingesta import _correr_pipeline
                _correr_pipeline(empresa_id, periodo, empresa["rfc"])
            except Exception as e:
                _log.error("Error en pipeline post-descarga FIEL: %s", e)

    _log.info("Solicitud %s: %d CFDIs importados de %d paquetes", solicitud_id, total_importados, len(paquetes))
    return estado_final


MAX_INTENTOS_PAQUETE = 3


def registrar_paquete_fallido(solicitud_id: str, num_paq: int, total_paq: int, error) -> str:
    """Anota el intento fallido de un paquete; al agotar los intentos, falla la solicitud.

    El número de intento viaja en el mismo ``error_msg`` que ve el usuario
    ("intento 2 de 3"), así no hace falta otra columna. Devuelve el estado en
    que queda la solicitud: 'terminado' (se reintentará) o 'fallo'.
    """
    previo = (db.query_one(
        "SELECT error_msg FROM sat_solicitudes WHERE id=%s", (solicitud_id,),
    ) or {}).get("error_msg") or ""
    m = re.match(rf"No se pudo descargar el paquete {num_paq} de \d+ \(intento (\d+) de", previo)
    intento = int(m.group(1)) + 1 if m else 1

    if intento >= MAX_INTENTOS_PAQUETE:
        db.execute(
            "UPDATE sat_solicitudes SET estado='fallo', error_msg=%s, updated_at=NOW() WHERE id=%s",
            (f"No se pudo descargar el paquete {num_paq} de {total_paq} tras "
             f"{MAX_INTENTOS_PAQUETE} intentos: {error}. Vuelve a solicitar el periodo.",
             solicitud_id),
        )
        return "fallo"

    db.execute(
        "UPDATE sat_solicitudes SET error_msg=%s, updated_at=NOW() WHERE id=%s",
        (f"No se pudo descargar el paquete {num_paq} de {total_paq} "
         f"(intento {intento} de {MAX_INTENTOS_PAQUETE}): {error}. "
         "Se reintentará en unos minutos.", solicitud_id),
    )
    return "terminado"


def _insertar_cfdi(empresa_id: str, resultado, periodo: str, xml_raw_bytes: bytes) -> None:
    """Inserta un CFDIParsed en la DB (idempotente por UUID).

    Delega en cfdi_store para compartir la lógica con la subida manual: además
    del INSERT, registra los Complementos de Pago (tipo P) y recalcula lo
    cobrado de los CFDIs relacionados.
    """
    cfdi_store.insertar_cfdi(empresa_id, resultado, xml_raw_bytes)



# Estados en los que el SAT todavía está preparando la solicitud.
ESTADOS_EN_SAT = ("solicitado", "en_proceso")
# Los anteriores más 'terminado' (lista en el SAT, importación sin terminar).
ESTADOS_PENDIENTES = ESTADOS_EN_SAT + ("terminado",)
ESTADOS_FALLO_SAT = ("error", "rechazada", "fallo", "falla", "vencida")


def avanzar_solicitud(creds, solicitud: dict) -> str:
    """Da un paso a una solicitud: la verifica en el SAT y, si ya está lista,
    descarga e importa sus paquetes. Devuelve el estado en que queda.

    Es segura ante pasadas concurrentes (loop en background y /fiel/sync/avanzar):
    solo quien logra el UPDATE condicional hace la descarga.
    """
    sol_id = str(solicitud["id"])
    if _en_espera(solicitud):
        return solicitud["estado"]
    try:
        resultado = verificar_solicitud(creds, solicitud["id_solicitud_sat"])
    except FIELError as exc:
        _log.warning("Error verificando %s: %s", sol_id, exc)
        if registrar_solicitud_fallida(sol_id, str(exc)) == "fallo":
            return "fallo"
        return solicitud["estado"]

    estado_str = estado_sat(resultado)
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
        return importar_paquetes(
            creds=creds,
            solicitud_id=sol_id,
            empresa_id=str(solicitud["empresa_id"]),
            periodo=solicitud["periodo_inicio"],
            paquetes=id_paquetes,
            desde=tomada.get("paquetes_descargados") or 0,
        )

    # El SAT procesó la solicitud y no encontró CFDI en el periodo: es una
    # descarga terminada con cero comprobantes, no un fallo.
    if sin_informacion(resultado):
        db.execute(
            """UPDATE sat_solicitudes
               SET estado='descargado', num_cfdi=0, num_paquetes=0, cfdi_importados=0,
                   error_msg=NULL, updated_at=NOW()
               WHERE id=%s AND estado IN ('solicitado', 'en_proceso')""",
            (sol_id,),
        )
        return "descargado"

    # El SAT manda EstadoSolicitud=0 cuando rechaza la consulta (p. ej. "No se
    # encontró la información"): no hay nada que esperar. Salvo el 404 ("Error
    # no controlado"), que el SAT pide reintentar. Un estado que no se reconoce
    # (otro número, o la respuesta sin estado) se sigue esperando: podría ser
    # transitorio y marcarlo como fallo descartaría la descarga.
    estado_raw = getattr(resultado.get("estado"), "value", resultado.get("estado"))
    consulta_rechazada = str(estado_raw).strip() == "0" and resultado.get("cod_estatus") != "404"
    if estado_str in ESTADOS_FALLO_SAT or consulta_rechazada:
        motivo = f"SAT reportó estado: {estado_str}." if estado_str else "El SAT respondió:"
        db.execute(
            "UPDATE sat_solicitudes SET estado='fallo', error_msg=%s, updated_at=NOW() WHERE id=%s",
            (f"{motivo} {resultado.get('mensaje') or 'sin detalle'}", sol_id),
        )
        return "fallo"

    # En proceso — actualizar contadores y seguir esperando
    db.execute(
        """UPDATE sat_solicitudes SET estado='en_proceso', num_cfdi=%s,
                  intentos=0, proximo_intento=NULL, updated_at=NOW()
           WHERE id=%s AND estado IN ('solicitado', 'en_proceso')""",
        (num_cfdi, sol_id),
    )
    return "en_proceso"
