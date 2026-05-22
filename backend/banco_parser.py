"""
Iteración 3: Ingesta de estados de cuenta bancarios
Soporta CSV y XLSX con detección automática de columnas.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from typing import Optional

RFC_RE = re.compile(r'\b([A-ZÑ&]{3,4}\d{6}[A-Z\d]{3})\b', re.IGNORECASE)

COLUMN_ALIASES = {
    "fecha":     ["fecha", "date", "fec", "dia", "f.operacion", "fecha operacion"],
    "concepto":  ["concepto", "descripcion", "descripcion movimiento", "detalle", "referencia corta", "text"],
    "referencia":["referencia", "ref", "numero", "folio", "num operacion", "clave rastreo"],
    "deposito":  ["deposito", "abono", "credito", "cargo/abono", "entrada", "importe+"],
    "cargo":     ["cargo", "retiro", "debito", "salida", "importe-"],
    "monto":     ["monto", "importe", "amount", "valor"],
    "saldo":     ["saldo", "balance", "saldo final"],
}


@dataclass
class MovimientoBancario:
    fecha: date
    concepto: str
    referencia: str
    monto: Decimal          # positivo=depósito, negativo=cargo
    tipo: str               # 'deposito' | 'cargo'
    saldo: Optional[Decimal] = None
    rfc_detectado: Optional[str] = None
    fila_origen: int = 0    # número de fila en archivo original

    @property
    def es_deposito(self) -> bool:
        return self.tipo == "deposito"

    @property
    def monto_abs(self) -> Decimal:
        return abs(self.monto)


@dataclass
class ResultadoIngesta:
    movimientos: list[MovimientoBancario] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)
    filas_ignoradas: int = 0
    banco_detectado: Optional[str] = None
    periodo_inicio: Optional[date] = None
    periodo_fin: Optional[date] = None

    @property
    def total_depositos(self) -> Decimal:
        return sum(m.monto_abs for m in self.movimientos if m.es_deposito)

    @property
    def total_cargos(self) -> Decimal:
        return sum(m.monto_abs for m in self.movimientos if not m.es_deposito)


class BancoParser:
    """
    Parsea estados de cuenta bancarios.
    Detección automática de columnas, fechas y montos.
    """

    def parse_csv(self, contenido: str | bytes, banco: str = "desconocido") -> ResultadoIngesta:
        import csv, io
        if isinstance(contenido, bytes):
            # Intentar decodificaciones comunes en México
            for enc in ("utf-8-sig", "latin-1", "cp1252"):
                try:
                    contenido = contenido.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue

        reader = csv.reader(io.StringIO(contenido))
        rows = list(reader)
        return self._procesar_filas(rows, banco)

    def parse_xlsx(self, contenido: bytes, banco: str = "desconocido", hoja: int = 0) -> ResultadoIngesta:
        try:
            import openpyxl
            wb = openpyxl.load_workbook(BytesIO(contenido), read_only=True, data_only=True)
            ws = wb.worksheets[hoja]
            rows = []
            for row in ws.iter_rows(values_only=True):
                rows.append([str(c) if c is not None else "" for c in row])
            return self._procesar_filas(rows, banco)
        except ImportError:
            raise RuntimeError("openpyxl no instalado. Ejecuta: pip install openpyxl")

    # ─── núcleo ────────────────────────────────────────────────

    def _procesar_filas(self, rows: list[list], banco: str) -> ResultadoIngesta:
        resultado = ResultadoIngesta(banco_detectado=banco)

        # Detectar fila de encabezado
        header_idx, col_map = self._detectar_encabezado(rows)
        if header_idx is None:
            resultado.errores.append("No se encontró encabezado reconocible")
            return resultado

        # Parsear filas de datos
        for i, row in enumerate(rows[header_idx + 1:], start=header_idx + 2):
            if not any(str(c).strip() for c in row):
                continue  # fila vacía
            try:
                mov = self._parsear_fila(row, col_map, fila=i)
                if mov:
                    self._detectar_rfc(mov)
                    resultado.movimientos.append(mov)
                    # Actualizar período
                    if resultado.periodo_inicio is None or mov.fecha < resultado.periodo_inicio:
                        resultado.periodo_inicio = mov.fecha
                    if resultado.periodo_fin is None or mov.fecha > resultado.periodo_fin:
                        resultado.periodo_fin = mov.fecha
                else:
                    resultado.filas_ignoradas += 1
            except Exception as e:
                resultado.errores.append(f"Fila {i}: {e}")
                resultado.filas_ignoradas += 1

        return resultado

    def _detectar_encabezado(self, rows: list[list]) -> tuple[Optional[int], dict]:
        """Busca la primera fila que contenga columnas reconocibles."""
        todos_aliases = {alias: campo for campo, aliases in COLUMN_ALIASES.items() for alias in aliases}

        for idx, row in enumerate(rows[:20]):  # buscar en primeras 20 filas
            row_lower = [str(c).strip().lower() for c in row]
            matches = {}
            for i, cell in enumerate(row_lower):
                if cell in todos_aliases:
                    campo = todos_aliases[cell]
                    if campo not in matches:
                        matches[campo] = i
            # Necesitamos al menos fecha + (monto o deposito/cargo)
            tiene_fecha = "fecha" in matches
            tiene_monto = "monto" in matches or ("deposito" in matches or "cargo" in matches)
            if tiene_fecha and tiene_monto:
                return idx, matches

        return None, {}

    def _parsear_fila(self, row: list, col_map: dict, fila: int) -> Optional[MovimientoBancario]:
        def get(campo: str, default="") -> str:
            idx = col_map.get(campo)
            if idx is None or idx >= len(row):
                return default
            return str(row[idx]).strip()

        # Fecha
        fecha_str = get("fecha")
        if not fecha_str or fecha_str.lower() in ("fecha", "none", "nan", ""):
            return None
        fecha = self._parse_fecha(fecha_str)
        if not fecha:
            return None

        # Monto
        monto, tipo = self._parse_monto(row, col_map)
        if monto is None or monto == Decimal("0"):
            return None

        # Saldo
        saldo_str = get("saldo")
        saldo = self._parse_decimal(saldo_str)

        return MovimientoBancario(
            fecha=fecha,
            concepto=get("concepto"),
            referencia=get("referencia"),
            monto=monto if tipo == "deposito" else -monto,
            tipo=tipo,
            saldo=saldo,
            fila_origen=fila,
        )

    def _parse_monto(self, row: list, col_map: dict) -> tuple[Optional[Decimal], str]:
        def get_decimal(campo: str) -> Optional[Decimal]:
            idx = col_map.get(campo)
            if idx is None or idx >= len(row):
                return None
            return self._parse_decimal(str(row[idx]))

        # Columnas separadas depósito/cargo
        if "deposito" in col_map or "cargo" in col_map:
            dep = get_decimal("deposito") or Decimal("0")
            car = get_decimal("cargo") or Decimal("0")
            if dep > Decimal("0"):
                return dep, "deposito"
            if car > Decimal("0"):
                return car, "cargo"
            return None, ""

        # Columna única de monto (positivo=depósito, negativo=cargo)
        if "monto" in col_map:
            m = get_decimal("monto")
            if m is not None:
                if m > 0:
                    return m, "deposito"
                elif m < 0:
                    return abs(m), "cargo"

        return None, ""

    def _detectar_rfc(self, mov: MovimientoBancario) -> None:
        texto = f"{mov.concepto} {mov.referencia}".upper()
        match = RFC_RE.search(texto)
        if match:
            mov.rfc_detectado = match.group(1).upper()

    @staticmethod
    def _parse_fecha(s: str) -> Optional[date]:
        s = s.strip().replace("/", "-").replace(".", "-")
        formatos = [
            "%Y-%m-%d", "%d-%m-%Y", "%m-%d-%Y",
            "%d-%b-%Y", "%d %b %Y", "%Y%m%d",
        ]
        for fmt in formatos:
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def _parse_decimal(s: str) -> Optional[Decimal]:
        if not s or s.lower() in ("none", "nan", "", "-"):
            return None
        # Limpiar formato monetario: $1,234.56 -> 1234.56
        s = re.sub(r'[$,\s]', '', s.strip())
        s = s.replace("(", "-").replace(")", "")  # (100) -> -100
        try:
            return Decimal(s)
        except Exception:
            return None
