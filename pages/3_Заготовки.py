"""Streamlit page for managing internal preparations/semi-finished products."""

from __future__ import annotations

import streamlit as st
from decimal import Decimal
from datetime import date
from sqlalchemy.orm import Session
from nutag.db.models import Ingredient, Unit
from nutag.db.session import create_engine_for_url, create_session_factory
from nutag.services.inventory import list_inventory_balances
from nutag.services.preparations import create_preparation, list_preparations, PreparationIngredientInput


st.set_page_config(page_title="Заготовки | Nutag", page_icon="🥣", layout="wide")

st.title("🥣 Заготовки")

# Session management
engine = create_engine_for_url()
SessionLocal = create_session_factory(engine)

tabs = st.tabs(["История заготовок", "Новая заготовка"])

# --- History Tab ---
with tabs[0]:
    st.header("История заготовок")
    with SessionLocal() as db:
        preps = list_preparations(db)
        if preps:
            for p in preps:
                with st.expander(f"{p.prepared_on} - {p.name} ({p.output_quantity} {p.output_unit.short_name})"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Дата:** {p.prepared_on}")
                        st.write(f"**Выход:** {p.output_quantity} {p.output_unit.short_name}")
                        st.write(f"**Труд:** {p.labor_cost:,.2f}")
                        st.write(f"**Прочее:** {p.other_direct_cost:,.2f}")
                    with col2:
                        st.write(f"**Себестоимость (общая):** {p.total_cost:,.2f}")
                        st.write(f"**Себестоимость (ед):** {p.unit_cost:,.4f}")
                    
                    st.subheader("Использованные ингредиенты")
                    ing_data = []
                    for use in p.ingredient_uses:
                        ing_data.append({
                            "Ингредиент": use.ingredient.name,
                            "Кол-во": use.quantity,
                            "Ед.изм.": use.unit.short_name,
                            "Цена": use.unit_cost,
                            "Итого": use.total_cost
                        })
                    st.table(ing_data)
        else:
            st.info("История заготовок пуста")

# --- New Preparation Tab ---
with tabs[1]:
    st.header("Новая заготовка")
    
    with SessionLocal() as db:
        # Load ingredients and their current prices
        balances = list_inventory_balances(db)
        ing_prices = {b.item_name: b.weighted_average_price for b in balances if b.item_type == "ingredient"}
        
        all_ingredients = {i.name: i for i in db.query(Ingredient).all()}
        all_units = {u.short_name: u for u in db.query(Unit).all()}
        
        if not all_ingredients:
            st.warning("Сначала добавьте ингредиенты в Справочниках")
        else:
            with st.form("new_prep_form"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    prep_date = st.date_input("Дата приготовления", value=date.today())
                with col2:
                    prep_name = st.text_input("Название (например, Тесто для пельменей)")
                with col3:
                    prep_comment = st.text_area("Комментарий", key="prep_comm")
                
                st.subheader("Выход")
                c1, c2 = st.columns(2)
                with c1:
                    output_qty = st.number_input("Кол-во на выходе", min_value=0.0, step=0.1, format="%.3f")
                with c2:
                    output_unit_name = st.selectbox("Ед. изм. выхода", options=list(all_units.keys()))
                
                st.subheader("Расходы")
                c3, c4 = st.columns(2)
                with c3:
                    labor_cost = st.number_input("Стоимость труда", min_value=0.0, step=10.0, format="%.2f")
                with c4:
                    other_cost = st.number_input("Прочие прямые расходы", min_value=0.0, step=10.0, format="%.2f")

                st.subheader("Ингредиенты (до 5 в MVP)")
                ingredient_uses = []
                for i in range(5):
                    st.markdown(f"**Ингредиент {i+1}**")
                    ca, cb, cc, cd = st.columns([3, 1, 2, 2])
                    with ca:
                        ing_name = st.selectbox(f"Выбор ингредиента {i}", options=[""] + list(all_ingredients.keys()), key=f"ing_name_{i}")
                    
                    # Try to pre-fill unit and price if ingredient is selected
                    default_unit = ""
                    default_price = 0.0
                    if ing_name:
                        ing_obj = all_ingredients[ing_name]
                        default_unit = ing_obj.unit.short_name
                        default_price = float(ing_prices.get(ing_name, 0))
                    
                    with cb:
                        u_name = st.selectbox(f"Ед {i}", options=list(all_units.keys()), index=list(all_units.keys()).index(default_unit) if default_unit in all_units else 0, key=f"ing_unit_{i}")
                    with cc:
                        qty = st.number_input(f"Кол-во {i}", min_value=0.0, step=0.1, format="%.3f", key=f"ing_qty_{i}")
                    with cd:
                        price = st.number_input(f"Цена за ед {i}", min_value=0.0, value=default_price, step=1.0, format="%.2f", key=f"ing_price_{i}")
                    
                    if ing_name and qty > 0:
                        ingredient_uses.append(PreparationIngredientInput(
                            ingredient=all_ingredients[ing_name],
                            unit=all_units[u_name],
                            quantity=Decimal(str(qty)),
                            unit_cost=Decimal(str(price))
                        ))
                
                submitted = st.form_submit_button("Сохранить заготовку")
                if submitted:
                    if not prep_name:
                        st.error("Укажите название заготовки")
                    elif output_qty <= 0:
                        st.error("Количество на выходе должно быть больше 0")
                    elif not ingredient_uses:
                        st.error("Добавьте хотя бы один ингредиент")
                    else:
                        try:
                            with SessionLocal() as db_write:
                                # Re-fetch units and ingredients for current session
                                db_output_unit = db_write.merge(all_units[output_unit_name])
                                db_ing_uses = []
                                for use in ingredient_uses:
                                    db_ing_uses.append(PreparationIngredientInput(
                                        ingredient=db_write.merge(use.ingredient),
                                        unit=db_write.merge(use.unit),
                                        quantity=use.quantity,
                                        unit_cost=use.unit_cost
                                    ))
                                
                                create_preparation(
                                    db_write,
                                    prepared_on=prep_date,
                                    name=prep_name,
                                    output_quantity=Decimal(str(output_qty)),
                                    output_unit=db_output_unit,
                                    ingredient_uses=db_ing_uses,
                                    labor_cost=Decimal(str(labor_cost)),
                                    other_direct_cost=Decimal(str(other_cost)),
                                    comment=prep_comment
                                )
                                db_write.commit()
                                st.success(f"Заготовка '{prep_name}' успешно сохранена!")
                                st.rerun()
                        except Exception as e:
                            st.error(f"Ошибка при сохранении: {e}")
