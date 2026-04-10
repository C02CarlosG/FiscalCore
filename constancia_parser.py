"""
constancia_parser.py
Extrae datos fiscales de la Constancia de Situación Fiscal del SAT (PDF).
Requiere: pip install pdfplumber
"""
from __future__ import annotations

import io
import re
from typing import Optional

try:
    import pdfplumber
    PDFPLUMBER_OK = True
except ImportError:
    PDFPLUMBER_OK = False


# ─── Regex SAT ───────────────────────────────────────────────────────────────

# RFC: persona moral 12 chars, persona física 13 chars
_RE_RFC   = re.compile(r'\b([A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3})\b')
_RE_CURP  = re.compile(r'\b([A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d)\b')
_RE_CP    = re.compile(r'C\.?P\.?\s*:?\s*(\d{5})')

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


def _extraer_texto(pdf_bytes: bytes) -> str:
    if not PDFPLUMBER_OK:
        raise RuntimeError("pdfplumber no está instalado. Ejecuta: pip install pdfplumber")
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        partes = []
        for page in pdf.pages:
            texto = page.extract_text()
            if texto:
                partes.append(texto)
        return "\n".join(partes)


def _buscar_rfc(texto: str) -> Optional[str]:
    # Busca primero después de etiqueta "RFC:"
    m = re.search(r'RFC[:\s]+([A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3})', texto, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    # Fallback: cualquier patrón RFC en el texto
    m = _RE_RFC.search(texto)
    return m.group(1).upper() if m else None


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
            texto_completo: str,   # para depuración / fallback manual
        }
    """
    texto = _extraer_texto(pdf_bytes)

    return {
        "rfc":           _buscar_rfc(texto),
        "razon_social":  _buscar_razon_social(texto),
        "regimenes":     _buscar_regimenes(texto),
        "obligaciones":  _buscar_obligaciones(texto),
        "cp_fiscal":     _buscar_cp(texto),
        "curp":          _buscar_curp(texto),
        "texto_completo": texto[:2000],  # primeros 2000 chars para depuración
    }
