"""Reintentos con espera creciente de las solicitudes al SAT (sat_sync). DB y SAT simulados."""
from datetime import datetime, timedelta, timezone

import pytest

from backend import db, sat_sync
from backend.sat_fiel import FIELError


class _BD:
    """Simula la fila de sat_solicitudes lo justo para los helpers de reintento."""

    def __init__(self, estado="solicitado", intentos=0):
        self.fila = {"estado": estado, "intentos": intentos, "proximo_intento": None, "error_msg": None}
        self.sqls = []

    def execute(self, sql, params=(), returning=False):
        self.sqls.append((sql, params))
        s = " ".join(sql.split())
        if "intentos = intentos + 1" in s:
            self.fila["intentos"] += 1
            self.fila["error_msg"] = params[0]
            return {"intentos": self.fila["intentos"], "estado": self.fila["estado"]} if returning else None
        if "estado = 'fallo'" in s or "estado='fallo'" in s:
            self.fila["estado"] = "fallo"
            self.fila["error_msg"] = params[0]
        elif "proximo_intento" in s:
            valor = params[0] if isinstance(params[0], timedelta) else None
            if valor is not None:
                self.fila["proximo_intento"] = valor
            if "error_msg" in s and valor is None:
                self.fila["error_msg"] = params[0]
        return None


@pytest.fixture()
def bd(monkeypatch):
    fake = _BD()
    monkeypatch.setattr(db, "execute", fake.execute)
    return fake


@pytest.mark.parametrize("fallo_n,espera", [
    (1, timedelta(minutes=5)), (2, timedelta(minutes=15)), (3, timedelta(hours=1)), (4, timedelta(hours=6)),
])
def test_fallos_transitorios_agendan_el_siguiente_intento(bd, fallo_n, espera):
    estado = None
    for _ in range(fallo_n):
        estado = sat_sync.registrar_solicitud_fallida("sol-1", "SAT no responde")
    assert estado == "solicitado"          # sigue viva: se reintentará
    assert bd.fila["intentos"] == fallo_n
    assert bd.fila["proximo_intento"] == espera


def test_el_quinto_fallo_cuatro_reintentos_agotados_deja_fallo_con_el_mensaje_del_sat(bd):
    for _ in range(4):
        sat_sync.registrar_solicitud_fallida("sol-1", "SAT no responde")
    estado = sat_sync.registrar_solicitud_fallida("sol-1", "SAT no responde")
    assert estado == "fallo"
    assert bd.fila["estado"] == "fallo"
    assert "SAT no responde" in bd.fila["error_msg"]


# ─── avanzar_solicitud ────────────────────────────────────────────────────────

def _solicitud(**extra):
    return {"id": "sol-1", "empresa_id": "emp-1", "estado": "solicitado", "id_solicitud_sat": "SAT-1",
            "periodo_inicio": "2026-09", **extra}


def test_no_toca_al_sat_si_el_proximo_intento_es_futuro(monkeypatch, bd):
    def _no_debe_llamarse(*a, **k):
        raise AssertionError("no debe consultar al SAT antes de proximo_intento")
    monkeypatch.setattr(sat_sync, "verificar_solicitud", _no_debe_llamarse)
    futuro = datetime.now(timezone.utc) + timedelta(minutes=10)

    assert sat_sync.avanzar_solicitud(object(), _solicitud(proximo_intento=futuro)) == "solicitado"
    assert bd.sqls == []


def test_consulta_al_sat_si_el_proximo_intento_ya_vencio(monkeypatch, bd):
    llamadas = []
    monkeypatch.setattr(sat_sync, "verificar_solicitud",
                        lambda *a, **k: llamadas.append(1) or {"estado": 2, "num_cfdi": 0, "id_paquetes": []})
    pasado = datetime.now(timezone.utc) - timedelta(minutes=1)

    sat_sync.avanzar_solicitud(object(), _solicitud(proximo_intento=pasado))
    assert llamadas == [1]


def test_error_al_verificar_cuenta_un_intento_y_conserva_el_estado(monkeypatch, bd):
    def _falla(*a, **k):
        raise FIELError("El SAT no respondió")
    monkeypatch.setattr(sat_sync, "verificar_solicitud", _falla)

    assert sat_sync.avanzar_solicitud(object(), _solicitud(estado="en_proceso")) == "en_proceso"
    assert bd.fila["intentos"] == 1
    assert bd.fila["proximo_intento"] == timedelta(minutes=5)


def test_error_al_verificar_agotado_deja_fallo(monkeypatch, bd):
    bd.fila["intentos"] = 4  # ya se agotaron los cuatro reintentos

    def _falla(*a, **k):
        raise FIELError("El SAT no respondió")
    monkeypatch.setattr(sat_sync, "verificar_solicitud", _falla)

    assert sat_sync.avanzar_solicitud(object(), _solicitud()) == "fallo"
    assert bd.fila["estado"] == "fallo"


def test_5004_sigue_siendo_exito_con_cero_cfdi(monkeypatch, bd):
    monkeypatch.setattr(sat_sync, "verificar_solicitud",
                        lambda *a, **k: {"estado": 0, "codigo_estado": "5004", "num_cfdi": 0, "id_paquetes": []})

    assert sat_sync.avanzar_solicitud(object(), _solicitud()) == "descargado"
    assert bd.fila["intentos"] == 0


def test_el_mensaje_de_error_solo_lleva_el_texto_del_sat_sin_credenciales(monkeypatch, bd):
    class _Signer:
        password = "SECRETO-FIEL"
        key = b"BYTES-LLAVE"

    def _falla(creds, *a, **k):
        raise FIELError("Error al verificar solicitud 'SAT-1': timeout")
    monkeypatch.setattr(sat_sync, "verificar_solicitud", _falla)

    for _ in range(5):
        sat_sync.avanzar_solicitud(_Signer(), _solicitud())

    assert "timeout" in bd.fila["error_msg"]
    for secreto in ("SECRETO-FIEL", "BYTES-LLAVE"):
        assert secreto not in bd.fila["error_msg"]
