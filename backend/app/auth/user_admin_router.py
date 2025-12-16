from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from passlib.hash import bcrypt
from sqlmodel import Session, select

from app.audit.service import log_audit
from app.auth.user_model import User
from app.db import get_session
from app.dependencies import (
    AuditRequestContext,
    get_request_audit_context,
    require_permission,
)
from app.permissions.models import PermissionCode
from app.permissions.service import (
    count_users_with_all_permissions,
    list_permission_codes,
    user_has_all_permissions,
)

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/", dependencies=[Depends(require_permission(PermissionCode.USERS_MANAGE))])
def list_users(session: Session = Depends(get_session)):
    users = session.exec(select(User)).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "must_change_password": u.must_change_password,
        }
        for u in users
    ]


@router.post("/")
def create_user(
    payload: dict,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission(PermissionCode.USERS_MANAGE)),
    audit_ctx: AuditRequestContext = Depends(get_request_audit_context),
):
    username = (payload.get("username") or "").strip()
    password = payload.get("password")

    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="username y password requeridos",
        )

    existing = session.exec(select(User).where(User.username == username)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="username ya existe",
        )

    new_user = User(
        username=username,
        hashed_password=bcrypt.hash(password),
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
        meta={"username": username},
        ip=audit_ctx.ip,
        ua=audit_ctx.user_agent,
        corr=audit_ctx.correlation_id,
    )
    session.commit()
    session.refresh(new_user)

    return {
        "id": new_user.id,
        "username": new_user.username,
        "must_change_password": new_user.must_change_password,
    }


@router.post("/{user_id}/reset-password")
def reset_password(
    user_id: int,
    payload: dict,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission(PermissionCode.USERS_MANAGE)),
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
    current_user: User = Depends(require_permission(PermissionCode.USERS_MANAGE)),
    audit_ctx: AuditRequestContext = Depends(get_request_audit_context),
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="usuario no encontrado",
        )

    target_username = user.username

    catalog_codes = list_permission_codes(session)
    if catalog_codes and user_has_all_permissions(user, session, catalog_codes):
        full_count = count_users_with_all_permissions(session, catalog_codes)
        if full_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No puedes eliminar al último usuario con todos los permisos.",
            )

    session.delete(user)
    log_audit(
        session,
        actor=current_user,
        action="users.delete",
        target_type="user",
        target_id=str(user_id),
        meta={"username": target_username},
        ip=audit_ctx.ip,
        ua=audit_ctx.user_agent,
        corr=audit_ctx.correlation_id,
    )
    session.commit()

    return {"ok": True}
