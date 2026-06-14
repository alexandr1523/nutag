"""Streamlit entry point for the Nutag MVP."""

from __future__ import annotations

import streamlit as st
from nutag.db.session import create_engine_for_url
from nutag.db.init_db import create_database


# Page configuration
st.set_page_config(page_title="Nutag", page_icon="🥟", layout="wide")

# Database initialization
engine = create_engine_for_url()
create_database(engine)

st.title("Nutag")
st.subheader("MVP учёта домашнего производства полуфабрикатов")

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
