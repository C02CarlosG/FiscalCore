"""Migración 066: datos fiscales y pagos manuales de la suscripción (M7.2). Requiere Postgres."""
import psycopg2
import pytest

from backend.tests.conftest import db_disponible

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]

CORREO = "m7-pagos-066@test.local"


def test_066_idempotente_y_con_restricciones():
    from backend import db

    db.init_db()
    db.init_db()
    db.execute("DELETE FROM usuarios WHERE email = %s", (CORREO,))
    try:
        uid = db.execute("INSERT INTO usuarios (email, password_hash) VALUES (%s, 'x') RETURNING id", (CORREO,),
                         returning=True)["id"]
        with pytest.raises(psycopg2.errors.CheckViolation):
            db.execute("INSERT INTO suscripciones_pagos (usuario_id, fecha, monto, vigente_hasta_nueva) "
                       "VALUES (%s, '2026-10-01', 0, '2026-11-01')", (uid,))
        # Anulado sin motivo ni fecha: no.
        with pytest.raises(psycopg2.errors.CheckViolation):
            db.execute("INSERT INTO suscripciones_pagos (usuario_id, fecha, monto, vigente_hasta_nueva, estado) "
                       "VALUES (%s, '2026-10-01', 10, '2026-11-01', 'anulado')", (uid,))
        with pytest.raises(psycopg2.errors.CheckViolation):
            db.execute("INSERT INTO suscripciones_datos_fiscales (usuario_id, rfc, razon_social, regimen_fiscal, "
                       "codigo_postal, uso_cfdi) VALUES (%s, 'ace010101aa1', 'X', '601', '68000', 'G03')", (uid,))
        # Borrar la cuenta borra sus pagos y datos fiscales.
        db.execute("INSERT INTO suscripciones_pagos (usuario_id, fecha, monto, vigente_hasta_nueva) "
                   "VALUES (%s, '2026-10-01', 10, '2026-11-01')", (uid,))
        db.execute("DELETE FROM usuarios WHERE id = %s", (uid,))
        assert db.query_one("SELECT COUNT(*) AS n FROM suscripciones_pagos WHERE usuario_id = %s", (uid,))["n"] == 0
    finally:
        db.execute("DELETE FROM usuarios WHERE email = %s", (CORREO,))
