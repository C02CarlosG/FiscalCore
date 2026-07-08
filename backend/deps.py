# backend/deps.py
from __future__ import annotations

import os
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_log = logging.getLogger(__name__)

try:
    from jose import JWTError, jwt
    JWT_OK = True
except ImportError:
    JWT_OK = False
    _log.warning("python-jose no instalado")

try:
    import bcrypt as _bcrypt
    BCRYPT_OK = True
except ImportError:
    BCRYPT_OK = False
    _log.warning("bcrypt no instalado")

try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    limiter = Limiter(key_func=get_remote_address)
except ImportError:
    limiter = None
    _log.warning("slowapi no instalado — rate limiting deshabilitado")

from . import db

# Mismo criterio que FIEL_ENCRYPTION_KEY en fiel_store.py: no hay default
# inseguro. Si la variable de entorno no está configurada, el proceso falla
# explícito al arrancar en lugar de levantar en modo inseguro silencioso.
# En desarrollo local, .env (cargado por main_api.py) debe proveer el valor.
_JWT_SECRET_ENV = os.environ.get("JWT_SECRET", "").strip()
if not _JWT_SECRET_ENV:
    raise RuntimeError(
        "Variable de entorno JWT_SECRET no configurada. "
        "Genera una con: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
    )
JWT_SECRET    = _JWT_SECRET_ENV
JWT_ALGORITHM = "HS256"
JWT_EXP_HOURS = 8

_bearer = HTTPBearer(auto_error=False)


def crear_token(payload: dict) -> str:
    if not JWT_OK:
        raise HTTPException(status_code=500, detail="python-jose no instalado")
    data = payload.copy()
    data["exp"] = datetime.utcnow() + timedelta(hours=JWT_EXP_HOURS)
    return jwt.encode(data, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verificar_token(token: str) -> dict:
    if not JWT_OK:
        raise HTTPException(status_code=500, detail="python-jose no instalado")
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")


def get_current_user(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict:
    if not creds:
        raise HTTPException(status_code=401, detail="Se requiere autenticación")
    return verificar_token(creds.credentials)


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Verifica que el usuario actual tenga rol 'admin'."""
    usuario = db.query_one("SELECT rol FROM usuarios WHERE id = %s", (current_user["user_id"],))
    if not usuario or usuario.get("rol") != "admin":
        raise HTTPException(status_code=403, detail="Se requiere rol de administrador")
    return current_user


def hash_password(plain: str) -> str:
    if not BCRYPT_OK:
        raise HTTPException(status_code=500, detail="bcrypt no instalado")
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    if not BCRYPT_OK:
        return False
    return _bcrypt.checkpw(plain.encode(), hashed.encode())


def empresa_or_404(empresa_id: str) -> dict:
    row = db.query_one("SELECT * FROM empresas WHERE id = %s", (empresa_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    return row


def validar_acceso_empresa(empresa_id: str, current_user: dict) -> None:
    row = db.query_one(
        "SELECT 1 FROM usuario_empresas WHERE usuario_id = %s AND empresa_id = %s",
        (current_user["user_id"], empresa_id),
    )
    if not row:
        raise HTTPException(status_code=403, detail="Sin acceso a esta empresa")


# ---------------------------------------------------------------------------
# Validación de archivos subidos (CFDI, estados de cuenta, constancia SAT)
# ---------------------------------------------------------------------------

MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10MB por archivo — CFDI/XLSX/PDF individuales no superan esto en la práctica


def validar_upload(
    archivo,
    contenido: bytes,
    extensiones_validas: tuple[str, ...],
    content_types_validos: tuple[str, ...],
    max_bytes: int = MAX_UPLOAD_SIZE_BYTES,
) -> None:
    """Valida extensión, content-type y tamaño de un archivo subido.

    - 400 si la extensión o el content-type declarado no coinciden con lo esperado.
    - 413 si el archivo excede max_bytes.

    El content-type solo se valida si el cliente lo envió (algunos clientes no
    lo setean); la extensión siempre se exige.
    """
    nombre = (archivo.filename or "").lower()
    if not nombre.endswith(extensiones_validas):
        raise HTTPException(
            status_code=400,
            detail=f"Extensión no permitida para '{archivo.filename}'. Se espera: {', '.join(extensiones_validas)}",
        )
    if archivo.content_type and archivo.content_type not in content_types_validos:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de contenido no permitido para '{archivo.filename}': {archivo.content_type}",
        )
    if len(contenido) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"'{archivo.filename}' excede el tamaño máximo permitido ({max_bytes // (1024 * 1024)}MB)",
        )


def serializar(obj: dict) -> dict:
    """Convierte Decimal y datetime a tipos JSON-serializables."""
    result = {}
    for k, v in obj.items():
        if isinstance(v, Decimal):
            result[k] = float(v)
        elif isinstance(v, datetime):
            result[k] = v.isoformat()
        else:
            result[k] = v
    return result
