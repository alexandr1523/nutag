from nutag.ui.auth import app_password_configured, database_url_is_valid, is_postgresql_url


def test_is_postgresql_url_detects_supported_postgresql_drivers() -> None:
    assert is_postgresql_url("postgresql://user:pass@localhost/db")
    assert is_postgresql_url("postgresql+psycopg://user:pass@localhost/db")


def test_is_postgresql_url_rejects_sqlite() -> None:
    assert not is_postgresql_url("sqlite:///nutag.sqlite3")


def test_database_url_validation_rejects_malformed_url() -> None:
    assert database_url_is_valid("postgresql+psycopg://user:pass@localhost/db")
    assert not database_url_is_valid("твоя PostgreSQL строка")
    assert not is_postgresql_url("твоя PostgreSQL строка")


def test_app_password_configured_requires_non_blank_secret() -> None:
    assert app_password_configured("secret")
    assert not app_password_configured("")
    assert not app_password_configured("   ")
    assert not app_password_configured(None)
