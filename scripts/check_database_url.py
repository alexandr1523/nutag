"""Smoke-check configured database URL and schema initialization."""

from __future__ import annotations

from sqlalchemy import inspect, text

from nutag.db.runtime import create_app_database
from nutag.db.session import database_url


ADMIN_LIKE_USER_TOKENS = ("owner", "admin", "postgres", "root")


def is_admin_like_database_user(username: str | None) -> bool:
    """Return whether a database username looks too privileged for app runtime."""

    if not username:
        return False
    normalized = username.lower()
    return any(token in normalized for token in ADMIN_LIKE_USER_TOKENS)


def main() -> int:
    url = database_url()
    engine, session_factory = create_app_database(url)

    with session_factory() as session:
        session.execute(text("SELECT 1")).scalar_one()
        if engine.dialect.name == "postgresql":
            current_user, current_database = session.execute(
                text("SELECT current_user, current_database()")
            ).one()
        else:
            current_user, current_database = None, None

    table_names = inspect(engine).get_table_names()
    safe_url = engine.url.render_as_string(hide_password=True)
    print(f"Database URL: {safe_url}")
    print(f"Dialect: {engine.dialect.name}")
    if current_user:
        print(f"Current user: {current_user}")
        print(f"Current database: {current_database}")
        if is_admin_like_database_user(current_user):
            print("Warning: current database user looks like an owner/admin account.")
    else:
        print("Mode: local/dev SQLite fallback")
    print(f"Tables: {len(table_names)}")
    print(f"Alembic version table: {'yes' if 'alembic_version' in table_names else 'no'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
