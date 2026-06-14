"""SQLAlchemy engine and session helpers."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

DEFAULT_SQLITE_PATH = Path("nutag.sqlite3")


def sqlite_url(path: str | Path = DEFAULT_SQLITE_PATH) -> str:
    """Build a SQLite database URL for a local file path."""

    return f"sqlite:///{Path(path)}"


def create_engine_for_url(url: str | None = None, *, echo: bool = False) -> Engine:
    """Create a SQLAlchemy engine.

    Args:
        url: Database URL. Defaults to a local ``nutag.sqlite3`` file.
        echo: Whether SQLAlchemy should log generated SQL.
    """

    return create_engine(url or sqlite_url(), echo=echo, future=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a configured SQLAlchemy session factory."""

    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
