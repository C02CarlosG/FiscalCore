"""Parser de la lista 69-B (spec 2026-10-13-efos-69b-design). Sin DB ni red."""
from datetime import date

import pytest

from backend import efos
from backend.tests.efos_fixtures import csv_muestra, fila, validas


def test_lee_la_fecha_del_archivo_y_las_filas():
    r = efos.parsear(csv_muestra(validas(3)))
    assert r.fecha_archivo == date(2025, 12, 31)
    assert [f.no_sat for f in r.filas] == [1, 2, 3]
    assert r.leidas == 3 and r.descartadas == 0 and r.genericas == 0


def test_conserva_acentos_y_enie_de_cp1252():
    r = efos.parsear(csv_muestra([fila(1, "AAA010101AB1", "ASESORES EN AVALÚOS Y ACTIVOS ÑANDÚ, S.A.", "Presunto")]))
    assert r.filas[0].nombre == "ASESORES EN AVALÚOS Y ACTIVOS ÑANDÚ, S.A."


def test_conserva_los_rfc_repetidos_con_su_historial():
    r = efos.parsear(csv_muestra([
        fila(155, "AAS110331G59", "ABIRA & SAFFI", "Definitivo", definitivo="01/08/2018"),
        fila(156, "AAS110331G59", "ABIRA & SAFFI", "Sentencia Favorable", sentencia="01/02/2019"),
    ]))
    assert [(f.no_sat, f.situacion) for f in r.filas] == [(155, "Definitivo"), (156, "Sentencia Favorable")]


def test_descarta_el_rfc_generico_y_lo_cuenta():
    r = efos.parsear(csv_muestra(validas(2) + [fila(9, "XXXXXXXXXXXX", "GENERICO", "Definitivo")]))
    assert len(r.filas) == 2 and r.genericas == 1 and r.descartadas == 0


def test_rfc_en_minusculas_se_normaliza_y_uno_invalido_se_descarta():
    r = efos.parsear(csv_muestra(validas(200) + [fila(900, "abc010101ab1", "MIN", "Presunto"), fila(901, "NO ES RFC", "X", "Presunto")]))
    assert "ABC010101AB1" in {f.rfc for f in r.filas}
    assert r.descartadas == 1


@pytest.mark.parametrize("campo,valor", [(3, "Otra situación"), (0, "no-es-numero")])
def test_descarta_filas_con_situacion_o_numero_invalidos(campo, valor):
    mala = fila(900, "ZZZ010101AB1", "MALA", "Presunto")
    mala[campo] = valor
    r = efos.parsear(csv_muestra(validas(200) + [mala]))
    assert r.descartadas == 1 and len(r.filas) == 200


def test_mas_de_1_por_ciento_de_filas_invalidas_falla():
    malas = [fila(900 + i, "NO ES RFC", "X", "Presunto") for i in range(3)]
    with pytest.raises(efos.ErrorImportacion, match="inválid"):
        efos.parsear(csv_muestra(validas(200) + malas))


def test_hasta_1_por_ciento_pasa():
    r = efos.parsear(csv_muestra(validas(200) + [fila(900, "NO ES RFC", "X", "Presunto")]))
    assert r.descartadas == 1


def test_cabecera_distinta_falla():
    cab = list(efos.COLUMNAS)
    cab[3] = "Estatus"
    with pytest.raises(efos.ErrorImportacion, match="cabecera"):
        efos.parsear(csv_muestra(validas(2), encabezado=cab))


def test_una_pagina_html_de_error_falla_por_cabecera():
    with pytest.raises(efos.ErrorImportacion, match="cabecera"):
        efos.parsear(b"<html><body>Servicio no disponible</body></html>")


def test_sin_filas_validas_falla():
    with pytest.raises(efos.ErrorImportacion, match="sin filas"):
        efos.parsear(csv_muestra([]))


def test_bytes_que_no_son_cp1252_fallan():
    with pytest.raises(efos.ErrorImportacion, match="cp1252"):
        efos.parsear(b"\x81\x8d\x8f\x90\x9d")


def test_archivo_mayor_al_maximo_falla(monkeypatch):
    monkeypatch.setattr(efos, "MAX_BYTES", 10)
    with pytest.raises(efos.ErrorImportacion, match="tamaño"):
        efos.parsear(csv_muestra(validas(2)))


def test_sin_preambulo_la_fecha_del_archivo_es_none():
    r = efos.parsear(csv_muestra(validas(2), preambulo=False))
    assert r.fecha_archivo is None and len(r.filas) == 2


def test_fechas_y_oficios_por_etapa():
    r = efos.parsear(csv_muestra([fila(1, "AAA010101AB1", "N", "Definitivo", presunto="01/06/2018", definitivo="01/08/2018")]))
    f = r.filas[0]
    assert f.fechas["presunto_sat"] == date(2018, 6, 1) and f.fechas["definitivo_dof"] == date(2018, 8, 1)
    assert f.fechas["desvirtuado_sat"] is None and f.oficios["definitivo_sat"] == "of-def"
    assert efos.fecha_de_etapa("Definitivo", f.fechas) == date(2018, 8, 1)
    assert efos.fecha_de_etapa("Presunto", f.fechas) == date(2018, 6, 1)


@pytest.mark.parametrize("nuevas,anteriores,falla", [(79, 100, True), (80, 100, False), (120, 100, False), (5, None, False)])
def test_caida_de_filas_mayor_a_20_por_ciento_falla(nuevas, anteriores, falla):
    if falla:
        with pytest.raises(efos.ErrorImportacion, match="(?i)caída"):
            efos.validar_contra_anterior(nuevas, anteriores)
    else:
        efos.validar_contra_anterior(nuevas, anteriores)


# ── fechas del archivo real del SAT (verificado 2026-10-13: 83 filas válidas se perdían por esto) ──

def test_celda_con_dos_publicaciones_toma_la_mas_reciente():
    r = efos.parsear(csv_muestra([fila(1, "AAA010101AB1", "N", "Definitivo", definitivo="25/05/2022 - 26/04/2021")]))
    assert r.filas[0].fechas["definitivo_sat"] == date(2022, 5, 25) and r.descartadas == 0


def test_fecha_como_numero_de_serie_de_excel():
    r = efos.parsear(csv_muestra([fila(1, "AAA010101AB1", "N", "Presunto", presunto="44014")]))
    assert r.filas[0].fechas["presunto_sat"] == date(2020, 7, 2)


@pytest.mark.parametrize("raro", ["31-12-2018", "2018/01/01", "pendiente", "32/13/2018", "123"])
def test_una_fecha_ilegible_no_descarta_la_fila_se_deja_vacia_y_se_cuenta(raro):
    r = efos.parsear(csv_muestra([fila(1, "AAA010101AB1", "N", "Definitivo", definitivo=raro)]))
    f = r.filas[0]
    assert (f.rfc, f.situacion) == ("AAA010101AB1", "Definitivo")        # el riesgo no depende de la fecha
    assert f.fechas["definitivo_sat"] is None and r.descartadas == 0 and r.fechas_ilegibles >= 1
