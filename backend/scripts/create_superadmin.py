"""Utility script to create a superadmin user manually."""

from __future__ import annotations

import os
import sys
import getpass

from passlib.hash import bcrypt
from sqlmodel import Session, select

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.dirname(CURRENT_DIR)
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.auth.user_model import User, UserRole
from app.db import engine


def prompt_credentials() -> tuple[str, str]:
    """Prompt for username and password via stdin."""
    username = input("Username: ").strip()
    if not username:
        print("Se requiere un nombre de usuario válido.", file=sys.stderr)
        sys.exit(1)

    password = getpass.getpass("Password: ").strip()
    if not password:
        print("Se requiere una contraseña válida.", file=sys.stderr)
        sys.exit(1)

    return username, password


def main() -> None:
    username, password = prompt_credentials()

    with Session(engine) as session:
        existing = session.exec(
            select(User).where(User.username == username)
        ).first()

        if existing:
            print("Usuario ya existe, no se creó otro superadmin")
            return

        hashed_pwd = bcrypt.hash(password)

        user = User(
            username=username,
            hashed_password=hashed_pwd,
            role=UserRole.SUPERADMIN,
        )
        user.mark_password_changed()
        session.add(user)
        session.commit()

        print(f"Superadmin creado: {username}")


if __name__ == "__main__":
    main()
