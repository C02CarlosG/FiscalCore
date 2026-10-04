"""Reglas puras de F8: lectura y validación de la constancia de situación fiscal y de
la opinión del cumplimiento. PDF sintéticos generados en memoria."""
from datetime import date

import pytest

from backend import informacion_fiscal as inf
from backend.tests.pdf_sintetico import RFC_PRUEBA, constancia_sintetica, opinion_sintetica, pdf_con_texto


# ─── buscar_rfc ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("texto", [
    "RFC: ACM010101AA1",
    "Clave de R.F.C.: ACM010101AA1",
    "Clave de R.F.C. acm010101aa1",
    "contribuyente ACM010101AA1 sin etiqueta",
])
def test_buscar_rfc(texto):
    assert inf.buscar_rfc(texto) == "ACM010101AA1"


def test_buscar_rfc_prefiere_el_etiquetado():
    assert inf.buscar_rfc("Emisor XYZ990101AB2\nRFC: ACM010101AA1") == "ACM010101AA1"


def test_buscar_rfc_persona_fisica_y_ausente():
    assert inf.buscar_rfc("RFC: GAHC800101AB3") == "GAHC800101AB3"
    assert inf.buscar_rfc("nada aquí") is None


# ─── detectar_tipo ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("texto,tipo", [
    ("CONSTANCIA DE SITUACIÓN FISCAL", "constancia"),
    ("Constancia de Situacion Fiscal", "constancia"),
    ("CÉDULA DE IDENTIFICACIÓN FISCAL", "constancia"),
    ("Opinión del cumplimiento de obligaciones fiscales", "opinion"),
    ("OPINION DE CUMPLIMIENTO DE OBLIGACIONES FISCALES", "opinion"),
    ("Estado de cuenta bancario", None),
])
def test_detectar_tipo(texto, tipo):
    assert inf.detectar_tipo(texto) == tipo


# ─── parsear_opinion ──────────────────────────────────────────────────────────

def test_parsear_opinion_completa():
    texto = (
        "Opinión del cumplimiento de obligaciones fiscales\n"
        "Folio 26NA1234567\n"
        "Clave de R.F.C.: ACM010101AA1\n"
        "Nombre, denominación o razón social: ACME COMERCIALIZADORA SA DE CV\n"
        "Fecha de inicio de operaciones: 01 de enero de 2001\n"
        "Revisión practicada el día 03 de octubre de 2026, a las 10:15 horas\n"
        "se emite opinión en sentido POSITIVO\n"
    )
    assert inf.parsear_opinion(texto) == {
        "rfc": "ACM010101AA1",
        "razon_social": "ACME COMERCIALIZADORA SA DE CV",
        "fecha_emision": "2026-10-03",
        "sentido": "positivo",
        "folio": "26NA1234567",
    }


@pytest.mark.parametrize("texto,sentido", [
    ("se emite opinión en sentido NEGATIVO", "negativo"),
    ("Sentido: Positivo", "positivo"),
    ("Opinión en sentido negativa", "negativo"),
    ("Su situación es INSCRITO SIN OBLIGACIONES", "inscrito_sin_obligaciones"),
    ("Su situación es NO INSCRITO en el RFC", "no_inscrito"),
    ("texto sin sentido identificable", None),
    ("sentido POSITIVO ... en caso de sentido NEGATIVO", None),
])
def test_sentido_de_la_opinion(texto, sentido):
    assert inf.parsear_opinion(texto)["sentido"] == sentido


def test_fecha_de_la_opinion_sin_revision_usa_la_primera_fecha():
    assert inf.parsear_opinion("Emitida el 05/09/2026")["fecha_emision"] == "2026-09-05"


# ─── estado_opinion / antiguedad ──────────────────────────────────────────────

def test_opinion_vigente_30_dias_naturales_contando_el_de_emision():
    emitida = date(2026, 10, 3)
    assert inf.estado_opinion(emitida, date(2026, 10, 3)) == {"vigente_hasta": "2026-11-01", "vigente": True}
    assert inf.estado_opinion(emitida, date(2026, 11, 1))["vigente"] is True
    assert inf.estado_opinion(emitida, date(2026, 11, 2))["vigente"] is False


def test_vigencia_no_depende_del_sentido():
    # Una opinión negativa también tiene fecha; la pantalla combina sentido y vigencia.
    assert inf.estado_opinion(date(2026, 10, 3), date(2026, 10, 10))["vigente"] is True


def test_opinion_sin_fecha_no_tiene_vigencia():
    assert inf.estado_opinion(None, date(2026, 10, 3)) == {"vigente_hasta": None, "vigente": None}


def test_antiguedad_dias():
    assert inf.antiguedad_dias(date(2026, 10, 3), date(2026, 10, 4)) == 1
    assert inf.antiguedad_dias(None, date(2026, 10, 4)) is None


# ─── leer_pdf ─────────────────────────────────────────────────────────────────

def test_leer_pdf_rechaza_lo_que_no_es_pdf():
    with pytest.raises(inf.DocumentoInvalido, match="No se pudo leer el PDF"):
        inf.leer_pdf(b"<html>no soy pdf</html>")


def test_leer_pdf_rechaza_pdf_corrupto():
    with pytest.raises(inf.DocumentoInvalido, match="No se pudo leer el PDF"):
        inf.leer_pdf(b"%PDF-1.4\nbasura sin estructura")


def test_leer_pdf_rechaza_pdf_sin_texto():
    with pytest.raises(inf.DocumentoInvalido, match="escaneo"):
        inf.leer_pdf(pdf_con_texto([]))


def test_leer_pdf_rechaza_mas_de_10_paginas():
    with pytest.raises(inf.DocumentoInvalido, match="10 páginas"):
        inf.leer_pdf(pdf_con_texto(["CONSTANCIA DE SITUACION FISCAL"], paginas=11))


def test_leer_pdf_devuelve_el_texto():
    assert "RFC: ACM010101AA1" in inf.leer_pdf(constancia_sintetica())


# ─── analizar_documento ───────────────────────────────────────────────────────

def test_analizar_constancia():
    r = inf.analizar_documento("constancia", constancia_sintetica(), RFC_PRUEBA)
    assert r["rfc"] == RFC_PRUEBA
    assert r["fecha_emision"] == "2026-10-03"
    assert r["datos"]["razon_social"] == "ACME COMERCIALIZADORA SA DE CV"
    assert r["datos"]["regimenes"] == ["Régimen General de Ley Personas Morales"]
    assert r["datos"]["cp_fiscal"] == "68000"
    assert r["datos"]["id_cif"] == "12345678901"
    assert r["datos"]["estatus_padron"] == "ACTIVO"
    assert "texto_completo" not in r["datos"]


def test_analizar_opinion():
    r = inf.analizar_documento("opinion", opinion_sintetica(sentido="NEGATIVO"), RFC_PRUEBA)
    assert r["rfc"] == RFC_PRUEBA
    assert r["fecha_emision"] == "2026-10-03"
    assert r["datos"] == {
        "razon_social": "ACME COMERCIALIZADORA SA DE CV",
        "sentido": "negativo",
        "folio": "26NA1234567",
    }


def test_analizar_compara_rfc_sin_importar_mayusculas_ni_espacios():
    r = inf.analizar_documento("constancia", constancia_sintetica(), " acm010101aa1 ")
    assert r["rfc"] == RFC_PRUEBA


def test_analizar_rechaza_otro_rfc():
    with pytest.raises(inf.DocumentoInvalido, match="ACM010101AA1.*XYZ990101AB2"):
        inf.analizar_documento("constancia", constancia_sintetica(), "XYZ990101AB2")


def test_analizar_rechaza_documento_sin_rfc():
    pdf = pdf_con_texto(["CONSTANCIA DE SITUACION FISCAL", "sin datos"])
    with pytest.raises(inf.DocumentoInvalido, match="No se encontró el RFC"):
        inf.analizar_documento("constancia", pdf, RFC_PRUEBA)


def test_analizar_rechaza_opinion_como_constancia_y_al_reves():
    with pytest.raises(inf.DocumentoInvalido, match="no parece una constancia"):
        inf.analizar_documento("constancia", opinion_sintetica(), RFC_PRUEBA)
    with pytest.raises(inf.DocumentoInvalido, match="no parece una opinión"):
        inf.analizar_documento("opinion", constancia_sintetica(), RFC_PRUEBA)


def test_analizar_rechaza_tipo_desconocido():
    with pytest.raises(ValueError):
        inf.analizar_documento("acta", constancia_sintetica(), RFC_PRUEBA)
