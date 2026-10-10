"""La e.firma nunca debe aparecer en logs, en error_msg ni en auditoría."""
import logging
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from backend.tests.conftest import db_disponible

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]

SECRETOS = ("SECRETO-FIEL", "BYTES-LLAVE", "CONTRASENA-FIEL")


class _SignerConSecretos:
    """Representa la e.firma descifrada: cualquier volcado accidental de este objeto la filtraría."""
    password = "CONTRASENA-FIEL"
    key = b"BYTES-LLAVE"

    def __repr__(self):
        return "<Signer SECRETO-FIEL>"

    __str__ = __repr__


def test_un_error_al_descargar_no_filtra_la_efirma(monkeypatch, caplog):
    import backend.routers.ingesta as ingesta
    from backend import db, fiel_store, sat_sync
    from backend.sat_fiel import FIELError

    db.init_db()
    rfc = "WRK010101" + uuid.uuid4().hex[:3].upper()
    empresa = str(db.execute("INSERT INTO empresas (rfc, razon_social) VALUES (%s, 'Seguridad') RETURNING id",
                             (rfc,), returning=True)["id"])
    ahora = datetime.now(timezone.utc)
    db.execute(
        "INSERT INTO sat_sync_config (empresa_id, activa, estado, carga_inicial_ok, ultima_exitosa, proxima_corrida) "
        "VALUES (%s, TRUE, 'al_dia', TRUE, %s, %s)", (empresa, ahora - timedelta(days=1), ahora - timedelta(minutes=1)))

    monkeypatch.setattr(fiel_store, "estado_fiel", lambda db_, eid: {"tiene_fiel": True, "vencida": False})
    monkeypatch.setattr(fiel_store, "obtener_signer", lambda db_, eid: _SignerConSecretos())
    monkeypatch.setattr(sat_sync, "ESPERA_VERIFICACION_SEG", 0)
    monkeypatch.setattr(ingesta, "_correr_pipeline", lambda *a: None)
    monkeypatch.setattr(sat_sync, "solicitar_descarga", lambda *a, **k: "SAT-1")
    monkeypatch.setattr(sat_sync, "verificar_solicitud",
                        lambda creds, id_sat: {"estado": 3, "num_cfdi": 1, "id_paquetes": ["p1"]})

    def _descargar(creds, id_paquete, extensiones=(".xml",)):
        raise FIELError(f"Error al descargar paquete {id_paquete!r}: tiempo de espera agotado")
    monkeypatch.setattr(sat_sync, "descargar_paquete", _descargar)

    try:
        with caplog.at_level(logging.DEBUG):
            for _ in range(6):
                sat_sync.procesar_empresa(empresa, ahora=ahora)

        textos = [caplog.text]
        textos += [f["error_msg"] or "" for f in db.query_all(
            "SELECT error_msg FROM sat_solicitudes WHERE empresa_id=%s", (empresa,))]
        textos += [str(f["metadata"]) for f in db.query_all(
            "SELECT metadata FROM auditoria WHERE empresa_id=%s", (empresa,))]
        assert any("tiempo de espera agotado" in t for t in textos)          # sí se registró el error del SAT
        for t in textos:
            for secreto in SECRETOS:
                assert secreto not in t
    finally:
        db.execute("DELETE FROM empresas WHERE id=%s", (empresa,))
