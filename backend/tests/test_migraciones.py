"""Regresión de esquema: la migración 025 amplía tipo_match a VARCHAR(30).

Antes de la migración 025, insertar 'complemento_pago_total' (23 chars) o
'complemento_pago_parcial' (25 chars) en conciliaciones.tipo_match lanzaba
StringDataRightTruncation, porque la columna seguía en VARCHAR(20) pese a que
las migraciones 009/010 ya permitían esos valores en el CHECK. Reproducido en
vivo durante la validación E2E de la Fase C (Día 26-27): un CFDI PPD liquidado
vía REP tumbaba con 500 todo el batch de conciliación.

Se salta automáticamente si no hay DB disponible.
"""
import pytest

from backend.tests.conftest import db_disponible

RFC = "MIG010101E2E"

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


def _limpiar(db):
    db.execute(
        "DELETE FROM conciliaciones WHERE empresa_id IN (SELECT id FROM empresas WHERE rfc = %s)", (RFC,))
    db.execute("DELETE FROM empresas WHERE rfc = %s", (RFC,))


def test_tipo_match_admite_complemento_pago_total_y_parcial():
    from backend import db

    db.init_db()
    _limpiar(db)
    try:
        empresa = db.execute(
            "INSERT INTO empresas (rfc, razon_social) VALUES (%s, 'Migración Test SA') RETURNING id",
            (RFC,),
            returning=True,
        )
        empresa_id = empresa["id"]

        for tipo in ("complemento_pago_total", "complemento_pago_parcial"):
            db.execute(
                "INSERT INTO conciliaciones (empresa_id, tipo_match, periodo) VALUES (%s, %s, '2026-01')",
                (empresa_id, tipo),
            )
            row = db.query_one(
                "SELECT tipo_match FROM conciliaciones WHERE empresa_id = %s AND tipo_match = %s",
                (empresa_id, tipo),
            )
            assert row is not None
            assert row["tipo_match"] == tipo
    finally:
        _limpiar(db)


TIPOS_MATCH_DEL_MOTOR = (
    "exacto", "parcial", "sin_cfdi", "sin_movimiento",
    "complemento_pago_total", "complemento_pago_parcial",
    "agrupado", "parcial_multiple", "heuristico",
    "pendiente_rep", "pagado_parcial",
)


def test_init_db_se_puede_repetir_con_conciliaciones_de_todos_los_tipos():
    """Regresión: `init_db` corre en cada arranque y re-ejecuta todas las
    migraciones. Las 004/006/007/009 redeclaraban el CHECK de tipo_match con
    listas más cortas que la vigente, así que con filas reales (p. ej.
    'pendiente_rep', que el motor emite para cualquier PPD sin REP) el
    ADD CONSTRAINT lanzaba CheckViolation y la app no podía reiniciar."""
    from backend import db

    db.init_db()
    _limpiar(db)
    try:
        empresa = db.execute(
            "INSERT INTO empresas (rfc, razon_social) VALUES (%s, 'Migración Test SA') RETURNING id",
            (RFC,),
            returning=True,
        )
        for tipo in TIPOS_MATCH_DEL_MOTOR:
            db.execute(
                "INSERT INTO conciliaciones (empresa_id, tipo_match, periodo) VALUES (%s, %s, '2026-01')",
                (empresa["id"], tipo),
            )

        db.init_db()  # simula el reinicio del proceso con esos datos ya guardados

        row = db.query_one(
            "SELECT COUNT(*) AS n FROM conciliaciones WHERE empresa_id = %s", (empresa["id"],))
        assert row["n"] == len(TIPOS_MATCH_DEL_MOTOR)
    finally:
        _limpiar(db)
