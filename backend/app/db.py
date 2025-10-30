from pathlib import Path
from typing import Iterator, Optional

from sqlmodel import SQLModel, Session, create_engine

# Resolve database path relative to this module so the app doesn't depend on the working directory.
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = (BASE_DIR / "app.db").resolve()
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"

engine = create_engine(SQLALCHEMY_DATABASE_URL, echo=False)


def init_db(*, bind: Optional[str] = None) -> None:
    """Create database tables on startup so a fresh environment boots cleanly."""
    SQLModel.metadata.create_all(bind=bind or engine)


def get_session() -> Iterator[Session]:
    """Provide a SQLModel session for dependency injection."""
    with Session(engine) as session:
        yield session
