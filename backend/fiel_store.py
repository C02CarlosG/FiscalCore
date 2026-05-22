# backend/fiel_store.py
"""
Almacenamiento seguro de credenciales FIEL por empresa.

Usa cifrado simétrico Fernet (AES-128-CBC + HMAC-SHA256) con una clave
maestra tomada de la variable de entorno FIEL_ENCRYPTION_KEY.

Generar clave:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
from __future__ import annotations

import base64
import logging
import os

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cargar clave de cifrado
# ---------------------------------------------------------------------------

def _get_fernet():
    """Devuelve una instancia Fernet lista para usar."""
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        raise RuntimeError(
            "cryptography no instalado. Ejecutar: pip install cryptography"
        )

    key_str = os.environ.get("FIEL_ENCRYPTION_KEY", "").strip()
    if not key_str:
        raise RuntimeError(
            "Variable de entorno FIEL_ENCRYPTION_KEY no configurada. "
            "Genera una con: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    try:
        return Fernet(key_str.encode())
    except Exception as exc:
        raise RuntimeError(f"FIEL_ENCRYPTION_KEY inválida: {exc}") from exc


def _cifrar(datos: bytes) -> str:
    """Cifra bytes y devuelve string base64 seguro."""
    return _get_fernet().encrypt(datos).decode()


def _descifrar(token: str) -> bytes:
    """Descifra un token Fernet y devuelve los bytes originales."""
    return _get_fernet().decrypt(token.encode())


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def guardar_fiel(
    db,
    empresa_id: str,
    cer_bytes: bytes,
    key_bytes: bytes,
    password: str,
) -> dict:
    """
    Guarda (o reemplaza) la FIEL de una empresa de forma cifrada.

    Valida primero que los archivos sean una FIEL válida usando satcfdi.
    Si ya existía una FIEL para la empresa, la sobreescribe.

    Retorna un dict con metadatos (sin credenciales en texto plano).
    """
    from .sat_fiel import cargar_fiel, FIELError

    # 1. Validar FIEL antes de guardar
    try:
        signer = cargar_fiel(cer_bytes, key_bytes, password)
    except FIELError as exc:
        raise ValueError(f"FIEL inválida: {exc}") from exc

    # 2. Extraer metadatos del certificado directamente del .cer
    rfc_cert = None
    vigencia_fin = None
    try:
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
        cert = x509.load_der_x509_certificate(cer_bytes, default_backend())
        # Obtener fecha de vencimiento (compatible Python 3.9+)
        try:
            vigencia_fin = cert.not_valid_after_utc.date()
        except AttributeError:
            vigencia_fin = cert.not_valid_after.date()  # fallback versiones anteriores
        # Extraer RFC del Subject (OID 2.5.4.45 o del CN)
        try:
            rfc_cert = getattr(signer, "rfc", None)
            if not rfc_cert:
                cn = cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
                if cn:
                    # El CN suele ser "NOMBRE / RFC"
                    rfc_cert = cn[0].value.split("/")[-1].strip()
        except Exception:
            pass
    except Exception as exc:
        _log.warning("No se pudo extraer metadatos del certificado: %s", exc)

    # 3. Cifrar credenciales
    cer_cifrado = _cifrar(cer_bytes)
    key_cifrado = _cifrar(key_bytes)
    pwd_cifrado = _cifrar(password.encode())

    # 4. Upsert en DB
    db.execute(
        """
        INSERT INTO empresas_fiel
            (empresa_id, cer_cifrado, key_cifrado, pwd_cifrado, rfc_certificado, vigencia_fin)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (empresa_id) DO UPDATE SET
            cer_cifrado     = EXCLUDED.cer_cifrado,
            key_cifrado     = EXCLUDED.key_cifrado,
            pwd_cifrado     = EXCLUDED.pwd_cifrado,
            rfc_certificado = EXCLUDED.rfc_certificado,
            vigencia_fin    = EXCLUDED.vigencia_fin,
            updated_at      = NOW()
        """,
        (empresa_id, cer_cifrado, key_cifrado, pwd_cifrado, rfc_cert, vigencia_fin),
    )

    _log.info("FIEL guardada para empresa_id=%s rfc=%s vigencia=%s", empresa_id, rfc_cert, vigencia_fin)
    return {
        "guardada": True,
        "rfc_certificado": rfc_cert,
        "vigencia_fin": str(vigencia_fin) if vigencia_fin else None,
    }


def obtener_signer(db, empresa_id: str):
    """
    Carga y descifra la FIEL guardada para la empresa y devuelve un Signer listo.

    Raises:
        ValueError: Si no hay FIEL guardada para la empresa.
        RuntimeError: Si la clave de cifrado no está configurada.
    """
    from .sat_fiel import cargar_fiel, FIELError

    row = db.query_one(
        "SELECT cer_cifrado, key_cifrado, pwd_cifrado FROM empresas_fiel WHERE empresa_id = %s",
        (empresa_id,),
    )
    if not row:
        raise ValueError("No hay FIEL guardada para esta empresa")

    cer_bytes = _descifrar(row["cer_cifrado"])
    key_bytes = _descifrar(row["key_cifrado"])
    password  = _descifrar(row["pwd_cifrado"]).decode()

    try:
        return cargar_fiel(cer_bytes, key_bytes, password)
    except FIELError as exc:
        raise ValueError(f"Error al cargar FIEL guardada: {exc}") from exc


def estado_fiel(db, empresa_id: str) -> dict | None:
    """
    Devuelve metadatos de la FIEL guardada (sin exponer credenciales).
    Retorna None si no hay FIEL guardada.
    """
    row = db.query_one(
        "SELECT rfc_certificado, vigencia_fin, updated_at FROM empresas_fiel WHERE empresa_id = %s",
        (empresa_id,),
    )
    if not row:
        return None

    from datetime import date
    hoy = date.today()
    vigencia = row["vigencia_fin"]
    dias_restantes = (vigencia - hoy).days if vigencia else None

    return {
        "tiene_fiel":       True,
        "rfc_certificado":  row["rfc_certificado"],
        "vigencia_fin":     str(vigencia) if vigencia else None,
        "dias_restantes":   dias_restantes,
        "vencida":          (dias_restantes is not None and dias_restantes < 0),
        "por_vencer":       (dias_restantes is not None and 0 <= dias_restantes <= 30),
        "guardada_el":      str(row["updated_at"]) if row["updated_at"] else None,
    }


def eliminar_fiel(db, empresa_id: str) -> bool:
    """Elimina la FIEL guardada. Retorna True si existía."""
    row = db.query_one(
        "SELECT id FROM empresas_fiel WHERE empresa_id = %s", (empresa_id,)
    )
    if not row:
        return False
    db.execute("DELETE FROM empresas_fiel WHERE empresa_id = %s", (empresa_id,))
    _log.info("FIEL eliminada para empresa_id=%s", empresa_id)
    return True
