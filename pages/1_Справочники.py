"""Streamlit page for managing dictionaries."""

from __future__ import annotations

import streamlit as st

from nutag.db.models import (
    Consumable,
    Equipment,
    FixedExpenseCategory,
    Ingredient,
    LaborRate,
    Packaging,
    PreparationType,
    Product,
    Unit,
)
from nutag.db.runtime import create_app_database
from nutag.services.maintenance import reset_operational_data
from nutag.services.references import create_unit
from nutag.ui.auth import require_app_access


st.set_page_config(page_title="Справочники | Nutag", page_icon="📖", layout="wide")
require_app_access()

st.title("📖 Справочники")

# Session management
engine, SessionLocal = create_app_database()


tabs = st.tabs(
    [
        "Единицы измерения",
        "Ингредиенты",
        "Продукты",
        "Виды заготовок",
        "Упаковка",
        "Расходники",
        "Оборудование",
        "Постоянные расходы",
        "Стоимость труда",
        "Обслуживание",
    ]
)

# --- Units Tab ---
with tabs[0]:
    st.header("Единицы измерения")

    with st.form("add_unit"):
        st.subheader("Добавить единицу")
        name = st.text_input("Название")
        short_name = st.text_input("Сокращение")
        comment = st.text_area("Комментарий")
        submitted = st.form_submit_button("Добавить")

        if submitted:
            if not name.strip() or not short_name.strip():
                st.error("Название и сокращение обязательны")
            else:
                with SessionLocal() as db:
                    try:
                        new_unit = create_unit(db, name=name, short_name=short_name, comment=comment)
                        db.commit()
                        st.success(f"Единица '{new_unit.name}' добавлена")
                    except ValueError as e:
                        db.rollback()
                        st.error(str(e))
                    except Exception:
                        db.rollback()
                        st.error(
                            "Не удалось добавить единицу измерения. "
                            "Проверьте, что название и сокращение не дублируются."
                        )

    st.subheader("Список единиц")
    with SessionLocal() as db:
        units = db.query(Unit).all()
        if units:
            for unit in units:
                st.write(f"**{unit.name}** ({unit.short_name})")
        else:
            st.info("Справочник пуст")

# --- Ingredients Tab ---
with tabs[1]:
    st.header("Ингредиенты")

    with SessionLocal() as db:
        units = db.query(Unit).all()
        unit_options = {unit.name: unit.id for unit in units}

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
                        new_ingredient = Ingredient(name=name, unit_id=unit_options[unit_name], comment=comment)
                        db.add(new_ingredient)
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
            for ingredient in ingredients:
                st.write(f"**{ingredient.name}** ({ingredient.unit.short_name})")
        else:
            st.info("Справочник пуст")

# --- Products Tab ---
with tabs[2]:
    st.header("Продукты")

    with st.form("add_product"):
        st.subheader("Добавить продукт")
        name = st.text_input("Название продукта")
        comment = st.text_area("Комментарий", key="prod_comment")
        submitted = st.form_submit_button("Добавить")

        if submitted:
            if not name:
                st.error("Название обязательно")
            else:
                with SessionLocal() as db:
                    new_product = Product(name=name, comment=comment)
                    db.add(new_product)
                    try:
                        db.commit()
                        st.success(f"Продукт '{name}' добавлен")
                    except Exception as e:
                        db.rollback()
                        st.error(f"Ошибка при добавлении: {e}")

    st.subheader("Список продуктов")
    with SessionLocal() as db:
        products = db.query(Product).all()
        if products:
            for product in products:
                st.write(f"**{product.name}**")
        else:
            st.info("Справочник пуст")

# --- Preparation Types Tab ---
with tabs[3]:
    st.header("Виды заготовок")

    with st.form("add_preparation_type"):
        st.subheader("Добавить вид заготовки")
        name = st.text_input("Название вида заготовки")
        comment = st.text_area("Комментарий", key="prep_type_comment")
        submitted = st.form_submit_button("Добавить")

        if submitted:
            if not name:
                st.error("Название обязательно")
            else:
                with SessionLocal() as db:
                    new_preparation_type = PreparationType(name=name, comment=comment)
                    db.add(new_preparation_type)
                    try:
                        db.commit()
                        st.success(f"Вид заготовки '{name}' добавлен")
                    except Exception as e:
                        db.rollback()
                        st.error(f"Ошибка при добавлении: {e}")

    st.subheader("Список видов заготовок")
    with SessionLocal() as db:
        preparation_types = db.query(PreparationType).all()
        if preparation_types:
            for preparation_type in preparation_types:
                st.write(f"**{preparation_type.name}**")
        else:
            st.info("Справочник пуст")

# --- Packaging Tab ---
with tabs[4]:
    st.header("Упаковка")

    with SessionLocal() as db:
        units = db.query(Unit).all()
        unit_options = {unit.name: unit.id for unit in units}

        if not unit_options:
            st.warning("Сначала добавьте единицы измерения")
        else:
            with st.form("add_packaging"):
                st.subheader("Добавить упаковку")
                name = st.text_input("Название упаковки")
                unit_name = st.selectbox("Единица измерения", options=list(unit_options.keys()), key="pkg_unit")
                comment = st.text_area("Комментарий", key="pkg_comment")
                submitted = st.form_submit_button("Добавить")

                if submitted:
                    if not name:
                        st.error("Название обязательно")
                    else:
                        new_packaging = Packaging(name=name, unit_id=unit_options[unit_name], comment=comment)
                        db.add(new_packaging)
                        try:
                            db.commit()
                            st.success(f"Упаковка '{name}' добавлена")
                        except Exception as e:
                            db.rollback()
                            st.error(f"Ошибка при добавлении: {e}")

    st.subheader("Список упаковок")
    with SessionLocal() as db:
        packaging_items = db.query(Packaging).all()
        if packaging_items:
            for packaging_item in packaging_items:
                st.write(f"**{packaging_item.name}** ({packaging_item.unit.short_name})")
        else:
            st.info("Справочник пуст")

# --- Consumables Tab ---
with tabs[5]:
    st.header("Расходники")

    with SessionLocal() as db:
        units = db.query(Unit).all()
        unit_options = {unit.name: unit.id for unit in units}

        if not unit_options:
            st.warning("Сначала добавьте единицы измерения")
        else:
            with st.form("add_consumable"):
                st.subheader("Добавить расходник")
                name = st.text_input("Название")
                unit_name = st.selectbox("Единица измерения", options=list(unit_options.keys()), key="cons_unit")
                comment = st.text_area("Комментарий", key="cons_comment")
                submitted = st.form_submit_button("Добавить")

                if submitted:
                    if not name:
                        st.error("Название обязательно")
                    else:
                        new_consumable = Consumable(name=name, unit_id=unit_options[unit_name], comment=comment)
                        db.add(new_consumable)
                        try:
                            db.commit()
                            st.success(f"Расходник '{name}' добавлен")
                        except Exception as e:
                            db.rollback()
                            st.error(f"Ошибка при добавлении: {e}")

    st.subheader("Список расходников")
    with SessionLocal() as db:
        consumables = db.query(Consumable).all()
        if consumables:
            for consumable in consumables:
                st.write(f"**{consumable.name}** ({consumable.unit.short_name})")
        else:
            st.info("Справочник пуст")

# --- Equipment Tab ---
with tabs[6]:
    st.header("Оборудование")

    with st.form("add_equipment"):
        st.subheader("Добавить оборудование")
        name = st.text_input("Название")
        cost = st.number_input("Стоимость покупки", min_value=0.0, step=100.0)
        life = st.number_input("Срок полезного использования (мес)", min_value=1, step=1)
        hourly_cost = st.number_input("Стоимость 1 часа работы", min_value=0.0, step=1.0)
        comment = st.text_area("Комментарий", key="equip_comment")
        submitted = st.form_submit_button("Добавить")

        if submitted:
            if not name:
                st.error("Название обязательно")
            else:
                with SessionLocal() as db:
                    new_equipment = Equipment(
                        name=name,
                        cost=cost,
                        useful_life_months=life,
                        hourly_cost=hourly_cost,
                        comment=comment,
                    )
                    db.add(new_equipment)
                    try:
                        db.commit()
                        st.success(f"Оборудование '{name}' добавлено")
                    except Exception as e:
                        db.rollback()
                        st.error(f"Ошибка при добавлении: {e}")

    st.subheader("Список оборудования")
    with SessionLocal() as db:
        equipment_items = db.query(Equipment).all()
        if equipment_items:
            for equipment_item in equipment_items:
                st.write(
                    f"**{equipment_item.name}** "
                    f"(Стоимость: {equipment_item.cost:,.2f}, Срок: {equipment_item.useful_life_months} мес)"
                )
        else:
            st.info("Справочник пуст")

# --- Fixed Expense Categories Tab ---
with tabs[7]:
    st.header("Категории постоянных расходов")

    with st.form("add_fixed_category"):
        st.subheader("Добавить категорию")
        name = st.text_input("Название")
        comment = st.text_area("Комментарий", key="fixed_cat_comment")
        submitted = st.form_submit_button("Добавить")

        if submitted:
            if not name:
                st.error("Название обязательно")
            else:
                with SessionLocal() as db:
                    new_category = FixedExpenseCategory(name=name, comment=comment)
                    db.add(new_category)
                    try:
                        db.commit()
                        st.success(f"Категория '{name}' добавлена")
                    except Exception as e:
                        db.rollback()
                        st.error(f"Ошибка при добавлении: {e}")

    st.subheader("Список категорий")
    with SessionLocal() as db:
        categories = db.query(FixedExpenseCategory).all()
        if categories:
            for category in categories:
                st.write(f"**{category.name}**")
        else:
            st.info("Справочник пуст")

# --- Labor Rate Tab ---
with tabs[8]:
    st.header("Стоимость труда")

    with SessionLocal() as db:
        current_rate = db.query(LaborRate).filter(LaborRate.is_active.is_(True)).first()

        with st.form("set_labor_rate"):
            st.subheader("Установить стоимость часа")
            rate_value = st.number_input(
                "Стоимость 1 часа работы",
                min_value=0.0,
                value=float(current_rate.hourly_rate) if current_rate else 0.0,
                step=10.0,
            )
            submitted = st.form_submit_button("Сохранить")

            if submitted:
                if current_rate:
                    current_rate.is_active = False

                new_rate = LaborRate(hourly_rate=rate_value, is_active=True)
                db.add(new_rate)
                try:
                    db.commit()
                    st.success(f"Стоимость часа установлена: {rate_value:,.2f}")
                    st.rerun()
                except Exception as e:
                    db.rollback()
                    st.error(f"Ошибка: {e}")

    if current_rate:
        st.metric("Текущая ставка", f"{current_rate.hourly_rate:,.2f} / час")
    else:
        st.warning("Ставка не установлена")

# --- Maintenance Tab ---
with tabs[9]:
    st.header("Обслуживание системы")
    st.warning("Внимание! Действия в этом разделе необратимы.")

    st.subheader("Очистка операционных данных")
    st.write(
        """
        Эта функция удалит все транзакционные данные:
        - Историю закупок и текущие остатки
        - Все записи о заготовках
        - Все производственные партии и фасовку
        - Все заказы клиентов

        Справочники останутся нетронутыми.
        """
    )

    col1, col2 = st.columns([2, 1])
    with col1:
        confirm_text = st.text_input("Введите слово 'УДАЛИТЬ' для подтверждения", key="reset_confirm")

    if st.button("Сбросить все данные", type="primary", disabled=(confirm_text != "УДАЛИТЬ")):
        try:
            with SessionLocal() as db:
                reset_operational_data(db)
                st.success("Все операционные данные успешно удалены.")
                st.balloons()
        except Exception as e:
            st.error(f"Ошибка при очистке данных: {e}")
