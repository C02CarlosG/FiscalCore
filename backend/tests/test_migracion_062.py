"""Migración 062: roles por empresa (U1). Requiere Postgres."""
import psycopg2
import pytest

from backend.tests.conftest import db_disponible

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]

RFC = "MIG062101E2E"
CORREOS = ("mig062-a@test.local", "mig062-b@test.local")


def _limpiar(db):
    db.execute("DELETE FROM empresas WHERE rfc = %s", (RFC,))
    db.execute("DELETE FROM usuarios WHERE email IN (%s, %s)", CORREOS)


def test_062_marca_al_creador_como_administrador_y_se_puede_repetir():
    from backend import db

    db.init_db()
    _limpiar(db)
    try:
        empresa = db.execute("INSERT INTO empresas (rfc, razon_social) VALUES (%s, 'Migración 062') RETURNING id",
                             (RFC,), returning=True)
        ids = [db.execute("INSERT INTO usuarios (email, password_hash) VALUES (%s, 'x') RETURNING id", (c,),
                          returning=True)["id"] for c in CORREOS]
        # Ambos vinculados como 'contador' (lo que hacía la app antes de U1); a es el más antiguo.
        db.execute("INSERT INTO usuario_empresas (usuario_id, empresa_id, rol, created_at) "
                   "VALUES (%s, %s, 'contador', '2026-01-01'), (%s, %s, 'contador', '2026-02-01')",
                   (ids[0], empresa["id"], ids[1], empresa["id"]))

        db.init_db()
        db.init_db()

        roles = {str(f["usuario_id"]): f["rol"] for f in db.query_all(
            "SELECT usuario_id, rol FROM usuario_empresas WHERE empresa_id = %s", (empresa["id"],))}
        assert roles == {str(ids[0]): "administrador", str(ids[1]): "contador"}

        with pytest.raises(psycopg2.errors.CheckViolation):
            db.execute("UPDATE usuario_empresas SET rol = 'lectura' WHERE usuario_id = %s", (ids[1],))

        # Invitaciones: una sola pendiente por empresa y correo, correo en minúsculas.
        db.execute("INSERT INTO invitaciones_empresa (empresa_id, email, rol) VALUES (%s, 'x@test.local', 'contador')",
                   (empresa["id"],))
        with pytest.raises(psycopg2.errors.UniqueViolation):
            db.execute("INSERT INTO invitaciones_empresa (empresa_id, email, rol) VALUES (%s, 'x@test.local', 'contador')",
                       (empresa["id"],))
        with pytest.raises(psycopg2.errors.CheckViolation):
            db.execute("INSERT INTO invitaciones_empresa (empresa_id, email, rol) VALUES (%s, 'X@test.local', 'contador')",
                       (empresa["id"],))
        # Una aceptación por aprobar también ocupa el lugar; resuelta, ya no.
        db.execute("UPDATE invitaciones_empresa SET estado = 'aceptada_pendiente' WHERE empresa_id = %s", (empresa["id"],))
        with pytest.raises(psycopg2.errors.UniqueViolation):
            db.execute("INSERT INTO invitaciones_empresa (empresa_id, email, rol) VALUES (%s, 'x@test.local', 'contador')",
                       (empresa["id"],))
        db.execute("UPDATE invitaciones_empresa SET estado = 'rechazada_admin' WHERE empresa_id = %s", (empresa["id"],))
        db.execute("INSERT INTO invitaciones_empresa (empresa_id, email, rol) VALUES (%s, 'x@test.local', 'contador')",
                   (empresa["id"],))
        with pytest.raises(psycopg2.errors.CheckViolation):
            db.execute("UPDATE invitaciones_empresa SET estado = 'aceptada' WHERE empresa_id = %s", (empresa["id"],))
    finally:
        _limpiar(db)


def test_062_conserva_variantes_de_administrador():
    from backend import db

    db.init_db()
    _limpiar(db)
    try:
        empresa = db.execute("INSERT INTO empresas (rfc, razon_social) VALUES (%s, 'Migración 062') RETURNING id",
                             (RFC,), returning=True)
        ids = [db.execute("INSERT INTO usuarios (email, password_hash) VALUES (%s, 'x') RETURNING id", (c,),
                          returning=True)["id"] for c in CORREOS]
        # Simula una base previa a la 062 (sin CHECK) con un 'Admin ' escrito a mano en el segundo vínculo.
        db.execute("ALTER TABLE usuario_empresas DROP CONSTRAINT IF EXISTS chk_usuario_empresas_rol")
        db.execute("INSERT INTO usuario_empresas (usuario_id, empresa_id, rol, created_at) "
                   "VALUES (%s, %s, 'contador', '2026-01-01'), (%s, %s, 'Admin ', '2026-02-01')",
                   (ids[0], empresa["id"], ids[1], empresa["id"]))
        db.init_db()
        roles = {str(f["usuario_id"]): f["rol"] for f in db.query_all(
            "SELECT usuario_id, rol FROM usuario_empresas WHERE empresa_id = %s", (empresa["id"],))}
        assert roles == {str(ids[0]): "contador", str(ids[1]): "administrador"}
    finally:
        _limpiar(db)
        db.init_db()
