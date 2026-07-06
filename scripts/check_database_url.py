"""Smoke-check configured database URL and schema initialization."""

from __future__ import annotations

from sqlalchemy import inspect, text

from nutag.db.runtime import create_app_database
from nutag.db.session import database_url


def main() -> int:
    url = database_url()
    engine, session_factory = create_app_database(url)

    with session_factory() as session:
        session.execute(text("SELECT 1")).scalar_one()

    table_names = inspect(engine).get_table_names()
    safe_url = engine.url.render_as_string(hide_password=True)
    print(f"Database URL: {safe_url}")
    print(f"Dialect: {engine.dialect.name}")
    print(f"Tables: {len(table_names)}")
    print(f"Alembic version table: {'yes' if 'alembic_version' in table_names else 'no'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
