"""Migración 065: historial de asignaciones de plan (M7.2). Requiere Postgres."""
import pytest

from backend.tests.conftest import db_disponible

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]

CORREO = "m7-historial-065@test.local"


def test_065_siembra_la_asignacion_vigente_una_sola_vez():
    from backend import db

    db.init_db()
    db.execute("DELETE FROM usuarios WHERE email = %s", (CORREO,))
    try:
        uid = db.execute("INSERT INTO usuarios (email, password_hash) VALUES (%s, 'x') RETURNING id", (CORREO,),
                         returning=True)["id"]
        # Una suscripción anterior a la 065 (sin fila de historial).
        db.execute("INSERT INTO suscripciones (usuario_id, plan_clave, estado, notas) VALUES (%s, 'basico', 'activa', 'previa')",
                   (uid,))
        db.init_db()
        db.init_db()  # repetirla no duplica
        filas = db.query_all("SELECT plan_clave, notas FROM suscripciones_historial WHERE usuario_id = %s", (uid,))
        assert [(f["plan_clave"], f["notas"]) for f in filas] == [("basico", "previa")]
    finally:
        db.execute("DELETE FROM usuarios WHERE email = %s", (CORREO,))
