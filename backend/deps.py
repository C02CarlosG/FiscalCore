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

from . import db

_JWT_INSECURE_DEFAULT = "fiscalcore-dev-secret-change-in-prod"
JWT_SECRET    = os.environ.get("JWT_SECRET", _JWT_INSECURE_DEFAULT)
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
