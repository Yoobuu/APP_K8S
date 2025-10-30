"""Helpers for creating and decoding JWT access tokens."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict

from jose import ExpiredSignatureError, JWTError, jwt

from app.config import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, SECRET_KEY


def create_access_token(
    data: Dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """
    Genera un token JWT a partir del payload recibido añadiendo la expiración
    configurada por defecto (ACCESS_TOKEN_EXPIRE_MINUTES) o el delta
    personalizado proporcionado.
    """
    to_encode = data.copy()
    expire_delta = expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = datetime.utcnow() + expire_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decodifica y valida un JWT.
    - Re-lanza ExpiredSignatureError si el token expiró.
    - Re-lanza JWTError si la firma es inválida.
    - Verifica que el payload incluya las claves 'sub', 'role' y 'username'.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except ExpiredSignatureError:
        raise
    except JWTError:
        raise

    for claim in ("sub", "role", "username"):
        if claim not in payload:
            raise JWTError(f"Missing claim '{claim}'")

    return payload
