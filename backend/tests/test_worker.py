"""Worker de descarga automática: ciclo, arranque y despliegue."""
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from backend import sat_sync, worker
from backend.tests.conftest import db_disponible

RAIZ = Path(__file__).parent.parent.parent


def test_ciclo_procesa_solo_las_elegibles_y_una_excepcion_no_detiene_a_las_demas(monkeypatch):
    llamadas = []

    def _procesar(empresa_id, ahora=None):
        llamadas.append(empresa_id)
        if empresa_id == "emp-2":
            raise RuntimeError("falla inesperada de una empresa")
        return "al_dia"

    monkeypatch.setattr(worker, "empresas_elegibles", lambda ahora: ["emp-1", "emp-2", "emp-3"])
    monkeypatch.setattr(sat_sync, "procesar_empresa", _procesar)

    resultados = worker.ciclo()

    assert llamadas == ["emp-1", "emp-2", "emp-3"]
    assert resultados == [("emp-1", "al_dia"), ("emp-2", "error_interno"), ("emp-3", "al_dia")]


def test_ciclo_sin_empresas_elegibles_no_hace_nada(monkeypatch):
    monkeypatch.setattr(worker, "empresas_elegibles", lambda ahora: [])
    assert worker.ciclo() == []


def test_ciclo_registra_la_empresa_que_falla(monkeypatch, caplog):
    def _procesar(empresa_id, ahora=None):
        raise RuntimeError("fallo")
    monkeypatch.setattr(worker, "empresas_elegibles", lambda ahora: ["emp-1"])
    monkeypatch.setattr(sat_sync, "procesar_empresa", _procesar)

    with caplog.at_level("ERROR"):
        worker.ciclo()

    assert "emp-1" in caplog.text


def test_arranque_sin_clave_de_cifrado_sale_con_codigo_1_y_mensaje_claro(monkeypatch, capsys):
    monkeypatch.delenv("FIEL_ENCRYPTION_KEY", raising=False)
    monkeypatch.setattr(worker.db, "init_db", lambda: pytest.fail("no debe tocar la base si falta la clave"))

    assert worker.main() == 1
    assert "FIEL_ENCRYPTION_KEY" in capsys.readouterr().err


def test_arranque_con_clave_invalida_sale_con_codigo_1(monkeypatch, capsys):
    monkeypatch.setenv("FIEL_ENCRYPTION_KEY", "no-es-una-clave-fernet")
    monkeypatch.setattr(worker.db, "init_db", lambda: pytest.fail("no debe tocar la base"))

    assert worker.main() == 1
    assert "FIEL_ENCRYPTION_KEY" in capsys.readouterr().err


def test_main_cicla_hasta_que_se_pide_detener(monkeypatch):
    from cryptography.fernet import Fernet

    monkeypatch.setenv("FIEL_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(worker.db, "init_db", lambda: None)
    monkeypatch.setattr(worker, "_instalar_senales", lambda: None)
    worker._detener.clear()
    vueltas = []

    def _ciclo(ahora=None):
        vueltas.append(1)
        if len(vueltas) == 2:
            worker._detener.set()
        return []
    monkeypatch.setattr(worker, "ciclo", _ciclo)
    monkeypatch.setattr(sat_sync, "config_sync", lambda: sat_sync.ConfigSync(intervalo_seg=1))
    monkeypatch.setattr(worker, "_dormir", lambda segundos: None)

    assert worker.main() == 0
    assert len(vueltas) == 2
    worker._detener.clear()


@pytest.mark.db
@pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")
def test_empresas_elegibles_segun_su_configuracion():
    from datetime import datetime, timedelta, timezone

    from backend import db

    db.init_db()
    ahora = datetime.now(timezone.utc)
    ids = {}
    for nombre, activa, estado, proxima, corrida in [
        ("vencida", True, "al_dia", ahora - timedelta(hours=1), None),
        ("futura", True, "al_dia", ahora + timedelta(hours=5), None),
        ("sin_proxima", True, "inactiva", None, None),
        ("en_corrida", True, "sincronizando", ahora + timedelta(hours=5), ahora),
        ("pausada", True, "pausada", ahora + timedelta(hours=5), None),
        ("inactiva", False, "inactiva", ahora - timedelta(hours=1), None),
    ]:
        rfc = ("WRK010101" + uuid.uuid4().hex[:3]).upper()
        emp = str(db.execute("INSERT INTO empresas (rfc, razon_social) VALUES (%s, %s) RETURNING id",
                             (rfc, nombre), returning=True)["id"])
        db.execute(
            "INSERT INTO sat_sync_config (empresa_id, activa, estado, proxima_corrida, corrida_inicio) "
            "VALUES (%s, %s, %s, %s, %s)", (emp, activa, estado, proxima, corrida))
        ids[nombre] = emp
    try:
        elegibles = set(worker.empresas_elegibles(ahora))
        assert {ids["vencida"], ids["sin_proxima"], ids["en_corrida"], ids["pausada"]} <= elegibles
        assert ids["futura"] not in elegibles and ids["inactiva"] not in elegibles

        # una empresa con corrida futura pero con una solicitud activa también es elegible
        db.execute(
            "INSERT INTO sat_solicitudes (empresa_id, tipo, periodo_inicio, periodo_fin, estado) "
            "VALUES (%s, 'emitidos', '2026-09', '2026-09', 'solicitado')", (ids["futura"],))
        assert ids["futura"] in set(worker.empresas_elegibles(ahora))
    finally:
        for emp in ids.values():
            db.execute("DELETE FROM empresas WHERE id=%s", (emp,))


# ─── despliegue ──────────────────────────────────────────────────────────────

def test_procfile_declara_el_proceso_worker():
    lineas = (RAIZ / "Procfile").read_text(encoding="utf-8").splitlines()
    assert any(l.startswith("web:") for l in lineas)
    assert "worker: python -m backend.worker" in lineas


def test_dev_sh_tiene_sintaxis_valida_y_maneja_el_worker():
    resultado = subprocess.run(["bash", "-n", str(RAIZ / "dev.sh")], capture_output=True, text=True)
    assert resultado.returncode == 0, resultado.stderr
    texto = (RAIZ / "dev.sh").read_text(encoding="utf-8")
    assert "backend.worker" in texto and "WORKER_PID" in texto


def test_modulo_worker_se_puede_ejecutar_con_python_dash_m_sin_clave():
    """Sin FIEL_ENCRYPTION_KEY el proceso termina de inmediato con código 1 (no se queda colgado)."""
    import os

    entorno = {k: v for k, v in os.environ.items() if k != "FIEL_ENCRYPTION_KEY"}
    entorno.setdefault("JWT_SECRET", "test")
    resultado = subprocess.run(
        [sys.executable, "-m", "backend.worker"], cwd=RAIZ, env=entorno,
        capture_output=True, text=True, timeout=60,
    )
    assert resultado.returncode == 1
    assert "FIEL_ENCRYPTION_KEY" in resultado.stderr
