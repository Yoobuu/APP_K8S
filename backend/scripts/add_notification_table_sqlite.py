import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.dirname(CURRENT_DIR)
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from sqlmodel import SQLModel

from app.db import get_engine
from app.notifications.models import Notification  # noqa: F401


def main() -> None:
    engine = get_engine()
    SQLModel.metadata.create_all(engine, tables=[Notification.__table__])
    print("Notification table created or already exists.")


if __name__ == "__main__":
    main()
