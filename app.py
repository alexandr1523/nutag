"""Streamlit entry point for the Nutag MVP."""

from __future__ import annotations

import streamlit as st


st.set_page_config(page_title="Nutag", page_icon="🥟", layout="wide")

st.title("Nutag")
st.subheader("MVP учёта домашнего производства полуфабрикатов")

st.markdown(
    """
    Первая версия будет собираться вокруг сквозного сценария:
    закупка → заготовка → партия → заказ → экономика.

    Сейчас добавлен каркас проекта и первые функции расчётного ядра.
    """
)

st.info("Следующий шаг: подключить SQLite/SQLAlchemy и первые формы ввода.")
