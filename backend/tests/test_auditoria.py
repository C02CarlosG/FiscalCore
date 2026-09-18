"""Tests de backend/auditoria.py — log de eventos sensibles.

No requieren Postgres real: se mockea backend.auditoria.db.execute.
"""
import logging

import psycopg2.extras
import pytest

from backend import auditoria


class _ExecuteRecorder:
    def __init__(self, lanzar: Exception | None = None):
        self.calls = []
        self._lanzar = lanzar

    def __call__(self, sql, params=()):
        self.calls.append((sql, params))
        if self._lanzar:
            raise self._lanzar


def test_registrar_evento_inserta_con_los_campos_esperados(monkeypatch):
    recorder = _ExecuteRecorder()
    monkeypatch.setattr(auditoria.db, "execute", recorder)

    auditoria.registrar_evento(
        "user-1", "cfdi_subido", empresa_id="emp-1",
        entidad="cfdi", entidad_id="uuid-123", metadata={"procesados": 5},
    )

    assert len(recorder.calls) == 1
    sql, params = recorder.calls[0]
    assert "INSERT INTO auditoria" in sql
    usuario_id, empresa_id, accion, entidad, entidad_id, metadata = params
    assert (usuario_id, empresa_id, accion, entidad, entidad_id) == (
        "user-1", "emp-1", "cfdi_subido", "cfdi", "uuid-123",
    )
    assert isinstance(metadata, psycopg2.extras.Json)


def test_registrar_evento_sin_metadata_ni_entidad(monkeypatch):
    recorder = _ExecuteRecorder()
    monkeypatch.setattr(auditoria.db, "execute", recorder)

    auditoria.registrar_evento("user-1", "fiel_cargada", empresa_id="emp-1")

    _, params = recorder.calls[0]
    assert params[3] is None  # entidad
    assert params[4] is None  # entidad_id
    assert params[5] is None  # metadata


def test_registrar_evento_no_propaga_excepcion_si_falla_el_insert(monkeypatch, caplog):
    monkeypatch.setattr(auditoria.db, "execute", _ExecuteRecorder(lanzar=RuntimeError("db caída")))

    with caplog.at_level(logging.ERROR):
        auditoria.registrar_evento("user-1", "cfdi_subido", empresa_id="emp-1")  # no debe lanzar

    assert "no se pudo registrar evento" in caplog.text
