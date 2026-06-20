"""Streamlit page for managing purchases and viewing inventory balances."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import streamlit as st

from nutag.db.init_db import initialize_database
from nutag.db.models import Consumable, Ingredient, Packaging, PurchaseItemType, Unit
from nutag.db.session import create_engine_for_url, create_session_factory
from nutag.services.inventory import list_available_stock_batches, list_inventory_balances
from nutag.services.purchases import (
    PurchaseLineInput,
    create_purchase,
    delete_purchase,
    list_purchases,
    purchase_has_stock_usage,
    update_purchase,
)


def make_empty_purchase_row(default_unit: str) -> dict[str, object]:
    """Return one empty purchase row."""

    return {
        "type": PurchaseItemType.INGREDIENT.value,
        "name": "",
        "unit": default_unit,
        "qty": 0.0,
        "price_unit": 0.0,
        "price_total": 0.0,
    }


def make_default_purchase_rows(default_unit: str) -> list[dict[str, object]]:
    """Return initial purchase rows for the purchase form."""

    return [make_empty_purchase_row(default_unit)]


def get_catalog_unit_name(
    *,
    row_type: str,
    row_name: str,
    ingredient_units: dict[str, str],
    packaging_units: dict[str, str],
    consumable_units: dict[str, str],
) -> str | None:
    """Return the fixed unit name from the selected catalog item."""

    if row_type == PurchaseItemType.INGREDIENT.value:
        return ingredient_units.get(row_name)
    if row_type == PurchaseItemType.PACKAGING.value:
        return packaging_units.get(row_name)
    if row_type == PurchaseItemType.CONSUMABLE.value:
        return consumable_units.get(row_name)
    return None


st.set_page_config(page_title="Закупки и остатки | Nutag", page_icon="📦", layout="wide")

st.title("📦 Закупки и остатки")

# Session management
engine = create_engine_for_url()
initialize_database(engine)
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
                df_data.append(
                    {
                        "Тип": b.item_type,
                        "Наименование": b.item_name,
                        "Закуплено/Сделано": f"{b.inflow_quantity:,.3f}",
                        "Использовано": f"{b.outflow_quantity:,.3f}",
                        "Остаток": f"{b.current_quantity:,.3f}",
                        "Ед.изм.": b.unit_short_name,
                        "Средняя цена": f"{b.weighted_average_price:,.2f}",
                        "Стоимость остатка": f"{(b.current_quantity * b.weighted_average_price):,.2f}",
                    }
                )
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
                df_batch_data.append(
                    {
                        "Дата": b.date,
                        "Тип": b.item_type,
                        "Наименование": b.item_name,
                        "Партия": f"#{b.batch_id} ({b.batch_type})",
                        "Начальное кол-во": f"{b.initial_quantity:,.3f}",
                        "Текущий остаток": f"{b.current_quantity:,.3f}",
                        "Ед.изм.": b.unit_short_name,
                        "Цена партии": f"{b.unit_price:,.2f}",
                    }
                )
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
                        items_data.append(
                            {
                                "№": item.line_number,
                                "Наименование": item.item_name,
                                "Кол-во": item.quantity,
                                "Ед.изм.": item.unit.short_name,
                                "Цена": item.unit_price,
                                "Итого": item.total_price,
                            }
                        )
                    st.table(items_data)

                    if purchase_has_stock_usage(db, p):
                        st.warning(
                            "Редактирование и удаление заблокированы: одна или несколько партий из этой закупки уже использованы."
                        )
                    else:
                        st.info(
                            "Можно исправить дату, поставщика, закупившего, транспорт, комментарий, количество и цену. "
                            "Состав строк пока фиксированный."
                        )
                        with st.form(f"edit_purchase_{p.id}"):
                            def validate_edited_purchase() -> list[str]:
                                errors = []
                                if edit_purchase_date > date.today():
                                    errors.append("Дата закупки не может быть в будущем.")
                                if not edited_lines:
                                    errors.append("В закупке должна быть хотя бы одна позиция.")

                                for line_index, line in enumerate(edited_lines, start=1):
                                    quantity = Decimal(str(line.quantity))
                                    unit_price = Decimal(str(line.unit_price))
                                    if quantity <= 0:
                                        errors.append(f"Строка {line_index}: количество должно быть больше 0.")
                                    if unit_price < 0:
                                        errors.append(f"Строка {line_index}: цена за единицу не может быть отрицательной.")

                                return errors

                            edit_col1, edit_col2, edit_col3 = st.columns(3)
                            with edit_col1:
                                edit_purchase_date = st.date_input(
                                    "Дата закупки",
                                    value=p.purchase_date,
                                    key=f"edit_purchase_date_{p.id}",
                                )
                            with edit_col2:
                                edit_supplier = st.text_input(
                                    "Поставщик",
                                    value=p.supplier or "",
                                    key=f"edit_supplier_{p.id}",
                                )
                            with edit_col3:
                                edit_purchased_by = st.text_input(
                                    "Кто закупил",
                                    value=p.purchased_by or "",
                                    key=f"edit_purchased_by_{p.id}",
                                )

                            edit_transport_cost = st.number_input(
                                "Транспортные расходы",
                                min_value=0.0,
                                step=10.0,
                                format="%.2f",
                                value=float(p.transport_cost),
                                key=f"edit_transport_cost_{p.id}",
                            )
                            edit_comment = st.text_area(
                                "Комментарий",
                                value=p.comment or "",
                                key=f"edit_comment_{p.id}",
                            )

                            edited_lines = []
                            st.markdown("**Позиции закупки**")
                            for item in p.items:
                                line_col1, line_col2, line_col3, line_col4, line_col5 = st.columns([3, 1, 1, 1, 1])
                                with line_col1:
                                    st.text_input(
                                        f"Позиция {item.line_number}",
                                        value=item.item_name,
                                        disabled=True,
                                        key=f"edit_item_name_{item.id}",
                                    )
                                with line_col2:
                                    edit_quantity = st.number_input(
                                        f"Кол-во {item.line_number}",
                                        min_value=0.001,
                                        step=0.1,
                                        format="%.3f",
                                        value=float(item.quantity),
                                        key=f"edit_item_qty_{item.id}",
                                    )
                                with line_col3:
                                    st.text_input(
                                        f"Ед. {item.line_number}",
                                        value=item.unit.short_name,
                                        disabled=True,
                                        key=f"edit_item_unit_{item.id}",
                                    )
                                with line_col4:
                                    edit_unit_price = st.number_input(
                                        f"Цена/ед {item.line_number}",
                                        min_value=0.0,
                                        step=1.0,
                                        format="%.2f",
                                        value=float(item.unit_price),
                                        key=f"edit_item_price_{item.id}",
                                    )
                                with line_col5:
                                    st.metric(
                                        f"Итого {item.line_number}",
                                        f"{Decimal(str(edit_quantity)) * Decimal(str(edit_unit_price)):,.2f}",
                                    )

                                edited_lines.append(
                                    PurchaseLineInput(
                                        item_type=PurchaseItemType(item.item_type),
                                        item_name=item.item_name,
                                        unit=item.unit,
                                        quantity=Decimal(str(edit_quantity)),
                                        unit_price=Decimal(str(edit_unit_price)),
                                        ingredient=item.ingredient,
                                        packaging=item.packaging,
                                        consumable=item.consumable,
                                        expires_on=item.expires_on,
                                        comment=item.comment,
                                    )
                                )

                            if st.form_submit_button("Сохранить изменения"):
                                validation_errors = validate_edited_purchase()
                                if validation_errors:
                                    for error in validation_errors:
                                        st.error(error)
                                else:
                                    try:
                                        update_purchase(
                                            db,
                                            p.id,
                                            purchase_date=edit_purchase_date,
                                            lines=edited_lines,
                                            supplier=edit_supplier or None,
                                            purchased_by=edit_purchased_by or None,
                                            shopping_minutes=p.shopping_minutes,
                                            transport_cost=Decimal(str(edit_transport_cost)),
                                            comment=edit_comment or None,
                                        )
                                        db.commit()
                                        st.success("Закупка обновлена.")
                                        st.rerun()
                                    except Exception as e:
                                        db.rollback()
                                        st.error(f"Ошибка при обновлении закупки: {e}")

                        with st.form(f"delete_purchase_{p.id}"):
                            confirm_delete = st.checkbox(
                                "Подтверждаю удаление этой закупки",
                                key=f"confirm_delete_purchase_{p.id}",
                            )
                            if st.form_submit_button("Удалить закупку"):
                                if not confirm_delete:
                                    st.error("Для удаления отметьте подтверждение.")
                                else:
                                    try:
                                        delete_purchase(db, p.id)
                                        db.commit()
                                        st.success("Закупка удалена.")
                                        st.rerun()
                                    except Exception as e:
                                        db.rollback()
                                        st.error(f"Ошибка при удалении закупки: {e}")
        else:
            st.info("История закупок пуста")

# --- New Purchase Tab ---
with tabs[3]:
    st.header("Новая закупка")

    with SessionLocal() as db:
        ingredients = {i.name: i for i in db.query(Ingredient).all()}
        packaging = {p.name: p for p in db.query(Packaging).all()}
        consumables = {c.name: c for c in db.query(Consumable).all()}
        ingredient_units = {i.name: i.unit.short_name for i in db.query(Ingredient).all()}
        packaging_units = {p.name: p.unit.short_name for p in db.query(Packaging).all()}
        consumable_units = {c.name: c.unit.short_name for c in db.query(Consumable).all()}
        units = {u.short_name: u for u in db.query(Unit).all()}

        if not units:
            st.warning("Сначала добавьте единицы измерения в Справочниках")
        else:
            default_unit = list(units.keys())[0]
            if "purchase_form_version" not in st.session_state:
                st.session_state.purchase_form_version = 0
            if "purchase_rows" not in st.session_state:
                st.session_state.purchase_rows = make_default_purchase_rows(default_unit)
            elif len(st.session_state.purchase_rows) > 1 and not any(
                row["name"] or row["qty"] > 0 or row["price_unit"] > 0 or row["price_total"] > 0
                for row in st.session_state.purchase_rows
            ):
                st.session_state.purchase_rows = make_default_purchase_rows(default_unit)

            form_version = st.session_state.purchase_form_version

            def field_key(name: str, idx: int | None = None) -> str:
                suffix = f"_{idx}" if idx is not None else ""
                return f"purchase_{form_version}_{name}{suffix}"

            col1, col2, col3 = st.columns(3)
            with col1:
                purchase_date = st.date_input("Дата закупки", value=date.today(), key=field_key("date"))
            with col2:
                supplier = st.text_input("Поставщик", key=field_key("supplier"))
            with col3:
                purchased_by = st.text_input("Кто закупил", key=field_key("purchased_by"))

            transport_cost = st.number_input(
                "Транспортные расходы",
                min_value=0.0,
                step=10.0,
                format="%.2f",
                key=field_key("transport_cost"),
            )
            comment = st.text_area("Общий комментарий", key=field_key("comment"))

            st.subheader("Позиции")

            def sync_row(idx: int, *, sync_unit_widget: bool = True) -> None:
                st.session_state.purchase_rows[idx]["type"] = st.session_state[field_key("type_sel", idx)]
                st.session_state.purchase_rows[idx]["unit"] = st.session_state[field_key("unit_sel", idx)]
                st.session_state.purchase_rows[idx]["qty"] = st.session_state[field_key("qty_val", idx)]
                st.session_state.purchase_rows[idx]["price_unit"] = st.session_state[field_key("price_unit_val", idx)]
                st.session_state.purchase_rows[idx]["price_total"] = st.session_state[field_key("price_total_val", idx)]

                if st.session_state.purchase_rows[idx]["type"] == PurchaseItemType.INGREDIENT.value:
                    st.session_state.purchase_rows[idx]["name"] = st.session_state.get(field_key("name_sel", idx), "")
                elif st.session_state.purchase_rows[idx]["type"] == PurchaseItemType.PACKAGING.value:
                    st.session_state.purchase_rows[idx]["name"] = st.session_state.get(field_key("name_sel_pkg", idx), "")
                elif st.session_state.purchase_rows[idx]["type"] == PurchaseItemType.CONSUMABLE.value:
                    st.session_state.purchase_rows[idx]["name"] = st.session_state.get(field_key("name_sel_cons", idx), "")
                else:
                    st.session_state.purchase_rows[idx]["name"] = st.session_state.get(field_key("name_txt", idx), "")

                fixed_unit = get_catalog_unit_name(
                    row_type=st.session_state.purchase_rows[idx]["type"],
                    row_name=st.session_state.purchase_rows[idx]["name"],
                    ingredient_units=ingredient_units,
                    packaging_units=packaging_units,
                    consumable_units=consumable_units,
                )
                if fixed_unit:
                    st.session_state.purchase_rows[idx]["unit"] = fixed_unit
                    if sync_unit_widget:
                        st.session_state[field_key("unit_sel", idx)] = fixed_unit

            def update_total(idx: int) -> None:
                sync_row(idx)
                row = st.session_state.purchase_rows[idx]
                st.session_state.purchase_rows[idx]["price_total"] = float(
                    round(Decimal(str(row["qty"])) * Decimal(str(row["price_unit"])), 2)
                )
                st.session_state[field_key("price_total_val", idx)] = st.session_state.purchase_rows[idx]["price_total"]

            def update_unit(idx: int) -> None:
                sync_row(idx)
                row = st.session_state.purchase_rows[idx]
                if row["qty"] > 0:
                    st.session_state.purchase_rows[idx]["price_unit"] = float(
                        round(Decimal(str(row["price_total"])) / Decimal(str(row["qty"])), 2)
                    )
                    st.session_state[field_key("price_unit_val", idx)] = st.session_state.purchase_rows[idx]["price_unit"]

            def validate_purchase_rows(rows: list[dict[str, object]]) -> list[str]:
                errors = []
                active_rows = 0

                for idx, row in enumerate(rows, start=1):
                    name = str(row["name"]).strip()
                    qty = Decimal(str(row["qty"]))
                    unit_price = Decimal(str(row["price_unit"]))
                    price_total = Decimal(str(row["price_total"]))
                    row_started = bool(name) or qty > 0 or unit_price > 0 or price_total > 0

                    if not row_started:
                        continue

                    active_rows += 1
                    if not name:
                        errors.append(f"Строка {idx}: выберите позицию.")
                    if qty <= 0:
                        errors.append(f"Строка {idx}: количество должно быть больше 0.")
                    if unit_price < 0:
                        errors.append(f"Строка {idx}: цена за единицу не может быть отрицательной.")
                    if price_total < 0:
                        errors.append(f"Строка {idx}: итоговая сумма не может быть отрицательной.")
                    if qty > 0 and abs((qty * unit_price) - price_total) > Decimal("0.01"):
                        errors.append(f"Строка {idx}: цена за единицу и итоговая сумма не согласованы.")

                if active_rows == 0:
                    errors.append("Добавьте хотя бы одну заполненную позицию.")

                return errors

            control_col1, control_col2, _ = st.columns([1, 1, 4])
            with control_col1:
                if st.button("Добавить строку", key=field_key("add_row")):
                    st.session_state.purchase_rows.append(make_empty_purchase_row(default_unit))
                    st.rerun()
            with control_col2:
                if st.button(
                    "Удалить последнюю",
                    key=field_key("remove_last_row"),
                    disabled=len(st.session_state.purchase_rows) == 1,
                ):
                    st.session_state.purchase_rows.pop()
                    st.rerun()

            for i in range(len(st.session_state.purchase_rows)):
                st.markdown(f"**Позиция {i + 1}**")
                c1, c2, c3, c4, c5, c6 = st.columns([2, 3, 1, 1, 2, 2])

                row = st.session_state.purchase_rows[i]
                fixed_unit = get_catalog_unit_name(
                    row_type=row["type"],
                    row_name=row["name"],
                    ingredient_units=ingredient_units,
                    packaging_units=packaging_units,
                    consumable_units=consumable_units,
                )
                if fixed_unit and row["unit"] != fixed_unit:
                    row["unit"] = fixed_unit
                    st.session_state.purchase_rows[i]["unit"] = fixed_unit
                    st.session_state[field_key("unit_sel", i)] = fixed_unit

                with c1:
                    st.selectbox(
                        f"Тип {i}",
                        options=[t.value for t in PurchaseItemType],
                        index=[t.value for t in PurchaseItemType].index(row["type"]),
                        key=field_key("type_sel", i),
                        on_change=sync_row,
                        args=(i,),
                    )
                with c2:
                    if row["type"] == PurchaseItemType.INGREDIENT.value:
                        name_options = [""] + list(ingredients.keys())
                        st.selectbox(
                            f"Ингредиент {i}",
                            options=name_options,
                            index=name_options.index(row["name"]) if row["name"] in name_options else 0,
                            key=field_key("name_sel", i),
                            on_change=sync_row,
                            args=(i,),
                        )
                    elif row["type"] == PurchaseItemType.PACKAGING.value:
                        name_options = [""] + list(packaging.keys())
                        st.selectbox(
                            f"Упаковка {i}",
                            options=name_options,
                            index=name_options.index(row["name"]) if row["name"] in name_options else 0,
                            key=field_key("name_sel_pkg", i),
                            on_change=sync_row,
                            args=(i,),
                        )
                    elif row["type"] == PurchaseItemType.CONSUMABLE.value:
                        name_options = [""] + list(consumables.keys())
                        st.selectbox(
                            f"Расходник {i}",
                            options=name_options,
                            index=name_options.index(row["name"]) if row["name"] in name_options else 0,
                            key=field_key("name_sel_cons", i),
                            on_change=sync_row,
                            args=(i,),
                        )
                    else:
                        st.text_input(
                            f"Наименование {i}",
                            value=row["name"],
                            key=field_key("name_txt", i),
                            on_change=sync_row,
                            args=(i,),
                        )

                with c3:
                    st.selectbox(
                        f"Ед {i}",
                        options=list(units.keys()),
                        index=list(units.keys()).index(row["unit"]) if row["unit"] in units else 0,
                        key=field_key("unit_sel", i),
                        on_change=sync_row,
                        args=(i,),
                        disabled=fixed_unit is not None,
                    )
                with c4:
                    st.number_input(
                        f"Кол-во {i}",
                        min_value=0.0,
                        step=0.1,
                        format="%.3f",
                        value=row["qty"],
                        key=field_key("qty_val", i),
                        on_change=update_total,
                        args=(i,),
                    )
                with c5:
                    st.number_input(
                        f"Цена/ед {i}",
                        min_value=0.0,
                        step=1.0,
                        format="%.2f",
                        value=row["price_unit"],
                        key=field_key("price_unit_val", i),
                        on_change=update_total,
                        args=(i,),
                    )
                with c6:
                    st.number_input(
                        f"Итого {i}",
                        min_value=0.0,
                        step=1.0,
                        format="%.2f",
                        value=row["price_total"],
                        key=field_key("price_total_val", i),
                        on_change=update_unit,
                        args=(i,),
                    )

            if st.button("Сохранить закупку", type="primary", key=field_key("save")):
                for idx in range(len(st.session_state.purchase_rows)):
                    sync_row(idx, sync_unit_widget=False)

                validation_errors = validate_purchase_rows(st.session_state.purchase_rows)
                lines = []
                for r in st.session_state.purchase_rows:
                    if r["name"] and r["qty"] > 0:
                        ing = ingredients.get(r["name"]) if r["type"] == PurchaseItemType.INGREDIENT.value else None
                        pkg = packaging.get(r["name"]) if r["type"] == PurchaseItemType.PACKAGING.value else None
                        cons = consumables.get(r["name"]) if r["type"] == PurchaseItemType.CONSUMABLE.value else None

                        lines.append(
                            PurchaseLineInput(
                                item_type=PurchaseItemType(r["type"]),
                                item_name=r["name"],
                                unit=units[r["unit"]],
                                quantity=Decimal(str(r["qty"])),
                                unit_price=Decimal(str(r["price_unit"])),
                                ingredient=ing,
                                packaging=pkg,
                                consumable=cons,
                            )
                        )

                if validation_errors:
                    for error in validation_errors:
                        st.error(error)
                else:
                    try:
                        with SessionLocal() as db_write:
                            db_lines = []
                            for line in lines:
                                db_lines.append(
                                    PurchaseLineInput(
                                        item_type=line.item_type,
                                        item_name=line.item_name,
                                        unit=db_write.merge(line.unit),
                                        quantity=line.quantity,
                                        unit_price=line.unit_price,
                                        ingredient=db_write.merge(line.ingredient) if line.ingredient else None,
                                        packaging=db_write.merge(line.packaging) if line.packaging else None,
                                        consumable=db_write.merge(line.consumable) if line.consumable else None,
                                    )
                                )

                            create_purchase(
                                db_write,
                                purchase_date=purchase_date,
                                lines=db_lines,
                                supplier=supplier,
                                purchased_by=purchased_by,
                                transport_cost=Decimal(str(transport_cost)),
                                comment=comment,
                            )
                            db_write.commit()
                            st.session_state.purchase_form_version += 1
                            st.session_state.purchase_rows = make_default_purchase_rows(default_unit)
                            st.success("Закупка успешно сохранена!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Ошибка при сохранении: {e}")
