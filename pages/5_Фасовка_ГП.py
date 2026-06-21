"""Streamlit page for packing unpacked finished product stock."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pandas as pd
import streamlit as st

from nutag.db.init_db import initialize_database
from nutag.db.models import FinishedProductPacking, Packaging, PurchaseItemType, Unit
from nutag.db.session import create_engine_for_url, create_session_factory
from nutag.services.inventory import list_available_bulk_finished_product_outputs, list_available_stock_batches
from nutag.services.packing import pack_finished_product


def format_money(value: Decimal | int | float | str) -> str:
    return f"{Decimal(str(value)):,.2f}"


def build_bulk_label(stock) -> str:
    stock_total_cost = Decimal(str(stock.current_quantity)) * Decimal(str(stock.unit_cost))
    return (
        f"{stock.product_name} | нефасованный остаток #{stock.bulk_output_id} | "
        f"партия производства #{stock.output.batch_id} от {stock.produced_on} | "
        f"остаток {stock.current_quantity:,.3f} {stock.unit_short_name} | "
        f"себестоимость остатка {stock_total_cost:,.2f}"
    )


def build_packaging_label(stock) -> str:
    return (
        f"{stock.item_name} | закупочная партия #{stock.batch_id} от {stock.date} | "
        f"остаток {stock.current_quantity:,.3f} {stock.unit_short_name} | "
        f"цена {stock.unit_price:,.4f}"
    )


st.set_page_config(page_title="Фасовка ГП | Nutag", page_icon="📦", layout="wide")

st.title("📦 Фасовка ГП")

engine = create_engine_for_url()
initialize_database(engine)
SessionLocal = create_session_factory(engine)

tabs = st.tabs(["Новая фасовка", "История фасовки"])

with tabs[0]:
    st.header("Новая фасовка")

    saved_message = st.session_state.pop("packing_saved_message", None)
    if saved_message:
        st.success(saved_message)

    if "packing_form_version" not in st.session_state:
        st.session_state.packing_form_version = 0
    form_version = st.session_state.packing_form_version

    def field_key(name: str) -> str:
        return f"packing_{form_version}_{name}"

    with SessionLocal() as db:
        bulk_outputs = list_available_bulk_finished_product_outputs(db)
        packaging_batches = [
            batch
            for batch in list_available_stock_batches(db)
            if batch.item_type == PurchaseItemType.PACKAGING
        ]
        packaging_by_id = {packaging.id: packaging for packaging in db.query(Packaging).all()}
        units_by_short_name = {unit.short_name: unit for unit in db.query(Unit).all()}

        bulk_options = {build_bulk_label(stock): stock for stock in bulk_outputs}
        packaging_options = {build_packaging_label(stock): stock for stock in packaging_batches}

        if not bulk_options:
            st.warning("Нет доступных нефасованных остатков готовой продукции. Сначала создайте производственную партию.")
        elif not packaging_options:
            st.warning("Нет доступных партий упаковки. Сначала добавьте закупку упаковки.")
        else:
            c1, c2 = st.columns(2)
            with c1:
                packed_on = st.date_input("Дата фасовки", value=date.today(), key=field_key("packed_on"))
            with c2:
                storage_place = st.text_input("Место хранения", key=field_key("storage_place"))

            bulk_label = st.selectbox(
                "Нефасованный остаток",
                options=list(bulk_options.keys()),
                key=field_key("bulk_output"),
            )
            selected_bulk = bulk_options[bulk_label]

            packaging_label = st.selectbox(
                "Партия упаковки",
                options=list(packaging_options.keys()),
                key=field_key("packaging_batch"),
            )
            selected_packaging_batch = packaging_options[packaging_label]
            selected_packaging = packaging_by_id.get(int(selected_packaging_batch.item_id))

            st.caption(
                f"Нефасованный остаток списывается в единицах: {selected_bulk.unit_short_name}. "
                f"Упаковка списывается в единицах: {selected_packaging_batch.unit_short_name}."
            )

            st.subheader("Параметры фасовки")
            p1, p2, p3 = st.columns(3)
            with p1:
                package_size = st.number_input(
                    "Размер фасовки",
                    min_value=0.0,
                    step=0.1,
                    format="%.3f",
                    key=field_key("package_size"),
                )
            with p2:
                st.caption("Ед. изм. фасовки")
                st.write(selected_bulk.unit_short_name)
            with p3:
                package_count = st.number_input(
                    "Количество фасовок",
                    min_value=0,
                    step=1,
                    key=field_key("package_count"),
                )

            total_quantity = Decimal(str(package_size)) * Decimal(package_count)
            packaging_quantity = Decimal(package_count)
            bulk_value = total_quantity * Decimal(str(selected_bulk.unit_cost))
            packaging_value = packaging_quantity * Decimal(str(selected_packaging_batch.unit_price))
            total_cost = bulk_value + packaging_value
            unit_cost = total_cost / total_quantity if total_quantity > 0 else Decimal("0")

            st.subheader("Расчёт")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Итоговый выпуск", f"{total_quantity:,.3f} {selected_bulk.unit_short_name}")
            m2.metric("Стоимость списываемого нефасованного остатка", format_money(bulk_value))
            m3.metric("Стоимость упаковки", format_money(packaging_value))
            m4.metric("Себестоимость за ед.", f"{unit_cost:,.4f}")

            st.caption(
                f"Будет списано упаковки: {packaging_quantity:,.0f} {selected_packaging_batch.unit_short_name}. "
                f"Доступно: {selected_packaging_batch.current_quantity:,.3f} {selected_packaging_batch.unit_short_name}."
            )

            optional_dates = st.checkbox("Указать даты заморозки и годности", key=field_key("optional_dates"))
            frozen_on = None
            use_by = None
            if optional_dates:
                d1, d2 = st.columns(2)
                with d1:
                    frozen_on = st.date_input("Дата заморозки", value=date.today(), key=field_key("frozen_on"))
                with d2:
                    use_by = st.date_input("Годен до", value=date.today(), key=field_key("use_by"))

            comment = st.text_area("Комментарий", key=field_key("comment"))

            submitted = st.button("Сохранить фасовку", type="primary", key=field_key("save"))
            if submitted:
                submit_errors = []
                if package_size <= 0:
                    submit_errors.append("Размер фасовки должен быть больше 0.")
                if package_count <= 0:
                    submit_errors.append("Количество фасовок должно быть больше 0.")
                if total_quantity > Decimal(str(selected_bulk.current_quantity)):
                    submit_errors.append("Итоговый выпуск превышает доступный нефасованный остаток.")
                if packaging_quantity > Decimal(str(selected_packaging_batch.current_quantity)):
                    submit_errors.append("Количество фасовок превышает доступный остаток выбранной упаковки.")
                if selected_packaging is None:
                    submit_errors.append("Выбранная упаковка не найдена в справочнике.")
                if selected_bulk.unit_short_name not in units_by_short_name:
                    submit_errors.append("Единица нефасованного остатка отсутствует в справочнике.")
                if selected_packaging_batch.unit_short_name not in units_by_short_name:
                    submit_errors.append("Единица упаковки отсутствует в справочнике.")
                if use_by is not None and use_by < packed_on:
                    submit_errors.append("Дата 'Годен до' не может быть раньше даты фасовки.")
                if frozen_on is not None and use_by is not None and use_by < frozen_on:
                    submit_errors.append("Дата 'Годен до' не может быть раньше даты заморозки.")

                if submit_errors:
                    for error in submit_errors:
                        st.error(error)
                else:
                    try:
                        with SessionLocal() as db_write:
                            db_packaging = db_write.merge(selected_packaging)
                            db_packaging_unit = db_write.merge(
                                units_by_short_name[selected_packaging_batch.unit_short_name]
                            )
                            db_package_unit = db_write.merge(units_by_short_name[selected_bulk.unit_short_name])
                            packing = pack_finished_product(
                                db_write,
                                packed_on=packed_on,
                                source_bulk_output_id=selected_bulk.bulk_output_id,
                                packaging=db_packaging,
                                packaging_unit=db_packaging_unit,
                                packaging_purchase_item_id=selected_packaging_batch.batch_id,
                                package_size=Decimal(str(package_size)),
                                package_unit=db_package_unit,
                                package_count=package_count,
                                frozen_on=frozen_on,
                                use_by=use_by,
                                storage_place=storage_place,
                                comment=comment,
                            )
                            db_write.commit()
                            st.session_state.packing_form_version += 1
                            st.session_state.packing_saved_message = (
                                f"Фасовка #{packing.id} сохранена: "
                                f"{total_quantity:,.3f} {selected_bulk.unit_short_name}."
                            )
                            st.rerun()
                    except Exception as exc:
                        st.error(f"Ошибка при сохранении: {exc}")

with tabs[1]:
    st.header("История фасовки")

    with SessionLocal() as db:
        packings = (
            db.query(FinishedProductPacking)
            .order_by(FinishedProductPacking.packed_on.desc(), FinishedProductPacking.id.desc())
            .all()
        )

        if not packings:
            st.info("Операций фасовки пока нет.")
        else:
            rows = []
            for packing in packings:
                rows.append(
                    {
                        "Дата": packing.packed_on,
                        "Фасовка": f"#{packing.id}",
                        "Продукт": packing.finished_output.batch.product.name,
                        "Нефасованный остаток": f"#{packing.source_bulk_output_id}",
                        "Выпуск": (
                            f"{packing.finished_output.package_count} x "
                            f"{packing.finished_output.package_size:,.3f} "
                            f"{packing.finished_output.package_unit.short_name}"
                        ),
                        "Итого": (
                            f"{packing.finished_output.total_quantity:,.3f} "
                            f"{packing.finished_output.package_unit.short_name}"
                        ),
                        "Упаковка": packing.packaging.name,
                        "Партия упаковки": f"#{packing.packaging_purchase_item_id}",
                        "Стоимость упаковки": f"{packing.packaging_total_cost:,.2f}",
                        "Себестоимость ед.": f"{packing.unit_cost:,.4f}",
                        "Комментарий": packing.comment or "",
                    }
                )

            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
