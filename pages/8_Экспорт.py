"""Streamlit page for exporting data to Excel."""

import streamlit as st
from nutag.db.runtime import create_app_database
from nutag.services.exports import (
    export_inventory_to_excel,
    export_orders_to_excel,
    export_production_to_excel
)

st.set_page_config(page_title="Экспорт | Nutag", page_icon="📥", layout="wide")

st.title("📥 Экспорт данных")

engine, SessionLocal = create_app_database()

st.info("Здесь вы можете скачать текущие данные в формате Excel (.xlsx)")

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("Склад")
    st.write("Текущие остатки, закупки и использование ингредиентов.")
    with SessionLocal() as db:
        try:
            excel_data = export_inventory_to_excel(db)
            st.download_button(
                label="📥 Скачать Остатки",
                data=excel_data,
                file_name="nutag_inventory.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except Exception as e:
            st.error(f"Ошибка: {e}")

with col2:
    st.subheader("Заказы")
    st.write("История всех клиентских заказов с их статусами и суммами.")
    with SessionLocal() as db:
        try:
            excel_data = export_orders_to_excel(db)
            st.download_button(
                label="📥 Скачать Заказы",
                data=excel_data,
                file_name="nutag_orders.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except Exception as e:
            st.error(f"Ошибка: {e}")

with col3:
    st.subheader("Производство")
    st.write("История всех производственных партий и их себестоимость.")
    with SessionLocal() as db:
        try:
            excel_data = export_production_to_excel(db)
            st.download_button(
                label="📥 Скачать Производство",
                data=excel_data,
                file_name="nutag_production.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except Exception as e:
            st.error(f"Ошибка: {e}")
