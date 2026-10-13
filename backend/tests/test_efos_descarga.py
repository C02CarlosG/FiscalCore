"""Descarga y ciclo semanal de la lista 69-B. Sin DB ni red (todo simulado)."""
from datetime import datetime, timedelta, timezone

import pytest

from backend import efos, efos_datos, worker

AHORA = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)


def _ultima(monkeypatch, estado=None, hace=None):
    fila = None if estado is None else {"estado": estado, "creado_en": AHORA - hace}
    monkeypatch.setattr(efos_datos.db, "query_one", lambda *a, **k: fila)


def test_toca_descargar_sin_historial(monkeypatch):
    _ultima(monkeypatch)
    assert efos_datos.toca_descargar(AHORA) is True


@pytest.mark.parametrize("estado,hace,esperado", [
    ("correcta", timedelta(days=6, hours=23), False),
    ("correcta", timedelta(days=7), True),
    ("sin_cambios", timedelta(days=3), False),
    ("fallida", timedelta(minutes=59), False),
    ("fallida", timedelta(hours=1), True),
])
def test_toca_descargar_segun_ultimo_intento_automatico(monkeypatch, estado, hace, esperado):
    _ultima(monkeypatch, estado, hace)
    assert efos_datos.toca_descargar(AHORA) is esperado


def test_descargar_rechaza_esquemas_que_no_son_http(monkeypatch):
    for url in ("file:///etc/passwd", "ftp://x/y.csv", "javascript:alert(1)"):
        with pytest.raises(ValueError, match="http"):
            efos_datos.descargar(url)


def test_descargar_usa_efos_url_y_corta_en_el_maximo(monkeypatch):
    visto = {}

    class Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self, n): visto["n"] = n; return b"x" * n

    monkeypatch.setenv("EFOS_URL", "http://ejemplo.test/lista.csv")
    monkeypatch.setattr(efos_datos.urllib.request, "urlopen", lambda req, timeout: visto.update(url=req.full_url, t=timeout) or Resp())
    with pytest.raises(efos.ErrorImportacion, match="tamaño"):
        efos_datos.descargar()
    assert visto["url"] == "http://ejemplo.test/lista.csv" and visto["t"] == 60 and visto["n"] == efos.MAX_BYTES + 1


def test_ciclo_no_hace_nada_si_no_toca(monkeypatch):
    monkeypatch.setattr(efos_datos, "toca_descargar", lambda ahora=None: False)
    monkeypatch.setattr(efos_datos, "descargar", lambda *a, **k: pytest.fail("no debe descargar"))
    assert efos_datos.ciclo_efos(AHORA) is None


def test_ciclo_descarga_e_importa_como_automatica(monkeypatch):
    monkeypatch.setattr(efos_datos, "toca_descargar", lambda ahora=None: True)
    monkeypatch.setattr(efos_datos, "descargar", lambda *a, **k: b"csv")
    visto = {}
    monkeypatch.setattr(efos_datos, "importar", lambda c, o, u=None: visto.update(c=c, o=o, u=u) or {"estado": "correcta"})
    assert efos_datos.ciclo_efos(AHORA) == "correcta"
    assert visto == {"c": b"csv", "o": "automatica", "u": None}


def test_una_falla_de_red_se_registra_como_fallida_y_no_lanza(monkeypatch):
    monkeypatch.setattr(efos_datos, "toca_descargar", lambda ahora=None: True)

    def _sin_red(*a, **k):
        raise OSError("timed out")

    registros = []
    monkeypatch.setattr(efos_datos, "descargar", _sin_red)
    monkeypatch.setattr(efos_datos, "_registrar", lambda *a, **k: registros.append(a))
    assert efos_datos.ciclo_efos(AHORA) == "fallida"
    assert registros and registros[0][0] == "automatica" and registros[0][2] == "fallida" and "timed out" in registros[0][3]


def test_un_archivo_invalido_ya_queda_registrado_por_importar_y_no_lanza(monkeypatch):
    monkeypatch.setattr(efos_datos, "toca_descargar", lambda ahora=None: True)
    monkeypatch.setattr(efos_datos, "descargar", lambda *a, **k: b"<html>")

    def _invalido(*a, **k):
        raise efos.ErrorImportacion("cabecera")

    monkeypatch.setattr(efos_datos, "importar", _invalido)
    monkeypatch.setattr(efos_datos, "_registrar", lambda *a, **k: pytest.fail("importar ya registró el intento"))
    assert efos_datos.ciclo_efos(AHORA) == "fallida"


def test_el_worker_no_se_detiene_si_el_ciclo_de_efos_explota(monkeypatch):
    def _explota(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(worker.efos_datos, "ciclo_efos", _explota)
    worker._ciclo_efos()          # no lanza
