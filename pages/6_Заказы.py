"""Streamlit page for managing customer orders."""

from __future__ import annotations

import streamlit as st
from decimal import Decimal
from datetime import date
from nutag.db.models import Product, Unit, OrderStatus, PaymentStatus, ReservationStatus
from nutag.db.runtime import create_app_database
from nutag.services.inventory import list_available_finished_product_outputs
from nutag.services.orders import create_order, delete_order, list_orders, OrderItemInput, update_order
from nutag.ui.auth import require_app_access


st.set_page_config(page_title="Заказы | Nutag", page_icon="🛍️", layout="wide")
require_app_access()

st.title("🛍️ Заказы")

# Session management
engine, SessionLocal = create_app_database()

tabs = st.tabs(["Список заказов", "Новый заказ"])


def enum_index(enum_cls, value) -> int:
    options = [item.value for item in enum_cls]
    current_value = value.value if hasattr(value, "value") else str(value)
    return options.index(current_value) if current_value in options else 0

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
                        batch_label = ""
                        if item.batch_output:
                            batch_label = (
                                f"Партия #{item.batch_output.batch_id}, "
                                f"выход #{item.batch_output_id}"
                            )
                        items_data.append({
                            "Продукт": item.product.name,
                            "Упаковка": f"{item.package_size} {item.package_unit.short_name}",
                            "Кол-во": item.package_count,
                            "Итого вес": item.total_quantity,
                            "Цена за упак": item.unit_price,
                            "Итого": item.total_price,
                            "Партия": batch_label or "Не выбрана",
                        })
                    st.table(items_data)

                    st.subheader("Редактирование заказа")
                    st.caption(
                        "В MVP можно изменить реквизиты, статусы, количество и продажную цену существующих строк. "
                        "Смена партии и добавление новых строк будут отдельной доработкой."
                    )
                    with st.form(f"edit_order_{o.id}"):
                        e_col1, e_col2, e_col3 = st.columns(3)
                        with e_col1:
                            edit_order_date = st.date_input(
                                "Дата заказа",
                                value=o.order_date,
                                key=f"edit_order_date_{o.id}",
                            )
                        with e_col2:
                            edit_customer_name = st.text_input(
                                "Имя клиента",
                                value=o.customer_name,
                                key=f"edit_customer_name_{o.id}",
                            )
                        with e_col3:
                            edit_customer_contact = st.text_input(
                                "Контакт",
                                value=o.customer_contact or "",
                                key=f"edit_customer_contact_{o.id}",
                            )

                        s_col1, s_col2, s_col3 = st.columns(3)
                        with s_col1:
                            edit_order_status = st.selectbox(
                                "Статус заказа",
                                options=[s.value for s in OrderStatus],
                                index=enum_index(OrderStatus, o.order_status),
                                key=f"edit_order_status_{o.id}",
                            )
                        with s_col2:
                            edit_payment_status = st.selectbox(
                                "Статус оплаты",
                                options=[s.value for s in PaymentStatus],
                                index=enum_index(PaymentStatus, o.payment_status),
                                key=f"edit_payment_status_{o.id}",
                            )
                        with s_col3:
                            edit_reservation_status = st.selectbox(
                                "Статус резерва",
                                options=[s.value for s in ReservationStatus],
                                index=enum_index(ReservationStatus, o.reservation_status),
                                key=f"edit_reservation_status_{o.id}",
                            )

                        edit_delivery_cost = st.number_input(
                            "Стоимость доставки",
                            min_value=0.0,
                            value=float(o.delivery_cost),
                            step=10.0,
                            format="%.2f",
                            key=f"edit_delivery_cost_{o.id}",
                        )
                        edit_comment = st.text_area(
                            "Комментарий",
                            value=o.comment or "",
                            key=f"edit_comment_{o.id}",
                        )

                        edited_lines = []
                        st.markdown("**Строки заказа**")
                        for idx, item in enumerate(o.items):
                            l_col1, l_col2, l_col3, l_col4 = st.columns([3, 3, 2, 2])
                            with l_col1:
                                st.write(item.product.name)
                                st.caption(
                                    f"{item.package_size:,.3f} {item.package_unit.short_name}"
                                )
                            with l_col2:
                                if item.batch_output:
                                    st.write(
                                        f"Партия #{item.batch_output.batch_id}, выход #{item.batch_output_id}"
                                    )
                                else:
                                    st.write("Партия не выбрана")
                            with l_col3:
                                edited_count = st.number_input(
                                    f"Кол-во фасовок {idx + 1}",
                                    min_value=1,
                                    value=int(item.package_count),
                                    step=1,
                                    key=f"edit_order_{o.id}_count_{item.id}",
                                )
                            with l_col4:
                                edited_price = st.number_input(
                                    f"Цена продажи за 1 фасовку {idx + 1}",
                                    min_value=0.0,
                                    value=float(item.unit_price),
                                    step=50.0,
                                    format="%.2f",
                                    key=f"edit_order_{o.id}_price_{item.id}",
                                )
                            edited_lines.append(
                                {
                                    "item_id": item.id,
                                    "count": edited_count,
                                    "price": Decimal(str(edited_price)),
                                }
                            )

                        submitted_edit = st.form_submit_button("Сохранить изменения")
                        if submitted_edit:
                            try:
                                with SessionLocal() as db_write:
                                    order_for_items = next(
                                        order for order in orders if order.id == o.id
                                    )
                                    db_items = []
                                    for edited_line in edited_lines:
                                        source_item = next(
                                            item
                                            for item in order_for_items.items
                                            if item.id == edited_line["item_id"]
                                        )
                                        db_items.append(
                                            OrderItemInput(
                                                product=db_write.merge(source_item.product),
                                                package_size=source_item.package_size,
                                                package_unit=db_write.merge(source_item.package_unit),
                                                package_count=edited_line["count"],
                                                unit_price=edited_line["price"],
                                                batch_output=(
                                                    db_write.merge(source_item.batch_output)
                                                    if source_item.batch_output
                                                    else None
                                                ),
                                                comment=source_item.comment,
                                            )
                                        )
                                    update_order(
                                        db_write,
                                        o.id,
                                        order_date=edit_order_date,
                                        customer_name=edit_customer_name,
                                        customer_contact=edit_customer_contact,
                                        items=db_items,
                                        delivery_cost=Decimal(str(edit_delivery_cost)),
                                        order_status=OrderStatus(edit_order_status),
                                        payment_status=PaymentStatus(edit_payment_status),
                                        reservation_status=ReservationStatus(edit_reservation_status),
                                        comment=edit_comment,
                                    )
                                    db_write.commit()
                                st.success("Заказ обновлён.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Ошибка при обновлении заказа: {e}")

                    st.subheader("Удаление заказа")
                    st.warning(
                        "Удаление уберёт заказ и освободит связанный резерв/списание в расчётах остатков."
                    )
                    with st.form(f"delete_order_{o.id}"):
                        confirmation = st.text_input(
                            "Для удаления введите УДАЛИТЬ",
                            key=f"delete_order_confirm_{o.id}",
                        )
                        submitted_delete = st.form_submit_button("Удалить заказ")
                        if submitted_delete:
                            if confirmation != "УДАЛИТЬ":
                                st.error("Введите УДАЛИТЬ для подтверждения удаления.")
                            else:
                                try:
                                    with SessionLocal() as db_write:
                                        delete_order(db_write, o.id)
                                        db_write.commit()
                                    st.success("Заказ удалён.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Ошибка при удалении заказа: {e}")
        else:
            st.info("Заказов пока нет")

# --- New Order Tab ---
with tabs[1]:
    st.header("Новый заказ")
    saved_message = st.session_state.pop("order_saved_message", None)
    if saved_message:
        st.success(saved_message)

    if "order_form_version" not in st.session_state:
        st.session_state.order_form_version = 0
    form_version = st.session_state.order_form_version

    def field_key(name: str, idx: int | None = None) -> str:
        suffix = f"_{idx}" if idx is not None else ""
        return f"order_{form_version}_{name}{suffix}"
    
    with SessionLocal() as db:
        all_products = {p.name: p for p in db.query(Product).all()}
        all_units = {u.short_name: u for u in db.query(Unit).all()}
        available_outputs = list_available_finished_product_outputs(db)
        available_output_options = {
            (
                f"{stock.product_name} | партия #{stock.output.batch_id}, выход #{stock.output_id} | "
                f"{stock.package_size} {stock.unit_short_name} | "
                f"доступно {stock.available_package_count:,.0f} уп. / {stock.available_quantity:,.3f} {stock.unit_short_name} | "
                f"факт {stock.physical_quantity:,.3f}, резерв {stock.reserved_quantity:,.3f} | "
                f"себестоимость {stock.unit_cost:,.4f}"
            ): stock
            for stock in available_outputs
        }
        
        if not all_products:
            st.warning("Сначала добавьте продукты в Справочниках")
        elif not available_output_options:
            st.warning("Нет доступных партий готовой продукции. Сначала выполните фасовку готовой продукции.")
        else:
            with st.container():
                col1, col2, col3 = st.columns(3)
                with col1:
                    order_date = st.date_input("Дата заказа", value=date.today(), key=field_key("date"))
                with col2:
                    customer_name = st.text_input("Имя клиента", key=field_key("customer"))
                with col3:
                    customer_contact = st.text_input("Контакт (телефон/тг)", key=field_key("contact"))
                
                c4, c5, c6 = st.columns(3)
                with c4:
                    o_status = st.selectbox("Статус заказа", options=[s.value for s in OrderStatus], key=field_key("order_status"))
                with c5:
                    p_status = st.selectbox("Статус оплаты", options=[s.value for s in PaymentStatus], key=field_key("payment_status"))
                with c6:
                    reservation_options = [s.value for s in ReservationStatus]
                    r_status = st.selectbox(
                        "Статус резерва",
                        options=reservation_options,
                        index=reservation_options.index(ReservationStatus.RESERVED.value),
                        key=field_key("reservation_status"),
                    )
                
                delivery_cost = st.number_input(
                    "Стоимость доставки",
                    min_value=0.0,
                    step=10.0,
                    format="%.2f",
                    key=field_key("delivery_cost"),
                )
                order_comment = st.text_area("Комментарий к заказу", key=field_key("comment"))
                
                st.subheader("Позиции (до 3 в MVP)")
                order_items = []
                validation_errors: list[str] = []
                requested_output_quantities: dict[int, Decimal] = {}
                outputs_by_id = {stock.output_id: stock for stock in available_outputs}
                for i in range(3):
                    st.markdown(f"**Позиция {i+1}**")
                    ca, cb, cc, cd, ce = st.columns([3, 5, 2, 2, 2])
                    with ca:
                        p_name = st.selectbox(
                            f"Продукт {i + 1}",
                            options=[""] + list(all_products.keys()),
                            key=field_key("product", i),
                        )
                    matching_output_options = []
                    if p_name:
                        matching_output_options = [
                            label
                            for label, stock in available_output_options.items()
                            if stock.product_id == all_products[p_name].id
                        ]
                    with cb:
                        output_label = st.selectbox(
                            f"Партия готовой продукции {i + 1}",
                            options=[""] + matching_output_options,
                            key=f"{field_key('output', i)}_{all_products[p_name].id if p_name else 'none'}",
                            help="Выберите конкретную доступную партию готовой продукции, если заказ списывается из наличия.",
                        )
                        if p_name and not matching_output_options:
                            st.caption("Нет доступных партий для выбранного продукта.")
                    selected_stock = available_output_options.get(output_label) if output_label else None
                    with cc:
                        st.caption(f"Фасовка {i + 1}")
                        if selected_stock:
                            st.write(f"{selected_stock.package_size:,.3f} {selected_stock.unit_short_name}")
                            package_cost = (
                                Decimal(str(selected_stock.package_size))
                                * Decimal(str(selected_stock.unit_cost))
                            )
                            st.caption(
                                f"Доступно: {selected_stock.available_quantity:,.3f}; "
                                f"резерв: {selected_stock.reserved_quantity:,.3f}; "
                                f"факт: {selected_stock.physical_quantity:,.3f}"
                            )
                            st.caption(f"Себестоимость: {package_cost:,.2f}")
                        else:
                            st.write("-")
                    with cd:
                        p_count = st.number_input(
                            f"Кол-во фасовок {i + 1}",
                            min_value=0,
                            step=1,
                            key=field_key("package_count", i),
                        )
                    with ce:
                        p_price = st.number_input(
                            f"Цена продажи за 1 фасовку {i + 1}",
                            min_value=0.0,
                            step=50.0,
                            format="%.2f",
                            key=field_key("unit_price", i),
                        )
                    
                    row_is_active = bool(p_name) or p_count > 0 or p_price > 0 or bool(output_label)
                    if not row_is_active:
                        continue

                    row_label = f"Позиция {i + 1}"
                    if not p_name:
                        validation_errors.append(f"{row_label}: выберите продукт или очистите строку.")
                        continue
                    if p_count <= 0:
                        validation_errors.append(f"{row_label}: укажите количество фасовок больше 0.")
                        continue
                    if not output_label:
                        validation_errors.append(f"{row_label}: выберите партию готовой продукции.")
                        continue
                    if selected_stock is None:
                        validation_errors.append(f"{row_label}: выбранная партия готовой продукции недоступна.")
                        continue
                    if selected_stock.unit_short_name not in all_units:
                        validation_errors.append(
                            f"{row_label}: единица партии '{selected_stock.unit_short_name}' отсутствует в справочнике."
                        )
                        continue

                    selected_output = selected_stock.output
                    requested_quantity = Decimal(str(selected_stock.package_size)) * Decimal(p_count)
                    requested_output_quantities[selected_stock.output_id] = (
                        requested_output_quantities.get(selected_stock.output_id, Decimal("0"))
                        + requested_quantity
                    )
                    order_items.append(
                        OrderItemInput(
                            product=all_products[p_name],
                            package_size=Decimal(str(selected_stock.package_size)),
                            package_unit=all_units[selected_stock.unit_short_name],
                            package_count=p_count,
                            unit_price=Decimal(str(p_price)),
                            batch_output=selected_output,
                        )
                    )

                for output_id, requested_quantity in requested_output_quantities.items():
                    available_quantity = Decimal(str(outputs_by_id[output_id].available_quantity))
                    if requested_quantity > available_quantity:
                        stock = outputs_by_id[output_id]
                        validation_errors.append(
                            f"Суммарное количество по партии готовой продукции #{output_id} больше доступно к продаже "
                            f"({stock.available_quantity:,.3f} {stock.unit_short_name})."
                        )
                
                submitted = st.button("Сохранить заказ", key=field_key("submit"))
                if submitted:
                    submit_errors = []
                    if not customer_name.strip():
                        submit_errors.append("Укажите имя клиента.")
                    if not order_items and not validation_errors:
                        submit_errors.append("Добавьте хотя бы одну позицию.")
                    submit_errors.extend(validation_errors)

                    if submit_errors:
                        for error in submit_errors:
                            st.error(error)
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
                                        unit_price=item.unit_price,
                                        batch_output=db_write.merge(item.batch_output) if item.batch_output else None,
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
                                st.session_state.order_form_version += 1
                                st.session_state.order_saved_message = f"Заказ для '{customer_name.strip()}' успешно сохранен!"
                                st.rerun()
                        except Exception as e:
                            st.error(f"Ошибка при сохранении: {e}")
