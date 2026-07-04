"""Database initialization utilities."""

from __future__ import annotations

from pathlib import Path
from threading import Lock

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import OperationalError

from nutag.db.base import Base

# Import models so SQLAlchemy registers them in Base.metadata.
from nutag.db import models as _models  # noqa: F401

_INIT_LOCK = Lock()


def create_database(engine: Engine) -> None:
    """Create all known database tables."""

    try:
        Base.metadata.create_all(bind=engine)
    except OperationalError as exc:
        if "already exists" not in str(exc).lower():
            raise
        # Another Streamlit run can create the same table between SQLAlchemy's
        # existence check and CREATE TABLE. Re-run the idempotent pass.
        Base.metadata.create_all(bind=engine)


def _add_column_if_missing(engine: Engine, table_name: str, column_name: str, column_definition: str) -> None:
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns(table_name)}
    if column_name in columns:
        return

    with engine.begin() as connection:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"))


def ensure_schema_compatibility(engine: Engine) -> None:
    """Fill schema gaps left by pre-Alembic or partially migrated SQLite DBs."""

    _add_column_if_missing(engine, "equipment", "hourly_cost", "NUMERIC(12, 2) NOT NULL DEFAULT '0'")
    _add_column_if_missing(engine, "preparations", "preparation_type_id", "INTEGER REFERENCES preparation_types(id)")
    _add_column_if_missing(engine, "preparations", "waste_quantity", "NUMERIC(12, 3) NOT NULL DEFAULT '0'")
    _add_column_if_missing(engine, "production_batches", "planned_quantity", "NUMERIC(12, 3)")
    _add_column_if_missing(engine, "production_batches", "waste_quantity", "NUMERIC(12, 3) NOT NULL DEFAULT '0'")
    _add_column_if_missing(
        engine,
        "production_batches",
        "equipment_depreciation",
        "NUMERIC(12, 2) NOT NULL DEFAULT '0'",
    )
    _add_column_if_missing(engine, "batch_ingredient_uses", "purchase_item_id", "INTEGER REFERENCES purchase_items(id)")
    _add_column_if_missing(engine, "batch_packaging_uses", "purchase_item_id", "INTEGER REFERENCES purchase_items(id)")
    _add_column_if_missing(engine, "batch_preparation_uses", "source_preparation_id", "INTEGER REFERENCES preparations(id)")
    _add_column_if_missing(engine, "preparation_ingredient_uses", "purchase_item_id", "INTEGER REFERENCES purchase_items(id)")
    _add_column_if_missing(
        engine,
        "preparation_ingredient_uses",
        "waste_quantity",
        "NUMERIC(12, 3) NOT NULL DEFAULT '0'",
    )
    _add_column_if_missing(engine, "purchase_items", "consumable_id", "INTEGER REFERENCES consumables(id)")


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

    with _INIT_LOCK:
        if engine.url.database == ":memory:":
            create_database(engine)
            ensure_schema_compatibility(engine)
            return

        inspector = inspect(engine)
        has_alembic_version = inspector.has_table("alembic_version")

        if has_alembic_version:
            run_migrations(engine)
        else:
            # Existing local MVP databases were created before Alembic stamping.
            # Bring their shape up to date idempotently, then mark the schema.
            create_database(engine)
            ensure_schema_compatibility(engine)
            stamp_database(engine)
            return

        create_database(engine)
        ensure_schema_compatibility(engine)
        return
