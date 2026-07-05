"""SQLAlchemy engine and session helpers."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from sqlalchemy.engine import make_url
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL_ENV = "NUTAG_DATABASE_URL"
LEGACY_SQLITE_PATH = Path("nutag.sqlite3")


def default_sqlite_path() -> Path:
    """Return the default persistent SQLite path outside the project directory."""

    if os.name == "nt":
        base_dir = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base_dir = Path.home() / "Library" / "Application Support"
    else:
        base_dir = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))

    return base_dir / "Nutag" / "nutag.sqlite3"


def sqlite_url(path: str | Path | None = None) -> str:
    """Build a SQLite database URL for a local file path."""

    return f"sqlite:///{Path(path or default_sqlite_path())}"


def database_url(url: str | None = None) -> str:
    """Return the configured database URL."""

    return url or os.environ.get(DATABASE_URL_ENV) or sqlite_url()


def _prepare_sqlite_file_database(url: str, *, copy_legacy: bool) -> None:
    parsed_url = make_url(url)
    if not parsed_url.drivername.startswith("sqlite"):
        return
    if not parsed_url.database or parsed_url.database == ":memory:":
        return

    database_path = Path(parsed_url.database)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    if not copy_legacy:
        return

    legacy_path = LEGACY_SQLITE_PATH
    if database_path.exists() or not legacy_path.exists():
        return

    if legacy_path.resolve() == database_path.resolve():
        return

    shutil.copy2(legacy_path, database_path)


def create_engine_for_url(url: str | None = None, *, echo: bool = False) -> Engine:
    """Create a SQLAlchemy engine.

    Args:
        url: Database URL. Defaults to ``NUTAG_DATABASE_URL`` or the user data SQLite path.
        echo: Whether SQLAlchemy should log generated SQL.
    """

    copy_legacy = url is None and DATABASE_URL_ENV not in os.environ
    resolved_url = database_url(url)
    _prepare_sqlite_file_database(resolved_url, copy_legacy=copy_legacy)
    return create_engine(resolved_url, echo=echo, future=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a configured SQLAlchemy session factory."""

    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
