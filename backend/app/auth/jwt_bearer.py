"""Backward-compatible HTTPBearer dependency for legacy usage."""

from __future__ import annotations

from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError
from starlette.status import HTTP_403_FORBIDDEN

from app.auth.jwt_handler import decode_access_token


class JWTBearer(HTTPBearer):
    """
    Componente de seguridad que extiende HTTPBearer para:
    1. Extraer el token Bearer de la cabecera Authorization.
    2. Verificar que el token tenga el esquema correcto.
    3. Validar la firma y expiración del JWT.
    """

    def __init__(self, auto_error: bool = True):
        super().__init__(auto_error=auto_error)

    async def __call__(self, request: Request):
        credentials: HTTPAuthorizationCredentials = await super().__call__(request)
        if credentials:
            if credentials.scheme != "Bearer":
                raise HTTPException(
                    status_code=HTTP_403_FORBIDDEN,
                    detail="Formato inválido de autenticación",
                )
            if not self.verify_jwt(credentials.credentials):
                raise HTTPException(
                    status_code=HTTP_403_FORBIDDEN,
                    detail="Token inválido o expirado",
                )
            return credentials.credentials
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="No se proporcionó token",
        )

    def verify_jwt(self, jwt_token: str) -> bool:
        try:
            decode_access_token(jwt_token)
            return True
        except (ExpiredSignatureError, JWTError):
            return False
