"""Streamlit page for managing dictionaries (units, ingredients, products, packaging)."""

from __future__ import annotations

import streamlit as st
from sqlalchemy.orm import Session
from nutag.db.models import Unit, Ingredient, Product, Packaging
from nutag.db.session import create_engine_for_url, create_session_factory


st.set_page_config(page_title="Справочники | Nutag", page_icon="📖", layout="wide")

st.title("📖 Справочники")

# Session management
engine = create_engine_for_url()
SessionLocal = create_session_factory(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


tabs = st.tabs(["Единицы измерения", "Ингредиенты", "Продукты", "Упаковка"])

# --- Units Tab ---
with tabs[0]:
    st.header("Единицы измерения")
    
    with st.form("add_unit"):
        st.subheader("Добавить единицу")
        name = st.text_input("Название (например, Килограмм)")
        short_name = st.text_input("Сокращение (например, кг)")
        comment = st.text_area("Комментарий")
        submitted = st.form_submit_button("Добавить")
        
        if submitted:
            if not name or not short_name:
                st.error("Название и сокращение обязательны")
            else:
                with SessionLocal() as db:
                    new_unit = Unit(name=name, short_name=short_name, comment=comment)
                    db.add(new_unit)
                    try:
                        db.commit()
                        st.success(f"Единица '{name}' добавлена")
                    except Exception as e:
                        db.rollback()
                        st.error(f"Ошибка при добавлении: {e}")

    st.subheader("Список единиц")
    with SessionLocal() as db:
        units = db.query(Unit).all()
        if units:
            for u in units:
                st.write(f"**{u.name}** ({u.short_name})")
        else:
            st.info("Справочник пуст")

# --- Ingredients Tab ---
with tabs[1]:
    st.header("Ингредиенты")
    
    with SessionLocal() as db:
        units = db.query(Unit).all()
        unit_options = {u.name: u.id for u in units}
        
        if not unit_options:
            st.warning("Сначала добавьте единицы измерения")
        else:
            with st.form("add_ingredient"):
                st.subheader("Добавить ингредиент")
                name = st.text_input("Название ингредиента")
                unit_name = st.selectbox("Единица измерения", options=list(unit_options.keys()))
                comment = st.text_area("Комментарий")
                submitted = st.form_submit_button("Добавить")
                
                if submitted:
                    if not name:
                        st.error("Название обязательно")
                    else:
                        new_ing = Ingredient(
                            name=name, 
                            unit_id=unit_options[unit_name], 
                            comment=comment
                        )
                        db.add(new_ing)
                        try:
                            db.commit()
                            st.success(f"Ингредиент '{name}' добавлен")
                        except Exception as e:
                            db.rollback()
                            st.error(f"Ошибка при добавлении: {e}")

    st.subheader("Список ингредиентов")
    with SessionLocal() as db:
        ingredients = db.query(Ingredient).all()
        if ingredients:
            for ing in ingredients:
                st.write(f"**{ing.name}** ({ing.unit.short_name})")
        else:
            st.info("Справочник пуст")

# Stubs for other tabs to be implemented later
with tabs[2]:
    st.header("Продукты")
    st.info("Раздел в разработке")

with tabs[3]:
    st.header("Упаковка")
    st.info("Раздел в разработке")
