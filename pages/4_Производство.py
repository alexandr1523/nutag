"""Streamlit page for managing final production batches."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import streamlit as st

from nutag.db.models import Equipment, Ingredient, LaborRate, Packaging, Preparation, Product, PurchaseItemType, Unit
from nutag.db.session import create_engine_for_url, create_session_factory
from nutag.services.inventory import ExtendedItemType, list_available_stock_batches
from nutag.services.preparations import list_preparations
from nutag.services.production import (
    BatchIngredientInput,
    BatchPackagingInput,
    BatchPreparationInput,
    FinishedProductOutputInput,
    create_production_batch,
    list_production_batches,
)


def build_batch_option_label(batch) -> str:
    """Build a unique label for stock batch selectors."""

    return f"{batch.date} - {batch.item_name} (Остаток: {batch.current_quantity} {batch.unit_short_name}, ID: {batch.batch_id})"


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
                        out_data.append(
                            {
                                "Размер": out.package_size,
                                "Ед.изм.": out.package_unit.short_name,
                                "Кол-во упак.": out.package_count,
                                "Итого вес": out.total_quantity,
                            }
                        )
                    st.table(out_data)

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
                    for use in b.packaging_uses:
                        source_info = f" (Партия #{use.purchase_item_id})" if use.purchase_item_id else ""
                        uses_data.append(
                            {
                                "Тип": "Упаковка",
                                "Наименование": use.packaging.name + source_info,
                                "Кол-во": use.quantity,
                                "Ед": use.unit.short_name,
                                "Цена": use.unit_cost,
                                "Итого": use.total_cost,
                            }
                        )
                    st.table(uses_data)
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
        pkg_batch_options = {
            build_batch_option_label(b): b
            for b in available_batches
            if b.item_type == PurchaseItemType.PACKAGING
        }

        all_ingredients = {i.id: i for i in db.query(Ingredient).all()}
        all_packaging = {p.id: p for p in db.query(Packaging).all()}
        all_products = {p.name: p for p in db.query(Product).all()}
        all_units = {u.short_name: u for u in db.query(Unit).all()}
        all_equipment = {e.name: e for e in db.query(Equipment).all()}

        current_labor_rate = db.query(LaborRate).filter(LaborRate.is_active.is_(True)).first()
        labor_rate_val = float(current_labor_rate.hourly_rate) if current_labor_rate else 0.0

        preps_db = list_preparations(db)
        prep_objs = {p.id: p for p in preps_db}

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
                    ca, cb, cc, cd = st.columns([4, 1, 2, 2])
                    with ca:
                        i_batch_label = st.selectbox(
                            f"Выбор партии ингредиента {i}",
                            options=[""] + list(ing_batch_options.keys()),
                            key=f"bi_batch_{i}",
                        )

                    selected_i_batch = ing_batch_options.get(i_batch_label)
                    def_unit = selected_i_batch.unit_short_name if selected_i_batch else ""
                    def_price = float(selected_i_batch.unit_price) if selected_i_batch else 0.0

                    with cb:
                        u_name = st.selectbox(
                            f"Ед и {i}",
                            options=list(all_units.keys()),
                            index=list(all_units.keys()).index(def_unit) if def_unit in all_units else 0,
                            key=f"bi_unit_{i}",
                        )
                    with cc:
                        qty = st.number_input(f"Кол-во {i}", min_value=0.0, step=0.1, format="%.3f", key=f"bi_qty_{i}")
                    with cd:
                        st.write("Цена:")
                        st.info(f"{def_price:,.2f}")

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
                    ca, cb, cc, cd = st.columns([4, 1, 2, 2])
                    with ca:
                        p_batch_label = st.selectbox(
                            f"Выбор заготовки {i}",
                            options=[""] + list(prep_batch_options.keys()),
                            key=f"bp_batch_{i}",
                        )

                    selected_p_batch = prep_batch_options.get(p_batch_label)
                    def_unit = selected_p_batch.unit_short_name if selected_p_batch else ""
                    def_price = float(selected_p_batch.unit_price) if selected_p_batch else 0.0

                    with cb:
                        u_name = st.selectbox(
                            f"Ед з {i}",
                            options=list(all_units.keys()),
                            index=list(all_units.keys()).index(def_unit) if def_unit in all_units else 0,
                            key=f"bp_unit_{i}",
                        )
                    with cc:
                        qty = st.number_input(f"Кол-во з {i}", min_value=0.0, step=0.1, format="%.3f", key=f"bp_qty_{i}")
                    with cd:
                        st.write("Цена:")
                        st.info(f"{def_price:,.2f}")

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

                st.subheader("Упаковка (до 2)")
                pkg_uses = []
                for i in range(2):
                    ca, cb, cc, cd = st.columns([4, 1, 2, 2])
                    with ca:
                        pk_batch_label = st.selectbox(
                            f"Выбор партии упаковки {i}",
                            options=[""] + list(pkg_batch_options.keys()),
                            key=f"bpk_batch_{i}",
                        )

                    selected_pk_batch = pkg_batch_options.get(pk_batch_label)
                    def_unit = selected_pk_batch.unit_short_name if selected_pk_batch else ""
                    def_price = float(selected_pk_batch.unit_price) if selected_pk_batch else 0.0

                    with cb:
                        u_name = st.selectbox(
                            f"Ед уп {i}",
                            options=list(all_units.keys()),
                            index=list(all_units.keys()).index(def_unit) if def_unit in all_units else 0,
                            key=f"bpk_unit_{i}",
                        )
                    with cc:
                        qty = st.number_input(f"Кол-во уп {i}", min_value=0.0, step=1.0, format="%.0f", key=f"bpk_qty_{i}")
                    with cd:
                        st.write("Цена:")
                        st.info(f"{def_price:,.2f}")

                    if selected_pk_batch and qty > 0:
                        pkg_uses.append(
                            BatchPackagingInput(
                                packaging=all_packaging[selected_pk_batch.item_id],
                                unit=all_units[u_name],
                                quantity=Decimal(str(qty)),
                                unit_cost=Decimal(str(def_price)),
                                purchase_item_id=selected_pk_batch.batch_id,
                            )
                        )

                st.subheader("Фасовка ГП (до 2)")
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
                        out_inputs.append(
                            FinishedProductOutputInput(
                                package_size=Decimal(str(p_size)),
                                package_unit=all_units[p_unit],
                                package_count=p_count,
                            )
                        )

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
                                db_pkg_uses = [
                                    BatchPackagingInput(
                                        packaging=db_write.merge(u.packaging),
                                        unit=db_write.merge(u.unit),
                                        quantity=u.quantity,
                                        unit_cost=u.unit_cost,
                                        purchase_item_id=u.purchase_item_id,
                                    )
                                    for u in pkg_uses
                                ]
                                db_outputs = [
                                    FinishedProductOutputInput(
                                        package_size=u.package_size,
                                        package_unit=db_write.merge(u.package_unit),
                                        package_count=u.package_count,
                                    )
                                    for u in out_inputs
                                ]

                                create_production_batch(
                                    db_write,
                                    produced_on=batch_date,
                                    product=db_prod,
                                    actual_output_quantity=Decimal(str(actual_qty)),
                                    output_unit=db_unit,
                                    outputs=db_outputs,
                                    ingredient_uses=db_ing_uses,
                                    preparation_uses=db_p_uses,
                                    packaging_uses=db_pkg_uses,
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
