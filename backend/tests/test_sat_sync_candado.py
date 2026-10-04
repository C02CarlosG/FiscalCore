"""Candado por empresa (advisory lock de Postgres). Requiere Postgres."""
import uuid

import pytest

from backend.tests.conftest import db_disponible

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


def _id():
    return str(uuid.uuid4())


def test_el_candado_se_obtiene_y_se_libera():
    from backend.sat_sync import candado_empresa

    emp = _id()
    with candado_empresa(emp) as obtenido:
        assert obtenido is True
    with candado_empresa(emp) as obtenido:
        assert obtenido is True


def test_dos_usos_de_la_misma_empresa_el_interior_no_lo_obtiene():
    from backend.sat_sync import candado_empresa

    emp = _id()
    with candado_empresa(emp) as externo:
        assert externo is True
        with candado_empresa(emp) as interno:
            assert interno is False
    with candado_empresa(emp) as despues:
        assert despues is True


def test_empresas_distintas_no_se_bloquean():
    from backend.sat_sync import candado_empresa

    with candado_empresa(_id()) as a:
        with candado_empresa(_id()) as b:
            assert a is True and b is True


def test_se_libera_aun_con_excepcion():
    from backend.sat_sync import candado_empresa

    emp = _id()
    with pytest.raises(RuntimeError):
        with candado_empresa(emp) as obtenido:
            assert obtenido is True
            raise RuntimeError("falla dentro del bloque")
    with candado_empresa(emp) as despues:
        assert despues is True


def test_el_trabajo_con_otras_conexiones_funciona_mientras_se_sostiene_el_candado():
    from backend import db
    from backend.sat_sync import candado_empresa

    with candado_empresa(_id()) as obtenido:
        assert obtenido is True
        for _ in range(8):  # más consultas que conexiones del pool (5)
            assert db.query_one("SELECT 1 AS x") == {"x": 1}


def test_el_candado_no_queda_tomado_al_devolver_la_conexion_al_pool():
    """Con el pool de 5 conexiones, tomar y soltar muchas veces no deja candados colgados."""
    from backend import db
    from backend.sat_sync import candado_empresa

    empresas = [_id() for _ in range(12)]
    for emp in empresas:
        with candado_empresa(emp):
            pass
    colgados = db.query_one(
        "SELECT COUNT(*) AS n FROM pg_locks WHERE locktype = 'advisory' AND granted AND pid IN "
        "(SELECT pid FROM pg_stat_activity WHERE datname = current_database())")
    assert colgados["n"] == 0
