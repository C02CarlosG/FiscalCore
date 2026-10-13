"""Importación y estado de la lista 69-B contra Postgres real."""
from datetime import date, timedelta

import pytest

from backend import efos
from backend.tests.conftest import db_disponible
from backend.tests.efos_fixtures import csv_muestra, fila, validas

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


@pytest.fixture(autouse=True)
def limpio():
    from backend import db

    db.init_db()
    db.execute("DELETE FROM efos_lista")
    db.execute("DELETE FROM efos_importaciones")
    yield
    db.execute("DELETE FROM efos_lista")
    db.execute("DELETE FROM efos_importaciones")


def _lista():
    from backend import db
    return db.query_all("SELECT rfc, no_sat, situacion FROM efos_lista ORDER BY no_sat")


def test_importa_filas_y_registra_la_bitacora():
    from backend import db, efos_datos

    r = efos_datos.importar(csv_muestra(validas(3)), "manual")
    assert r["estado"] == "correcta" and r["filas"] == 3 and r["rfc_unicos"] == 3 and r["fecha_archivo"] == "2025-12-31"
    assert len(_lista()) == 3
    bitacora = db.query_one("SELECT origen, estado, filas FROM efos_importaciones")
    assert (bitacora["origen"], bitacora["estado"], bitacora["filas"]) == ("manual", "correcta", 3)


def test_duplicados_se_conservan_y_la_vista_toma_el_mayor_no():
    from backend import db, efos_datos

    efos_datos.importar(csv_muestra([
        fila(155, "AAS110331G59", "A", "Definitivo", definitivo="01/08/2018"),
        fila(156, "AAS110331G59", "A", "Sentencia Favorable", sentencia="01/02/2019"),
    ] + validas(10, desde=1000)), "manual")
    assert len([f for f in _lista() if f["rfc"] == "AAS110331G59"]) == 2
    assert db.query_one("SELECT situacion FROM efos_vigente WHERE rfc = 'AAS110331G59'")["situacion"] == "Sentencia Favorable"


def test_archivo_identico_no_reemplaza_y_queda_sin_cambios():
    from backend import db, efos_datos

    contenido = csv_muestra(validas(5))
    efos_datos.importar(contenido, "manual")
    r = efos_datos.importar(contenido, "automatica")
    assert r["estado"] == "sin_cambios"
    assert [x["estado"] for x in db.query_all("SELECT estado FROM efos_importaciones ORDER BY id")] == ["correcta", "sin_cambios"]
    assert len(_lista()) == 5


def test_importacion_nueva_reemplaza_la_lista():
    from backend import efos_datos

    efos_datos.importar(csv_muestra(validas(5)), "manual")
    efos_datos.importar(csv_muestra(validas(6, desde=100)), "manual")
    assert [f["no_sat"] for f in _lista()] == [100, 101, 102, 103, 104, 105]


@pytest.mark.parametrize("malo", [
    b"<html>Servicio no disponible</html>",
    csv_muestra(validas(2), encabezado=["a"] * 20),
    csv_muestra(validas(200) + [fila(900 + i, "NO ES RFC", "X", "Presunto") for i in range(5)]),
])
def test_un_archivo_malo_falla_registra_el_intento_y_deja_intacta_la_lista(malo):
    from backend import db, efos_datos

    efos_datos.importar(csv_muestra(validas(5)), "manual")
    antes = _lista()
    with pytest.raises(efos.ErrorImportacion):
        efos_datos.importar(malo, "manual")
    assert _lista() == antes
    ultimo = db.query_one("SELECT estado, mensaje FROM efos_importaciones ORDER BY id DESC LIMIT 1")
    assert ultimo["estado"] == "fallida" and ultimo["mensaje"]


def test_una_caida_de_mas_de_20_por_ciento_falla_y_deja_intacta_la_lista():
    from backend import efos_datos

    efos_datos.importar(csv_muestra(validas(100)), "manual")
    antes = _lista()
    with pytest.raises(efos.ErrorImportacion, match="(?i)caída"):
        efos_datos.importar(csv_muestra(validas(70, desde=500)), "manual")
    assert _lista() == antes


def test_estado_sin_lista_es_desactualizado():
    from backend import efos_datos

    e = efos_datos.estado()
    assert e["hay_lista"] is False and e["desactualizada"] is True and e["dias_de_antiguedad"] is None


def test_estado_con_lista_vieja_o_reciente():
    from backend import efos_datos

    efos_datos.importar(csv_muestra(validas(3), actualizada="31 de diciembre de 2025"), "manual")
    assert efos_datos.estado(hoy=date(2026, 10, 13))["desactualizada"] is True
    reciente = (date.today() - timedelta(days=10))
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    efos_datos.importar(csv_muestra(validas(4, desde=50), actualizada=f"{reciente.day} de {meses[reciente.month - 1]} de {reciente.year}"), "manual")
    e = efos_datos.estado()
    assert e["desactualizada"] is False and e["dias_de_antiguedad"] == 10 and e["filas"] == 4


def test_estado_incluye_el_ultimo_intento_fallido():
    from backend import efos_datos

    efos_datos.importar(csv_muestra(validas(3)), "manual")
    with pytest.raises(efos.ErrorImportacion):
        efos_datos.importar(b"<html></html>", "manual")
    e = efos_datos.estado()
    assert e["hay_lista"] is True and e["ultimo_intento"]["estado"] == "fallida"


def test_situaciones_de_devuelve_riesgo_y_fecha_de_la_etapa():
    from backend import efos_datos

    efos_datos.importar(csv_muestra([
        fila(1, "AAA010101AB1", "A", "Presunto", presunto="01/06/2018"),
        fila(2, "BBB010101AB1", "B", "Definitivo", presunto="01/06/2018", definitivo="01/08/2018"),
        fila(3, "CCC010101AB1", "C", "Desvirtuado", desvirtuado="01/12/2018"),
    ] + validas(10, desde=100)), "manual")
    s = efos_datos.situaciones_de(["AAA010101AB1", "BBB010101AB1", "CCC010101AB1", "ZZZ010101AB1"])
    assert s["AAA010101AB1"] == {"situacion": "Presunto", "riesgo": "alto", "fecha_publicacion": "2018-06-01"}
    assert s["BBB010101AB1"]["riesgo"] == "critico" and s["BBB010101AB1"]["fecha_publicacion"] == "2018-08-01"
    assert s["CCC010101AB1"]["riesgo"] == "informativo"
    assert "ZZZ010101AB1" not in s
    assert efos_datos.situaciones_de([]) == {}
