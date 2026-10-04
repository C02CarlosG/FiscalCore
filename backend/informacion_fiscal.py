"""
informacion_fiscal.py
Reglas de F8: lectura y validación de la Constancia de Situación Fiscal y de la
Opinión del cumplimiento de obligaciones fiscales (art. 32-D CFF) que el contador
sube en PDF. Módulo puro: sin base de datos; el router decide qué guardar.
"""
from __future__ import annotations

import io
import re
import unicodedata
from datetime import date, timedelta
from typing import Optional

from . import constancia_parser as cp

TIPOS = ("constancia", "opinion")
MAX_BYTES = 5 * 1024 * 1024
MAX_PAGINAS = 10

# La opinión del cumplimiento vale 30 días naturales a partir de su emisión
# (regla de la RMF sobre la obtención de la opinión, 2.1.37 en las RMF recientes).
# El día de emisión cuenta como el primero: emitida el 3 de octubre, vale hasta el
# 1 de noviembre. Es la lectura conservadora; no presenta como vigente una opinión
# que un tercero ya podría rechazar.
VIGENCIA_OPINION_DIAS = 30

_ILEGIBLE = (
    "No se pudo leer el PDF. Sube el archivo que descargaste del SAT, "
    "no una foto ni un escaneo."
)
_NOMBRE_TIPO = {
    "constancia": "una constancia de situación fiscal",
    "opinion": "una opinión del cumplimiento de obligaciones fiscales",
}

_RFC = r'[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}'
_RE_RFC_ETIQUETADO = re.compile(r'R\.?\s?F\.?\s?C\.?\s*:?\s*(' + _RFC + r')\b', re.IGNORECASE)
_RE_RFC_LIBRE = re.compile(r'\b(' + _RFC + r')\b')
_RE_FOLIO = re.compile(r'\bFolio\s*:?\s*([A-Z0-9]{8,})', re.IGNORECASE)

# Sobre texto normalizado (mayúsculas sin acentos).
_SENTIDOS = (
    (re.compile(r'SENTIDO\s*:?\s*POSITIV[OA]'), "positivo"),
    (re.compile(r'SENTIDO\s*:?\s*NEGATIV[OA]'), "negativo"),
    (re.compile(r'INSCRITO\s+SIN\s+OBLIGACIONES'), "inscrito_sin_obligaciones"),
    (re.compile(r'\bNO\s+INSCRITO\b'), "no_inscrito"),
)


class DocumentoInvalido(ValueError):
    """El PDF no cumple una regla de F8; el mensaje se muestra tal cual al usuario."""


def _normalizar(texto: str) -> str:
    sin_acentos = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in sin_acentos if not unicodedata.combining(c)).upper()


def leer_pdf(contenido: bytes) -> str:
    """Texto del PDF. Rechaza lo que no es PDF, lo cifrado, lo enorme y lo escaneado."""
    if not contenido.startswith(b"%PDF-"):
        raise DocumentoInvalido(_ILEGIBLE)
    if not cp.PDFPLUMBER_OK:
        raise RuntimeError("pdfplumber no está instalado. Ejecuta: pip install pdfplumber")
    try:
        with cp.pdfplumber.open(io.BytesIO(contenido)) as pdf:
            if len(pdf.pages) > MAX_PAGINAS:
                raise DocumentoInvalido(
                    f"El PDF tiene {len(pdf.pages)} páginas; se aceptan hasta {MAX_PAGINAS} páginas."
                )
            texto = "\n".join(p.extract_text() or "" for p in pdf.pages)
    except DocumentoInvalido:
        raise
    except Exception as e:
        if "Password" in type(e).__name__:
            raise DocumentoInvalido("El PDF está protegido con contraseña.")
        raise DocumentoInvalido(_ILEGIBLE)
    if not texto.strip():
        raise DocumentoInvalido(_ILEGIBLE)
    return texto


def detectar_tipo(texto: str) -> Optional[str]:
    norm = _normalizar(texto)
    if re.search(r'OPINION\s+(DEL|DE)\s+CUMPLIMIENTO', norm):
        return "opinion"
    if "CONSTANCIA DE SITUACION FISCAL" in norm or "CEDULA DE IDENTIFICACION FISCAL" in norm:
        return "constancia"
    return None


def buscar_rfc(texto: str) -> Optional[str]:
    """RFC tras la etiqueta "RFC" o "R.F.C."; si no hay etiqueta, el primero del texto."""
    m = _RE_RFC_ETIQUETADO.search(texto) or _RE_RFC_LIBRE.search(texto.upper())
    return m.group(1).upper() if m else None


def _buscar_sentido(texto: str) -> Optional[str]:
    """Sentido de la opinión; si el texto menciona dos distintos, no se adivina."""
    norm = _normalizar(texto)
    encontrados = {sentido for patron, sentido in _SENTIDOS if patron.search(norm)}
    return encontrados.pop() if len(encontrados) == 1 else None


def _buscar_fecha_opinion(texto: str) -> Optional[str]:
    m = re.search(r'practicada\s+el\s+d[ií]a', texto, re.IGNORECASE)
    if m:
        fecha = cp.fecha_en_texto(texto[m.end():])
        if fecha:
            return fecha
    return cp.fecha_en_texto(texto)


def parsear_opinion(texto: str) -> dict:
    folio = _RE_FOLIO.search(texto)
    return {
        "rfc": buscar_rfc(texto),
        "razon_social": cp._buscar_razon_social(texto),
        "fecha_emision": _buscar_fecha_opinion(texto),
        "sentido": _buscar_sentido(texto),
        "folio": folio.group(1).upper() if folio else None,
    }


def analizar_documento(tipo: str, contenido: bytes, rfc_empresa: str) -> dict:
    """Lee y valida el PDF para la empresa. Devuelve ``{rfc, fecha_emision, datos}``.

    Lanza `DocumentoInvalido` si el PDF no se puede leer, no es del tipo indicado o
    no es del RFC de la empresa.
    """
    if tipo not in TIPOS:
        raise ValueError(f"tipo de documento desconocido: {tipo}")
    texto = leer_pdf(contenido)
    detectado = detectar_tipo(texto)
    if detectado != tipo:
        raise DocumentoInvalido(f"El archivo no parece {_NOMBRE_TIPO[tipo]}.")

    if tipo == "constancia":
        leido = cp.parsear_texto_constancia(texto)
        rfc = buscar_rfc(texto)
        fecha = leido["fecha_emision"]
        datos = {k: leido[k] for k in (
            "razon_social", "regimenes", "obligaciones", "cp_fiscal", "curp",
            "id_cif", "estatus_padron",
        )}
    else:
        leido = parsear_opinion(texto)
        rfc = leido["rfc"]
        fecha = leido["fecha_emision"]
        datos = {k: leido[k] for k in ("razon_social", "sentido", "folio")}

    if not rfc:
        raise DocumentoInvalido("No se encontró el RFC en el documento.")
    esperado = (rfc_empresa or "").strip().upper()
    if rfc != esperado:
        raise DocumentoInvalido(f"El documento es del RFC {rfc}, pero la empresa es {esperado}.")

    return {"rfc": rfc, "fecha_emision": fecha, "datos": datos}


def estado_opinion(fecha_emision: Optional[date], hoy: date) -> dict:
    """Vigencia de la opinión: 30 días naturales, el de emisión incluido."""
    if fecha_emision is None:
        return {"vigente_hasta": None, "vigente": None}
    hasta = fecha_emision + timedelta(days=VIGENCIA_OPINION_DIAS - 1)
    return {"vigente_hasta": hasta.isoformat(), "vigente": hoy <= hasta}


def antiguedad_dias(fecha_emision: Optional[date], hoy: date) -> Optional[int]:
    return None if fecha_emision is None else (hoy - fecha_emision).days
