"""Streamlit page for managing customer orders."""

from __future__ import annotations

import streamlit as st
from decimal import Decimal
from datetime import date
from sqlalchemy.orm import Session
from nutag.db.models import Product, Unit, OrderStatus, PaymentStatus, ReservationStatus
from nutag.db.session import create_engine_for_url, create_session_factory
from nutag.services.orders import create_order, list_orders, OrderItemInput


st.set_page_config(page_title="Заказы | Nutag", page_icon="🛍️", layout="wide")

st.title("🛍️ Заказы")

# Session management
engine = create_engine_for_url()
SessionLocal = create_session_factory(engine)

tabs = st.tabs(["Список заказов", "Новый заказ"])

# --- List Orders Tab ---
with tabs[0]:
    st.header("Список заказов")
    with SessionLocal() as db:
        orders = list_orders(db)
        if orders:
            for o in orders:
                status_color = {
                    OrderStatus.NEW: "blue",
                    OrderStatus.CONFIRMED: "orange",
                    OrderStatus.READY: "green",
                    OrderStatus.DELIVERED: "gray",
                    OrderStatus.CANCELLED: "red"
                }.get(o.order_status, "black")
                
                with st.expander(f"{o.order_date} - {o.customer_name} ({o.total_amount:,.2f}) - {o.order_status.upper()}"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.write(f"**Клиент:** {o.customer_name}")
                        st.write(f"**Контакт:** {o.customer_contact}")
                        st.write(f"**Статус заказа:** :{status_color}[{o.order_status}]")
                    with col2:
                        st.write(f"**Статус оплаты:** {o.payment_status}")
                        st.write(f"**Резерв:** {o.reservation_status}")
                        st.write(f"**Сумма:** {o.total_amount:,.2f}")
                    with col3:
                        st.write(f"**Доставка:** {o.delivery_cost:,.2f}")
                        st.write(f"**Комментарий:** {o.comment}")
                    
                    st.subheader("Позиции")
                    items_data = []
                    for item in o.items:
                        items_data.append({
                            "Продукт": item.product.name,
                            "Упаковка": f"{item.package_size} {item.package_unit.short_name}",
                            "Кол-во": item.package_count,
                            "Итого вес": item.total_quantity,
                            "Цена за упак": item.unit_price,
                            "Итого": item.total_price
                        })
                    st.table(items_data)
        else:
            st.info("Заказов пока нет")

# --- New Order Tab ---
with tabs[1]:
    st.header("Новый заказ")
    
    with SessionLocal() as db:
        all_products = {p.name: p for p in db.query(Product).all()}
        all_units = {u.short_name: u for u in db.query(Unit).all()}
        
        if not all_products:
            st.warning("Сначала добавьте продукты в Справочниках")
        else:
            with st.form("new_order_form"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    order_date = st.date_input("Дата заказа", value=date.today())
                with col2:
                    customer_name = st.text_input("Имя клиента")
                with col3:
                    customer_contact = st.text_input("Контакт (телефон/тг)")
                
                c4, c5, c6 = st.columns(3)
                with c4:
                    o_status = st.selectbox("Статус заказа", options=[s.value for s in OrderStatus])
                with c5:
                    p_status = st.selectbox("Статус оплаты", options=[s.value for s in PaymentStatus])
                with c6:
                    r_status = st.selectbox("Статус резерва", options=[s.value for s in ReservationStatus])
                
                delivery_cost = st.number_input("Стоимость доставки", min_value=0.0, step=10.0, format="%.2f")
                order_comment = st.text_area("Комментарий к заказу")
                
                st.subheader("Позиции (до 3 в MVP)")
                order_items = []
                for i in range(3):
                    st.markdown(f"**Позиция {i+1}**")
                    ca, cb, cc, cd, ce = st.columns([3, 2, 1, 2, 2])
                    with ca:
                        p_name = st.selectbox(f"Продукт {i}", options=[""] + list(all_products.keys()), key=f"oi_prod_{i}")
                    with cb:
                        p_size = st.number_input(f"Размер упак {i}", min_value=0.0, step=0.1, format="%.3f", key=f"oi_size_{i}")
                    with cc:
                        p_unit = st.selectbox(f"Ед {i}", options=list(all_units.keys()), key=f"oi_unit_{i}")
                    with cd:
                        p_count = st.number_input(f"Кол-во упак {i}", min_value=0, step=1, key=f"oi_count_{i}")
                    with ce:
                        p_price = st.number_input(f"Цена за упак {i}", min_value=0.0, step=50.0, format="%.2f", key=f"oi_price_{i}")
                    
                    if p_name and p_count > 0:
                        order_items.append(OrderItemInput(
                            product=all_products[p_name],
                            package_size=Decimal(str(p_size)),
                            package_unit=all_units[p_unit],
                            package_count=p_count,
                            unit_price=Decimal(str(p_price))
                        ))
                
                submitted = st.form_submit_button("Сохранить заказ")
                if submitted:
                    if not customer_name:
                        st.error("Укажите имя клиента")
                    elif not order_items:
                        st.error("Добавьте хотя бы одну позицию")
                    else:
                        try:
                            with SessionLocal() as db_write:
                                db_items = []
                                for item in order_items:
                                    db_items.append(OrderItemInput(
                                        product=db_write.merge(item.product),
                                        package_size=item.package_size,
                                        package_unit=db_write.merge(item.package_unit),
                                        package_count=item.package_count,
                                        unit_price=item.unit_price
                                    ))
                                
                                create_order(
                                    db_write,
                                    order_date=order_date,
                                    customer_name=customer_name,
                                    customer_contact=customer_contact,
                                    items=db_items,
                                    delivery_cost=Decimal(str(delivery_cost)),
                                    order_status=OrderStatus(o_status),
                                    payment_status=PaymentStatus(p_status),
                                    reservation_status=ReservationStatus(r_status),
                                    comment=order_comment
                                )
                                db_write.commit()
                                st.success(f"Заказ для '{customer_name}' успешно сохранен!")
                                st.rerun()
                        except Exception as e:
                            st.error(f"Ошибка при сохранении: {e}")
