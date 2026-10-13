"""Lista 69-B del SAT (spec 2026-10-13-efos-69b-design): lectura y validación del CSV.

Sin base de datos ni red. El archivo es un dato **no confiable** (se descarga por HTTP sin TLS): se valida
la cabecera, cada fila y la proporción de filas inválidas, y nada se interpola en SQL.
"""
from __future__ import annotations

import csv
import io
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

MAX_BYTES = 50 * 1024 * 1024
MAX_DESCARTE = 0.01          # más de 1 % de filas inválidas: el archivo no es confiable
CAIDA_MAXIMA = 0.20          # menos filas que 80 % de la importación anterior: archivo truncado o manipulado
RFC_GENERICO = "XXXXXXXXXXXX"
_RFC_RE = re.compile(r"[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}")

SITUACIONES = ("Presunto", "Desvirtuado", "Definitivo", "Sentencia Favorable")
RIESGO = {"Presunto": "alto", "Definitivo": "critico", "Desvirtuado": "informativo", "Sentencia Favorable": "informativo"}
_POR_MINUSCULAS = {s.casefold(): s for s in SITUACIONES}

COLUMNAS = (
    "No", "RFC", "Nombre del Contribuyente", "Situación del contribuyente",
    "Número y fecha de oficio global de presunción SAT", "Publicación página SAT presuntos",
    "Número y fecha de oficio global de presunción DOF", "Publicación DOF presuntos",
    "Número y fecha de oficio global de contribuyentes que desvirtuaron SAT", "Publicación página SAT desvirtuados",
    "Número y fecha de oficio global de contribuyentes que desvirtuaron DOF", "Publicación DOF desvirtuados",
    "Número y fecha de oficio global de definitivos SAT", "Publicación página SAT definitivos",
    "Número y fecha de oficio global de definitivos DOF", "Publicación DOF definitivos",
    "Número y fecha de oficio global de sentencia favorable SAT", "Publicación página SAT sentencia favorable",
    "Número y fecha de oficio global de sentencia favorable DOF", "Publicación DOF sentencia favorable",
)

# (etapa, origen) → (columna del oficio, columna de la fecha)
_ETAPAS = {
    "presunto_sat": (4, 5), "presunto_dof": (6, 7),
    "desvirtuado_sat": (8, 9), "desvirtuado_dof": (10, 11),
    "definitivo_sat": (12, 13), "definitivo_dof": (14, 15),
    "sentencia_sat": (16, 17), "sentencia_dof": (18, 19),
}
_ETAPA_DE_SITUACION = {"Presunto": "presunto_sat", "Desvirtuado": "desvirtuado_sat",
                       "Definitivo": "definitivo_sat", "Sentencia Favorable": "sentencia_sat"}

_MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
          "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}
_FECHA_RE = re.compile(r"\d{1,2}/\d{1,2}/\d{4}")
_EXCEL_BASE = date(1899, 12, 30)       # origen del número de serie de fechas de Excel
_ACTUALIZADA = re.compile(r"actualizada\s+al\s+(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})", re.IGNORECASE)


class ErrorImportacion(ValueError):
    """El archivo no se puede importar; el mensaje es apto para mostrarse al administrador."""


@dataclass(frozen=True)
class FilaEfos:
    no_sat: int
    rfc: str
    nombre: str
    situacion: str
    fechas: dict
    oficios: dict


@dataclass(frozen=True)
class ResultadoParseo:
    fecha_archivo: Optional[date]
    filas: list
    leidas: int
    descartadas: int
    genericas: int
    fechas_ilegibles: int = 0


def _norm(texto: str) -> str:
    return unicodedata.normalize("NFC", texto).strip()


def _fecha_del_preambulo(filas: list) -> Optional[date]:
    for fila in filas[:5]:
        for celda in fila:
            m = _ACTUALIZADA.search(celda)
            if m and m.group(2).casefold() in _MESES:
                try:
                    return date(int(m.group(3)), _MESES[m.group(2).casefold()], int(m.group(1)))
                except ValueError:
                    return None
    return None


def _indice_cabecera(filas: list) -> int:
    for i, fila in enumerate(filas):
        if len(fila) >= 2 and _norm(fila[0]) == "No" and _norm(fila[1]) == "RFC":
            return i
    raise ErrorImportacion("No se encontró la cabecera esperada (No, RFC, …) en el archivo")


def _fecha(valor: str) -> tuple:
    """``(fecha, legible)``. El SAT publica fechas sueltas, **dos publicaciones en una celda** separadas por « - » (se
    toma la más reciente) y, en algunas filas, el **número de serie de Excel**. Una fecha ilegible no invalida la fila:
    el riesgo lo da el RFC y la situación; la fecha solo informa (verificado con el archivo real del SAT)."""
    valor = valor.strip()
    if not valor:
        return None, True
    if valor.isdigit() and 20000 <= int(valor) <= 80000:
        return _EXCEL_BASE + timedelta(days=int(valor)), True
    encontradas = []
    for texto in _FECHA_RE.findall(valor):
        try:
            encontradas.append(datetime.strptime(texto, "%d/%m/%Y").date())
        except ValueError:
            pass
    return (max(encontradas), True) if encontradas else (None, False)


def _fila(fila: list) -> tuple:
    """``(fila validada o None si es inválida, fechas ilegibles de la fila)``."""
    if len(fila) < len(COLUMNAS):
        return None, 0
    try:
        no = int(fila[0].strip())
        situacion = _POR_MINUSCULAS.get(_norm(fila[3]).casefold())
        rfc = fila[1].strip().upper()
        if situacion is None or not _RFC_RE.fullmatch(rfc):
            return None, 0
    except ValueError:
        return None, 0
    leidas = {k: _fecha(fila[f]) for k, (_, f) in _ETAPAS.items()}
    fechas = {k: d for k, (d, _) in leidas.items()}
    oficios = {k: _norm(fila[o]) for k, (o, _) in _ETAPAS.items()}
    return FilaEfos(no, rfc, _norm(fila[2]), situacion, fechas, oficios), sum(1 for _, ok in leidas.values() if not ok)


def parsear(contenido: bytes) -> ResultadoParseo:
    if len(contenido) > MAX_BYTES:
        raise ErrorImportacion(f"El archivo excede el tamaño máximo de {MAX_BYTES // (1024 * 1024)} MB")
    try:
        texto = contenido.decode("cp1252")
    except UnicodeDecodeError:
        raise ErrorImportacion("El archivo no está en codificación cp1252")
    filas = list(csv.reader(io.StringIO(texto)))
    fecha_archivo = _fecha_del_preambulo(filas)
    i = _indice_cabecera(filas)
    if [_norm(c) for c in filas[i]] != [_norm(c) for c in COLUMNAS]:
        raise ErrorImportacion("La cabecera del archivo no es la esperada (20 columnas del listado 69-B)")

    validas, descartadas, genericas, ilegibles = [], 0, 0, 0
    for crudo in filas[i + 1:]:
        if not any(c.strip() for c in crudo):
            continue
        if len(crudo) > 1 and crudo[1].strip().upper() == RFC_GENERICO:
            genericas += 1
            continue
        fila, malas = _fila(crudo)
        if fila is None:
            descartadas += 1
        else:
            validas.append(fila)
            ilegibles += malas

    leidas = len(validas) + descartadas + genericas
    if not validas:
        raise ErrorImportacion("El archivo no trae filas válidas (sin filas de contribuyentes)")
    if descartadas / leidas > MAX_DESCARTE:
        raise ErrorImportacion(f"{descartadas} de {leidas} filas son inválidas (más de {int(MAX_DESCARTE * 100)} %)")
    return ResultadoParseo(fecha_archivo, validas, leidas, descartadas, genericas, ilegibles)


def validar_contra_anterior(nuevas: int, anteriores: Optional[int]) -> None:
    """Rechaza un archivo con muchas menos filas que la última importación correcta (truncado o manipulado)."""
    if anteriores and nuevas < anteriores * (1 - CAIDA_MAXIMA):
        raise ErrorImportacion(
            f"Caída sospechosa de filas: {nuevas} contra {anteriores} de la importación anterior (más de 20 %)")


def fecha_de_etapa(situacion: str, fechas: dict) -> Optional[date]:
    """Fecha de publicación en la página del SAT de la etapa que corresponde a la situación vigente."""
    return fechas.get(_ETAPA_DE_SITUACION.get(situacion, ""))
