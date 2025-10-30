import logging

from fastapi import APIRouter, Depends, HTTPException, status
from passlib.hash import bcrypt
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.jwt_handler import create_access_token
from app.auth.user_model import User, UserRole
from app.db import get_session
from app.dependencies import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


class LoginRequest(BaseModel):
    """Payload con credenciales de acceso."""

    username: str
    password: str


class TokenUser(BaseModel):
    """Información simplificada del usuario autenticado."""

    id: int
    username: str
    role: UserRole


class TokenResponse(BaseModel):
    """Respuesta del endpoint de login con token y datos básicos del usuario."""

    access_token: str
    token_type: str = "bearer"
    user: TokenUser


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, session: Session = Depends(get_session)):
    """
    1. Busca al usuario por username.
    2. Verifica contraseña usando bcrypt.
    3. Emite un JWT con id, role y username en el payload.
    """
    statement = select(User).where(User.username == request.username)
    user = session.exec(statement).first()

    logger.info("Login attempt for user '%s'", request.username)

    if not user or not bcrypt.verify(request.password, user.hashed_password):
        logger.warning("Login failed for user '%s'", request.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
        )

    logger.info("Login succeeded for user '%s'", request.username)

    token_payload = {
        "sub": str(user.id),
        "role": user.role.value if isinstance(user.role, UserRole) else str(user.role),
        "username": user.username,
    }
    token = create_access_token(token_payload)

    return TokenResponse(
        access_token=token,
        user=TokenUser(id=user.id, username=user.username, role=user.role),
    )


@router.get("/me")
def read_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "role": current_user.role,
    }
