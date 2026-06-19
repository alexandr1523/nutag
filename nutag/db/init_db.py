"""Database initialization utilities."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect

from nutag.db.base import Base

# Import models so SQLAlchemy registers them in Base.metadata.
from nutag.db import models as _models  # noqa: F401


def create_database(engine: Engine) -> None:
    """Create all known database tables."""

    Base.metadata.create_all(bind=engine)


def run_migrations(engine: Engine) -> None:
    """Apply Alembic migrations for persistent databases."""

    if not engine.url.database or engine.url.database == ":memory:":
        return

    alembic_cfg = Config(str(Path("alembic.ini")))
    alembic_cfg.set_main_option("sqlalchemy.url", str(engine.url))
    command.upgrade(alembic_cfg, "head")


def stamp_database(engine: Engine) -> None:
    """Mark a freshly created database as up to date in Alembic."""

    if not engine.url.database or engine.url.database == ":memory:":
        return

    alembic_cfg = Config(str(Path("alembic.ini")))
    alembic_cfg.set_main_option("sqlalchemy.url", str(engine.url))
    command.stamp(alembic_cfg, "head")


def initialize_database(engine: Engine) -> None:
    """Create base tables and upgrade the schema to the latest version."""

    if engine.url.database == ":memory:":
        create_database(engine)
        return

    inspector = inspect(engine)
    if inspector.has_table("alembic_version"):
        run_migrations(engine)
        create_database(engine)
        return

    create_database(engine)
    stamp_database(engine)
