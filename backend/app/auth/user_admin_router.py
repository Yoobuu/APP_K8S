from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from passlib.hash import bcrypt
from sqlmodel import Session, select

from app.audit.service import log_audit
from app.auth.user_model import User, UserRole
from app.db import get_session
from app.dependencies import (
    AuditRequestContext,
    get_request_audit_context,
    require_superadmin,
)

router = APIRouter(prefix="/api/users", tags=["users"])


def _coerce_role(value: str) -> UserRole:
    """
    Accept role names case-insensitively and normalize to UserRole.
    """
    if not value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="rol inválido",
        )

    normalized = value.strip().lower()

    valid_map = {
        "user": UserRole.USER,
        "admin": UserRole.ADMIN,
        "superadmin": UserRole.SUPERADMIN,
    }

    if normalized not in valid_map:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="rol inválido",
        )

    return valid_map[normalized]


@router.get("/", dependencies=[Depends(require_superadmin)])
def list_users(session: Session = Depends(get_session)):
    users = session.exec(select(User)).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "role": u.role,
            "must_change_password": u.must_change_password,
        }
        for u in users
    ]


@router.post("/")
def create_user(
    payload: dict,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_superadmin),
    audit_ctx: AuditRequestContext = Depends(get_request_audit_context),
):
    username = (payload.get("username") or "").strip()
    password = payload.get("password")
    role_raw = payload.get("role", "USER")

    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="username y password requeridos",
        )

    role = _coerce_role(role_raw)

    existing = session.exec(select(User).where(User.username == username)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="username ya existe",
        )

    new_user = User(
        username=username,
        hashed_password=bcrypt.hash(password),
        role=role,
    )
    new_user.mark_password_changed()
    session.add(new_user)
    session.flush()
    log_audit(
        session,
        actor=current_user,
        action="users.create",
        target_type="user",
        target_id=str(new_user.id),
        meta={"username": username, "role": role.value},
        ip=audit_ctx.ip,
        ua=audit_ctx.user_agent,
        corr=audit_ctx.correlation_id,
    )
    session.commit()
    session.refresh(new_user)

    return {
        "id": new_user.id,
        "username": new_user.username,
        "role": new_user.role,
        "must_change_password": new_user.must_change_password,
    }


@router.patch("/{user_id}/role")
def update_role(
    user_id: int,
    payload: dict,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_superadmin),
    audit_ctx: AuditRequestContext = Depends(get_request_audit_context),
):
    new_role_raw = payload.get("role")
    if not new_role_raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="rol inválido",
        )

    new_role = _coerce_role(new_role_raw)

    user = session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="usuario no encontrado",
        )

    old_role = user.role.value if isinstance(user.role, UserRole) else str(user.role)
    user.role = new_role
    session.add(user)
    log_audit(
        session,
        actor=current_user,
        action="users.change_role",
        target_type="user",
        target_id=str(user.id),
        meta={"from": old_role, "to": new_role.value},
        ip=audit_ctx.ip,
        ua=audit_ctx.user_agent,
        corr=audit_ctx.correlation_id,
    )
    session.commit()
    session.refresh(user)

    return {"id": user.id, "username": user.username, "role": user.role}


@router.post("/{user_id}/reset-password")
def reset_password(
    user_id: int,
    payload: dict,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_superadmin),
    audit_ctx: AuditRequestContext = Depends(get_request_audit_context),
):
    new_password = payload.get("new_password")
    if not new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="falta new_password",
        )

    user = session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="usuario no encontrado",
        )

    user.hashed_password = bcrypt.hash(new_password)
    user.mark_password_reset()
    session.add(user)
    log_audit(
        session,
        actor=current_user,
        action="users.reset_password",
        target_type="user",
        target_id=str(user.id),
        meta={"mode": "admin_reset"},
        ip=audit_ctx.ip,
        ua=audit_ctx.user_agent,
        corr=audit_ctx.correlation_id,
    )
    session.commit()
    session.refresh(user)

    return {"ok": True, "must_change_password": user.must_change_password}


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_superadmin),
    audit_ctx: AuditRequestContext = Depends(get_request_audit_context),
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="usuario no encontrado",
        )

    if user.role == UserRole.SUPERADMIN:
        superadmins = session.exec(
            select(User).where(User.role == UserRole.SUPERADMIN)
        ).all()
        if len(superadmins) <= 1:
            detail = "no puedes eliminarte si eres el último superadmin"
            if user.id != current_user.id:
                detail = "no se puede eliminar el último superadmin"
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=detail,
            )

    target_username = user.username
    target_role = user.role.value if isinstance(user.role, UserRole) else str(user.role)

    session.delete(user)
    log_audit(
        session,
        actor=current_user,
        action="users.delete",
        target_type="user",
        target_id=str(user_id),
        meta={"username": target_username, "role": target_role},
        ip=audit_ctx.ip,
        ua=audit_ctx.user_agent,
        corr=audit_ctx.correlation_id,
    )
    session.commit()

    return {"ok": True}
