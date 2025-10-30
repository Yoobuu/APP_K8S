from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from passlib.hash import bcrypt
from sqlmodel import Session, select

from app.auth.user_model import User, UserRole
from app.db import get_session
from app.dependencies import require_superadmin

router = APIRouter(prefix="/api/users", tags=["users"])


def _coerce_role(value: str) -> UserRole:
    """
    Acepta role en mayúsculas o minúsculas ("ADMIN", "admin", etc.)
    y lo normaliza al valor real del Enum:
    "user", "admin", "superadmin".
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
        {"id": u.id, "username": u.username, "role": u.role}
        for u in users
    ]


@router.post("/", dependencies=[Depends(require_superadmin)])
def create_user(payload: dict, session: Session = Depends(get_session)):
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
    session.add(new_user)
    session.commit()
    session.refresh(new_user)

    return {"id": new_user.id, "username": new_user.username, "role": new_user.role}


@router.patch("/{user_id}/role", dependencies=[Depends(require_superadmin)])
def update_role(user_id: int, payload: dict, session: Session = Depends(get_session)):
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

    user.role = new_role
    session.add(user)
    session.commit()
    session.refresh(user)

    return {"id": user.id, "username": user.username, "role": user.role}


@router.post("/{user_id}/reset-password", dependencies=[Depends(require_superadmin)])
def reset_password(user_id: int, payload: dict, session: Session = Depends(get_session)):
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
    session.add(user)
    session.commit()

    return {"ok": True}
