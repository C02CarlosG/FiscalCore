"""Reglas puras de F8: lectura y validación de la constancia de situación fiscal y de
la opinión del cumplimiento. PDF sintéticos generados en memoria."""
from datetime import date

import pytest

from backend import informacion_fiscal as inf
from backend.tests.pdf_sintetico import RFC_PRUEBA, constancia_sintetica, opinion_sintetica, pdf_con_texto


# ─── buscar_rfc ───────────────────────────────────────────────────────────────

def test_buscar_rfc_que_empieza_con_ampersand_sin_etiqueta():
    assert inf.buscar_rfc("contribuyente &AM010101AA1 sin etiqueta") == "&AM010101AA1"


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
    ("Sentido: En suspensión de actividades", "suspension_actividades"),
    ("se emite opinión en sentido EN SUSPENSION DE ACTIVIDADES", "suspension_actividades"),
    ("texto sin sentido identificable", None),
    # Si el texto menciona varios, gana el desfavorable: nunca se presenta como
    # positiva una opinión que podría no serlo (revisión dominio-fiscal, A4).
    ("en sentido NEGATIVO. Para obtener la opinión en sentido positivo…", "negativo"),
    ("sentido POSITIVO ... en caso de sentido NEGATIVO", "negativo"),
])
def test_sentido_de_la_opinion(texto, sentido):
    assert inf.parsear_opinion(texto)["sentido"] == sentido


def test_fecha_de_la_opinion_solo_con_ancla():
    # Sin "practicada el día" ni "Fecha de emisión" no se adivina con la primera fecha del texto.
    assert inf.parsear_opinion("Inicio de operaciones 05/09/2001")["fecha_emision"] is None
    assert inf.parsear_opinion("Fecha de emisión: 05/09/2026")["fecha_emision"] == "2026-09-05"


# ─── estado_opinion / antiguedad ──────────────────────────────────────────────

def test_opinion_positiva_vigente_30_dias_naturales_contando_el_de_emision():
    emitida = date(2026, 10, 3)
    assert inf.estado_opinion(emitida, "positivo", date(2026, 10, 3)) == {
        "vigente_hasta": "2026-11-01", "vigente": True, "motivo": None,
    }
    assert inf.estado_opinion(emitida, "positivo", date(2026, 11, 1))["vigente"] is True
    vencida = inf.estado_opinion(emitida, "positivo", date(2026, 11, 2))
    assert vencida["vigente"] is False
    assert vencida["motivo"] == "vencida"


@pytest.mark.parametrize("sentido,motivo", [
    ("negativo", "sentido_no_positivo"),
    ("suspension_actividades", "sentido_no_positivo"),
    ("inscrito_sin_obligaciones", "sentido_no_positivo"),
    ("no_inscrito", "sentido_no_positivo"),
    (None, "sentido_no_identificado"),
])
def test_solo_la_opinion_positiva_tiene_vigencia(sentido, motivo):
    # Regla 2.1.36 RMF 2026: los 30 días aplican a la opinión "en sentido positivo".
    r = inf.estado_opinion(date(2026, 10, 3), sentido, date(2026, 10, 4))
    assert r == {"vigente_hasta": None, "vigente": False, "motivo": motivo}


def test_opinion_positiva_sin_fecha_no_es_vigente():
    r = inf.estado_opinion(None, "positivo", date(2026, 10, 3))
    assert r == {"vigente_hasta": None, "vigente": False, "motivo": "sin_fecha"}


def test_hoy_es_la_fecha_de_la_ciudad_de_mexico():
    from datetime import datetime, timezone
    # 2026-10-04 01:00 UTC todavía es 3 de octubre en la Ciudad de México.
    assert inf.hoy_mexico(datetime(2026, 10, 4, 1, 0, tzinfo=timezone.utc)) == date(2026, 10, 3)


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
    # Solo lo que la pantalla muestra: ni el texto, ni la CURP, ni las obligaciones.
    assert set(r["datos"]) == {"razon_social", "regimenes", "cp_fiscal", "id_cif", "estatus_padron"}


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


def test_analizar_normaliza_guiones_y_espacios_del_rfc_de_la_empresa():
    r = inf.analizar_documento("constancia", constancia_sintetica(), "ACM-010101 AA1")
    assert r["rfc"] == RFC_PRUEBA


def test_analizar_rechaza_fecha_de_emision_futura():
    with pytest.raises(inf.DocumentoInvalido, match="posterior a hoy"):
        inf.analizar_documento("opinion", opinion_sintetica(), RFC_PRUEBA, hoy=date(2026, 10, 1))


def test_analizar_acepta_emitido_hoy():
    r = inf.analizar_documento("opinion", opinion_sintetica(), RFC_PRUEBA, hoy=date(2026, 10, 3))
    assert r["fecha_emision"] == "2026-10-03"


def test_leer_pdf_con_contrasena(monkeypatch):
    from pdfminer.pdfdocument import PDFPasswordIncorrect

    def _abrir(*a, **k):
        try:
            raise PDFPasswordIncorrect()
        except PDFPasswordIncorrect as e:
            # pdfplumber la envuelve en su propia excepción
            raise RuntimeError("no se pudo abrir") from e

    monkeypatch.setattr(inf.cp.pdfplumber, "open", _abrir)
    with pytest.raises(inf.DocumentoInvalido, match="contraseña"):
        inf.leer_pdf(b"%PDF-1.7 cifrado")


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


@pytest.mark.parametrize("nombre,codigo", [
    ("Régimen de las Actividades Empresariales con ingresos a través de Plataformas Tecnológicas", "625"),
    ("Régimen de las Personas Físicas con Actividades Empresariales y Profesionales", "612"),
    ("Régimen de Actividades Empresariales y Profesionales", "612"),
    ("Régimen Simplificado de Confianza", "626"),
    ("REGIMEN GENERAL DE LEY PERSONAS MORALES", "601"),
    ("Sueldos y Salarios e Ingresos Asimilados a Salarios", "605"),
    ("Régimen de Arrendamiento", "606"),
    ("Régimen de Incorporación Fiscal", "621"),
    ("612 - Personas Físicas con Actividades Empresariales y Profesionales", "612"),
    ("Régimen desconocido", None),
    (None, None),
])
def test_codigo_de_regimen(nombre, codigo):
    assert inf.codigo_regimen(nombre) == codigo


def test_regimenes_detectados_y_principal():
    detectados = inf.regimenes_detectados(["Régimen Simplificado de Confianza", "Régimen Simplificado de Confianza",
                                           "Sueldos y Salarios", "Otra línea", 5])
    assert [d["codigo"] for d in detectados] == ["626", "605"]
    assert detectados[0]["descripcion"] == "Régimen Simplificado de Confianza"
    assert inf.regimen_principal(["612", "605"]) == "612"
    assert inf.regimen_principal(["605"]) == "605"
    assert inf.regimen_principal(["612", "606"]) is None
    assert inf.regimen_principal([]) is None
    assert inf.texto_regimen("601") == "601 - General de Ley Personas Morales"
    with pytest.raises(ValueError):
        inf.texto_regimen("999")
