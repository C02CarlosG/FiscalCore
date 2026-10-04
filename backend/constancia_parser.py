"""
constancia_parser.py
Extrae datos fiscales de la Constancia de Situación Fiscal del SAT (PDF).
Requiere: pip install pdfplumber
"""
from __future__ import annotations

import io
import re
from datetime import date
from typing import Optional

try:
    import pdfplumber
    PDFPLUMBER_OK = True
except ImportError:
    PDFPLUMBER_OK = False


# ─── Regex SAT ───────────────────────────────────────────────────────────────

# RFC: persona moral 12 chars, persona física 13 chars. Se deriva del canónico de
# cfdi_parser (sin anclas y con grupos no capturantes) para no mantener dos copias.
from .cfdi_parser import RFC_REGEX as _RFC_CANONICO

RFC_PATRON = re.sub(r'\((?!\?)', '(?:', _RFC_CANONICO.pattern.strip('^$'))
_RE_RFC   = re.compile(r'\b(' + RFC_PATRON + r')\b')
_RE_CURP  = re.compile(r'\b([A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d)\b')
_RE_CP    = re.compile(r'(?:C\.?P\.?|C[óo]digo\s+Postal)\s*:?\s*(\d{5})', re.IGNORECASE)
_RE_ID_CIF = re.compile(r'idCIF\s*:?\s*(\d{6,})', re.IGNORECASE)
_RE_ESTATUS = re.compile(r'Estatus\s+en\s+el\s+padr[óo]n\s*:?\s*([A-ZÁÉÍÓÚÑ ]+?)\s*$', re.IGNORECASE | re.MULTILINE)

_MESES = {
    "ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4, "MAYO": 5, "JUNIO": 6,
    "JULIO": 7, "AGOSTO": 8, "SEPTIEMBRE": 9, "SETIEMBRE": 9, "OCTUBRE": 10,
    "NOVIEMBRE": 11, "DICIEMBRE": 12,
}
_RE_FECHA_LETRA = re.compile(r'\b(\d{1,2})\s+DE\s+([A-Z]+)\s+DE(?:L)?\s+(\d{4})\b', re.IGNORECASE)
_RE_FECHA_NUM   = re.compile(r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b')

# Regímenes más comunes del SAT — texto que aparece en la constancia
_REGIMENES_CONOCIDOS = [
    "Régimen Simplificado de Confianza",
    "Régimen de Actividades Empresariales y Profesionales",
    "Régimen de Incorporación Fiscal",
    "Régimen General de Ley Personas Morales",
    "Régimen de Arrendamiento",
    "Sueldos y Salarios e Ingresos Asimilados a Salarios",
    "Régimen de las Personas Físicas con Actividades Empresariales",
    "Dividendos (socios y accionistas)",
    "Demás ingresos",
    "Consolidación",
    "Personas Morales con Fines no Lucrativos",
    "Residentes en el Extranjero sin Establecimiento Permanente",
    "Ingresos por Intereses",
    "Sin obligaciones fiscales",
    "Incorporación Fiscal",
]

# Etiquetas de periodicidad para detectar obligaciones
_PERIODICIDADES = {"Mensual", "Bimestral", "Anual", "Trimestral", "Eventual", "Semestral"}


def extraer_texto(pdf_bytes: bytes) -> str:
    if not PDFPLUMBER_OK:
        raise RuntimeError("pdfplumber no está instalado. Ejecuta: pip install pdfplumber")
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        partes = []
        for page in pdf.pages:
            texto = page.extract_text()
            if texto:
                partes.append(texto)
        return "\n".join(partes)


_extraer_texto = extraer_texto  # nombre anterior, por compatibilidad


def _buscar_rfc(texto: str) -> Optional[str]:
    # Busca primero después de etiqueta "RFC:"
    m = re.search(r'RFC[:\s]+(' + RFC_PATRON + r')', texto, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    # Fallback: cualquier patrón RFC en el texto
    m = _RE_RFC.search(texto)
    return m.group(1).upper() if m else None


def _campo(texto: str, etiqueta: str) -> Optional[str]:
    m = re.search(etiqueta + r'\s*:[ \t]*([^\n]*)', texto, re.IGNORECASE)
    valor = m.group(1).strip() if m else ""
    return valor or None


def _buscar_nombre_persona_fisica(texto: str) -> Optional[str]:
    """La constancia de persona física separa Nombre (s), Primer y Segundo Apellido."""
    if not re.search(r'Primer\s+Apellido', texto, re.IGNORECASE):
        return None
    partes = [
        _campo(texto, r'Nombre\s*\(s\)'),
        _campo(texto, r'Primer\s+Apellido'),
        _campo(texto, r'Segundo\s+Apellido'),
    ]
    nombre = " ".join(p for p in partes if p)
    return nombre or None


def _buscar_razon_social(texto: str) -> Optional[str]:
    lineas = texto.splitlines()
    for i, linea in enumerate(lineas):
        linea_norm = linea.strip()
        if re.search(r'(Nombre|Denominaci[oó]n|Raz[oó]n\s+Social)', linea_norm, re.IGNORECASE):
            # La razón social suele estar en la misma línea después de ":" o en la siguiente
            partes = linea_norm.split(":", 1)
            if len(partes) == 2 and partes[1].strip():
                return partes[1].strip()
            if i + 1 < len(lineas):
                candidato = lineas[i + 1].strip()
                # Filtra líneas que son etiquetas (muy cortas o con palabras clave de campo)
                if candidato and len(candidato) > 3 and not re.search(r'^(RFC|CURP|C\.P\.|Fecha)', candidato, re.IGNORECASE):
                    return candidato
    return None


def _buscar_regimenes(texto: str) -> list[str]:
    encontrados = []
    texto_upper = texto.upper()
    for reg in _REGIMENES_CONOCIDOS:
        if reg.upper() in texto_upper:
            encontrados.append(reg)
    if not encontrados:
        # Búsqueda genérica: líneas que contengan "Régimen"
        for linea in texto.splitlines():
            if re.search(r'r[eé]gimen', linea, re.IGNORECASE) and len(linea.strip()) > 10:
                limpio = linea.strip()
                if limpio not in encontrados:
                    encontrados.append(limpio)
    return encontrados


def _buscar_obligaciones(texto: str) -> list[dict]:
    obligaciones = []
    lineas = texto.splitlines()
    for linea in lineas:
        linea_strip = linea.strip()
        for periodo in _PERIODICIDADES:
            if periodo.lower() in linea_strip.lower():
                # Intenta extraer nombre de la obligación + periodicidad
                obligaciones.append({
                    "descripcion": linea_strip,
                    "periodicidad": periodo,
                })
                break
    # Deduplica por descripción
    vistos = set()
    unicos = []
    for o in obligaciones:
        key = o["descripcion"][:60]
        if key not in vistos:
            vistos.add(key)
            unicos.append(o)
    return unicos


def _buscar_cp(texto: str) -> Optional[str]:
    m = _RE_CP.search(texto)
    return m.group(1) if m else None


def _buscar_curp(texto: str) -> Optional[str]:
    m = _RE_CURP.search(texto)
    return m.group(1) if m else None


def _fecha_iso(dia: int, mes: int, anio: int) -> Optional[str]:
    try:
        return date(anio, mes, dia).isoformat()
    except ValueError:
        return None


def fecha_en_texto(texto: str) -> Optional[str]:
    """Primera fecha válida del texto ("03 DE OCTUBRE DE 2026" o "03/10/2026"), en ISO.

    Las fechas con día o mes imposibles se ignoran y se sigue buscando.
    """
    candidatas = []
    for m in _RE_FECHA_LETRA.finditer(texto):
        mes = _MESES.get(m.group(2).upper())
        if mes:
            candidatas.append((m.start(), _fecha_iso(int(m.group(1)), mes, int(m.group(3)))))
    for m in _RE_FECHA_NUM.finditer(texto):
        candidatas.append((m.start(), _fecha_iso(int(m.group(1)), int(m.group(2)), int(m.group(3)))))
    for _, fecha in sorted(candidatas):
        if fecha:
            return fecha
    return None


def _buscar_fecha_emision(texto: str) -> Optional[str]:
    """Fecha tras "Fecha de Emisión"; la constancia trae otras fechas (inicio de
    operaciones, último cambio de estado) que no son la de emisión."""
    m = re.search(r'Fecha\s+de\s+Emisi[óo]n', texto, re.IGNORECASE)
    if m:
        fecha = fecha_en_texto(texto[m.end():])
        if fecha:
            return fecha
    return None


def _buscar_id_cif(texto: str) -> Optional[str]:
    m = _RE_ID_CIF.search(texto)
    return m.group(1) if m else None


def _buscar_estatus(texto: str) -> Optional[str]:
    m = _RE_ESTATUS.search(texto)
    return m.group(1).strip().upper() if m else None


# ─── Función principal ───────────────────────────────────────────────────────

def parsear_constancia(pdf_bytes: bytes) -> dict:
    """
    Extrae datos fiscales de la Constancia de Situación Fiscal del SAT.

    Returns:
        {
            rfc: str | None,
            razon_social: str | None,
            regimenes: list[str],
            obligaciones: list[{descripcion, periodicidad}],
            cp_fiscal: str | None,
            curp: str | None,
            fecha_emision: str | None,   # ISO, tras "Fecha de Emisión"
            id_cif: str | None,
            estatus_padron: str | None,  # ACTIVO, SUSPENDIDO, …
            texto_completo: str,   # para depuración / fallback manual
        }
    """
    return parsear_texto_constancia(extraer_texto(pdf_bytes))


def parsear_texto_constancia(texto: str) -> dict:
    """Igual que `parsear_constancia`, sobre el texto ya extraído del PDF."""
    return {
        "rfc":           _buscar_rfc(texto),
        "razon_social":  _buscar_nombre_persona_fisica(texto) or _buscar_razon_social(texto),
        "regimenes":     _buscar_regimenes(texto),
        "obligaciones":  _buscar_obligaciones(texto),
        "cp_fiscal":     _buscar_cp(texto),
        "curp":          _buscar_curp(texto),
        "fecha_emision": _buscar_fecha_emision(texto),
        "id_cif":        _buscar_id_cif(texto),
        "estatus_padron": _buscar_estatus(texto),
        "texto_completo": texto[:2000],  # primeros 2000 chars para depuración
    }
