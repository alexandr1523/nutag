"""Streamlit page for managing internal preparations/semi-finished products."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import streamlit as st

from nutag.db.init_db import initialize_database
from nutag.db.models import Ingredient, LaborRate, PreparationType, PurchaseItemType, Unit
from nutag.db.session import create_engine_for_url, create_session_factory
from nutag.services.inventory import list_available_stock_batches
from nutag.services.preparations import PreparationIngredientInput, create_preparation, list_preparations


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
                ca, cb, cc, cd, ce, cf = st.columns([4, 1, 2, 2, 2, 2.5])
                with ca:
                    batch_label = st.selectbox(
                        f"Выбор партии {i + 1}",
                        options=[""] + list(batch_options.keys()),
                        key=field_key("batch_label", i),
                    )

                selected_batch = batch_options.get(batch_label)
                selected_ingredient = all_ingredients.get(selected_batch.item_id) if selected_batch else None
                ingredient_unit = selected_ingredient.unit.short_name if selected_ingredient else ""
                batch_unit = selected_batch.unit_short_name if selected_batch else ""
                default_unit = ingredient_unit
                default_price = float(selected_batch.unit_price) if selected_batch else 0.0

                with cb:
                    st.caption("Ед. авто")
                    st.write(default_unit or "—")
                with cc:
                    qty = st.number_input(
                        f"Кол-во {i + 1}",
                        min_value=0.0,
                        step=0.1,
                        format="%.3f",
                        key=field_key("ing_qty", i),
                    )
                with cd:
                    ingredient_waste_qty = st.number_input(
                        f"Отходы {i + 1}",
                        min_value=0.0,
                        step=0.1,
                        format="%.3f",
                        key=field_key("ing_waste_qty", i),
                    )
                with ce:
                    qty_decimal = Decimal(str(qty))
                    ingredient_waste_decimal = Decimal(str(ingredient_waste_qty))
                    useful_qty = qty_decimal - ingredient_waste_decimal
                    st.metric(f"Полезно {i + 1}", f"{useful_qty:,.3f}")
                with cf:
                    line_total = qty_decimal * Decimal(str(default_price))
                    st.metric(f"Стоимость списания {i + 1}", f"{line_total:,.2f}")
                    if useful_qty > 0 and default_unit:
                        useful_unit_cost = line_total / useful_qty
                        st.caption(f"Себест. полезного: {useful_unit_cost:,.2f}/{default_unit}")

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
