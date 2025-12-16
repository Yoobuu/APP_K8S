import logging

from fastapi import APIRouter, Depends, HTTPException, status
from passlib.hash import bcrypt
from pydantic import BaseModel
from sqlmodel import Session, select

from app.audit.service import log_audit
from app.auth.jwt_handler import create_access_token
from app.auth.user_model import User
from app.db import get_session
from app.dependencies import (
    AuditRequestContext,
    get_current_user,
    get_request_audit_context,
)
from app.permissions.service import user_effective_permissions

router = APIRouter()
logger = logging.getLogger(__name__)


class LoginRequest(BaseModel):
    """Payload con credenciales de acceso."""

    username: str
    password: str


class TokenUser(BaseModel):
    """InformaciA3n simplificada del usuario autenticado."""

    id: int
    username: str


class TokenResponse(BaseModel):
    """Respuesta del endpoint de login con token y datos bA�sicos del usuario."""

    access_token: str
    token_type: str = "bearer"
    user: TokenUser
    require_password_change: bool
    permissions: list[str]


class ChangePasswordRequest(BaseModel):
    """Payload para cambio de contraseA�a por el propio usuario."""

    old_password: str
    new_password: str


def _build_token_response(user: User, session: Session) -> TokenResponse:
    permissions = sorted(user_effective_permissions(user, session))
    token_payload = {
        "sub": str(user.id),
        "username": user.username,
        "perms": permissions,
    }
    token = create_access_token(token_payload)
    return TokenResponse(
        access_token=token,
        user=TokenUser(id=user.id, username=user.username),
        require_password_change=user.must_change_password,
        permissions=permissions,
    )


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, session: Session = Depends(get_session)):
    """
    1. Busca al usuario por username.
    2. Verifica contraseA�a usando bcrypt.
    3. Emite un JWT con id, role y username en el payload.
    """
    statement = select(User).where(User.username == request.username)
    user = session.exec(statement).first()

    logger.info("Login attempt for user '%s'", request.username)

    if not user or not bcrypt.verify(request.password, user.hashed_password):
        logger.warning("Login failed for user '%s'", request.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales invA�lidas",
        )

    logger.info("Login succeeded for user '%s'", request.username)

    return _build_token_response(user, session)


@router.get("/me")
def read_me(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "must_change_password": current_user.must_change_password,
        "permissions": sorted(user_effective_permissions(current_user, session)),
    }


@router.post("/change-password", response_model=TokenResponse)
def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    audit_ctx: AuditRequestContext = Depends(get_request_audit_context),
):
    if not request.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="falta new_password",
        )

    user = session.get(User, current_user.id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="usuario no encontrado",
        )

    if not bcrypt.verify(request.old_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="old_password incorrecto",
        )

    user.hashed_password = bcrypt.hash(request.new_password)
    user.mark_password_changed()

    session.add(user)
    log_audit(
        session,
        actor=user,
        action="auth.change_password",
        target_type="user",
        target_id=str(user.id),
        meta={"mode": "self_service"},
        ip=audit_ctx.ip,
        ua=audit_ctx.user_agent,
        corr=audit_ctx.correlation_id,
    )
    session.commit()
    session.refresh(user)

    return _build_token_response(user, session)
