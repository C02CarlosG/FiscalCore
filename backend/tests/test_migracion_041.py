"""Migración 041: orden del nodo y forma de pago en pagos_cfdi. Requiere Postgres real."""
import pytest

from backend.tests.conftest import db_disponible

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


def test_041_agrega_columnas_cambia_la_llave_y_se_puede_repetir():
    from backend import db

    db.init_db()
    db.init_db()  # idempotente

    columnas = {f["column_name"]: f for f in db.query_all(
        "SELECT column_name, data_type, column_default, is_nullable FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = 'pagos_cfdi'")}
    assert {"nodo", "forma_pago"} <= set(columnas)
    assert columnas["nodo"]["is_nullable"] == "NO" and columnas["nodo"]["column_default"] == "0"
    assert columnas["forma_pago"]["is_nullable"] == "YES"

    # La llave vieja (cfdi_id, fecha_pago, monto) ya no existe y la nueva es parcial (nodo > 0).
    restricciones = {f["conname"] for f in db.query_all("SELECT conname FROM pg_constraint WHERE conrelid = 'pagos_cfdi'::regclass")}
    assert "pagos_cfdi_cfdi_id_fecha_pago_monto_key" not in restricciones
    indice = db.query_one("SELECT indexdef FROM pg_indexes WHERE tablename = 'pagos_cfdi' AND indexname = 'uq_pagos_cfdi_nodo'")
    assert "UNIQUE" in indice["indexdef"] and "nodo > 0" in indice["indexdef"]
