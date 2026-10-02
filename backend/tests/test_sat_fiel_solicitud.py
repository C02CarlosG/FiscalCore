"""Tests de `sat_fiel.solicitar_descarga`: qué se le manda al SAT y cómo se
interpreta su respuesta. El cliente `SAT` de satcfdi se sustituye por un doble."""
from datetime import date, datetime

import pytest

from backend import sat_fiel
from backend.sat_fiel import FIELError


class _SATFalso:
    respuesta = {"IdSolicitud": "id-sat-1", "CodEstatus": "5000", "Mensaje": "Solicitud Aceptada"}
    llamadas: list = []

    def __init__(self, signer=None):
        pass

    def recover_comprobante_emitted_request(self, **kw):
        _SATFalso.llamadas.append(("emitidos", kw))
        return _SATFalso.respuesta

    def recover_comprobante_received_request(self, **kw):
        _SATFalso.llamadas.append(("recibidos", kw))
        return _SATFalso.respuesta


@pytest.fixture
def sat_falso(monkeypatch):
    _SATFalso.llamadas = []
    monkeypatch.setattr(_SATFalso, "respuesta", {
        "IdSolicitud": "id-sat-1", "CodEstatus": "5000", "Mensaje": "Solicitud Aceptada",
    })
    monkeypatch.setattr(sat_fiel, "SAT", _SATFalso)
    return _SATFalso


@pytest.mark.parametrize("tipo", ["emitidos", "recibidos"])
def test_solicitar_descarga_cubre_el_periodo_completo_hasta_el_ultimo_segundo(sat_falso, tipo):
    id_sat = sat_fiel.solicitar_descarga(
        object(), "TEST010101AAA", tipo, date(2026, 9, 1), date(2026, 9, 30),
    )

    assert id_sat == "id-sat-1"
    tipo_llamado, kw = sat_falso.llamadas[0]
    assert tipo_llamado == tipo
    assert kw["fecha_inicial"] == datetime(2026, 9, 1, 0, 0, 0)
    assert kw["fecha_final"] == datetime(2026, 9, 30, 23, 59, 59)


def test_solicitar_descarga_respeta_una_fecha_con_hora(sat_falso):
    sat_fiel.solicitar_descarga(
        object(), "TEST010101AAA", "emitidos",
        datetime(2026, 9, 1, 8, 0, 0), datetime(2026, 9, 15, 12, 0, 0),
    )

    _, kw = sat_falso.llamadas[0]
    assert kw["fecha_inicial"] == datetime(2026, 9, 1, 8, 0, 0)
    assert kw["fecha_final"] == datetime(2026, 9, 15, 12, 0, 0)


def test_solicitar_descarga_rechazada_por_el_sat_aunque_traiga_id(sat_falso, monkeypatch):
    monkeypatch.setattr(sat_falso, "respuesta", {
        "IdSolicitud": "id-sat-1", "CodEstatus": "5005", "Mensaje": "Solicitud duplicada",
    })

    with pytest.raises(FIELError, match="5005.*Solicitud duplicada"):
        sat_fiel.solicitar_descarga(
            object(), "TEST010101AAA", "emitidos", date(2026, 9, 1), date(2026, 9, 30),
        )


def test_solicitar_descarga_sin_id_de_solicitud_falla(sat_falso, monkeypatch):
    monkeypatch.setattr(sat_falso, "respuesta", {"CodEstatus": "5002", "Mensaje": "Se agotaron las solicitudes"})

    with pytest.raises(FIELError, match="5002"):
        sat_fiel.solicitar_descarga(
            object(), "TEST010101AAA", "recibidos", date(2026, 9, 1), date(2026, 9, 30),
        )
