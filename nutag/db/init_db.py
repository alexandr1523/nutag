"""Database initialization utilities."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from threading import Lock

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
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


def _is_sqlite_file_database(engine: Engine) -> bool:
    return (
        engine.url.drivername.startswith("sqlite")
        and bool(engine.url.database)
        and engine.url.database != ":memory:"
    )


def backup_sqlite_database(engine: Engine, *, reason: str) -> Path | None:
    """Create a timestamped SQLite backup before schema changes."""

    if not _is_sqlite_file_database(engine):
        return None

    database_path = Path(str(engine.url.database))
    if not database_path.exists():
        return None

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = database_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{database_path.stem}.{reason}.{timestamp}{database_path.suffix}"
    shutil.copy2(database_path, backup_path)
    return backup_path


def _alembic_config(engine: Engine) -> Config:
    alembic_cfg = Config(str(Path("alembic.ini")))
    alembic_cfg.set_main_option("sqlalchemy.url", str(engine.url))
    return alembic_cfg


def _migration_head(engine: Engine) -> str | None:
    heads = ScriptDirectory.from_config(_alembic_config(engine)).get_heads()
    return heads[0] if len(heads) == 1 else None


def _current_revision(engine: Engine) -> str | None:
    if not inspect(engine).has_table("alembic_version"):
        return None

    with engine.connect() as connection:
        return connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()


def _has_column(engine: Engine, table_name: str, column_name: str) -> bool:
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return True

    columns = {column["name"] for column in inspector.get_columns(table_name)}
    return column_name in columns


def _add_column_if_missing(engine: Engine, table_name: str, column_name: str, column_definition: str) -> None:
    if _has_column(engine, table_name, column_name):
        return
    with engine.begin() as connection:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"))


def ensure_schema_compatibility(engine: Engine) -> None:
    """Fill schema gaps left by pre-Alembic or partially migrated SQLite DBs."""

    compatibility_columns = [
        ("equipment", "hourly_cost", "NUMERIC(12, 2) NOT NULL DEFAULT '0'"),
        ("preparations", "preparation_type_id", "INTEGER REFERENCES preparation_types(id)"),
        ("preparations", "waste_quantity", "NUMERIC(12, 3) NOT NULL DEFAULT '0'"),
        ("production_batches", "planned_quantity", "NUMERIC(12, 3)"),
        ("production_batches", "waste_quantity", "NUMERIC(12, 3) NOT NULL DEFAULT '0'"),
        ("production_batches", "equipment_depreciation", "NUMERIC(12, 2) NOT NULL DEFAULT '0'"),
        ("batch_ingredient_uses", "purchase_item_id", "INTEGER REFERENCES purchase_items(id)"),
        ("batch_packaging_uses", "purchase_item_id", "INTEGER REFERENCES purchase_items(id)"),
        ("batch_preparation_uses", "source_preparation_id", "INTEGER REFERENCES preparations(id)"),
        ("preparation_ingredient_uses", "purchase_item_id", "INTEGER REFERENCES purchase_items(id)"),
        ("preparation_ingredient_uses", "waste_quantity", "NUMERIC(12, 3) NOT NULL DEFAULT '0'"),
        ("purchase_items", "consumable_id", "INTEGER REFERENCES consumables(id)"),
    ]
    missing_columns = [
        column
        for column in compatibility_columns
        if not _has_column(engine, column[0], column[1])
    ]
    if missing_columns:
        backup_sqlite_database(engine, reason="before-compatibility")

    for table_name, column_name, column_definition in missing_columns:
        _add_column_if_missing(engine, table_name, column_name, column_definition)


def run_migrations(engine: Engine) -> None:
    """Apply Alembic migrations for persistent databases."""

    if not engine.url.database or engine.url.database == ":memory:":
        return

    if _current_revision(engine) != _migration_head(engine):
        backup_sqlite_database(engine, reason="before-migration")
    command.upgrade(_alembic_config(engine), "head")


def stamp_database(engine: Engine) -> None:
    """Mark a freshly created database as up to date in Alembic."""

    if not engine.url.database or engine.url.database == ":memory:":
        return

    command.stamp(_alembic_config(engine), "head")


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
            if inspector.get_table_names():
                backup_sqlite_database(engine, reason="before-initialization")
            create_database(engine)
            ensure_schema_compatibility(engine)
            stamp_database(engine)
            return

        create_database(engine)
        ensure_schema_compatibility(engine)
        return
