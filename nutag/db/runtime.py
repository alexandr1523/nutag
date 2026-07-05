"""Runtime database helpers for the Streamlit application."""

from __future__ import annotations

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from nutag.db.init_db import initialize_database
from nutag.db.session import create_engine_for_url, create_session_factory


def create_initialized_engine(url: str | None = None, *, echo: bool = False) -> Engine:
    """Create an engine and ensure the application schema is ready."""

    engine = create_engine_for_url(url, echo=echo)
    initialize_database(engine)
    return engine


def create_app_database(url: str | None = None, *, echo: bool = False) -> tuple[Engine, sessionmaker[Session]]:
    """Create the initialized application engine and session factory."""

    engine = create_initialized_engine(url, echo=echo)
    return engine, create_session_factory(engine)
