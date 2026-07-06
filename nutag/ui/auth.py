"""Minimal one-user access protection for Streamlit pages."""

from __future__ import annotations

import hmac
import os

import streamlit as st
from sqlalchemy.exc import ArgumentError
from sqlalchemy.engine import make_url

from nutag.db.session import DATABASE_URL_ENV, database_url

APP_PASSWORD_ENV = "NUTAG_APP_PASSWORD"
AUTH_SESSION_KEY = "nutag_authenticated"
STREAMLIT_SECRET_ENV_NAMES = (DATABASE_URL_ENV, APP_PASSWORD_ENV)


def is_postgresql_url(url: str) -> bool:
    """Return whether a database URL points to PostgreSQL."""

    try:
        return make_url(url).drivername.startswith("postgresql")
    except ArgumentError:
        return False


def is_sqlite_url(url: str) -> bool:
    """Return whether a database URL points to SQLite."""

    try:
        return make_url(url).drivername.startswith("sqlite")
    except ArgumentError:
        return False


def database_url_is_valid(url: str) -> bool:
    """Return whether a database URL can be parsed by SQLAlchemy."""

    try:
        make_url(url)
    except ArgumentError:
        return False
    return True


def app_password_configured(password: str | None) -> bool:
    """Return whether an app password is configured."""

    return bool(password and password.strip())


def _secret_value(name: str) -> str | None:
    try:
        value = st.secrets.get(name)
    except Exception:
        return None
    return str(value) if value else None


def load_streamlit_secrets_into_environment(names: tuple[str, ...] = STREAMLIT_SECRET_ENV_NAMES) -> None:
    """Expose configured Streamlit secrets through ``os.environ`` for shared DB code."""

    for name in names:
        if os.environ.get(name):
            continue
        value = _secret_value(name)
        if value:
            os.environ[name] = value


def configured_app_password() -> str | None:
    """Read the app password from environment or Streamlit secrets."""

    return os.environ.get(APP_PASSWORD_ENV) or _secret_value(APP_PASSWORD_ENV)


def require_app_access() -> None:
    """Stop the page unless the current Streamlit session is authenticated."""

    load_streamlit_secrets_into_environment()
    password = configured_app_password()
    current_database_url = database_url()

    if not database_url_is_valid(current_database_url):
        st.error(f"`{DATABASE_URL_ENV}` задан неверно. Проверьте строку подключения к БД.")
        st.stop()

    if app_password_configured(password) and DATABASE_URL_ENV not in os.environ and is_sqlite_url(current_database_url):
        st.error(
            f"`{APP_PASSWORD_ENV}` задан, но `{DATABASE_URL_ENV}` не найден. "
            "Для онлайн-режима нужно явно указать внешнюю PostgreSQL-БД в переменных окружения "
            "или Streamlit secrets."
        )
        st.stop()

    if not app_password_configured(password):
        if is_postgresql_url(current_database_url):
            st.error(
                f"Для PostgreSQL-режима нужно задать `{APP_PASSWORD_ENV}` "
                "в переменных окружения или Streamlit secrets."
            )
            st.stop()
        return

    if st.session_state.get(AUTH_SESSION_KEY):
        if st.sidebar.button("Выйти из Nutag", key="nutag_auth_logout"):
            st.session_state[AUTH_SESSION_KEY] = False
            st.rerun()
        return

    st.title("Nutag")
    st.subheader("Доступ к приложению")
    st.info("Введите пароль доступа.")

    with st.form("nutag_access_form"):
        entered_password = st.text_input("Пароль", type="password")
        submitted = st.form_submit_button("Войти")

    if submitted:
        if hmac.compare_digest(entered_password, password or ""):
            st.session_state[AUTH_SESSION_KEY] = True
            st.rerun()
        st.error("Неверный пароль доступа.")

    st.stop()
