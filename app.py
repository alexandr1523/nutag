"""Streamlit entry point for the Nutag MVP."""

from __future__ import annotations

import logging
import streamlit as st
from alembic.config import Config
from alembic import command
from nutag.db.session import create_engine_for_url, create_session_factory
from nutag.db.init_db import create_database
from nutag.services.validation import get_control_signals

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("nutag.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("nutag.app")

def run_migrations():
    """Apply alembic migrations programmatically."""
    try:
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations applied successfully")
    except Exception as e:
        logger.error(f"Failed to apply migrations: {e}")
        raise

# Page configuration
st.set_page_config(page_title="Nutag", page_icon="🥟", layout="wide")

try:
    # Database initialization
    engine = create_engine_for_url()
    # Still run create_database to ensure initial tables for a fresh install
    # Alembic will handle subsequent updates
    create_database(engine)
    run_migrations()
    
    SessionLocal = create_session_factory(engine)

    st.title("Nutag")
    st.subheader("MVP учёта домашнего производства полуфабрикатов")

    # Control Signals Section
    with SessionLocal() as db:
        signals = get_control_signals(db)
        if signals:
            st.warning(f"⚠️ Обнаружено сигналов: {len(signals)}")
            with st.expander("Показать детали ошибок и предупреждений"):
                for s in signals:
                    if s.level == "error":
                        st.error(f"**[{s.category}]** {s.message}")
                    else:
                        st.warning(f"**[{s.category}]** {s.message}")
        else:
            st.success("✅ Системных проблем не обнаружено. Все данные корректны.")

    st.divider()

except Exception as e:
    logger.exception("Application failed to start or encountered a fatal error")
    st.error(f"Произошла критическая ошибка: {e}")
    st.info("Подробности записаны в файл nutag.log")
    st.stop()

st.markdown(
    """
    Добро пожаловать в систему Nutag!

    Этот инструмент поможет вам вести точный учёт ингредиентов, заготовок и готовой продукции,
    а также видеть реальную экономику вашего домашнего производства.

    ### С чего начать?
    1. Перейдите в раздел **Справочники**, чтобы завести основные единицы измерения и ингредиенты.
    2. Зафиксируйте первую **Закупку**, чтобы появились остатки на складе.
    3. Создайте **Заготовку** или **Производственную партию**.
    """
)

st.sidebar.success("Выберите раздел выше, чтобы начать.")
