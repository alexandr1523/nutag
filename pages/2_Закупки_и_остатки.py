"""Streamlit page for managing purchases and viewing inventory balances."""

from __future__ import annotations

import streamlit as st
from decimal import Decimal
from datetime import date
from sqlalchemy.orm import Session
from nutag.db.models import Ingredient, Packaging, Unit, PurchaseItemType, Consumable
from nutag.db.session import create_engine_for_url, create_session_factory
from nutag.services.inventory import list_inventory_balances, list_available_stock_batches
from nutag.services.purchases import create_purchase, list_purchases, PurchaseLineInput


st.set_page_config(page_title="Закупки и остатки | Nutag", page_icon="📦", layout="wide")

st.title("📦 Закупки и остатки")

# Session management
engine = create_engine_for_url()
SessionLocal = create_session_factory(engine)

tabs = st.tabs(["Текущие остатки", "Остатки по партиям", "История закупок", "Новая закупка"])

# --- Current Stocks Tab ---
with tabs[0]:
    st.header("Текущие остатки (агрегированно)")
    with SessionLocal() as db:
        balances = list_inventory_balances(db)
        if balances:
            import pandas as pd
            df_data = []
            for b in balances:
                df_data.append({
                    "Тип": b.item_type,
                    "Наименование": b.item_name,
                    "Закуплено/Сделано": f"{b.inflow_quantity:,.3f}",
                    "Использовано": f"{b.outflow_quantity:,.3f}",
                    "Остаток": f"{b.current_quantity:,.3f}",
                    "Ед.изм.": b.unit_short_name,
                    "Средняя цена": f"{b.weighted_average_price:,.2f}",
                    "Стоимость остатка": f"{(b.current_quantity * b.weighted_average_price):,.2f}"
                })
            st.table(pd.DataFrame(df_data))
        else:
            st.info("На складе пока ничего нет. Зафиксируйте первую закупку.")

# --- Batch Stocks Tab ---
with tabs[1]:
    st.header("Остатки в разрезе партий (FIFO)")
    with SessionLocal() as db:
        batches = list_available_stock_batches(db)
        if batches:
            import pandas as pd
            df_batch_data = []
            for b in batches:
                df_batch_data.append({
                    "Дата": b.date,
                    "Тип": b.item_type,
                    "Наименование": b.item_name,
                    "Партия": f"#{b.batch_id} ({b.batch_type})",
                    "Начальное кол-во": f"{b.initial_quantity:,.3f}",
                    "Текущий остаток": f"{b.current_quantity:,.3f}",
                    "Ед.изм.": b.unit_short_name,
                    "Цена партии": f"{b.unit_price:,.2f}"
                })
            st.table(pd.DataFrame(df_batch_data))
        else:
            st.info("Нет доступных партий с остатками.")

# --- Purchase History Tab ---
with tabs[2]:
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
with tabs[3]:
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
            # Initialize session state for 10 rows if not exists
            if 'purchase_rows' not in st.session_state:
                st.session_state.purchase_rows = [
                    {'type': 'Ингредиент', 'name': '', 'unit': list(units.keys())[0], 'qty': 0.0, 'price_unit': 0.0, 'price_total': 0.0} 
                    for _ in range(10)
                ]

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
            
            def sync_row(idx):
                st.session_state.purchase_rows[idx]['type'] = st.session_state[f"type_sel_{idx}"]
                st.session_state.purchase_rows[idx]['unit'] = st.session_state[f"unit_sel_{idx}"]
                st.session_state.purchase_rows[idx]['qty'] = st.session_state[f"qty_val_{idx}"]
                st.session_state.purchase_rows[idx]['price_unit'] = st.session_state[f"price_unit_val_{idx}"]
                st.session_state.purchase_rows[idx]['price_total'] = st.session_state[f"price_total_val_{idx}"]
                
                # Sync name based on widget type
                if st.session_state.purchase_rows[idx]['type'] == "Ингредиент":
                    st.session_state.purchase_rows[idx]['name'] = st.session_state.get(f"name_sel_{idx}", "")
                elif st.session_state.purchase_rows[idx]['type'] == "Упаковка":
                    st.session_state.purchase_rows[idx]['name'] = st.session_state.get(f"name_sel_pkg_{idx}", "")
                elif st.session_state.purchase_rows[idx]['type'] == "Расходник":
                    st.session_state.purchase_rows[idx]['name'] = st.session_state.get(f"name_sel_cons_{idx}", "")
                else:
                    st.session_state.purchase_rows[idx]['name'] = st.session_state.get(f"name_txt_{idx}", "")

            def update_total(idx):
                sync_row(idx)
                row = st.session_state.purchase_rows[idx]
                st.session_state.purchase_rows[idx]['price_total'] = float(round(Decimal(str(row['qty'])) * Decimal(str(row['price_unit'])), 2))

            def update_unit(idx):
                sync_row(idx)
                row = st.session_state.purchase_rows[idx]
                if row['qty'] > 0:
                    st.session_state.purchase_rows[idx]['price_unit'] = float(round(Decimal(str(row['price_total'])) / Decimal(str(row['qty'])), 2))

            for i in range(10):
                st.markdown(f"**Позиция {i+1}**")
                c1, c2, c3, c4, c5, c6 = st.columns([2, 3, 1, 1, 2, 2])
                
                row = st.session_state.purchase_rows[i]
                
                with c1:
                    st.selectbox(
                        f"Тип {i}", 
                        options=[t.value for t in PurchaseItemType], 
                        index=[t.value for t in PurchaseItemType].index(row['type']),
                        key=f"type_sel_{i}",
                        on_change=sync_row, args=(i,)
                    )
                with c2:
                    if row['type'] == "Ингредиент":
                        name_options = [""] + list(ingredients.keys())
                        st.selectbox(f"Ингредиент {i}", options=name_options, index=name_options.index(row['name']) if row['name'] in name_options else 0, key=f"name_sel_{i}", on_change=sync_row, args=(i,))
                    elif row['type'] == "Упаковка":
                        name_options = [""] + list(packaging.keys())
                        st.selectbox(f"Упаковка {i}", options=name_options, index=name_options.index(row['name']) if row['name'] in name_options else 0, key=f"name_sel_pkg_{i}", on_change=sync_row, args=(i,))
                    elif row['type'] == "Расходник":
                        name_options = [""] + list(consumables.keys())
                        st.selectbox(f"Расходник {i}", options=name_options, index=name_options.index(row['name']) if row['name'] in name_options else 0, key=f"name_sel_cons_{i}", on_change=sync_row, args=(i,))
                    else:
                        st.text_input(f"Наименование {i}", value=row['name'], key=f"name_txt_{i}", on_change=sync_row, args=(i,))
                
                with c3:
                    st.selectbox(f"Ед {i}", options=list(units.keys()), index=list(units.keys()).index(row['unit']) if row['unit'] in units else 0, key=f"unit_sel_{i}", on_change=sync_row, args=(i,))
                with c4:
                    st.number_input(f"Кол-во {i}", min_value=0.0, step=0.1, format="%.3f", value=row['qty'], key=f"qty_val_{i}", on_change=update_total, args=(i,))
                with c5:
                    st.number_input(f"Цена/ед {i}", min_value=0.0, step=1.0, format="%.2f", value=row['price_unit'], key=f"price_unit_val_{i}", on_change=update_total, args=(i,))
                with c6:
                    st.number_input(f"Итого {i}", min_value=0.0, step=1.0, format="%.2f", value=row['price_total'], key=f"price_total_val_{i}", on_change=update_unit, args=(i,))

            if st.button("Сохранить закупку", type="primary"):
                lines = []
                for r in st.session_state.purchase_rows:
                    if r['name'] and r['qty'] > 0:
                        ing = ingredients.get(r['name']) if r['type'] == "Ингредиент" else None
                        pkg = packaging.get(r['name']) if r['type'] == "Упаковка" else None
                        cons = consumables.get(r['name']) if r['type'] == "Расходник" else None
                        
                        lines.append(PurchaseLineInput(
                            item_type=PurchaseItemType(r['type']),
                            item_name=r['name'],
                            unit=units[r['unit']],
                            quantity=Decimal(str(r['qty'])),
                            unit_price=Decimal(str(r['price_unit'])),
                            ingredient=ing,
                            packaging=pkg,
                            consumable=cons
                        ))

                if not lines:
                    st.error("Добавьте хотя бы одну позицию с количеством > 0")
                else:
                    try:
                        with SessionLocal() as db_write:
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
                            # Clear state after success
                            if 'purchase_rows' in st.session_state:
                                del st.session_state.purchase_rows
                            st.success("Закупка успешно сохранена!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Ошибка при сохранении: {e}")
