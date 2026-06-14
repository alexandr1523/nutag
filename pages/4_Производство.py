"""Streamlit page for managing final production batches."""

from __future__ import annotations

import streamlit as st
from decimal import Decimal
from datetime import date
from sqlalchemy.orm import Session
from nutag.db.models import Ingredient, Product, Unit, Preparation
from nutag.db.session import create_engine_for_url, create_session_factory
from nutag.services.inventory import list_inventory_balances
from nutag.services.preparations import list_preparations
from nutag.services.production import (
    create_production_batch,
    list_production_batches,
    BatchIngredientInput,
    BatchPreparationInput,
    FinishedProductOutputInput
)


st.set_page_config(page_title="Производство | Nutag", page_icon="🏭", layout="wide")

st.title("🏭 Производство")

# Session management
engine = create_engine_for_url()
SessionLocal = create_session_factory(engine)

tabs = st.tabs(["История партий", "Новая партия"])

# --- History Tab ---
with tabs[0]:
    st.header("История партий")
    with SessionLocal() as db:
        batches = list_production_batches(db)
        if batches:
            for b in batches:
                with st.expander(f"{b.produced_on} - {b.product.name} ({b.actual_output_quantity} {b.output_unit.short_name})"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Дата:** {b.produced_on}")
                        st.write(f"**Выход:** {b.actual_output_quantity} {b.output_unit.short_name}")
                        st.write(f"**Труд:** {b.labor_cost:,.2f}")
                        st.write(f"**Амортизация:** {b.equipment_depreciation:,.2f}")
                        st.write(f"**Накладные:** {b.allocated_overhead:,.2f}")
                    with col2:
                        st.write(f"**Себестоимость (общая):** {b.total_cost:,.2f}")
                        st.write(f"**Себестоимость (ед):** {b.unit_cost:,.4f}")
                    
                    st.subheader("Фасовка")
                    out_data = []
                    for out in b.outputs:
                        out_data.append({
                            "Размер": out.package_size,
                            "Ед.изм.": out.package_unit.short_name,
                            "Кол-во упак.": out.package_count,
                            "Итого вес": out.total_quantity
                        })
                    st.table(out_data)

                    st.subheader("Затраты")
                    uses_data = []
                    for use in b.ingredient_uses:
                        uses_data.append({"Тип": "Ингредиент", "Наименование": use.ingredient.name, "Кол-во": use.quantity, "Ед": use.unit.short_name, "Цена": use.unit_cost, "Итого": use.total_cost})
                    for use in b.preparation_uses:
                        uses_data.append({"Тип": "Заготовка", "Наименование": use.preparation.name, "Кол-во": use.quantity, "Ед": use.unit.short_name, "Цена": use.unit_cost, "Итого": use.total_cost})
                    st.table(uses_data)
        else:
            st.info("История партий пуста")

# --- New Batch Tab ---
with tabs[1]:
    st.header("Новая партия")
    
    with SessionLocal() as db:
        # Load directories and prices
        balances = list_inventory_balances(db)
        ing_prices = {b.item_name: b.weighted_average_price for b in balances if b.item_type == "ingredient"}
        
        preps = list_preparations(db)
        # For preparations, price is from the preparation record itself (unit_cost)
        # Note: In a real app we might want weighted average if there are multiple prep batches
        prep_prices = {p.name: p.unit_cost for p in preps}
        prep_objs = {p.name: p for p in preps}
        
        all_ingredients = {i.name: i for i in db.query(Ingredient).all()}
        all_products = {p.name: p for p in db.query(Product).all()}
        all_units = {u.short_name: u for u in db.query(Unit).all()}
        
        if not all_products:
            st.warning("Сначала добавьте продукты в Справочниках")
        else:
            with st.form("new_batch_form"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    batch_date = st.date_input("Дата производства", value=date.today())
                with col2:
                    prod_name = st.selectbox("Продукт", options=list(all_products.keys()))
                with col3:
                    batch_comment = st.text_area("Комментарий", key="batch_comm")
                
                st.subheader("Выход")
                c1, c2 = st.columns(2)
                with c1:
                    actual_qty = st.number_input("Фактический выход (всего)", min_value=0.0, step=0.1, format="%.3f")
                with c2:
                    out_unit_name = st.selectbox("Ед. изм. выхода", options=list(all_units.keys()))
                
                st.subheader("Доп. расходы")
                c3, c4, c5 = st.columns(3)
                with c3:
                    labor_cost = st.number_input("Стоимость труда", min_value=0.0, step=10.0, format="%.2f")
                with c4:
                    depr_cost = st.number_input("Амортизация", min_value=0.0, step=10.0, format="%.2f")
                with c5:
                    overhead = st.number_input("Накладные расходы", min_value=0.0, step=10.0, format="%.2f")

                st.subheader("Ингредиенты (до 3)")
                ing_uses = []
                for i in range(3):
                    ca, cb, cc, cd = st.columns([3, 1, 2, 2])
                    with ca:
                        i_name = st.selectbox(f"Ингредиент {i}", options=[""] + list(all_ingredients.keys()), key=f"bi_name_{i}")
                    
                    def_unit = all_ingredients[i_name].unit.short_name if i_name else ""
                    def_price = float(ing_prices.get(i_name, 0)) if i_name else 0.0
                    
                    with cb:
                        u_name = st.selectbox(f"Ед и {i}", options=list(all_units.keys()), index=list(all_units.keys()).index(def_unit) if def_unit in all_units else 0, key=f"bi_unit_{i}")
                    with cc:
                        qty = st.number_input(f"Кол-во и {i}", min_value=0.0, step=0.1, format="%.3f", key=f"bi_qty_{i}")
                    with cd:
                        price = st.number_input(f"Цена и {i}", min_value=0.0, value=def_price, step=1.0, format="%.2f", key=f"bi_price_{i}")
                    
                    if i_name and qty > 0:
                        ing_uses.append(BatchIngredientInput(ingredient=all_ingredients[i_name], unit=all_units[u_name], quantity=Decimal(str(qty)), unit_cost=Decimal(str(price))))

                st.subheader("Заготовки (до 3)")
                p_uses = []
                for i in range(3):
                    ca, cb, cc, cd = st.columns([3, 1, 2, 2])
                    with ca:
                        p_name = st.selectbox(f"Заготовка {i}", options=[""] + list(prep_prices.keys()), key=f"bp_name_{i}")
                    
                    def_unit = prep_objs[p_name].output_unit.short_name if p_name else ""
                    def_price = float(prep_prices.get(p_name, 0)) if p_name else 0.0
                    
                    with cb:
                        u_name = st.selectbox(f"Ед з {i}", options=list(all_units.keys()), index=list(all_units.keys()).index(def_unit) if def_unit in all_units else 0, key=f"bp_unit_{i}")
                    with cc:
                        qty = st.number_input(f"Кол-во з {i}", min_value=0.0, step=0.1, format="%.3f", key=f"bp_qty_{i}")
                    with cd:
                        price = st.number_input(f"Цена з {i}", min_value=0.0, value=def_price, step=1.0, format="%.2f", key=f"bp_price_{i}")
                    
                    if p_name and qty > 0:
                        p_uses.append(BatchPreparationInput(preparation=prep_objs[p_name], unit=all_units[u_name], quantity=Decimal(str(qty)), unit_cost=Decimal(str(price))))

                st.subheader("Фасовка (до 2)")
                out_inputs = []
                for i in range(2):
                    ca, cb, cc = st.columns([2, 2, 2])
                    with ca:
                        p_size = st.number_input(f"Размер упак {i}", min_value=0.0, step=0.1, format="%.3f", key=f"bo_size_{i}")
                    with cb:
                        p_unit = st.selectbox(f"Ед упак {i}", options=list(all_units.keys()), key=f"bo_unit_{i}")
                    with cc:
                        p_count = st.number_input(f"Кол-во упак {i}", min_value=0, step=1, key=f"bo_count_{i}")
                    
                    if p_size > 0 and p_count > 0:
                        out_inputs.append(FinishedProductOutputInput(package_size=Decimal(str(p_size)), package_unit=all_units[p_unit], package_count=p_count))

                submitted = st.form_submit_button("Сохранить партию")
                if submitted:
                    if actual_qty <= 0:
                        st.error("Фактический выход должен быть больше 0")
                    elif not out_inputs:
                        st.error("Добавьте хотя бы одну строку фасовки")
                    elif not (ing_uses or p_uses):
                        st.error("Добавьте хотя бы один ингредиент или заготовку")
                    else:
                        try:
                            with SessionLocal() as db_write:
                                db_prod = db_write.merge(all_products[prod_name])
                                db_unit = db_write.merge(all_units[out_unit_name])
                                db_ing_uses = [BatchIngredientInput(ingredient=db_write.merge(u.ingredient), unit=db_write.merge(u.unit), quantity=u.quantity, unit_cost=u.unit_cost) for u in ing_uses]
                                db_p_uses = [BatchPreparationInput(preparation=db_write.merge(u.preparation), unit=db_write.merge(u.unit), quantity=u.quantity, unit_cost=u.unit_cost) for u in p_uses]
                                db_outputs = [FinishedProductOutputInput(package_size=u.package_size, package_unit=db_write.merge(u.package_unit), package_count=u.package_count) for u in out_inputs]
                                
                                create_production_batch(
                                    db_write,
                                    produced_on=batch_date,
                                    product=db_prod,
                                    actual_output_quantity=Decimal(str(actual_qty)),
                                    output_unit=db_unit,
                                    outputs=db_outputs,
                                    ingredient_uses=db_ing_uses,
                                    preparation_uses=db_p_uses,
                                    labor_cost=Decimal(str(labor_cost)),
                                    equipment_depreciation=Decimal(str(depr_cost)),
                                    allocated_overhead=Decimal(str(overhead)),
                                    comment=batch_comment
                                )
                                db_write.commit()
                                st.success("Партия успешно сохранена!")
                                st.rerun()
                        except Exception as e:
                            st.error(f"Ошибка при сохранении: {e}")
