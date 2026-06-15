"""Streamlit page for managing purchases and viewing inventory balances."""

from __future__ import annotations

import streamlit as st
from decimal import Decimal
from datetime import date
from sqlalchemy.orm import Session
from nutag.db.models import Ingredient, Packaging, Unit, PurchaseItemType, Consumable
from nutag.db.session import create_engine_for_url, create_session_factory
from nutag.services.inventory import list_inventory_balances
from nutag.services.purchases import create_purchase, list_purchases, PurchaseLineInput


st.set_page_config(page_title="Закупки и остатки | Nutag", page_icon="📦", layout="wide")

st.title("📦 Закупки и остатки")

# Session management
engine = create_engine_for_url()
SessionLocal = create_session_factory(engine)

tabs = st.tabs(["Текущие остатки", "История закупок", "Новая закупка"])

# --- Current Stocks Tab ---
with tabs[0]:
    st.header("Текущие остатки")
    with SessionLocal() as db:
        balances = list_inventory_balances(db)
        if balances:
            import pandas as pd
            df_data = []
            for b in balances:
                df_data.append({
                    "Тип": b.item_type,
                    "Наименование": b.item_name,
                    "Закуплено": f"{b.purchased_quantity:,.3f}",
                    "Использовано": f"{b.used_quantity:,.3f}",
                    "Остаток": f"{b.current_quantity:,.3f}",
                    "Ед.изм.": b.unit_short_name,
                    "Средняя цена": f"{b.weighted_average_price:,.2f}",
                    "Стоимость остатка": f"{(b.current_quantity * b.weighted_average_price):,.2f}"
                })
            st.table(pd.DataFrame(df_data))
        else:
            st.info("На складе пока ничего нет. Зафиксируйте первую закупку.")

# --- Purchase History Tab ---
with tabs[1]:
    st.header("История закупок")
    with SessionLocal() as db:
        purchases = list_purchases(db)
        if purchases:
            for p in purchases:
                with st.expander(f"Закупка от {p.purchase_date} - {p.supplier or 'Без поставщика'} ({len(p.items)} поз.)"):
                    st.write(f"**Поставщик:** {p.supplier}")
                    st.write(f"**Закупил:** {p.purchased_by}")
                    st.write(f"**Транспортные расходы:** {p.transport_cost}")
                    st.write(f"**Комментарий:** {p.comment}")
                    
                    st.subheader("Позиции")
                    items_data = []
                    for item in p.items:
                        items_data.append({
                            "№": item.line_number,
                            "Наименование": item.item_name,
                            "Кол-во": item.quantity,
                            "Ед.изм.": item.unit.short_name,
                            "Цена": item.unit_price,
                            "Итого": item.total_price
                        })
                    st.table(items_data)
        else:
            st.info("История закупок пуста")

# --- New Purchase Tab ---
with tabs[2]:
    st.header("Новая закупка")
    
    with SessionLocal() as db:
        # Load directories for dropdowns
        ingredients = {i.name: i for i in db.query(Ingredient).all()}
        packaging = {p.name: p for p in db.query(Packaging).all()}
        consumables = {c.name: c for c in db.query(Consumable).all()}
        units = {u.short_name: u for u in db.query(Unit).all()}
        
        if not units:
            st.warning("Сначала добавьте единицы измерения в Справочниках")
        else:
            with st.form("new_purchase_form"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    purchase_date = st.date_input("Дата закупки", value=date.today())
                with col2:
                    supplier = st.text_input("Поставщик")
                with col3:
                    purchased_by = st.text_input("Кто закупил")
                
                transport_cost = st.number_input("Транспортные расходы", min_value=0.0, step=10.0, format="%.2f")
                comment = st.text_area("Общий комментарий")
                
                st.subheader("Позиции (до 10 за раз в MVP)")
                lines = []
                for i in range(10):
                    st.markdown(f"**Позиция {i+1}**")
                    c1, c2, c3, c4, c5, c6 = st.columns([2, 3, 1, 1, 2, 2])
                    with c1:
                        item_type_val = st.selectbox(
                            f"Тип {i}", 
                            options=[t.value for t in PurchaseItemType], 
                            key=f"type_{i}"
                        )
                    with c2:
                        # Depending on type, show different options
                        if item_type_val == PurchaseItemType.INGREDIENT:
                            name_options = list(ingredients.keys())
                            item_name = st.selectbox(f"Ингредиент {i}", options=[""] + name_options, key=f"name_{i}")
                        elif item_type_val == PurchaseItemType.PACKAGING:
                            name_options = list(packaging.keys())
                            item_name = st.selectbox(f"Упаковка {i}", options=[""] + name_options, key=f"name_{i}")
                        elif item_type_val == PurchaseItemType.CONSUMABLE:
                            name_options = list(consumables.keys())
                            item_name = st.selectbox(f"Расходник {i}", options=[""] + name_options, key=f"name_{i}")
                        else:
                            item_name = st.text_input(f"Наименование {i}", key=f"name_{i}")
                    
                    with c3:
                        unit_short = st.selectbox(f"Ед {i}", options=list(units.keys()), key=f"unit_{i}")
                    with c4:
                        qty = st.number_input(f"Кол-во {i}", min_value=0.0, step=0.1, format="%.3f", key=f"qty_{i}")
                    with c5:
                        price_unit = st.number_input(f"Цена/ед {i}", min_value=0.0, step=1.0, format="%.2f", key=f"price_unit_{i}")
                    with c6:
                        price_total = st.number_input(f"Итого {i}", min_value=0.0, step=1.0, format="%.2f", key=f"price_total_{i}")
                    
                    if item_name and qty > 0:
                        # Logic: if price_total is provided and price_unit is 0, calculate price_unit.
                        # If both are provided, price_unit takes priority or we can validate.
                        final_price_unit = Decimal(str(price_unit))
                        if final_price_unit == 0 and price_total > 0:
                            final_price_unit = Decimal(str(price_total)) / Decimal(str(qty))
                        
                        ing = ingredients.get(item_name) if item_type_val == PurchaseItemType.INGREDIENT else None
                        pkg = packaging.get(item_name) if item_type_val == PurchaseItemType.PACKAGING else None
                        cons = consumables.get(item_name) if item_type_val == PurchaseItemType.CONSUMABLE else None
                        
                        lines.append(PurchaseLineInput(
                            item_type=PurchaseItemType(item_type_val),
                            item_name=item_name,
                            unit=units[unit_short],
                            quantity=Decimal(str(qty)),
                            unit_price=final_price_unit,
                            ingredient=ing,
                            packaging=pkg,
                            consumable=cons
                        ))
                
                submitted = st.form_submit_button("Сохранить закупку")
                if submitted:
                    if not lines:
                        st.error("Добавьте хотя бы одну позицию с количеством > 0")
                    else:
                        try:
                            with SessionLocal() as db_write:
                                # Re-fetch objects for the new session
                                db_lines = []
                                for line in lines:
                                    db_lines.append(PurchaseLineInput(
                                        item_type=line.item_type,
                                        item_name=line.item_name,
                                        unit=db_write.merge(line.unit),
                                        quantity=line.quantity,
                                        unit_price=line.unit_price,
                                        ingredient=db_write.merge(line.ingredient) if line.ingredient else None,
                                        packaging=db_write.merge(line.packaging) if line.packaging else None,
                                        consumable=db_write.merge(line.consumable) if line.consumable else None
                                    ))
                                
                                create_purchase(
                                    db_write,
                                    purchase_date=purchase_date,
                                    lines=db_lines,
                                    supplier=supplier,
                                    purchased_by=purchased_by,
                                    transport_cost=Decimal(str(transport_cost)),
                                    comment=comment
                                )
                                db_write.commit()
                                st.success("Закупка успешно сохранена!")
                                st.rerun()
                        except Exception as e:
                            st.error(f"Ошибка при сохранении: {e}")
