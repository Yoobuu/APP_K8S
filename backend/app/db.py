from __future__ import annotations

from pathlib import Path
from typing import Iterator, Optional

from sqlalchemy.engine import Engine
from sqlmodel import SQLModel, Session, create_engine

# Resolve database path relative to this module so the app doesn't depend on the working directory.
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = (BASE_DIR / "app.db").resolve()
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"

_engine: Engine | None = None


def get_engine() -> Engine:
    """Return the application engine, creating it if necessary."""
    global _engine
    if _engine is None:
        _engine = create_engine(SQLALCHEMY_DATABASE_URL, echo=False)
    return _engine


def set_engine(engine: Engine | None) -> None:
    """Override the application engine (useful for testing)."""
    global _engine
    _engine = engine


def init_db(*, bind: Optional[Engine] = None) -> None:
    """Create database tables on startup so a fresh environment boots cleanly."""
    engine = bind or get_engine()
    SQLModel.metadata.create_all(bind=engine)


def get_session() -> Iterator[Session]:
    """Provide a SQLModel session for dependency injection."""
    engine = get_engine()
    with Session(engine) as session:
        yield session
