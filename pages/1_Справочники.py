"""Streamlit page for managing dictionaries (units, ingredients, products, packaging)."""

from __future__ import annotations

import streamlit as st
from sqlalchemy.orm import Session
from nutag.db.models import Unit, Ingredient, Product, Packaging, Consumable, Equipment, FixedExpenseCategory, LaborRate
from nutag.db.session import create_engine_for_url, create_session_factory


from nutag.services.maintenance import reset_operational_data

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


tabs = st.tabs([
    "Единицы измерения", 
    "Ингредиенты", 
    "Продукты", 
    "Упаковка", 
    "Расходники", 
    "Оборудование", 
    "Постоянные расходы", 
    "Стоимость труда",
    "⚙️ Обслуживание"
])

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

# --- Products Tab ---
with tabs[2]:
    st.header("Продукты")
    
    with st.form("add_product"):
        st.subheader("Добавить продукт")
        name = st.text_input("Название продукта (например, Пельмени)")
        comment = st.text_area("Комментарий", key="prod_comment")
        submitted = st.form_submit_button("Добавить")
        
        if submitted:
            if not name:
                st.error("Название обязательно")
            else:
                with SessionLocal() as db:
                    new_prod = Product(name=name, comment=comment)
                    db.add(new_prod)
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
            for p in products:
                st.write(f"**{p.name}**")
        else:
            st.info("Справочник пуст")

# --- Packaging Tab ---
with tabs[3]:
    st.header("Упаковка")
    
    with SessionLocal() as db:
        units = db.query(Unit).all()
        unit_options = {u.name: u.id for u in units}
        
        if not unit_options:
            st.warning("Сначала добавьте единицы измерения")
        else:
            with st.form("add_packaging"):
                st.subheader("Добавить упаковку")
                name = st.text_input("Название упаковки (например, Контейнер 0.5)")
                unit_name = st.selectbox("Единица измерения", options=list(unit_options.keys()), key="pkg_unit")
                comment = st.text_area("Комментарий", key="pkg_comment")
                submitted = st.form_submit_button("Добавить")
                
                if submitted:
                    if not name:
                        st.error("Название обязательно")
                    else:
                        new_pkg = Packaging(
                            name=name, 
                            unit_id=unit_options[unit_name], 
                            comment=comment
                        )
                        db.add(new_pkg)
                        try:
                            db.commit()
                            st.success(f"Упаковка '{name}' добавлена")
                        except Exception as e:
                            db.rollback()
                            st.error(f"Ошибка при добавлении: {e}")

    st.subheader("Список упаковок")
    with SessionLocal() as db:
        packaging = db.query(Packaging).all()
        if packaging:
            for pkg in packaging:
                st.write(f"**{pkg.name}** ({pkg.unit.short_name})")
        else:
            st.info("Справочник пуст")

# --- Consumables Tab ---
with tabs[4]:
    st.header("Расходники")
    
    with SessionLocal() as db:
        units = db.query(Unit).all()
        unit_options = {u.name: u.id for u in units}
        
        if not unit_options:
            st.warning("Сначала добавьте единицы измерения")
        else:
            with st.form("add_consumable"):
                st.subheader("Добавить расходник")
                name = st.text_input("Название (например, Перчатки)")
                unit_name = st.selectbox("Единица измерения", options=list(unit_options.keys()), key="cons_unit")
                comment = st.text_area("Комментарий", key="cons_comment")
                submitted = st.form_submit_button("Добавить")
                
                if submitted:
                    if not name:
                        st.error("Название обязательно")
                    else:
                        new_cons = Consumable(
                            name=name, 
                            unit_id=unit_options[unit_name], 
                            comment=comment
                        )
                        db.add(new_cons)
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
            for c in consumables:
                st.write(f"**{c.name}** ({c.unit.short_name})")
        else:
            st.info("Справочник пуст")

# --- Equipment Tab ---
with tabs[5]:
    st.header("Оборудование")
    
    with st.form("add_equipment"):
        st.subheader("Добавить оборудование")
        name = st.text_input("Название (например, Морозильник)")
        cost = st.number_input("Стоимость покупки", min_value=0.0, step=100.0)
        life = st.number_input("Срок полезного использования (мес)", min_value=1, step=1)
        h_cost = st.number_input("Стоимость 1 часа работы", min_value=0.0, step=1.0, help="Для автоматического расчёта амортизации")
        comment = st.text_area("Комментарий", key="equip_comment")
        submitted = st.form_submit_button("Добавить")
        
        if submitted:
            if not name:
                st.error("Название обязательно")
            else:
                with SessionLocal() as db:
                    new_equip = Equipment(
                        name=name, 
                        cost=cost, 
                        useful_life_months=life, 
                        hourly_cost=h_cost,
                        comment=comment
                    )
                    db.add(new_equip)
                    try:
                        db.commit()
                        st.success(f"Оборудование '{name}' добавлено")
                    except Exception as e:
                        db.rollback()
                        st.error(f"Ошибка при добавлении: {e}")

    st.subheader("Список оборудования")
    with SessionLocal() as db:
        equipment = db.query(Equipment).all()
        if equipment:
            for e in equipment:
                st.write(f"**{e.name}** (Стоимость: {e.cost:,.2f}, Срок: {e.useful_life_months} мес)")
        else:
            st.info("Справочник пуст")

# --- Fixed Expense Categories Tab ---
with tabs[6]:
    st.header("Категории постоянных расходов")
    
    with st.form("add_fixed_category"):
        st.subheader("Добавить категорию")
        name = st.text_input("Название (например, Аренда)")
        comment = st.text_area("Комментарий", key="fixed_cat_comment")
        submitted = st.form_submit_button("Добавить")
        
        if submitted:
            if not name:
                st.error("Название обязательно")
            else:
                with SessionLocal() as db:
                    new_cat = FixedExpenseCategory(name=name, comment=comment)
                    db.add(new_cat)
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
            for cat in categories:
                st.write(f"**{cat.name}**")
        else:
            st.info("Справочник пуст")

# --- Labor Rate Tab ---
with tabs[7]:
    st.header("Стоимость труда")
    
    with SessionLocal() as db:
        current_rate = db.query(LaborRate).filter(LaborRate.is_active == True).first()
        
        with st.form("set_labor_rate"):
            st.subheader("Установить стоимость часа")
            rate_val = st.number_input(
                "Стоимость 1 часа работы", 
                min_value=0.0, 
                value=float(current_rate.hourly_rate) if current_rate else 0.0,
                step=10.0
            )
            submitted = st.form_submit_button("Сохранить")
            
            if submitted:
                # Deactivate old rate
                if current_rate:
                    current_rate.is_active = False
                
                new_rate = LaborRate(hourly_rate=rate_val, is_active=True)
                db.add(new_rate)
                try:
                    db.commit()
                    st.success(f"Стоимость часа установлена: {rate_val:,.2f}")
                    st.rerun()
                except Exception as e:
                    db.rollback()
                    st.error(f"Ошибка: {e}")

    if current_rate:
        st.metric("Текущая ставка", f"{current_rate.hourly_rate:,.2f} / час")
    else:
        st.warning("Ставка не установлена")

# --- Maintenance Tab ---
with tabs[8]:
    st.header("⚙️ Обслуживание системы")
    st.warning("Внимание! Действия в этом разделе необратимы.")
    
    st.subheader("Очистка операционных данных")
    st.write("""
        Эта функция удалит все транзакционные данные:
        - Историю закупок и текущие остатки
        - Все записи о заготовках
        - Все производственные партии и фасовку
        - Все заказы клиентов
        
        **Справочники (единицы, ингредиенты, продукты, оборудование) останутся нетронутыми.**
    """)
    
    col1, col2 = st.columns([2, 1])
    with col1:
        confirm_text = st.text_input("Введите слово 'УДАЛИТЬ' для подтверждения", key="reset_confirm")
    
    if st.button("Сбросить все данные", type="primary", disabled=(confirm_text != "УДАЛИТЬ")):
        try:
            with SessionLocal() as db:
                reset_operational_data(db)
                st.success("Все операционные данные успешно удалены. Система готова к работе с чистого листа.")
                st.balloons()
                # We don't rerun immediately to let user see success message, 
                # but any navigation will show empty lists.
        except Exception as e:
            st.error(f"Ошибка при очистке данных: {e}")
