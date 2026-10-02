"""Guardas de producción de backend/db.py.

Se evalúan al importar el módulo, así que cada caso corre en un subproceso
con su propio entorno (sin contaminar el `backend.db` ya importado).
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]


def _importar_db(**env_extra):
    env = {k: v for k, v in os.environ.items()
           if k not in ("RAILWAY_ENVIRONMENT", "VERCEL", "SEED_ADMIN_PASSWORD")}
    env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-c", "import backend.db"],
        cwd=RAIZ, env=env, capture_output=True, text=True, timeout=60,
    )


@pytest.mark.parametrize("variable", ["RAILWAY_ENVIRONMENT", "VERCEL"])
def test_despliegue_sin_contrasena_de_admin_explicita_no_arranca(variable):
    r = _importar_db(**{variable: "1"})
    assert r.returncode != 0
    assert "SEED_ADMIN_PASSWORD no configurada" in r.stderr
    assert f"{variable} detectado" in r.stderr


def test_despliegue_con_contrasena_de_admin_explicita_arranca():
    r = _importar_db(VERCEL="1", SEED_ADMIN_PASSWORD="una-contrasena-propia")
    assert r.returncode == 0, r.stderr


def test_desarrollo_local_admite_el_default():
    r = _importar_db()
    assert r.returncode == 0, r.stderr
