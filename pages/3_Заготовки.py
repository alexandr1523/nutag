"""Streamlit page for managing internal preparations/semi-finished products."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import streamlit as st

from nutag.db.init_db import initialize_database
from nutag.db.models import Ingredient, LaborRate, PreparationType, PurchaseItemType, Unit
from nutag.db.session import create_engine_for_url, create_session_factory
from nutag.services.inventory import list_available_stock_batches
from nutag.services.preparations import (
    PreparationIngredientInput,
    create_preparation,
    delete_preparation,
    is_preparation_used,
    list_preparations,
    update_preparation,
)


st.set_page_config(page_title="Заготовки | Nutag", page_icon="🥣", layout="wide")

st.title("🥣 Заготовки")

engine = create_engine_for_url()
initialize_database(engine)
SessionLocal = create_session_factory(engine)

tabs = st.tabs(["История заготовок", "Новая заготовка"])

with tabs[0]:
    st.header("История заготовок")
    with SessionLocal() as db:
        preparations = list_preparations(db)
        if preparations:
            for preparation in preparations:
                preparation_label = preparation.preparation_type.name if preparation.preparation_type else preparation.name
                with st.expander(
                    f"{preparation.prepared_on} - {preparation_label} "
                    f"({preparation.output_quantity} {preparation.output_unit.short_name})"
                ):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Дата:** {preparation.prepared_on}")
                        st.write(f"**Вид заготовки:** {preparation_label}")
                        st.write(f"**Выход:** {preparation.output_quantity} {preparation.output_unit.short_name}")
                        if preparation.waste_quantity:
                            st.write(
                                f"**Общие отходы:** {preparation.waste_quantity} "
                                f"{preparation.output_unit.short_name}"
                            )
                        st.write(f"**Труд:** {preparation.labor_cost:,.2f}")
                        st.write(f"**Прочее:** {preparation.other_direct_cost:,.2f}")
                    with col2:
                        st.write(f"**Себестоимость (общая):** {preparation.total_cost:,.2f}")
                        st.write(f"**Себестоимость (ед):** {preparation.unit_cost:,.4f}")

                    st.subheader("Использованные ингредиенты")
                    ingredient_rows = []
                    for use in preparation.ingredient_uses:
                        source_info = f" (Партия #{use.purchase_item_id})" if use.purchase_item_id else ""
                        ingredient_rows.append(
                            {
                                "Ингредиент": use.ingredient.name + source_info,
                                "Расход": use.quantity,
                                "Отходы": use.waste_quantity,
                                "Полезно": use.quantity - use.waste_quantity,
                                "Ед.изм.": use.unit.short_name,
                                "Цена": use.unit_cost,
                                "Итого": use.total_cost,
                            }
                        )
                    st.table(ingredient_rows)

                    if is_preparation_used(db, preparation.id):
                        st.warning("Заготовка уже использована в производстве, корректировка недоступна.")
                    else:
                        with st.expander("Редактировать заготовку"):
                            preparation_types = db.query(PreparationType).order_by(PreparationType.name).all()
                            all_units = {unit.short_name: unit for unit in db.query(Unit).all()}
                            all_ingredients = {ingredient.id: ingredient for ingredient in db.query(Ingredient).all()}
                            edit_available_batches = [
                                batch
                                for batch in list_available_stock_batches(db)
                                if batch.item_type == PurchaseItemType.INGREDIENT
                            ]
                            edit_batches_by_id = {batch.batch_id: batch for batch in edit_available_batches}

                            for use in preparation.ingredient_uses:
                                if use.purchase_item_id is None or use.purchase_item is None:
                                    continue
                                if use.purchase_item_id in edit_batches_by_id:
                                    batch = edit_batches_by_id[use.purchase_item_id]
                                    edit_batches_by_id[use.purchase_item_id] = SimpleNamespace(
                                        batch_id=batch.batch_id,
                                        item_id=batch.item_id,
                                        item_name=batch.item_name,
                                        date=batch.date,
                                        unit_short_name=batch.unit_short_name,
                                        current_quantity=batch.current_quantity + use.quantity,
                                        unit_price=batch.unit_price,
                                    )
                                else:
                                    edit_batches_by_id[use.purchase_item_id] = SimpleNamespace(
                                        batch_id=use.purchase_item_id,
                                        item_id=use.ingredient_id,
                                        item_name=use.ingredient.name,
                                        date=use.purchase_item.purchase.purchase_date,
                                        unit_short_name=use.unit.short_name,
                                        current_quantity=use.quantity,
                                        unit_price=use.purchase_item.unit_price,
                                    )

                            edit_batch_options = {
                                (
                                    f"#{batch.batch_id} {batch.date} - {batch.item_name} "
                                    f"(Доступно для корректировки: {batch.current_quantity} {batch.unit_short_name})"
                                ): batch
                                for batch in sorted(
                                    edit_batches_by_id.values(),
                                    key=lambda batch: (batch.item_name, batch.date, batch.batch_id),
                                )
                            }
                            edit_ingredient_options = {
                                ingredient.name: ingredient
                                for ingredient in sorted(all_ingredients.values(), key=lambda ingredient: ingredient.name)
                            }
                            edit_preparation_type_options = {
                                preparation_type.name: preparation_type for preparation_type in preparation_types
                            }

                            def edit_key(name: str, idx: int | None = None) -> str:
                                suffix = f"_{idx}" if idx is not None else ""
                                return f"preparation_edit_{preparation.id}_{name}{suffix}"

                            edit_c1, edit_c2, edit_c3 = st.columns(3)
                            with edit_c1:
                                edit_date = st.date_input(
                                    "Дата приготовления",
                                    value=preparation.prepared_on,
                                    key=edit_key("date"),
                                )
                            with edit_c2:
                                edit_type_names = list(edit_preparation_type_options.keys())
                                current_type_name = preparation.preparation_type.name if preparation.preparation_type else preparation.name
                                edit_type = st.selectbox(
                                    "Вид заготовки",
                                    options=edit_type_names,
                                    index=edit_type_names.index(current_type_name) if current_type_name in edit_type_names else 0,
                                    key=edit_key("type"),
                                )
                            with edit_c3:
                                edit_comment = st.text_area(
                                    "Комментарий",
                                    value=preparation.comment or "",
                                    key=edit_key("comment"),
                                )

                            edit_o1, edit_o2, edit_o3, edit_o4 = st.columns(4)
                            with edit_o1:
                                edit_output_qty = st.number_input(
                                    "Кол-во на выходе (годное)",
                                    min_value=0.0,
                                    step=0.1,
                                    format="%.3f",
                                    value=float(preparation.output_quantity),
                                    key=edit_key("output_qty"),
                                )
                            with edit_o2:
                                unit_names = list(all_units.keys())
                                edit_output_unit = st.selectbox(
                                    "Ед. изм.",
                                    options=unit_names,
                                    index=unit_names.index(preparation.output_unit.short_name)
                                    if preparation.output_unit.short_name in unit_names
                                    else 0,
                                    key=edit_key("output_unit"),
                                )
                            with edit_o3:
                                edit_labor_cost = st.number_input(
                                    "Труд (сумма)",
                                    min_value=0.0,
                                    step=10.0,
                                    format="%.2f",
                                    value=float(preparation.labor_cost),
                                    key=edit_key("labor_cost"),
                                )
                            with edit_o4:
                                edit_other_cost = st.number_input(
                                    "Прочие расходы",
                                    min_value=0.0,
                                    step=10.0,
                                    format="%.2f",
                                    value=float(preparation.other_direct_cost),
                                    key=edit_key("other_cost"),
                                )

                            edit_ingredient_uses = []
                            edit_validation_errors: list[str] = []
                            edit_requested_quantities_by_batch: dict[int, Decimal] = {}
                            edit_rows = list(preparation.ingredient_uses)
                            row_count = max(5, len(edit_rows))
                            for idx in range(row_count):
                                existing_use = edit_rows[idx] if idx < len(edit_rows) else None
                                st.markdown(f"**Ингредиент {idx + 1}**")
                                ea, eb, ec, ed, ee, ef, eg = st.columns([2.5, 4, 1, 2, 2, 2, 2.5])
                                ingredient_names = [""] + list(edit_ingredient_options.keys())
                                current_ingredient_name = existing_use.ingredient.name if existing_use else ""
                                with ea:
                                    edit_ingredient_name = st.selectbox(
                                        f"Ингредиент {idx + 1}",
                                        options=ingredient_names,
                                        index=ingredient_names.index(current_ingredient_name)
                                        if current_ingredient_name in ingredient_names
                                        else 0,
                                        key=edit_key("ingredient", idx),
                                    )
                                edit_selected_ingredient_filter = edit_ingredient_options.get(edit_ingredient_name)
                                filtered_edit_batch_options = {
                                    label: batch
                                    for label, batch in edit_batch_options.items()
                                    if edit_selected_ingredient_filter is not None
                                    and batch.item_id == edit_selected_ingredient_filter.id
                                }
                                batch_labels = [""] + list(filtered_edit_batch_options.keys())
                                current_label = ""
                                if existing_use and existing_use.purchase_item_id is not None:
                                    current_label = next(
                                        (
                                            label
                                            for label, batch in filtered_edit_batch_options.items()
                                            if batch.batch_id == existing_use.purchase_item_id
                                        ),
                                        "",
                                    )
                                with eb:
                                    edit_batch_label = st.selectbox(
                                        f"Выбор партии {idx + 1}",
                                        options=batch_labels,
                                        index=batch_labels.index(current_label) if current_label in batch_labels else 0,
                                        key=(
                                            f"{edit_key('batch', idx)}_"
                                            f"{edit_selected_ingredient_filter.id if edit_selected_ingredient_filter else 'none'}"
                                        ),
                                    )

                                edit_selected_batch = filtered_edit_batch_options.get(edit_batch_label)
                                edit_selected_ingredient = (
                                    all_ingredients.get(edit_selected_batch.item_id) if edit_selected_batch else None
                                )
                                edit_ingredient_unit = (
                                    edit_selected_ingredient.unit.short_name if edit_selected_ingredient else ""
                                )
                                edit_batch_unit = edit_selected_batch.unit_short_name if edit_selected_batch else ""
                                edit_default_price = float(edit_selected_batch.unit_price) if edit_selected_batch else 0.0
                                edit_qty_default = float(existing_use.quantity) if existing_use else 0.0
                                edit_waste_default = float(existing_use.waste_quantity) if existing_use else 0.0

                                with ec:
                                    st.caption("Ед. авто")
                                    st.write(edit_ingredient_unit or "—")
                                with ed:
                                    edit_qty = st.number_input(
                                        f"Кол-во {idx + 1}",
                                        min_value=0.0,
                                        step=0.1,
                                        format="%.3f",
                                        value=edit_qty_default,
                                        key=edit_key("qty", idx),
                                    )
                                with ee:
                                    edit_waste_qty = st.number_input(
                                        f"Отходы {idx + 1}",
                                        min_value=0.0,
                                        step=0.1,
                                        format="%.3f",
                                        value=edit_waste_default,
                                        key=edit_key("waste", idx),
                                    )
                                with ef:
                                    edit_qty_decimal = Decimal(str(edit_qty))
                                    edit_waste_decimal = Decimal(str(edit_waste_qty))
                                    edit_useful_qty = edit_qty_decimal - edit_waste_decimal
                                    st.metric(f"Полезно {idx + 1}", f"{edit_useful_qty:,.3f}")
                                with eg:
                                    edit_line_total = edit_qty_decimal * Decimal(str(edit_default_price))
                                    st.metric(f"Стоимость списания {idx + 1}", f"{edit_line_total:,.2f}")
                                    if edit_useful_qty > 0 and edit_ingredient_unit:
                                        st.caption(
                                            f"Себест. полезного: {edit_line_total / edit_useful_qty:,.2f}/"
                                            f"{edit_ingredient_unit}"
                                        )

                                if (
                                    edit_selected_ingredient_filter is not None
                                    and not filtered_edit_batch_options
                                    and (edit_qty_decimal > 0 or edit_waste_decimal > 0)
                                ):
                                    edit_validation_errors.append(
                                        f"Строка {idx + 1}: по выбранному ингредиенту нет доступных партий."
                                    )
                                    continue
                                if edit_selected_batch is None and (edit_qty_decimal > 0 or edit_waste_decimal > 0):
                                    edit_validation_errors.append(
                                        f"Строка {idx + 1}: выберите партию ингредиента или очистите количество и отходы."
                                    )
                                    continue
                                if edit_selected_batch is not None and edit_qty_decimal <= 0:
                                    edit_validation_errors.append(
                                        f"Строка {idx + 1}: укажите количество больше 0 или очистите строку."
                                    )
                                    continue
                                if edit_selected_batch is None:
                                    continue
                                if edit_waste_decimal > edit_qty_decimal:
                                    edit_validation_errors.append(
                                        f"Строка {idx + 1}: отходы не могут быть больше расхода ингредиента."
                                    )
                                    continue
                                if edit_selected_ingredient is None:
                                    edit_validation_errors.append(
                                        f"Строка {idx + 1}: ингредиент партии отсутствует в справочнике."
                                    )
                                    continue
                                if edit_ingredient_unit not in all_units:
                                    edit_validation_errors.append(
                                        f"Строка {idx + 1}: единица измерения ингредиента отсутствует в справочнике."
                                    )
                                    continue
                                if edit_batch_unit != edit_ingredient_unit:
                                    edit_validation_errors.append(
                                        f"Строка {idx + 1}: единица партии ({edit_batch_unit}) не совпадает "
                                        f"с единицей ингредиента ({edit_ingredient_unit})."
                                    )
                                    continue

                                edit_requested_quantities_by_batch[edit_selected_batch.batch_id] = (
                                    edit_requested_quantities_by_batch.get(edit_selected_batch.batch_id, Decimal("0"))
                                    + edit_qty_decimal
                                )
                                if edit_qty_decimal > Decimal(str(edit_selected_batch.current_quantity)):
                                    edit_validation_errors.append(
                                        f"Строка {idx + 1}: количество больше доступного остатка партии."
                                    )
                                    continue

                                edit_ingredient_uses.append(
                                    PreparationIngredientInput(
                                        ingredient=edit_selected_ingredient,
                                        unit=all_units[edit_ingredient_unit],
                                        quantity=edit_qty_decimal,
                                        unit_cost=Decimal(str(edit_default_price)),
                                        waste_quantity=edit_waste_decimal,
                                        purchase_item_id=edit_selected_batch.batch_id,
                                    )
                                )

                            for batch_id, requested_quantity in edit_requested_quantities_by_batch.items():
                                batch = edit_batches_by_id[batch_id]
                                if requested_quantity > Decimal(str(batch.current_quantity)):
                                    edit_validation_errors.append(
                                        f"Суммарное количество по партии '{batch.item_name}' больше доступного остатка."
                                    )

                            if st.button("Сохранить изменения", key=edit_key("save"), type="primary"):
                                submit_errors = []
                                if edit_output_qty <= 0:
                                    submit_errors.append("Количество на выходе должно быть больше 0.")
                                if not edit_ingredient_uses and not edit_validation_errors:
                                    submit_errors.append("Добавьте хотя бы один ингредиент.")
                                submit_errors.extend(edit_validation_errors)

                                if submit_errors:
                                    for error in submit_errors:
                                        st.error(error)
                                else:
                                    try:
                                        with SessionLocal() as db_write:
                                            db_preparation_type = db_write.merge(
                                                edit_preparation_type_options[edit_type]
                                            )
                                            db_output_unit = db_write.merge(all_units[edit_output_unit])
                                            db_ingredient_uses = [
                                                PreparationIngredientInput(
                                                    ingredient=db_write.merge(use.ingredient),
                                                    unit=db_write.merge(use.unit),
                                                    quantity=use.quantity,
                                                    unit_cost=use.unit_cost,
                                                    waste_quantity=use.waste_quantity,
                                                    purchase_item_id=use.purchase_item_id,
                                                )
                                                for use in edit_ingredient_uses
                                            ]
                                            update_preparation(
                                                db_write,
                                                preparation.id,
                                                prepared_on=edit_date,
                                                preparation_type=db_preparation_type,
                                                output_quantity=Decimal(str(edit_output_qty)),
                                                waste_quantity=Decimal("0"),
                                                output_unit=db_output_unit,
                                                ingredient_uses=db_ingredient_uses,
                                                labor_cost=Decimal(str(edit_labor_cost)),
                                                other_direct_cost=Decimal(str(edit_other_cost)),
                                                comment=edit_comment,
                                            )
                                            db_write.commit()
                                            st.success("Заготовка обновлена.")
                                            st.rerun()
                                    except Exception as e:
                                        st.error(f"Ошибка при сохранении: {e}")

                        with st.expander("Удалить заготовку"):
                            st.warning(
                                "Удаление вернёт ингредиенты в остатки и уберёт остаток самой заготовки. "
                                "Действие нельзя отменить."
                            )
                            delete_confirmation = st.text_input(
                                "Для удаления введите УДАЛИТЬ",
                                key=f"preparation_delete_confirm_{preparation.id}",
                            )
                            if st.button(
                                "Удалить заготовку",
                                key=f"preparation_delete_{preparation.id}",
                                type="secondary",
                            ):
                                if delete_confirmation != "УДАЛИТЬ":
                                    st.error("Введите УДАЛИТЬ для подтверждения удаления.")
                                else:
                                    try:
                                        with SessionLocal() as db_write:
                                            delete_preparation(db_write, preparation.id)
                                            db_write.commit()
                                            st.success("Заготовка удалена.")
                                            st.rerun()
                                    except Exception as e:
                                        st.error(f"Ошибка при удалении: {e}")
        else:
            st.info("История заготовок пуста")

with tabs[1]:
    st.header("Новая заготовка")

    saved_message = st.session_state.pop("preparation_saved_message", None)
    if saved_message:
        st.success(saved_message)

    with SessionLocal() as db:
        available_batches = list_available_stock_batches(db)
        ingredient_batches = [batch for batch in available_batches if batch.item_type == PurchaseItemType.INGREDIENT]
        preparation_types = db.query(PreparationType).order_by(PreparationType.name).all()

        batch_options = {
            f"{batch.date} - {batch.item_name} (Остаток: {batch.current_quantity} {batch.unit_short_name})": batch
            for batch in ingredient_batches
        }
        preparation_type_options = {preparation_type.name: preparation_type for preparation_type in preparation_types}
        all_ingredients = {ingredient.id: ingredient for ingredient in db.query(Ingredient).all()}
        ingredient_options = {
            ingredient.name: ingredient for ingredient in sorted(all_ingredients.values(), key=lambda ingredient: ingredient.name)
        }
        all_units = {unit.short_name: unit for unit in db.query(Unit).all()}

        if not preparation_type_options:
            st.warning("Сначала добавьте виды заготовок в Справочниках.")
        elif not ingredient_batches:
            st.warning("На складе нет доступных ингредиентов. Сначала оформите закупки.")
        else:
            if "preparation_form_version" not in st.session_state:
                st.session_state.preparation_form_version = 0

            form_version = st.session_state.preparation_form_version

            def field_key(name: str, idx: int | None = None) -> str:
                suffix = f"_{idx}" if idx is not None else ""
                return f"preparation_{form_version}_{name}{suffix}"

            col1, col2, col3 = st.columns(3)
            with col1:
                prep_date = st.date_input("Дата приготовления", value=date.today(), key=field_key("date"))
            with col2:
                preparation_type_name = st.selectbox(
                    "Вид заготовки",
                    options=list(preparation_type_options.keys()),
                    key=field_key("type"),
                )
            with col3:
                prep_comment = st.text_area("Комментарий", key=field_key("comment"))

            st.subheader("Выход")
            c1, c2 = st.columns(2)
            with c1:
                output_qty = st.number_input(
                    "Кол-во на выходе (годное)",
                    min_value=0.0,
                    step=0.1,
                    format="%.3f",
                    key=field_key("output_qty"),
                )
            with c2:
                output_unit_name = st.selectbox("Ед. изм.", options=list(all_units.keys()), key=field_key("output_unit"))

            st.subheader("Расходы")
            c3, c4, c5 = st.columns(3)
            with SessionLocal() as db_rate:
                current_labor_rate = db_rate.query(LaborRate).filter(LaborRate.is_active.is_(True)).first()
                rate_val = float(current_labor_rate.hourly_rate) if current_labor_rate else 0.0

            with c3:
                labor_hours = st.number_input(
                    "Время труда (часы)",
                    min_value=0.0,
                    step=0.1,
                    format="%.2f",
                    key=field_key("labor_hours"),
                )
            with c4:
                st.session_state["prep_rate_display"] = rate_val
                st.number_input(
                    "Текущая ставка",
                    min_value=0.0,
                    step=1.0,
                    format="%.2f",
                    key="prep_rate_display",
                    disabled=True,
                )
            with c5:
                calculated_labor_cost = Decimal(str(labor_hours * rate_val))
                st.session_state["prep_labor_total"] = float(calculated_labor_cost)
                st.number_input(
                    "Итого за труд",
                    min_value=0.0,
                    step=1.0,
                    format="%.2f",
                    key="prep_labor_total",
                    disabled=True,
                )

            other_cost = st.number_input(
                "Прочие прямые расходы",
                min_value=0.0,
                step=10.0,
                format="%.2f",
                key=field_key("other_cost"),
            )

            st.subheader("Ингредиенты (до 5 в MVP)")
            ingredient_uses = []
            validation_errors: list[str] = []
            requested_quantities_by_batch: dict[int, Decimal] = {}
            batches_by_id = {}
            for i in range(5):
                st.markdown(f"**Ингредиент {i + 1}**")
                ca, cb, cc, cd, ce, cf, cg = st.columns([2.5, 4, 1, 2, 2, 2, 2.5])
                with ca:
                    ingredient_name = st.selectbox(
                        f"Ингредиент {i + 1}",
                        options=[""] + list(ingredient_options.keys()),
                        key=field_key("ingredient", i),
                    )
                selected_ingredient_filter = ingredient_options.get(ingredient_name)
                filtered_batch_options = {
                    label: batch
                    for label, batch in batch_options.items()
                    if selected_ingredient_filter is not None and batch.item_id == selected_ingredient_filter.id
                }
                with cb:
                    batch_label = st.selectbox(
                        f"Выбор партии {i + 1}",
                        options=[""] + list(filtered_batch_options.keys()),
                        key=(
                            f"{field_key('batch_label', i)}_"
                            f"{selected_ingredient_filter.id if selected_ingredient_filter else 'none'}"
                        ),
                    )

                selected_batch = filtered_batch_options.get(batch_label)
                selected_ingredient = all_ingredients.get(selected_batch.item_id) if selected_batch else None
                ingredient_unit = selected_ingredient.unit.short_name if selected_ingredient else ""
                batch_unit = selected_batch.unit_short_name if selected_batch else ""
                default_unit = ingredient_unit
                default_price = float(selected_batch.unit_price) if selected_batch else 0.0

                with cc:
                    st.caption("Ед. авто")
                    st.write(default_unit or "—")
                with cd:
                    qty = st.number_input(
                        f"Кол-во {i + 1}",
                        min_value=0.0,
                        step=0.1,
                        format="%.3f",
                        key=field_key("ing_qty", i),
                    )
                with ce:
                    ingredient_waste_qty = st.number_input(
                        f"Отходы {i + 1}",
                        min_value=0.0,
                        step=0.1,
                        format="%.3f",
                        key=field_key("ing_waste_qty", i),
                    )
                with cf:
                    qty_decimal = Decimal(str(qty))
                    ingredient_waste_decimal = Decimal(str(ingredient_waste_qty))
                    useful_qty = qty_decimal - ingredient_waste_decimal
                    st.metric(f"Полезно {i + 1}", f"{useful_qty:,.3f}")
                with cg:
                    line_total = qty_decimal * Decimal(str(default_price))
                    st.metric(f"Стоимость списания {i + 1}", f"{line_total:,.2f}")
                    if useful_qty > 0 and default_unit:
                        useful_unit_cost = line_total / useful_qty
                        st.caption(f"Себест. полезного: {useful_unit_cost:,.2f}/{default_unit}")

                if (
                    selected_ingredient_filter is not None
                    and not filtered_batch_options
                    and (qty_decimal > 0 or ingredient_waste_decimal > 0)
                ):
                    validation_errors.append(
                        f"Строка {i + 1}: по выбранному ингредиенту нет доступных партий."
                    )
                    continue
                if selected_batch is None and (qty_decimal > 0 or ingredient_waste_decimal > 0):
                    validation_errors.append(
                        f"Строка {i + 1}: выберите партию ингредиента или очистите количество и отходы."
                    )
                    continue
                if selected_batch is not None and qty_decimal <= 0:
                    validation_errors.append(f"Строка {i + 1}: укажите количество больше 0 или очистите строку.")
                    continue
                if selected_batch is None:
                    continue
                if ingredient_waste_decimal > qty_decimal:
                    validation_errors.append(f"Строка {i + 1}: отходы не могут быть больше расхода ингредиента.")
                    continue
                if selected_ingredient is None:
                    validation_errors.append(f"Строка {i + 1}: ингредиент партии отсутствует в справочнике.")
                    continue
                if default_unit not in all_units:
                    validation_errors.append(
                        f"Строка {i + 1}: единица измерения ингредиента отсутствует в справочнике."
                    )
                    continue
                if batch_unit != default_unit:
                    validation_errors.append(
                        f"Строка {i + 1}: единица партии ({batch_unit}) не совпадает "
                        f"с единицей ингредиента ({default_unit})."
                    )
                    continue

                batch_id = selected_batch.batch_id
                batches_by_id[batch_id] = selected_batch
                requested_quantities_by_batch[batch_id] = requested_quantities_by_batch.get(
                    batch_id, Decimal("0")
                ) + qty_decimal
                if qty_decimal > Decimal(str(selected_batch.current_quantity)):
                    validation_errors.append(
                        f"Строка {i + 1}: количество больше остатка выбранной партии."
                    )
                    continue

                if selected_batch and qty_decimal > 0:
                    ingredient_uses.append(
                        PreparationIngredientInput(
                            ingredient=selected_ingredient,
                            unit=all_units[default_unit],
                            quantity=qty_decimal,
                            unit_cost=Decimal(str(default_price)),
                            waste_quantity=ingredient_waste_decimal,
                            purchase_item_id=selected_batch.batch_id,
                        )
                    )

            for batch_id, requested_quantity in requested_quantities_by_batch.items():
                available_quantity = Decimal(str(batches_by_id[batch_id].current_quantity))
                if requested_quantity > available_quantity:
                    batch = batches_by_id[batch_id]
                    validation_errors.append(
                        f"Суммарное количество по партии '{batch.item_name}' больше доступного остатка."
                    )

            if st.button("Сохранить заготовку", type="primary", key=field_key("save")):
                submit_errors = []
                if not preparation_type_name or preparation_type_name not in preparation_type_options:
                    submit_errors.append("Выберите вид заготовки.")
                if output_qty <= 0:
                    submit_errors.append("Количество на выходе должно быть больше 0.")
                if not output_unit_name or output_unit_name not in all_units:
                    submit_errors.append("Выберите единицу измерения выхода.")
                if not ingredient_uses and not validation_errors:
                    submit_errors.append("Добавьте хотя бы один ингредиент.")
                submit_errors.extend(validation_errors)

                if submit_errors:
                    for error in submit_errors:
                        st.error(error)
                else:
                    try:
                        with SessionLocal() as db_write:
                            db_output_unit = db_write.merge(all_units[output_unit_name])
                            db_preparation_type = db_write.merge(preparation_type_options[preparation_type_name])
                            db_ingredient_uses = [
                                PreparationIngredientInput(
                                    ingredient=db_write.merge(use.ingredient),
                                    unit=db_write.merge(use.unit),
                                    quantity=use.quantity,
                                    unit_cost=use.unit_cost,
                                    waste_quantity=use.waste_quantity,
                                    purchase_item_id=use.purchase_item_id,
                                )
                                for use in ingredient_uses
                            ]

                            create_preparation(
                                db_write,
                                prepared_on=prep_date,
                                preparation_type=db_preparation_type,
                                output_quantity=Decimal(str(output_qty)),
                                waste_quantity=Decimal("0"),
                                output_unit=db_output_unit,
                                ingredient_uses=db_ingredient_uses,
                                labor_cost=calculated_labor_cost,
                                other_direct_cost=Decimal(str(other_cost)),
                                comment=prep_comment,
                            )
                            db_write.commit()
                            st.session_state.preparation_form_version += 1
                            st.session_state.preparation_saved_message = (
                                f"Заготовка '{preparation_type_name}' успешно сохранена."
                            )
                            st.rerun()
                    except Exception as e:
                        st.error(f"Ошибка при сохранении: {e}")
