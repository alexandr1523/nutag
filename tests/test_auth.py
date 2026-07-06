import os

from nutag.db.session import DATABASE_URL_ENV
from nutag.ui.auth import (
    APP_PASSWORD_ENV,
    app_password_configured,
    database_url_is_valid,
    is_postgresql_url,
    is_sqlite_url,
    load_streamlit_secrets_into_environment,
)


def test_is_postgresql_url_detects_supported_postgresql_drivers() -> None:
    assert is_postgresql_url("postgresql://user:pass@localhost/db")
    assert is_postgresql_url("postgresql+psycopg://user:pass@localhost/db")


def test_is_postgresql_url_rejects_sqlite() -> None:
    assert not is_postgresql_url("sqlite:///nutag.sqlite3")


def test_is_sqlite_url_detects_sqlite() -> None:
    assert is_sqlite_url("sqlite:///nutag.sqlite3")
    assert not is_sqlite_url("postgresql+psycopg://user:pass@localhost/db")


def test_database_url_validation_rejects_malformed_url() -> None:
    assert database_url_is_valid("postgresql+psycopg://user:pass@localhost/db")
    assert not database_url_is_valid("твоя PostgreSQL строка")
    assert not is_postgresql_url("твоя PostgreSQL строка")


def test_app_password_configured_requires_non_blank_secret() -> None:
    assert app_password_configured("secret")
    assert not app_password_configured("")
    assert not app_password_configured("   ")
    assert not app_password_configured(None)


def test_load_streamlit_secrets_into_environment_sets_missing_values(monkeypatch) -> None:
    monkeypatch.delenv(DATABASE_URL_ENV, raising=False)
    monkeypatch.delenv(APP_PASSWORD_ENV, raising=False)
    monkeypatch.setattr(
        "nutag.ui.auth._secret_value",
        lambda name: {
            DATABASE_URL_ENV: "postgresql+psycopg://user:pass@localhost/db",
            APP_PASSWORD_ENV: "test-password",
        }.get(name),
    )

    load_streamlit_secrets_into_environment()

    assert os.environ[DATABASE_URL_ENV] == "postgresql+psycopg://user:pass@localhost/db"
    assert os.environ[APP_PASSWORD_ENV] == "test-password"


def test_load_streamlit_secrets_into_environment_does_not_override_env(monkeypatch) -> None:
    monkeypatch.setenv(DATABASE_URL_ENV, "sqlite:///local.sqlite3")
    monkeypatch.setattr(
        "nutag.ui.auth._secret_value",
        lambda name: "postgresql+psycopg://user:pass@localhost/db",
    )

    load_streamlit_secrets_into_environment((DATABASE_URL_ENV,))

    assert os.environ[DATABASE_URL_ENV] == "sqlite:///local.sqlite3"
