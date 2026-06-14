"""Database initialization utilities."""

from __future__ import annotations

from sqlalchemy import Engine

from nutag.db.base import Base

# Import models so SQLAlchemy registers them in Base.metadata.
from nutag.db import models as _models  # noqa: F401


def create_database(engine: Engine) -> None:
    """Create all known database tables."""

    Base.metadata.create_all(bind=engine)
