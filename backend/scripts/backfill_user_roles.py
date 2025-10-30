"""Backfill script to assign the default role to legacy users."""

from __future__ import annotations

import os
import sys

from sqlalchemy import or_
from sqlmodel import Session, select

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.dirname(CURRENT_DIR)
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.auth.user_model import User, UserRole
from app.db import engine


def main() -> None:
    with Session(engine) as session:
        users = session.exec(
            select(User).where(
                or_(User.role == None, User.role == "")  # noqa: E711
            )
        ).all()

        if not users:
            print("No se encontraron usuarios sin role. 0 registros actualizados.")
            return

        for user in users:
            user.role = UserRole.USER

        session.commit()
        print(f"Usuarios actualizados: {len(users)}")


if __name__ == "__main__":
    main()
