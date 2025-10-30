"""Backfill script to initialise must_change_password for all users."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

from sqlmodel import Session, select

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.dirname(CURRENT_DIR)
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.auth.user_model import User  # noqa: E402
from app.db import engine  # noqa: E402


def main() -> None:
    with Session(engine) as session:
        users = session.exec(select(User)).all()
        if not users:
            print("No hay usuarios que actualizar.")
            return

        updated = 0
        for user in users:
            changed = False
            if user.must_change_password is None or user.must_change_password:
                user.must_change_password = False
                changed = True
            if user.password_last_set_at is None:
                user.password_last_set_at = datetime.now(timezone.utc)
                changed = True
            if changed:
                session.add(user)
                updated += 1

        if updated:
            session.commit()
        print(f"Usuarios actualizados: {updated}")


if __name__ == "__main__":
    main()
