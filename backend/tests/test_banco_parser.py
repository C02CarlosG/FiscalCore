"""Tests de backend/banco_parser.py — ingesta de estados de cuenta bancarios."""
from datetime import date
from decimal import Decimal
from io import BytesIO

from backend.banco_parser import BancoParser, MovimientoBancario


# ─── parse_csv: columnas separadas depósito/cargo ─────────────────────────────

def test_parse_csv_columnas_separadas_deposito_cargo():
    csv = (
        "Fecha,Concepto,Referencia,Deposito,Cargo,Saldo\n"
        "2026-01-05,PAGO CLIENTE ACM010101AA1,REF001,1000.00,,5000.00\n"
        "2026-01-06,COMISION BANCARIA,REF002,,50.00,4950.00\n"
    )
    resultado = BancoParser().parse_csv(csv, banco="bbva")

    assert resultado.errores == []
    assert len(resultado.movimientos) == 2

    dep = resultado.movimientos[0]
    assert dep.es_deposito is True
    assert dep.monto == Decimal("1000.00")
    assert dep.monto_abs == Decimal("1000.00")
    assert dep.rfc_detectado == "ACM010101AA1"
    assert dep.saldo == Decimal("5000.00")

    cargo = resultado.movimientos[1]
    assert cargo.es_deposito is False
    assert cargo.monto == Decimal("-50.00")
    assert cargo.monto_abs == Decimal("50.00")

    assert resultado.total_depositos == Decimal("1000.00")
    assert resultado.total_cargos == Decimal("50.00")
    assert resultado.periodo_inicio == date(2026, 1, 5)
    assert resultado.periodo_fin == date(2026, 1, 6)
    assert resultado.banco_detectado == "bbva"


# ─── parse_csv: columna única de monto ────────────────────────────────────────

def test_parse_csv_columna_unica_monto_signo_indica_tipo():
    csv = "Fecha,Concepto,Monto\n2026-02-01,Deposito nomina,1500.50\n2026-02-02,Retiro cajero,-200.00\n"
    resultado = BancoParser().parse_csv(csv)

    assert len(resultado.movimientos) == 2
    assert resultado.movimientos[0].tipo == "deposito"
    assert resultado.movimientos[0].monto == Decimal("1500.50")
    assert resultado.movimientos[1].tipo == "cargo"
    assert resultado.movimientos[1].monto == Decimal("-200.00")


# ─── Detección de encabezado ──────────────────────────────────────────────────

def test_detecta_encabezado_con_filas_basura_arriba():
    csv = "ESTADO DE CUENTA BBVA\nPeriodo: Enero 2026\nFecha,Concepto,Monto\n2026-01-10,Pago,100.00\n"
    resultado = BancoParser().parse_csv(csv)

    assert resultado.errores == []
    assert len(resultado.movimientos) == 1
    assert resultado.movimientos[0].concepto == "Pago"


def test_sin_encabezado_reconocible_genera_error():
    csv = "A,B,C\n1,2,3\n"
    resultado = BancoParser().parse_csv(csv)

    assert resultado.movimientos == []
    assert len(resultado.errores) == 1
    assert "encabezado" in resultado.errores[0].lower()


# ─── Filas vacías / inválidas ──────────────────────────────────────────────────

def test_fila_vacia_se_ignora_silenciosamente():
    csv = "Fecha,Concepto,Monto\n2026-01-10,Pago,100.00\n\n2026-01-11,Otro pago,200.00\n"
    resultado = BancoParser().parse_csv(csv)

    assert len(resultado.movimientos) == 2
    assert resultado.filas_ignoradas == 0
    assert resultado.errores == []


def test_fila_con_fecha_invalida_se_cuenta_como_ignorada():
    csv = "Fecha,Concepto,Monto\nno-es-fecha,Pago raro,100.00\n2026-01-11,Pago valido,200.00\n"
    resultado = BancoParser().parse_csv(csv)

    assert len(resultado.movimientos) == 1
    assert resultado.filas_ignoradas == 1
    assert resultado.errores == []


def test_fila_con_monto_cero_se_ignora():
    csv = "Fecha,Concepto,Monto\n2026-01-10,Sin movimiento,0.00\n"
    resultado = BancoParser().parse_csv(csv)

    assert resultado.movimientos == []
    assert resultado.filas_ignoradas == 1


# ─── Detección de RFC ──────────────────────────────────────────────────────────

def test_detectar_rfc_en_concepto():
    mov = MovimientoBancario(
        fecha=date(2026, 1, 1), concepto="TRANSFERENCIA A PROV010101AA1",
        referencia="", monto=Decimal("100"), tipo="deposito",
    )
    BancoParser()._detectar_rfc(mov)
    assert mov.rfc_detectado == "PROV010101AA1"


def test_detectar_rfc_ausente():
    mov = MovimientoBancario(
        fecha=date(2026, 1, 1), concepto="PAGO SIN RFC VISIBLE",
        referencia="", monto=Decimal("100"), tipo="deposito",
    )
    BancoParser()._detectar_rfc(mov)
    assert mov.rfc_detectado is None


# ─── Parsing de fechas ──────────────────────────────────────────────────────────

def test_parse_fecha_iso():
    assert BancoParser._parse_fecha("2026-01-05") == date(2026, 1, 5)


def test_parse_fecha_con_slashes_dia_mes_anio():
    assert BancoParser._parse_fecha("05/01/2026") == date(2026, 1, 5)


def test_parse_fecha_sin_separadores():
    assert BancoParser._parse_fecha("20260105") == date(2026, 1, 5)


def test_parse_fecha_invalida_retorna_none():
    assert BancoParser._parse_fecha("no-es-una-fecha") is None


# ─── Parsing de decimales ───────────────────────────────────────────────────────

def test_parse_decimal_formato_monetario():
    assert BancoParser._parse_decimal("$1,234.56") == Decimal("1234.56")


def test_parse_decimal_parentesis_es_negativo():
    assert BancoParser._parse_decimal("(100.00)") == Decimal("-100.00")


def test_parse_decimal_valores_vacios_retornan_none():
    assert BancoParser._parse_decimal("") is None
    assert BancoParser._parse_decimal("nan") is None
    assert BancoParser._parse_decimal("-") is None
    assert BancoParser._parse_decimal(None) is None


# ─── Encoding de bytes ───────────────────────────────────────────────────────────

def test_parse_csv_bytes_con_acentos_latin1():
    csv = "Fecha,Concepto,Monto\n2026-01-10,PAGO NÓMINA,100.00\n"
    resultado = BancoParser().parse_csv(csv.encode("latin-1"))

    assert len(resultado.movimientos) == 1
    assert resultado.movimientos[0].concepto == "PAGO NÓMINA"


# ─── XLSX ────────────────────────────────────────────────────────────────────────

def test_parse_xlsx_basico():
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Fecha", "Concepto", "Monto"])
    ws.append(["2026-01-10", "Pago proveedor", -300.00])
    buf = BytesIO()
    wb.save(buf)

    resultado = BancoParser().parse_xlsx(buf.getvalue())

    assert len(resultado.movimientos) == 1
    mov = resultado.movimientos[0]
    assert mov.tipo == "cargo"
    assert mov.monto == Decimal("-300.00")
