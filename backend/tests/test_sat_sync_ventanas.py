"""Funciones puras de sat_sync: ventanas mensuales, partición, esperas de reintento y configuración."""
from datetime import date, timedelta

import pytest

from backend import sat_sync


# ─── ventanas_mensuales ──────────────────────────────────────────────────────

def test_ventanas_mensuales_parte_por_mes_natural():
    assert sat_sync.ventanas_mensuales(date(2025, 1, 15), date(2025, 3, 10)) == [
        (date(2025, 1, 15), date(2025, 1, 31)),
        (date(2025, 2, 1), date(2025, 2, 28)),
        (date(2025, 3, 1), date(2025, 3, 10)),
    ]


def test_ventanas_mensuales_febrero_bisiesto():
    assert sat_sync.ventanas_mensuales(date(2024, 2, 1), date(2024, 2, 29)) == [
        (date(2024, 2, 1), date(2024, 2, 29))]


def test_ventanas_mensuales_cruza_de_anio():
    assert sat_sync.ventanas_mensuales(date(2025, 12, 20), date(2026, 1, 5)) == [
        (date(2025, 12, 20), date(2025, 12, 31)),
        (date(2026, 1, 1), date(2026, 1, 5)),
    ]


def test_ventanas_mensuales_un_solo_dia():
    assert sat_sync.ventanas_mensuales(date(2025, 5, 7), date(2025, 5, 7)) == [
        (date(2025, 5, 7), date(2025, 5, 7))]


def test_ventanas_mensuales_rango_invertido_da_lista_vacia():
    assert sat_sync.ventanas_mensuales(date(2025, 3, 1), date(2025, 2, 1)) == []


# ─── partir_ventana ──────────────────────────────────────────────────────────

def _dias(ventanas):
    return [(f - i).days + 1 for i, f in ventanas]


@pytest.mark.parametrize("inicio,fin", [
    (date(2025, 1, 1), date(2025, 1, 31)),
    (date(2025, 2, 1), date(2025, 2, 28)),
    (date(2025, 1, 1), date(2025, 1, 3)),
    (date(2025, 1, 1), date(2025, 1, 2)),
])
def test_partir_ventana_cubre_todo_sin_huecos_ni_solapes(inicio, fin):
    mitades = sat_sync.partir_ventana(inicio, fin)
    assert len(mitades) == 2
    assert mitades[0][0] == inicio and mitades[1][1] == fin
    assert mitades[1][0] == mitades[0][1] + timedelta(days=1)
    assert all(i <= f for i, f in mitades)
    assert sum(_dias(mitades)) == (fin - inicio).days + 1


def test_partir_ventana_de_un_dia_no_se_puede_partir():
    assert sat_sync.partir_ventana(date(2025, 1, 1), date(2025, 1, 1)) is None


def test_partir_ventana_dos_dias_da_dos_de_un_dia():
    assert sat_sync.partir_ventana(date(2025, 1, 1), date(2025, 1, 2)) == [
        (date(2025, 1, 1), date(2025, 1, 1)), (date(2025, 1, 2), date(2025, 1, 2))]


# ─── espera_reintento ────────────────────────────────────────────────────────

@pytest.mark.parametrize("intentos,espera", [
    (1, timedelta(minutes=5)),
    (2, timedelta(minutes=15)),
    (3, timedelta(hours=1)),
    (4, timedelta(hours=6)),
])
def test_espera_reintento_creciente(intentos, espera):
    assert sat_sync.espera_reintento(intentos) == espera


@pytest.mark.parametrize("intentos", [0, -1, 5, 99])
def test_espera_reintento_fuera_de_rango_es_none(intentos):
    assert sat_sync.espera_reintento(intentos) is None


# ─── config_sync ─────────────────────────────────────────────────────────────

_VARIABLES = ("SAT_SYNC_INTERVALO_SEG", "SAT_SYNC_HORA_LOCAL", "SAT_SYNC_TRASLAPE_DIAS",
              "SAT_SYNC_MESES_CANCELACION", "SAT_SYNC_MAX_EN_VUELO", "SAT_SYNC_DIAS_BARRIDO_CANCELADOS")


@pytest.fixture()
def sin_variables(monkeypatch):
    for v in _VARIABLES:
        monkeypatch.delenv(v, raising=False)
    return monkeypatch


def test_config_sync_valores_por_defecto(sin_variables):
    cfg = sat_sync.config_sync()
    assert (cfg.intervalo_seg, cfg.hora_local, cfg.traslape_dias,
            cfg.meses_cancelacion, cfg.max_en_vuelo) == (60, "03:00", 7, 3, 4)


def test_config_sync_respeta_variables_de_entorno(sin_variables):
    sin_variables.setenv("SAT_SYNC_INTERVALO_SEG", "30")
    sin_variables.setenv("SAT_SYNC_HORA_LOCAL", "05:30")
    sin_variables.setenv("SAT_SYNC_TRASLAPE_DIAS", "10")
    sin_variables.setenv("SAT_SYNC_MESES_CANCELACION", "6")
    sin_variables.setenv("SAT_SYNC_MAX_EN_VUELO", "2")
    cfg = sat_sync.config_sync()
    assert (cfg.intervalo_seg, cfg.hora_local, cfg.traslape_dias,
            cfg.meses_cancelacion, cfg.max_en_vuelo) == (30, "05:30", 10, 6, 2)


@pytest.mark.parametrize("variable,valor", [
    ("SAT_SYNC_INTERVALO_SEG", "abc"),
    ("SAT_SYNC_INTERVALO_SEG", "0"),
    ("SAT_SYNC_TRASLAPE_DIAS", "-3"),
    ("SAT_SYNC_MAX_EN_VUELO", ""),
    ("SAT_SYNC_HORA_LOCAL", "25:99"),
    ("SAT_SYNC_HORA_LOCAL", "tarde"),
])
def test_config_sync_valor_invalido_cae_al_defecto(sin_variables, variable, valor):
    sin_variables.setenv(variable, valor)
    cfg = sat_sync.config_sync()  # no truena
    assert (cfg.intervalo_seg, cfg.hora_local, cfg.traslape_dias,
            cfg.meses_cancelacion, cfg.max_en_vuelo) == (60, "03:00", 7, 3, 4)


def test_config_sync_dias_entre_barridos_de_cancelados(sin_variables):
    assert sat_sync.config_sync().dias_barrido_cancelados == 7
    sin_variables.setenv("SAT_SYNC_DIAS_BARRIDO_CANCELADOS", "14")
    assert sat_sync.config_sync().dias_barrido_cancelados == 14
    sin_variables.setenv("SAT_SYNC_DIAS_BARRIDO_CANCELADOS", "0")
    assert sat_sync.config_sync().dias_barrido_cancelados == 7


def test_config_sync_es_inmutable(sin_variables):
    cfg = sat_sync.config_sync()
    with pytest.raises(Exception):
        cfg.intervalo_seg = 1
