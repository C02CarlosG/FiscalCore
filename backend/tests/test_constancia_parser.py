"""Tests de backend/constancia_parser.py — extracción de datos fiscales del PDF
de la Constancia de Situación Fiscal del SAT.

Las funciones internas de regex/texto se prueban directamente sobre strings.
Para `parsear_constancia` (que sí abre un PDF con pdfplumber) se genera un PDF
mínimo válido en memoria (`pdf_sintetico.py`), sin depender de un PDF real del SAT ni de librerías
extra de generación de PDFs.
"""
import pytest

from backend import constancia_parser as cp
from backend.tests.pdf_sintetico import constancia_sintetica, pdf_con_texto as _pdf_con_texto


# ─── _buscar_rfc ──────────────────────────────────────────────────────────────

def test_buscar_rfc_con_etiqueta():
    texto = "Datos de identificación\nRFC: ACM010101AA1\nOtro dato"
    assert cp._buscar_rfc(texto) == "ACM010101AA1"


def test_buscar_rfc_fallback_sin_etiqueta():
    texto = "Contribuyente ACM010101AA1 con obligaciones vigentes"
    assert cp._buscar_rfc(texto) == "ACM010101AA1"


def test_buscar_rfc_ausente_retorna_none():
    assert cp._buscar_rfc("Sin ningún identificador fiscal aquí") is None


# ─── _buscar_razon_social ─────────────────────────────────────────────────────

def test_buscar_razon_social_misma_linea():
    texto = "RFC: ACM010101AA1\nRazón Social: ACME COMERCIALIZADORA SA DE CV\nCP: 06600"
    assert cp._buscar_razon_social(texto) == "ACME COMERCIALIZADORA SA DE CV"


def test_buscar_razon_social_linea_siguiente():
    texto = "Nombre, denominación o razón social:\nACME COMERCIALIZADORA SA DE CV\nRFC: ACM010101AA1"
    assert cp._buscar_razon_social(texto) == "ACME COMERCIALIZADORA SA DE CV"


def test_buscar_razon_social_ausente_retorna_none():
    assert cp._buscar_razon_social("Texto sin ese campo") is None


# ─── _buscar_regimenes ────────────────────────────────────────────────────────

def test_buscar_regimenes_conocidos():
    texto = "Regímenes:\nRégimen General de Ley Personas Morales\nOtro texto"
    assert cp._buscar_regimenes(texto) == ["Régimen General de Ley Personas Morales"]


def test_buscar_regimenes_multiples():
    texto = (
        "Régimen de Arrendamiento\n"
        "Sueldos y Salarios e Ingresos Asimilados a Salarios\n"
    )
    resultado = cp._buscar_regimenes(texto)
    assert "Régimen de Arrendamiento" in resultado
    assert "Sueldos y Salarios e Ingresos Asimilados a Salarios" in resultado


def test_buscar_regimenes_generico_si_no_hay_conocidos():
    texto = "Régimen especial no catalogado de prueba extendida"
    assert cp._buscar_regimenes(texto) == [texto]


def test_buscar_regimenes_sin_coincidencias():
    assert cp._buscar_regimenes("Texto sin la palabra clave") == []


# ─── _buscar_obligaciones ─────────────────────────────────────────────────────

def test_buscar_obligaciones_detecta_periodicidad():
    texto = "Pago Definitivo de IVA Mensual\nDeclaración Anual Anual\n"
    resultado = cp._buscar_obligaciones(texto)
    assert {"descripcion": "Pago Definitivo de IVA Mensual", "periodicidad": "Mensual"} in resultado
    assert {"descripcion": "Declaración Anual Anual", "periodicidad": "Anual"} in resultado


def test_buscar_obligaciones_deduplica():
    texto = "Pago Definitivo de IVA Mensual\nPago Definitivo de IVA Mensual\n"
    resultado = cp._buscar_obligaciones(texto)
    assert len(resultado) == 1


def test_buscar_obligaciones_sin_coincidencias():
    assert cp._buscar_obligaciones("Sin ninguna periodicidad aquí") == []


# ─── _buscar_cp / _buscar_curp ────────────────────────────────────────────────

def test_buscar_cp_encontrado():
    assert cp._buscar_cp("Domicilio fiscal C.P. 06600 Ciudad de México") == "06600"


def test_buscar_cp_ausente():
    assert cp._buscar_cp("Sin código postal") is None


def test_buscar_curp_encontrado():
    texto = "CURP: XAXX010101HDFRRR09"
    assert cp._buscar_curp(texto) == "XAXX010101HDFRRR09"


def test_buscar_curp_ausente():
    assert cp._buscar_curp("Persona moral sin CURP") is None


# ─── parsear_constancia (integración con PDF real generado en memoria) ────────

def test_parsear_constancia_extrae_todos_los_campos():
    pdf_bytes = _pdf_con_texto([
        "CONSTANCIA DE SITUACION FISCAL",
        "RFC: ACM010101AA1",
        "Razón Social: ACME COMERCIALIZADORA SA DE CV",
        "Régimen General de Ley Personas Morales",
        "Pago Definitivo de IVA Mensual",
        "C.P. 06600",
    ])

    resultado = cp.parsear_constancia(pdf_bytes)

    assert resultado["rfc"] == "ACM010101AA1"
    assert resultado["razon_social"] == "ACME COMERCIALIZADORA SA DE CV"
    assert resultado["regimenes"] == ["Régimen General de Ley Personas Morales"]
    assert resultado["obligaciones"] == [
        {"descripcion": "Pago Definitivo de IVA Mensual", "periodicidad": "Mensual"}
    ]
    assert resultado["cp_fiscal"] == "06600"
    assert resultado["curp"] is None
    assert "RFC: ACM010101AA1" in resultado["texto_completo"]


def test_parsear_constancia_sin_pdfplumber_lanza_runtime_error(monkeypatch):
    monkeypatch.setattr(cp, "PDFPLUMBER_OK", False)
    with pytest.raises(RuntimeError, match="pdfplumber"):
        cp.parsear_constancia(b"lo que sea")


# ─── Datos agregados en F8: fecha de emisión, idCIF y estatus ────────────────

def test_parsear_constancia_lee_fecha_idcif_y_estatus():
    resultado = cp.parsear_constancia(constancia_sintetica())

    assert resultado["rfc"] == "ACM010101AA1"
    assert resultado["fecha_emision"] == "2026-10-03"
    assert resultado["id_cif"] == "12345678901"
    assert resultado["estatus_padron"] == "ACTIVO"
    assert resultado["cp_fiscal"] == "68000"


@pytest.mark.parametrize("texto,esperada", [
    ("OAXACA A 03 DE OCTUBRE DE 2026", "2026-10-03"),
    ("emitida el 1 de septiembre de 2026", "2026-09-01"),
    ("Fecha: 15/01/2026", "2026-01-15"),
    ("A 31 DE FEBRERO DE 2026", None),
    ("A 03 DE BRUMARIO DE 2026", None),
    ("sin fecha", None),
])
def test_fecha_en_texto(texto, esperada):
    assert cp.fecha_en_texto(texto) == esperada


def test_fecha_de_emision_prefiere_la_etiqueta_sobre_otras_fechas():
    texto = (
        "Fecha inicio de operaciones: 01 DE ENERO DE 2001\n"
        "Lugar y Fecha de Emisión\nOAXACA A 03 DE OCTUBRE DE 2026"
    )
    assert cp._buscar_fecha_emision(texto) == "2026-10-03"


def test_campos_nuevos_ausentes_son_none():
    resultado = cp.parsear_constancia(_pdf_con_texto(["CONSTANCIA DE SITUACION FISCAL", "RFC: ACM010101AA1"]))
    assert resultado["fecha_emision"] is None
    assert resultado["id_cif"] is None
    assert resultado["estatus_padron"] is None
