"""Migración 031: descarga automática del SAT (sat_solicitudes ampliada y sat_sync_config). Requiere Postgres."""
import uuid
from pathlib import Path

import psycopg2
import pytest

from backend.tests.conftest import db_disponible

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]

_ACTIVAS = ("pendiente", "solicitado", "en_proceso", "terminado")
_MIGRACION = Path(__file__).parent.parent.parent / "database" / "migrations" / "031_sat_sync.sql"


@pytest.fixture()
def empresa():
    from backend import db

    db.init_db()
    rfc = ("T" + uuid.uuid4().hex[:11]).upper()
    fila = db.execute(
        "INSERT INTO empresas (rfc, razon_social) VALUES (%s, 'Empresa 031') RETURNING id",
        (rfc,), returning=True,
    )
    yield str(fila["id"])
    db.execute("DELETE FROM empresas WHERE id = %s", (str(fila["id"]),))


def _solicitud(db, empresa_id, estado="solicitado", periodo="2026-01", **extra):
    columnas = {"empresa_id": empresa_id, "tipo": "emitidos", "periodo_inicio": periodo,
                "periodo_fin": periodo, "estado": estado, **extra}
    return db.execute(
        f"INSERT INTO sat_solicitudes ({', '.join(columnas)}) "
        f"VALUES ({', '.join(['%s'] * len(columnas))}) RETURNING id",
        tuple(columnas.values()), returning=True,
    )


def test_031_se_puede_repetir_y_agrega_columnas_y_tabla():
    from backend import db

    db.init_db()
    db.init_db()

    columnas = {f["column_name"]: f for f in db.query_all(
        "SELECT column_name, is_nullable, column_default FROM information_schema.columns "
        "WHERE table_name = 'sat_solicitudes'")}
    assert {"origen", "estado_comprobante", "tipo_solicitud", "intentos",
            "proximo_intento", "fecha_inicio", "fecha_fin"} <= set(columnas)
    assert columnas["usuario_id"]["is_nullable"] == "YES"
    assert "manual" in columnas["origen"]["column_default"]
    assert "Vigente" in columnas["estado_comprobante"]["column_default"]
    assert "CFDI" in columnas["tipo_solicitud"]["column_default"]

    config = {f["column_name"] for f in db.query_all(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'sat_sync_config'")}
    assert config == {"empresa_id", "activa", "consentimiento_por", "consentimiento_el",
                      "carga_inicial_ok", "ultima_exitosa", "proxima_corrida", "estado",
                      "motivo_pausa", "updated_at", "corrida_inicio"}


def test_031_solicitud_sin_usuario_y_origen_manual_por_defecto(empresa):
    from backend import db

    fila = _solicitud(db, empresa)
    guardada = db.query_one("SELECT usuario_id, origen, intentos FROM sat_solicitudes WHERE id = %s",
                            (str(fila["id"]),))
    assert guardada["usuario_id"] is None
    assert guardada["origen"] == "manual"
    assert guardada["intentos"] == 0


def test_031_origen_fuera_del_catalogo_se_rechaza(empresa):
    from backend import db

    with pytest.raises(psycopg2.errors.CheckViolation):
        _solicitud(db, empresa, origen="otro")


def test_031_ventana_activa_duplicada_viola_el_indice(empresa):
    from backend import db

    _solicitud(db, empresa, estado="solicitado")
    with pytest.raises(psycopg2.errors.UniqueViolation):
        _solicitud(db, empresa, estado="en_proceso")


def test_031_activa_convive_con_terminadas_y_con_otras_ventanas(empresa):
    from backend import db

    _solicitud(db, empresa, estado="solicitado")
    _solicitud(db, empresa, estado="descargado")
    _solicitud(db, empresa, estado="fallo")
    _solicitud(db, empresa, estado="solicitado", periodo="2026-02")
    _solicitud(db, empresa, estado="solicitado", estado_comprobante="Cancelado", tipo_solicitud="Metadata")
    # mitades del mismo mes (partición por volumen) no chocan entre sí
    _solicitud(db, empresa, estado="solicitado", periodo="2026-03",
               fecha_inicio="2026-03-01", fecha_fin="2026-03-15")
    _solicitud(db, empresa, estado="solicitado", periodo="2026-03",
               fecha_inicio="2026-03-16", fecha_fin="2026-03-31")


def test_031_sat_sync_config_valida_estado_y_cascada(empresa):
    from backend import db

    db.execute("INSERT INTO sat_sync_config (empresa_id) VALUES (%s)", (empresa,))
    fila = db.query_one("SELECT activa, estado, carga_inicial_ok FROM sat_sync_config WHERE empresa_id = %s",
                        (empresa,))
    assert fila == {"activa": False, "estado": "inactiva", "carga_inicial_ok": False}

    with pytest.raises(psycopg2.errors.CheckViolation):
        db.execute("UPDATE sat_sync_config SET estado = 'rara' WHERE empresa_id = %s", (empresa,))

    db.execute("DELETE FROM empresas WHERE id = %s", (empresa,))
    assert db.query_one("SELECT 1 AS x FROM sat_sync_config WHERE empresa_id = %s", (empresa,)) is None


def test_031_repara_activas_duplicadas_previas_sin_fallar(empresa):
    """Con duplicados activos anteriores a la migración, ésta termina y deja una sola activa."""
    from backend import db

    db.execute("DROP INDEX IF EXISTS uq_sat_solicitudes_ventana_activa")
    vieja = _solicitud(db, empresa, estado="solicitado")
    nueva = _solicitud(db, empresa, estado="en_proceso")
    db.execute("UPDATE sat_solicitudes SET created_at = NOW() - INTERVAL '1 day' WHERE id = %s",
               (str(vieja["id"]),))

    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(_MIGRACION.read_text(encoding="utf-8"))

    estados = {str(f["id"]): f for f in db.query_all(
        "SELECT id, estado, error_msg FROM sat_solicitudes WHERE empresa_id = %s", (empresa,))}
    assert estados[str(vieja["id"])]["estado"] == "fallo"
    assert "duplicada" in estados[str(vieja["id"])]["error_msg"].lower()
    assert estados[str(nueva["id"])]["estado"] == "en_proceso"
    assert sum(1 for f in estados.values() if f["estado"] in _ACTIVAS) == 1


def test_031_repara_duplicadas_con_created_at_nulo(empresa):
    """created_at admite NULL desde la 016: el desempate no debe dejar duplicados sin resolver."""
    from backend import db

    db.execute("DROP INDEX IF EXISTS uq_sat_solicitudes_ventana_activa")
    a = _solicitud(db, empresa, estado="pendiente")
    b = _solicitud(db, empresa, estado="pendiente")
    db.execute("UPDATE sat_solicitudes SET created_at = NULL WHERE id IN (%s, %s)", (str(a["id"]), str(b["id"])))

    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(_MIGRACION.read_text(encoding="utf-8"))

    estados = [f["estado"] for f in db.query_all(
        "SELECT estado FROM sat_solicitudes WHERE empresa_id = %s", (empresa,))]
    assert sorted(estados) == ["fallo", "pendiente"]


def test_031_rangos_distintos_con_el_mismo_inicio_no_son_duplicados(empresa):
    from backend import db

    _solicitud(db, empresa, estado="solicitado", periodo="2026-01")
    db.execute(
        "INSERT INTO sat_solicitudes (empresa_id, tipo, periodo_inicio, periodo_fin, estado) "
        "VALUES (%s, 'emitidos', '2026-01', '2026-03', 'solicitado')", (empresa,))
