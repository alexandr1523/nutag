"""Streamlit page for managing internal preparations/semi-finished products."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import streamlit as st

from nutag.db.models import Ingredient, LaborRate, PurchaseItemType, Unit
from nutag.db.session import create_engine_for_url, create_session_factory
from nutag.services.inventory import list_available_stock_batches
from nutag.services.preparations import PreparationIngredientInput, create_preparation, list_preparations


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
                        st.write(f"**Отходы:** {p.waste_quantity} {p.output_unit.short_name}")
                        st.write(f"**Труд:** {p.labor_cost:,.2f}")
                        st.write(f"**Прочее:** {p.other_direct_cost:,.2f}")
                    with col2:
                        st.write(f"**Себестоимость (общая):** {p.total_cost:,.2f}")
                        st.write(f"**Себестоимость (ед):** {p.unit_cost:,.4f}")

                    st.subheader("Использованные ингредиенты")
                    ing_data = []
                    for use in p.ingredient_uses:
                        source_info = f" (Партия #{use.purchase_item_id})" if use.purchase_item_id else ""
                        ing_data.append(
                            {
                                "Ингредиент": use.ingredient.name + source_info,
                                "Кол-во": use.quantity,
                                "Ед.изм.": use.unit.short_name,
                                "Цена": use.unit_cost,
                                "Итого": use.total_cost,
                            }
                        )
                    st.table(ing_data)
        else:
            st.info("История заготовок пуста")

# --- New Preparation Tab ---
with tabs[1]:
    st.header("Новая заготовка")

    with SessionLocal() as db:
        available_batches = list_available_stock_batches(db)
        ing_batches = [b for b in available_batches if b.item_type == PurchaseItemType.INGREDIENT]

        batch_options = {
            f"{b.date} - {b.item_name} (Остаток: {b.current_quantity} {b.unit_short_name})": b
            for b in ing_batches
        }

        all_ingredients = {i.id: i for i in db.query(Ingredient).all()}
        all_units = {u.short_name: u for u in db.query(Unit).all()}

        if not ing_batches:
            st.warning("На складе нет доступных ингредиентов. Сначала оформите закупки.")
        else:
            col1, col2, col3 = st.columns(3)
            with col1:
                prep_date = st.date_input("Дата приготовления", value=date.today())
            with col2:
                prep_name = st.text_input("Название (например, Тесто для пельменей)")
            with col3:
                prep_comment = st.text_area("Комментарий", key="prep_comm")

            st.subheader("Выход и отходы")
            c1, c2, c3 = st.columns(3)
            with c1:
                output_qty = st.number_input("Кол-во на выходе (годное)", min_value=0.0, step=0.1, format="%.3f")
            with c2:
                waste_qty = st.number_input("Отходы/Обрезь", min_value=0.0, step=0.1, format="%.3f")
            with c3:
                output_unit_name = st.selectbox("Ед. изм.", options=list(all_units.keys()))

            st.subheader("Расходы")
            c3, c4, c5 = st.columns(3)
            with SessionLocal() as db_rate:
                current_labor_rate = db_rate.query(LaborRate).filter(LaborRate.is_active.is_(True)).first()
                rate_val = float(current_labor_rate.hourly_rate) if current_labor_rate else 0.0

            with c3:
                labor_hours = st.number_input("Время труда (часы)", min_value=0.0, step=0.1, format="%.2f")
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

            other_cost = st.number_input("Прочие прямые расходы", min_value=0.0, step=10.0, format="%.2f")

            st.subheader("Ингредиенты (до 5 в MVP)")
            ingredient_uses = []
            for i in range(5):
                st.markdown(f"**Ингредиент {i + 1}**")
                ca, cb, cc, cd = st.columns([4, 1, 2, 2.5])
                with ca:
                    batch_label = st.selectbox(
                        f"Выбор партии {i}",
                        options=[""] + list(batch_options.keys()),
                        key=f"batch_label_{i}",
                    )

                selected_batch = batch_options.get(batch_label)
                default_unit = selected_batch.unit_short_name if selected_batch else ""
                default_price = float(selected_batch.unit_price) if selected_batch else 0.0

                if selected_batch and st.session_state.get(f"ing_unit_{i}") != default_unit:
                    st.session_state[f"ing_unit_{i}"] = default_unit

                with cb:
                    u_name = st.selectbox(
                        f"Ед {i}",
                        options=list(all_units.keys()),
                        index=list(all_units.keys()).index(
                            st.session_state.get(f"ing_unit_{i}", default_unit or list(all_units.keys())[0])
                        ),
                        key=f"ing_unit_{i}",
                        disabled=selected_batch is not None,
                    )
                with cc:
                    qty = st.number_input(f"Кол-во {i}", min_value=0.0, step=0.1, format="%.3f", key=f"ing_qty_{i}")
                with cd:
                    line_total = Decimal(str(qty)) * Decimal(str(default_price))
                    st.session_state[f"ing_total_{i}"] = float(line_total)
                    st.number_input(
                        f"Стоимость {i}",
                        min_value=0.0,
                        step=1.0,
                        format="%.2f",
                        key=f"ing_total_{i}",
                        disabled=True,
                    )

                if selected_batch and qty > 0:
                    ingredient_uses.append(
                        PreparationIngredientInput(
                            ingredient=all_ingredients[selected_batch.item_id],
                            unit=all_units[u_name],
                            quantity=Decimal(str(qty)),
                            unit_cost=Decimal(str(default_price)),
                            purchase_item_id=selected_batch.batch_id,
                        )
                    )

            if st.button("Сохранить заготовку", type="primary"):
                if not prep_name:
                    st.error("Укажите название заготовки")
                elif output_qty <= 0:
                    st.error("Количество на выходе должно быть больше 0")
                elif not ingredient_uses:
                    st.error("Добавьте хотя бы один ингредиент")
                else:
                    try:
                        with SessionLocal() as db_write:
                            db_output_unit = db_write.merge(all_units[output_unit_name])
                            db_ing_uses = []
                            for use in ingredient_uses:
                                db_ing_uses.append(
                                    PreparationIngredientInput(
                                        ingredient=db_write.merge(use.ingredient),
                                        unit=db_write.merge(use.unit),
                                        quantity=use.quantity,
                                        unit_cost=use.unit_cost,
                                        purchase_item_id=use.purchase_item_id,
                                    )
                                )

                            create_preparation(
                                db_write,
                                prepared_on=prep_date,
                                name=prep_name,
                                output_quantity=Decimal(str(output_qty)),
                                waste_quantity=Decimal(str(waste_qty)),
                                output_unit=db_output_unit,
                                ingredient_uses=db_ing_uses,
                                labor_cost=calculated_labor_cost,
                                other_direct_cost=Decimal(str(other_cost)),
                                comment=prep_comment,
                            )
                            db_write.commit()
                            st.success(f"Заготовка '{prep_name}' успешно сохранена!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Ошибка при сохранении: {e}")
