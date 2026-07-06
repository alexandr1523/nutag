"""Runtime database helpers for the Streamlit application."""

from __future__ import annotations

import os
from functools import lru_cache

from sqlalchemy import Engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from nutag.db.init_db import initialize_database
from nutag.db.session import DATABASE_URL_ENV, create_engine_for_url, create_session_factory, database_url


def create_initialized_engine(url: str | None = None, *, echo: bool = False) -> Engine:
    """Create an engine and ensure the application schema is ready."""

    engine = create_engine_for_url(url, echo=echo)
    initialize_database(engine)
    return engine


def _is_in_memory_database(url: str) -> bool:
    parsed_url = make_url(url)
    return not parsed_url.database or parsed_url.database == ":memory:"


@lru_cache(maxsize=8)
def _create_persistent_app_database(
    resolved_url: str,
    echo: bool,
    use_default_url: bool,
) -> tuple[Engine, sessionmaker[Session]]:
    """Create and cache DB runtime objects for persistent Streamlit processes."""

    engine = create_initialized_engine(None if use_default_url else resolved_url, echo=echo)
    return engine, create_session_factory(engine)


def create_app_database(url: str | None = None, *, echo: bool = False) -> tuple[Engine, sessionmaker[Session]]:
    """Create the initialized application engine and session factory."""

    resolved_url = database_url(url)
    if _is_in_memory_database(resolved_url):
        engine = create_initialized_engine(url, echo=echo)
        return engine, create_session_factory(engine)

    use_default_url = url is None and DATABASE_URL_ENV not in os.environ
    return _create_persistent_app_database(resolved_url, echo, use_default_url)
