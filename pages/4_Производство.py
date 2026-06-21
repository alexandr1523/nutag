"""Streamlit page for managing final production batches."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import streamlit as st

from nutag.db.init_db import initialize_database
from nutag.db.models import Equipment, Ingredient, LaborRate, Preparation, Product, PurchaseItemType, Unit
from nutag.db.session import create_engine_for_url, create_session_factory
from nutag.services.inventory import ExtendedItemType, list_available_stock_batches
from nutag.services.preparations import list_preparations
from nutag.services.production import (
    BatchIngredientInput,
    BatchPreparationInput,
    create_production_batch,
    is_production_batch_used,
    list_production_batches,
    update_production_batch,
)


def build_batch_option_label(batch) -> str:
    """Build a unique label for stock batch selectors."""

    return f"{batch.date} - {batch.item_name} (Остаток: {batch.current_quantity} {batch.unit_short_name}, ID: {batch.batch_id})"


def format_money(value: Decimal) -> str:
    """Format money values for read-only UI fields."""

    return f"{value:,.2f}"


st.set_page_config(page_title="Производство | Nutag", page_icon="🏭", layout="wide")

st.title("🏭 Производство")

# Session management
engine = create_engine_for_url()
initialize_database(engine)
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

                    st.subheader("Нефасованный выпуск")
                    bulk_data = []
                    for out in b.bulk_outputs:
                        bulk_data.append(
                            {
                                "Количество": out.quantity,
                                "Ед.изм.": out.unit.short_name,
                                "Место хранения": out.storage_place or "",
                                "Годен до": out.use_by or "",
                            }
                        )
                    st.table(bulk_data)

                    st.subheader("Затраты")
                    uses_data = []
                    for use in b.ingredient_uses:
                        source_info = f" (Партия #{use.purchase_item_id})" if use.purchase_item_id else ""
                        uses_data.append(
                            {
                                "Тип": "Ингредиент",
                                "Наименование": use.ingredient.name + source_info,
                                "Кол-во": use.quantity,
                                "Ед": use.unit.short_name,
                                "Цена": use.unit_cost,
                                "Итого": use.total_cost,
                            }
                        )
                    for use in b.preparation_uses:
                        source_info = f" (Заготовка #{use.source_preparation_id})" if use.source_preparation_id else ""
                        uses_data.append(
                            {
                                "Тип": "Заготовка",
                                "Наименование": use.preparation.name + source_info,
                                "Кол-во": use.quantity,
                                "Ед": use.unit.short_name,
                                "Цена": use.unit_cost,
                                "Итого": use.total_cost,
                            }
                        )
                    st.table(uses_data)

                    if is_production_batch_used(db, b.id):
                        st.warning("Партия уже использована в фасовке, корректировка недоступна.")
                    else:
                        with st.expander("Редактировать партию"):
                            edit_available_batches = list_available_stock_batches(db)
                            edit_ing_batches = [
                                batch
                                for batch in edit_available_batches
                                if batch.item_type == PurchaseItemType.INGREDIENT
                            ]
                            edit_prep_batches = [
                                batch
                                for batch in edit_available_batches
                                if batch.item_type == ExtendedItemType.PREPARATION
                            ]
                            edit_ing_batches_by_id = {batch.batch_id: batch for batch in edit_ing_batches}
                            edit_prep_batches_by_id = {batch.batch_id: batch for batch in edit_prep_batches}

                            for use in b.ingredient_uses:
                                if use.purchase_item_id is None or use.purchase_item is None:
                                    continue
                                if use.purchase_item_id in edit_ing_batches_by_id:
                                    batch = edit_ing_batches_by_id[use.purchase_item_id]
                                    edit_ing_batches_by_id[use.purchase_item_id] = SimpleNamespace(
                                        batch_id=batch.batch_id,
                                        item_id=batch.item_id,
                                        item_name=batch.item_name,
                                        date=batch.date,
                                        unit_short_name=batch.unit_short_name,
                                        current_quantity=batch.current_quantity + use.quantity,
                                        unit_price=batch.unit_price,
                                    )
                                else:
                                    edit_ing_batches_by_id[use.purchase_item_id] = SimpleNamespace(
                                        batch_id=use.purchase_item_id,
                                        item_id=use.ingredient_id,
                                        item_name=use.ingredient.name,
                                        date=use.purchase_item.purchase.purchase_date,
                                        unit_short_name=use.unit.short_name,
                                        current_quantity=use.quantity,
                                        unit_price=use.purchase_item.unit_price,
                                    )

                            for use in b.preparation_uses:
                                source_preparation = use.source_preparation
                                if use.source_preparation_id is None or source_preparation is None:
                                    continue
                                if use.source_preparation_id in edit_prep_batches_by_id:
                                    batch = edit_prep_batches_by_id[use.source_preparation_id]
                                    edit_prep_batches_by_id[use.source_preparation_id] = SimpleNamespace(
                                        batch_id=batch.batch_id,
                                        item_id=batch.item_id,
                                        item_name=batch.item_name,
                                        date=batch.date,
                                        unit_short_name=batch.unit_short_name,
                                        current_quantity=batch.current_quantity + use.quantity,
                                        unit_price=batch.unit_price,
                                    )
                                else:
                                    edit_prep_batches_by_id[use.source_preparation_id] = SimpleNamespace(
                                        batch_id=use.source_preparation_id,
                                        item_id=source_preparation.name,
                                        item_name=source_preparation.name,
                                        date=source_preparation.prepared_on,
                                        unit_short_name=source_preparation.output_unit.short_name,
                                        current_quantity=use.quantity,
                                        unit_price=source_preparation.unit_cost,
                                    )

                            edit_ing_batch_options = {
                                (
                                    f"#{batch.batch_id} {batch.date} - {batch.item_name} "
                                    f"(Доступно для корректировки: {batch.current_quantity} {batch.unit_short_name})"
                                ): batch
                                for batch in sorted(
                                    edit_ing_batches_by_id.values(),
                                    key=lambda batch: (batch.item_name, batch.date, batch.batch_id),
                                )
                            }
                            edit_prep_batch_options = {
                                (
                                    f"#{batch.batch_id} {batch.date} - {batch.item_name} "
                                    f"(Доступно для корректировки: {batch.current_quantity} {batch.unit_short_name})"
                                ): batch
                                for batch in sorted(
                                    edit_prep_batches_by_id.values(),
                                    key=lambda batch: (batch.item_name, batch.date, batch.batch_id),
                                )
                            }
                            edit_all_products = {
                                product.name: product for product in db.query(Product).order_by(Product.name).all()
                            }
                            edit_all_units = {unit.short_name: unit for unit in db.query(Unit).all()}
                            edit_unit_names = list(edit_all_units.keys())
                            edit_all_ingredients = {ingredient.id: ingredient for ingredient in db.query(Ingredient).all()}
                            edit_ingredient_options = {
                                ingredient.name: ingredient
                                for ingredient in sorted(edit_all_ingredients.values(), key=lambda ingredient: ingredient.name)
                            }
                            edit_preparations = {preparation.id: preparation for preparation in list_preparations(db)}
                            edit_prep_names = sorted({batch.item_name for batch in edit_prep_batches_by_id.values()})

                            def edit_key(name: str, idx: int | None = None) -> str:
                                suffix = f"_{idx}" if idx is not None else ""
                                return f"production_edit_{b.id}_{name}{suffix}"

                            ec1, ec2, ec3 = st.columns(3)
                            with ec1:
                                edit_date = st.date_input(
                                    "Дата производства",
                                    value=b.produced_on,
                                    key=edit_key("date"),
                                )
                            with ec2:
                                product_names = list(edit_all_products.keys())
                                edit_product_name = st.selectbox(
                                    "Продукт",
                                    options=product_names,
                                    index=product_names.index(b.product.name) if b.product.name in product_names else 0,
                                    key=edit_key("product"),
                                )
                            with ec3:
                                edit_comment = st.text_area(
                                    "Комментарий",
                                    value=b.comment or "",
                                    key=edit_key("comment"),
                                )

                            eo1, eo2, eo3, eo4 = st.columns(4)
                            with eo1:
                                edit_actual_qty = st.number_input(
                                    "Фактический выход",
                                    min_value=0.0,
                                    step=0.1,
                                    format="%.3f",
                                    value=float(b.actual_output_quantity),
                                    key=edit_key("actual_qty"),
                                )
                            with eo2:
                                edit_output_unit = st.selectbox(
                                    "Ед. изм. выхода",
                                    options=edit_unit_names,
                                    index=edit_unit_names.index(b.output_unit.short_name)
                                    if b.output_unit.short_name in edit_unit_names
                                    else 0,
                                    key=edit_key("output_unit"),
                                )
                            with eo3:
                                edit_labor_cost = st.number_input(
                                    "Труд (сумма)",
                                    min_value=0.0,
                                    step=10.0,
                                    format="%.2f",
                                    value=float(b.labor_cost),
                                    key=edit_key("labor_cost"),
                                )
                            with eo4:
                                edit_overhead = st.number_input(
                                    "Накладные расходы",
                                    min_value=0.0,
                                    step=10.0,
                                    format="%.2f",
                                    value=float(b.allocated_overhead),
                                    key=edit_key("overhead"),
                                )

                            edit_ingredient_uses = []
                            edit_preparation_uses = []
                            edit_validation_errors: list[str] = []
                            edit_requested_ing_by_batch: dict[int, Decimal] = {}
                            edit_requested_prep_by_batch: dict[int, Decimal] = {}

                            st.subheader("Ингредиенты")
                            edit_ing_rows = list(b.ingredient_uses)
                            for idx in range(max(3, len(edit_ing_rows))):
                                existing_use = edit_ing_rows[idx] if idx < len(edit_ing_rows) else None
                                ca, cb, cc, cd, ce = st.columns([3, 4, 1, 2, 2])
                                ingredient_names = [""] + list(edit_ingredient_options.keys())
                                current_ingredient_name = existing_use.ingredient.name if existing_use else ""
                                with ca:
                                    edit_ingredient_name = st.selectbox(
                                        f"Ингредиент {idx + 1}",
                                        options=ingredient_names,
                                        index=ingredient_names.index(current_ingredient_name)
                                        if current_ingredient_name in ingredient_names
                                        else 0,
                                        key=edit_key("ingredient", idx),
                                    )
                                selected_ingredient_filter = edit_ingredient_options.get(edit_ingredient_name)
                                filtered_batch_options = {
                                    label: batch
                                    for label, batch in edit_ing_batch_options.items()
                                    if selected_ingredient_filter is not None
                                    and batch.item_id == selected_ingredient_filter.id
                                }
                                batch_labels = [""] + list(filtered_batch_options.keys())
                                current_label = ""
                                if existing_use and existing_use.purchase_item_id is not None:
                                    current_label = next(
                                        (
                                            label
                                            for label, batch in filtered_batch_options.items()
                                            if batch.batch_id == existing_use.purchase_item_id
                                        ),
                                        "",
                                    )
                                with cb:
                                    edit_batch_label = st.selectbox(
                                        f"Выбор партии ингредиента {idx + 1}",
                                        options=batch_labels,
                                        index=batch_labels.index(current_label) if current_label in batch_labels else 0,
                                        key=(
                                            f"{edit_key('ingredient_batch', idx)}_"
                                            f"{selected_ingredient_filter.id if selected_ingredient_filter else 'none'}"
                                        ),
                                    )
                                selected_batch = filtered_batch_options.get(edit_batch_label)
                                selected_ingredient = edit_all_ingredients.get(selected_batch.item_id) if selected_batch else None
                                default_unit = selected_batch.unit_short_name if selected_batch else ""
                                default_price = float(selected_batch.unit_price) if selected_batch else 0.0
                                qty_default = float(existing_use.quantity) if existing_use else 0.0
                                with cc:
                                    st.caption("Ед.")
                                    st.write(default_unit or "—")
                                with cd:
                                    edit_qty = st.number_input(
                                        f"Кол-во ингредиента {idx + 1}",
                                        min_value=0.0,
                                        step=0.1,
                                        format="%.3f",
                                        value=qty_default,
                                        key=edit_key("ingredient_qty", idx),
                                    )
                                with ce:
                                    edit_qty_decimal = Decimal(str(edit_qty))
                                    edit_line_total = edit_qty_decimal * Decimal(str(default_price))
                                    st.metric(f"Стоимость списания {idx + 1}", f"{edit_line_total:,.2f}")

                                if selected_batch is None and edit_qty_decimal > 0:
                                    edit_validation_errors.append(
                                        f"Ингредиент {idx + 1}: выберите партию или очистите количество."
                                    )
                                    continue
                                if selected_batch is not None and edit_qty_decimal <= 0:
                                    edit_validation_errors.append(
                                        f"Ингредиент {idx + 1}: укажите количество больше 0 или очистите строку."
                                    )
                                    continue
                                if selected_batch is None:
                                    continue
                                if selected_ingredient is None:
                                    edit_validation_errors.append(f"Ингредиент {idx + 1}: позиция не найдена.")
                                    continue
                                if default_unit not in edit_all_units:
                                    edit_validation_errors.append(
                                        f"Ингредиент {idx + 1}: единица партии отсутствует в справочнике."
                                    )
                                    continue

                                batch_id = selected_batch.batch_id
                                edit_requested_ing_by_batch[batch_id] = edit_requested_ing_by_batch.get(
                                    batch_id, Decimal("0")
                                ) + edit_qty_decimal
                                edit_ingredient_uses.append(
                                    BatchIngredientInput(
                                        ingredient=selected_ingredient,
                                        unit=edit_all_units[default_unit],
                                        quantity=edit_qty_decimal,
                                        unit_cost=Decimal(str(default_price)),
                                        purchase_item_id=batch_id,
                                    )
                                )

                            st.subheader("Заготовки")
                            edit_prep_rows = list(b.preparation_uses)
                            for idx in range(max(3, len(edit_prep_rows))):
                                existing_use = edit_prep_rows[idx] if idx < len(edit_prep_rows) else None
                                ca, cb, cc, cd, ce = st.columns([3, 4, 1, 2, 2])
                                prep_names = [""] + edit_prep_names
                                current_prep_name = existing_use.preparation.name if existing_use else ""
                                with ca:
                                    edit_prep_name = st.selectbox(
                                        f"Вид заготовки {idx + 1}",
                                        options=prep_names,
                                        index=prep_names.index(current_prep_name) if current_prep_name in prep_names else 0,
                                        key=edit_key("prep", idx),
                                    )
                                filtered_prep_options = {
                                    label: batch
                                    for label, batch in edit_prep_batch_options.items()
                                    if edit_prep_name and batch.item_name == edit_prep_name
                                }
                                prep_batch_labels = [""] + list(filtered_prep_options.keys())
                                current_prep_label = ""
                                if existing_use and existing_use.source_preparation_id is not None:
                                    current_prep_label = next(
                                        (
                                            label
                                            for label, batch in filtered_prep_options.items()
                                            if batch.batch_id == existing_use.source_preparation_id
                                        ),
                                        "",
                                    )
                                with cb:
                                    edit_prep_batch_label = st.selectbox(
                                        f"Выбор партии заготовки {idx + 1}",
                                        options=prep_batch_labels,
                                        index=prep_batch_labels.index(current_prep_label)
                                        if current_prep_label in prep_batch_labels
                                        else 0,
                                        key=f"{edit_key('prep_batch', idx)}_{edit_prep_name or 'none'}",
                                    )
                                selected_prep_batch = filtered_prep_options.get(edit_prep_batch_label)
                                selected_preparation = (
                                    edit_preparations.get(selected_prep_batch.batch_id) if selected_prep_batch else None
                                )
                                default_unit = selected_prep_batch.unit_short_name if selected_prep_batch else ""
                                default_price = float(selected_prep_batch.unit_price) if selected_prep_batch else 0.0
                                qty_default = float(existing_use.quantity) if existing_use else 0.0
                                with cc:
                                    st.caption("Ед.")
                                    st.write(default_unit or "—")
                                with cd:
                                    edit_prep_qty = st.number_input(
                                        f"Кол-во заготовки {idx + 1}",
                                        min_value=0.0,
                                        step=0.1,
                                        format="%.3f",
                                        value=qty_default,
                                        key=edit_key("prep_qty", idx),
                                    )
                                with ce:
                                    edit_prep_qty_decimal = Decimal(str(edit_prep_qty))
                                    edit_line_total = edit_prep_qty_decimal * Decimal(str(default_price))
                                    st.metric(f"Стоимость заготовки {idx + 1}", f"{edit_line_total:,.2f}")

                                if selected_prep_batch is None and edit_prep_qty_decimal > 0:
                                    edit_validation_errors.append(
                                        f"Заготовка {idx + 1}: выберите партию или очистите количество."
                                    )
                                    continue
                                if selected_prep_batch is not None and edit_prep_qty_decimal <= 0:
                                    edit_validation_errors.append(
                                        f"Заготовка {idx + 1}: укажите количество больше 0 или очистите строку."
                                    )
                                    continue
                                if selected_prep_batch is None:
                                    continue
                                if selected_preparation is None:
                                    edit_validation_errors.append(f"Заготовка {idx + 1}: партия не найдена.")
                                    continue
                                if default_unit not in edit_all_units:
                                    edit_validation_errors.append(
                                        f"Заготовка {idx + 1}: единица партии отсутствует в справочнике."
                                    )
                                    continue

                                batch_id = selected_prep_batch.batch_id
                                edit_requested_prep_by_batch[batch_id] = edit_requested_prep_by_batch.get(
                                    batch_id, Decimal("0")
                                ) + edit_prep_qty_decimal
                                edit_preparation_uses.append(
                                    BatchPreparationInput(
                                        preparation=selected_preparation,
                                        unit=edit_all_units[default_unit],
                                        quantity=edit_prep_qty_decimal,
                                        unit_cost=Decimal(str(default_price)),
                                        source_preparation_id=batch_id,
                                    )
                                )

                            for batch_id, requested_quantity in edit_requested_ing_by_batch.items():
                                available_quantity = Decimal(str(edit_ing_batches_by_id[batch_id].current_quantity))
                                if requested_quantity > available_quantity:
                                    batch = edit_ing_batches_by_id[batch_id]
                                    edit_validation_errors.append(
                                        f"Суммарное количество по ингредиенту '{batch.item_name}' больше доступного остатка."
                                    )
                            for batch_id, requested_quantity in edit_requested_prep_by_batch.items():
                                available_quantity = Decimal(str(edit_prep_batches_by_id[batch_id].current_quantity))
                                if requested_quantity > available_quantity:
                                    batch = edit_prep_batches_by_id[batch_id]
                                    edit_validation_errors.append(
                                        f"Суммарное количество по заготовке '{batch.item_name}' больше доступного остатка."
                                    )

                            if st.button("Сохранить изменения партии", key=edit_key("save"), type="primary"):
                                submit_errors = []
                                if edit_actual_qty <= 0:
                                    submit_errors.append("Фактический выход должен быть больше 0.")
                                if not (edit_ingredient_uses or edit_preparation_uses) and not edit_validation_errors:
                                    submit_errors.append("Добавьте хотя бы один ингредиент или заготовку.")
                                submit_errors.extend(edit_validation_errors)

                                if submit_errors:
                                    for error in submit_errors:
                                        st.error(error)
                                else:
                                    try:
                                        with SessionLocal() as db_write:
                                            db_product = db_write.merge(edit_all_products[edit_product_name])
                                            db_output_unit = db_write.merge(edit_all_units[edit_output_unit])
                                            db_ingredient_uses = [
                                                BatchIngredientInput(
                                                    ingredient=db_write.merge(use.ingredient),
                                                    unit=db_write.merge(use.unit),
                                                    quantity=use.quantity,
                                                    unit_cost=use.unit_cost,
                                                    purchase_item_id=use.purchase_item_id,
                                                )
                                                for use in edit_ingredient_uses
                                            ]
                                            db_preparation_uses = [
                                                BatchPreparationInput(
                                                    preparation=db_write.merge(use.preparation),
                                                    unit=db_write.merge(use.unit),
                                                    quantity=use.quantity,
                                                    unit_cost=use.unit_cost,
                                                    source_preparation_id=use.source_preparation_id,
                                                )
                                                for use in edit_preparation_uses
                                            ]
                                            update_production_batch(
                                                db_write,
                                                b.id,
                                                produced_on=edit_date,
                                                product=db_product,
                                                actual_output_quantity=Decimal(str(edit_actual_qty)),
                                                output_unit=db_output_unit,
                                                ingredient_uses=db_ingredient_uses,
                                                preparation_uses=db_preparation_uses,
                                                labor_cost=Decimal(str(edit_labor_cost)),
                                                equipment_depreciation=b.equipment_depreciation,
                                                allocated_overhead=Decimal(str(edit_overhead)),
                                                comment=edit_comment,
                                            )
                                            db_write.commit()
                                            st.success("Производственная партия обновлена.")
                                            st.rerun()
                                    except Exception as e:
                                        st.error(f"Ошибка при сохранении: {e}")
        else:
            st.info("История партий пуста")

# --- New Batch Tab ---
with tabs[1]:
    st.header("Новая партия")

    with SessionLocal() as db:
        # Load available stock batches
        available_batches = list_available_stock_batches(db)

        ing_batch_options = {
            build_batch_option_label(b): b
            for b in available_batches
            if b.item_type == PurchaseItemType.INGREDIENT
        }
        prep_batch_options = {
            build_batch_option_label(b): b
            for b in available_batches
            if b.item_type == ExtendedItemType.PREPARATION
        }
        all_ingredients = {i.id: i for i in db.query(Ingredient).all()}
        ingredient_by_name = {i.name: i for i in db.query(Ingredient).order_by(Ingredient.name).all()}
        available_ingredient_names = sorted({b.item_name for b in ing_batch_options.values()})
        available_prep_names = sorted({b.item_name for b in prep_batch_options.values()})
        all_products = {p.name: p for p in db.query(Product).all()}
        all_units = {u.short_name: u for u in db.query(Unit).all()}
        unit_names = list(all_units.keys())
        all_equipment = {e.name: e for e in db.query(Equipment).all()}

        current_labor_rate = db.query(LaborRate).filter(LaborRate.is_active.is_(True)).first()
        labor_rate_val = float(current_labor_rate.hourly_rate) if current_labor_rate else 0.0

        preps_db = list_preparations(db)
        prep_objs = {p.id: p for p in preps_db}

        if not all_products:
            st.warning("Сначала добавьте продукты в Справочниках")
        else:
            with st.container():
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

                st.subheader("Расходы ресурсов")
                row1_c1, row1_c2, row1_c3 = st.columns(3)
                with row1_c1:
                    labor_h = st.number_input("Труд (часы)", min_value=0.0, step=0.1)
                    calc_labor_cost = Decimal(str(labor_h * labor_rate_val))
                    st.write(f"Стоимость труда: **{calc_labor_cost:,.2f}**")

                with row1_c2:
                    selected_equip = st.selectbox("Оборудование", options=[""] + list(all_equipment.keys()))
                    equip_h = st.number_input("Работа оборуд. (часы)", min_value=0.0, step=0.1)
                    equip_rate = float(all_equipment[selected_equip].hourly_cost) if selected_equip else 0.0
                    calc_depr = Decimal(str(equip_h * equip_rate))
                    st.write(f"Амортизация: **{calc_depr:,.2f}**")

                with row1_c3:
                    overhead = st.number_input("Накладные расходы", min_value=0.0, step=10.0, format="%.2f")

                st.subheader("Ингредиенты (до 3)")
                ing_uses = []
                for i in range(3):
                    ca, cb, cc, cd, ce = st.columns([3, 4, 1, 2, 2])
                    with ca:
                        ingredient_name = st.selectbox(
                            f"Ингредиент {i}",
                            options=[""] + available_ingredient_names,
                            key=f"bi_item_{i}",
                        )
                    selected_ingredient = ingredient_by_name.get(ingredient_name)
                    filtered_ing_batch_options = {
                        label: batch
                        for label, batch in ing_batch_options.items()
                        if selected_ingredient and batch.item_id == selected_ingredient.id
                    }

                    with cb:
                        i_batch_label = st.selectbox(
                            f"Выбор партии {i}",
                            options=[""] + list(filtered_ing_batch_options.keys()),
                            key=f"bi_batch_{i}_{selected_ingredient.id if selected_ingredient else 'none'}",
                        )
                        if selected_ingredient and not filtered_ing_batch_options:
                            st.caption("Нет доступных партий выбранного ингредиента")

                    selected_i_batch = filtered_ing_batch_options.get(i_batch_label)
                    def_unit = selected_i_batch.unit_short_name if selected_i_batch else ""
                    def_price = float(selected_i_batch.unit_price) if selected_i_batch else 0.0

                    with cc:
                        u_name = st.selectbox(
                            f"Ед и {i}",
                            options=unit_names,
                            index=unit_names.index(def_unit) if def_unit in all_units else 0,
                            key=f"bi_unit_{i}_{selected_i_batch.batch_id if selected_i_batch else 'none'}",
                        )
                    with cd:
                        qty = st.number_input(f"Кол-во {i}", min_value=0.0, step=0.1, format="%.3f", key=f"bi_qty_{i}")
                    with ce:
                        line_total = Decimal(str(qty)) * Decimal(str(def_price))
                        st.text_input(
                            f"Стоимость списания {i}",
                            value=format_money(line_total),
                            disabled=True,
                        )
                        if selected_i_batch:
                            st.caption(f"Цена партии: {def_price:,.2f}/{def_unit}")

                    if selected_i_batch and qty > 0:
                        ing_uses.append(
                            BatchIngredientInput(
                                ingredient=all_ingredients[selected_i_batch.item_id],
                                unit=all_units[u_name],
                                quantity=Decimal(str(qty)),
                                unit_cost=Decimal(str(def_price)),
                                purchase_item_id=selected_i_batch.batch_id,
                            )
                        )

                st.subheader("Заготовки (до 3)")
                p_uses = []
                for i in range(3):
                    ca, cb, cc, cd, ce = st.columns([3, 4, 1, 2, 2])
                    with ca:
                        prep_name = st.selectbox(
                            f"Вид заготовки {i}",
                            options=[""] + available_prep_names,
                            key=f"bp_item_{i}",
                        )
                    filtered_prep_batch_options = {
                        label: batch
                        for label, batch in prep_batch_options.items()
                        if prep_name and batch.item_name == prep_name
                    }

                    with cb:
                        p_batch_label = st.selectbox(
                            f"Выбор партии заготовки {i}",
                            options=[""] + list(filtered_prep_batch_options.keys()),
                            key=f"bp_batch_{i}_{prep_name or 'none'}",
                        )
                        if prep_name and not filtered_prep_batch_options:
                            st.caption("Нет доступных партий выбранной заготовки")

                    selected_p_batch = filtered_prep_batch_options.get(p_batch_label)
                    def_unit = selected_p_batch.unit_short_name if selected_p_batch else ""
                    def_price = float(selected_p_batch.unit_price) if selected_p_batch else 0.0

                    with cc:
                        u_name = st.selectbox(
                            f"Ед з {i}",
                            options=unit_names,
                            index=unit_names.index(def_unit) if def_unit in all_units else 0,
                            key=f"bp_unit_{i}_{selected_p_batch.batch_id if selected_p_batch else 'none'}",
                        )
                    with cd:
                        qty = st.number_input(f"Кол-во з {i}", min_value=0.0, step=0.1, format="%.3f", key=f"bp_qty_{i}")
                    with ce:
                        line_total = Decimal(str(qty)) * Decimal(str(def_price))
                        st.text_input(
                            f"Стоимость списания з {i}",
                            value=format_money(line_total),
                            disabled=True,
                        )
                        if selected_p_batch:
                            st.caption(f"Цена партии: {def_price:,.2f}/{def_unit}")

                    if selected_p_batch and qty > 0:
                        prep_obj = prep_objs.get(selected_p_batch.batch_id)
                        if prep_obj:
                            p_uses.append(
                                BatchPreparationInput(
                                    preparation=prep_obj,
                                    unit=all_units[u_name],
                                    quantity=Decimal(str(qty)),
                                    unit_cost=Decimal(str(def_price)),
                                    source_preparation_id=selected_p_batch.batch_id,
                                )
                            )

                submitted = st.button("Сохранить партию", type="primary")
                if submitted:
                    if actual_qty <= 0:
                        st.error("Фактический выход должен быть больше 0")
                    elif not (ing_uses or p_uses):
                        st.error("Добавьте хотя бы один ингредиент или заготовку")
                    else:
                        try:
                            with SessionLocal() as db_write:
                                db_prod = db_write.merge(all_products[prod_name])
                                db_unit = db_write.merge(all_units[out_unit_name])
                                db_ing_uses = [
                                    BatchIngredientInput(
                                        ingredient=db_write.merge(u.ingredient),
                                        unit=db_write.merge(u.unit),
                                        quantity=u.quantity,
                                        unit_cost=u.unit_cost,
                                        purchase_item_id=u.purchase_item_id,
                                    )
                                    for u in ing_uses
                                ]
                                db_p_uses = [
                                    BatchPreparationInput(
                                        preparation=db_write.merge(u.preparation),
                                        unit=db_write.merge(u.unit),
                                        quantity=u.quantity,
                                        unit_cost=u.unit_cost,
                                        source_preparation_id=u.source_preparation_id,
                                    )
                                    for u in p_uses
                                ]
                                create_production_batch(
                                    db_write,
                                    produced_on=batch_date,
                                    product=db_prod,
                                    actual_output_quantity=Decimal(str(actual_qty)),
                                    output_unit=db_unit,
                                    ingredient_uses=db_ing_uses,
                                    preparation_uses=db_p_uses,
                                    labor_cost=calc_labor_cost,
                                    equipment_depreciation=calc_depr,
                                    allocated_overhead=Decimal(str(overhead)),
                                    comment=batch_comment,
                                )
                                db_write.commit()
                                st.success("Партия успешно сохранена!")
                                st.rerun()
                        except Exception as e:
                            st.error(f"Ошибка при сохранении: {e}")
