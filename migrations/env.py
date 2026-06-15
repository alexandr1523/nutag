import logging
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# 1. Import your models and metadata
from nutag.db.base import Base
from nutag.db import models  # Ensure all models are registered
from nutag.services.calculations import to_decimal  # Not strictly needed but shows we can import from nutag

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 2. Set target_metadata
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    # 3. Dynamic URL from project if not in config
    url = config.get_main_option("sqlalchemy.url")
    if url == "driver://user:pass@localhost/dbname":
        from nutag.db.session import sqlite_url
        url = sqlite_url()
        
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True, # Important for SQLite!
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # 4. Handle dynamic engine creation for SQLite
    configuration = config.get_section(config.config_ini_section, {})
    if configuration.get("sqlalchemy.url") == "driver://user:pass@localhost/dbname":
         from nutag.db.session import sqlite_url
         configuration["sqlalchemy.url"] = sqlite_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata,
            render_as_batch=True, # Important for SQLite!
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
