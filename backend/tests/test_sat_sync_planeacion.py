"""Planeación pura de una corrida de descarga: qué ventanas pedir y cuándo toca la siguiente."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from backend import sat_sync
from backend.sat_sync import VentanaPlan, planear_corrida, proxima_corrida

HOY = date(2026, 10, 4)


def _plan(**kw):
    base = dict(hoy=HOY, carga_inicial_ok=False, ultima_exitosa=None, traslape_dias=7, descargadas=set())
    base.update(kw)
    return planear_corrida(**base)


# ─── carga inicial ───────────────────────────────────────────────────────────

def test_inicial_pide_ejercicio_anterior_y_en_curso_por_tipo_y_mes():
    plan = _plan()
    assert len(plan) == 2 * 22                      # 2025-01 .. 2026-10
    assert {v.origen for v in plan} == {"inicial"}
    emitidos = [v for v in plan if v.tipo == "emitidos"]
    assert emitidos[0] == VentanaPlan("emitidos", date(2025, 1, 1), date(2025, 1, 31), "inicial")
    assert emitidos[-1] == VentanaPlan("emitidos", date(2026, 10, 1), date(2026, 10, 4), "inicial")
    assert [v.tipo for v in plan] == ["emitidos"] * 22 + ["recibidos"] * 22


def test_inicial_omite_meses_cerrados_ya_descargados_pero_no_el_mes_en_curso():
    descargadas = {
        ("emitidos", date(2025, 1, 1), date(2025, 1, 31)),
        ("emitidos", date(2025, 2, 1), date(2025, 2, 28)),
        ("recibidos", date(2025, 1, 1), date(2025, 1, 31)),
        ("emitidos", date(2026, 10, 1), date(2026, 10, 4)),   # mes en curso: fin == hoy
    }
    plan = _plan(descargadas=descargadas)
    assert len(plan) == 44 - 3
    assert VentanaPlan("emitidos", date(2026, 10, 1), date(2026, 10, 4), "inicial") in plan
    assert VentanaPlan("emitidos", date(2025, 1, 1), date(2025, 1, 31), "inicial") not in plan


# ─── corrida diaria ──────────────────────────────────────────────────────────

def test_diaria_pide_desde_ultima_exitosa_menos_traslape_partido_por_mes():
    plan = _plan(carga_inicial_ok=True, ultima_exitosa=date(2026, 10, 2))
    assert plan == [
        VentanaPlan("emitidos", date(2026, 9, 25), date(2026, 9, 30), "diaria"),
        VentanaPlan("emitidos", date(2026, 10, 1), date(2026, 10, 4), "diaria"),
        VentanaPlan("recibidos", date(2026, 9, 25), date(2026, 9, 30), "diaria"),
        VentanaPlan("recibidos", date(2026, 10, 1), date(2026, 10, 4), "diaria"),
    ]


def test_diaria_cruza_de_anio():
    plan = _plan(hoy=date(2027, 1, 3), carga_inicial_ok=True, ultima_exitosa=date(2027, 1, 1), traslape_dias=7)
    emitidos = [v for v in plan if v.tipo == "emitidos"]
    assert emitidos == [
        VentanaPlan("emitidos", date(2026, 12, 25), date(2026, 12, 31), "diaria"),
        VentanaPlan("emitidos", date(2027, 1, 1), date(2027, 1, 3), "diaria"),
    ]


def test_diaria_con_traslape_que_cae_en_el_mes_anterior():
    plan = _plan(hoy=date(2026, 10, 1), carga_inicial_ok=True, ultima_exitosa=date(2026, 10, 1), traslape_dias=1)
    assert [(v.inicio, v.fin) for v in plan if v.tipo == "emitidos"] == [
        (date(2026, 9, 30), date(2026, 9, 30)), (date(2026, 10, 1), date(2026, 10, 1))]


def test_diaria_sin_ultima_exitosa_se_trata_como_carga_inicial():
    plan = _plan(carga_inicial_ok=True, ultima_exitosa=None)
    assert {v.origen for v in plan} == {"inicial"}
    assert len(plan) == 44


def test_diaria_ultima_exitosa_futura_no_rompe():
    plan = _plan(carga_inicial_ok=True, ultima_exitosa=date(2026, 10, 10))
    assert [(v.inicio, v.fin) for v in plan if v.tipo == "emitidos"] == [
        (date(2026, 10, 3), date(2026, 10, 4))]


# ─── proxima_corrida ─────────────────────────────────────────────────────────

MX = ZoneInfo("America/Mexico_City")


def _local(*args):
    return datetime(*args, tzinfo=MX)


def test_proxima_corrida_antes_de_la_hora_es_hoy():
    ahora = _local(2026, 10, 4, 1, 0).astimezone(timezone.utc)
    esperada = _local(2026, 10, 4, 3, 0).astimezone(timezone.utc)
    assert proxima_corrida(ahora, "03:00") == esperada


def test_proxima_corrida_despues_de_la_hora_es_manana():
    ahora = _local(2026, 10, 4, 3, 30).astimezone(timezone.utc)
    assert proxima_corrida(ahora, "03:00") == _local(2026, 10, 5, 3, 0).astimezone(timezone.utc)


def test_proxima_corrida_exactamente_a_la_hora_es_manana():
    ahora = _local(2026, 10, 4, 3, 0).astimezone(timezone.utc)
    assert proxima_corrida(ahora, "03:00") == _local(2026, 10, 5, 3, 0).astimezone(timezone.utc)


def test_proxima_corrida_devuelve_utc_y_es_posterior():
    ahora = datetime(2026, 12, 31, 23, 0, tzinfo=timezone.utc)
    r = proxima_corrida(ahora, "05:30")
    assert r.utcoffset().total_seconds() == 0
    assert r > ahora


@pytest.mark.parametrize("hora", ["tarde", "25:00", "", "3:00"])
def test_proxima_corrida_con_hora_invalida_usa_las_3(hora):
    ahora = _local(2026, 10, 4, 1, 0).astimezone(timezone.utc)
    assert proxima_corrida(ahora, hora) == proxima_corrida(ahora, "03:00")


def test_proxima_corrida_acepta_fecha_sin_zona_como_utc():
    ahora = datetime(2026, 10, 4, 1, 0)
    assert proxima_corrida(ahora, "03:00") > ahora.replace(tzinfo=timezone.utc)
