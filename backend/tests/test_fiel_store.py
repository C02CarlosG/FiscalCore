"""Tests de backend/fiel_store.py — cifrado/descifrado de credenciales FIEL y CRUD.

No requieren Postgres real: la DB se mockea con FakeDB (misma interfaz que
backend/db.py: query_one(sql, params) / execute(sql, params)).
"""
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from backend import fiel_store
from backend.sat_fiel import FIELError


class FakeDB:
    def __init__(self, query_one_result=None):
        self._query_one_result = query_one_result
        self.execute_calls = []

    def execute(self, sql, params=()):
        self.execute_calls.append((sql, params))

    def query_one(self, sql, params=()):
        return self._query_one_result


@pytest.fixture(autouse=True)
def _fiel_key(monkeypatch):
    monkeypatch.setenv("FIEL_ENCRYPTION_KEY", Fernet.generate_key().decode())


def _cert_der(rfc_en_cn: str | None, dias_vigencia: int = 365) -> bytes:
    """Genera un certificado autofirmado DER, con RFC embebido en el CN si se pide."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    cn = f"ACME SA DE CV / {rfc_en_cn}" if rfc_en_cn else "ACME SA DE CV"
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc) - timedelta(days=1))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=dias_vigencia))
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(encoding=serialization.Encoding.DER)


# ─── _cifrar / _descifrar ────────────────────────────────────────────────────

def test_cifrar_descifrar_roundtrip():
    original = b"contenido-binario-de-prueba"
    token = fiel_store._cifrar(original)
    assert token != original
    assert fiel_store._descifrar(token) == original


def test_falta_encryption_key_lanza_runtime_error(monkeypatch):
    monkeypatch.delenv("FIEL_ENCRYPTION_KEY", raising=False)
    with pytest.raises(RuntimeError, match="FIEL_ENCRYPTION_KEY"):
        fiel_store._cifrar(b"x")


def test_encryption_key_invalida_lanza_runtime_error(monkeypatch):
    monkeypatch.setenv("FIEL_ENCRYPTION_KEY", "no-es-una-clave-fernet-valida")
    with pytest.raises(RuntimeError, match="inválida"):
        fiel_store._cifrar(b"x")


# ─── guardar_fiel ─────────────────────────────────────────────────────────────

def test_guardar_fiel_cifra_credenciales_antes_de_guardar(monkeypatch):
    monkeypatch.setattr("backend.sat_fiel.cargar_fiel", lambda cer, key, pwd: SimpleNamespace(rfc=None))

    db = FakeDB()
    cer_bytes, key_bytes, password = b"no-es-un-cert-valido", b"llave-privada", "clave123"

    resultado = fiel_store.guardar_fiel(db, "emp-1", cer_bytes, key_bytes, password)

    assert resultado["guardada"] is True
    assert resultado["rfc_certificado"] is None
    assert resultado["vigencia_fin"] is None

    assert len(db.execute_calls) == 1
    sql, params = db.execute_calls[0]
    assert "INSERT INTO empresas_fiel" in sql
    empresa_id, cer_cifrado, key_cifrado, pwd_cifrado, rfc_cert, vigencia_fin = params
    assert empresa_id == "emp-1"
    assert rfc_cert is None
    assert vigencia_fin is None
    # Nunca se guardan las credenciales en texto plano.
    assert cer_cifrado != cer_bytes
    assert key_cifrado != key_bytes
    assert pwd_cifrado != password
    assert fiel_store._descifrar(cer_cifrado) == cer_bytes
    assert fiel_store._descifrar(key_cifrado) == key_bytes
    assert fiel_store._descifrar(pwd_cifrado).decode() == password


def test_guardar_fiel_extrae_rfc_directo_del_signer(monkeypatch):
    cer_bytes = _cert_der(rfc_en_cn=None)
    monkeypatch.setattr("backend.sat_fiel.cargar_fiel", lambda cer, key, pwd: SimpleNamespace(rfc="SIG010101AAA"))

    db = FakeDB()
    resultado = fiel_store.guardar_fiel(db, "emp-1", cer_bytes, b"key", "pwd")

    assert resultado["rfc_certificado"] == "SIG010101AAA"
    assert resultado["vigencia_fin"] is not None


def test_guardar_fiel_extrae_rfc_del_cn_si_signer_no_lo_expone(monkeypatch):
    cer_bytes = _cert_der(rfc_en_cn="CNX010101BBB")
    monkeypatch.setattr("backend.sat_fiel.cargar_fiel", lambda cer, key, pwd: SimpleNamespace())

    db = FakeDB()
    resultado = fiel_store.guardar_fiel(db, "emp-1", cer_bytes, b"key", "pwd")

    assert resultado["rfc_certificado"] == "CNX010101BBB"


def test_guardar_fiel_extrae_vigencia_del_certificado(monkeypatch):
    cer_bytes = _cert_der(rfc_en_cn="VIG010101CCC", dias_vigencia=100)
    monkeypatch.setattr("backend.sat_fiel.cargar_fiel", lambda cer, key, pwd: SimpleNamespace())

    db = FakeDB()
    resultado = fiel_store.guardar_fiel(db, "emp-1", cer_bytes, b"key", "pwd")

    esperado = (datetime.now(timezone.utc) + timedelta(days=100)).date()
    assert resultado["vigencia_fin"] == str(esperado)


def test_guardar_fiel_fiel_invalida_lanza_valueerror(monkeypatch):
    def _raise(cer, key, pwd):
        raise FIELError("contraseña incorrecta")

    monkeypatch.setattr("backend.sat_fiel.cargar_fiel", _raise)

    db = FakeDB()
    with pytest.raises(ValueError, match="FIEL inválida"):
        fiel_store.guardar_fiel(db, "emp-1", b"cer", b"key", "mal")
    assert db.execute_calls == []


# ─── obtener_signer ───────────────────────────────────────────────────────────

def test_obtener_signer_sin_fiel_guardada_lanza_valueerror():
    db = FakeDB(query_one_result=None)
    with pytest.raises(ValueError, match="No hay FIEL guardada"):
        fiel_store.obtener_signer(db, "emp-1")


def test_obtener_signer_descifra_y_carga_la_fiel(monkeypatch):
    cer_bytes, key_bytes, password = b"cert-real", b"llave-real", "secreto"
    db = FakeDB(query_one_result={
        "cer_cifrado": fiel_store._cifrar(cer_bytes),
        "key_cifrado": fiel_store._cifrar(key_bytes),
        "pwd_cifrado": fiel_store._cifrar(password.encode()),
    })

    llamada = {}

    def _cargar_fiel(cer, key, pwd):
        llamada["args"] = (cer, key, pwd)
        return "signer-listo"

    monkeypatch.setattr("backend.sat_fiel.cargar_fiel", _cargar_fiel)

    signer = fiel_store.obtener_signer(db, "emp-1")

    assert signer == "signer-listo"
    assert llamada["args"] == (cer_bytes, key_bytes, password)


def test_obtener_signer_error_al_cargar_lanza_valueerror(monkeypatch):
    db = FakeDB(query_one_result={
        "cer_cifrado": fiel_store._cifrar(b"cer"),
        "key_cifrado": fiel_store._cifrar(b"key"),
        "pwd_cifrado": fiel_store._cifrar(b"pwd"),
    })

    def _raise(cer, key, pwd):
        raise FIELError("certificado corrupto")

    monkeypatch.setattr("backend.sat_fiel.cargar_fiel", _raise)

    with pytest.raises(ValueError, match="Error al cargar FIEL guardada"):
        fiel_store.obtener_signer(db, "emp-1")


# ─── estado_fiel ──────────────────────────────────────────────────────────────

def test_estado_fiel_sin_fiel_retorna_none():
    db = FakeDB(query_one_result=None)
    assert fiel_store.estado_fiel(db, "emp-1") is None


def test_estado_fiel_vencida():
    db = FakeDB(query_one_result={
        "rfc_certificado": "ABC010101AAA",
        "vigencia_fin": date.today() - timedelta(days=5),
        "updated_at": None,
    })
    resultado = fiel_store.estado_fiel(db, "emp-1")
    assert resultado["dias_restantes"] == -5
    assert resultado["vencida"] is True
    assert resultado["por_vencer"] is False


def test_estado_fiel_por_vencer():
    db = FakeDB(query_one_result={
        "rfc_certificado": "ABC010101AAA",
        "vigencia_fin": date.today() + timedelta(days=10),
        "updated_at": None,
    })
    resultado = fiel_store.estado_fiel(db, "emp-1")
    assert resultado["dias_restantes"] == 10
    assert resultado["vencida"] is False
    assert resultado["por_vencer"] is True


def test_estado_fiel_vigente_lejos_no_esta_por_vencer():
    db = FakeDB(query_one_result={
        "rfc_certificado": "ABC010101AAA",
        "vigencia_fin": date.today() + timedelta(days=90),
        "updated_at": None,
    })
    resultado = fiel_store.estado_fiel(db, "emp-1")
    assert resultado["vencida"] is False
    assert resultado["por_vencer"] is False


# ─── eliminar_fiel ────────────────────────────────────────────────────────────

def test_eliminar_fiel_existente_retorna_true_y_borra():
    db = FakeDB(query_one_result={"id": 1})
    assert fiel_store.eliminar_fiel(db, "emp-1") is True
    assert any("DELETE FROM empresas_fiel" in sql for sql, _ in db.execute_calls)


def test_eliminar_fiel_inexistente_retorna_false():
    db = FakeDB(query_one_result=None)
    assert fiel_store.eliminar_fiel(db, "emp-1") is False
    assert db.execute_calls == []
