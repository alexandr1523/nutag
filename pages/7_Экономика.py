"""Streamlit page for viewing business economics and reports."""

from __future__ import annotations

import streamlit as st
import pandas as pd

from nutag.db.runtime import create_app_database
from nutag.services.economics import list_finished_product_cost_reports, list_order_margin_reports
from nutag.ui.auth import require_app_access


st.set_page_config(page_title="Экономика | Nutag", page_icon="📊", layout="wide")
require_app_access()

st.title("📊 Экономика")

# Session management
engine, SessionLocal = create_app_database()

with SessionLocal() as db:
    tabs = st.tabs(["Себестоимость партий ГП", "Заказы и маржа"])

    with tabs[0]:
        st.subheader("Фактическая прямая себестоимость фасованных партий ГП")
        st.caption(
            "Fast-track отчёт использует только трассируемые фактические операции: производство, "
            "нефасованный выпуск и фасовку. Амортизация, расходные материалы и постоянные расходы "
            "пока показаны как не включённые компоненты."
        )
        reports = list_finished_product_cost_reports(db)
        if not reports:
            st.info("Фасованных партий готовой продукции пока нет.")
        else:
            total_direct_cost = sum(report.total_direct_cost for report in reports)
            total_packages = sum(report.package_count for report in reports)
            col1, col2, col3 = st.columns(3)
            col1.metric("Фасованных партий", len(reports))
            col2.metric("Фасовок всего", f"{total_packages:,.0f}")
            col3.metric("Прямая себестоимость", f"{total_direct_cost:,.2f}")

            rows = [
                {
                    "Операция фасовки": f"#{report.packing_id}",
                    "Партия ГП": f"#{report.output_id}",
                    "Продукт": report.product_name,
                    "Дата производства": report.produced_on,
                    "Дата фасовки": report.packed_on,
                    "Размер фасовки": (
                        f"{report.package_count} x {report.package_size:,.3f} "
                        f"{report.unit_short_name}"
                    ),
                    "Итого выпуск": f"{report.total_quantity:,.3f} {report.unit_short_name}",
                    "Ингредиенты": float(report.ingredient_cost),
                    "Заготовки": float(report.preparation_cost),
                    "Труд": float(report.labor_cost),
                    "Нефасованный выпуск": float(report.unpacked_output_cost),
                    "Упаковка": float(report.packaging_cost),
                    "Себестоимость партии": float(report.total_direct_cost),
                    "Себестоимость 1 фасовки": float(report.cost_per_package),
                    "Себестоимость базовой ед.": float(report.cost_per_base_unit),
                    "Пока не включено": ", ".join(report.excluded_components),
                }
                for report in reports
            ]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with tabs[1]:
        st.subheader("Fast-track валовая маржа заказов")
        st.caption(
            "Расчёт использует продажную цену заказа и себестоимость выбранной фасованной партии ГП. "
            "Амортизация, расходные материалы и постоянные расходы пока не включены."
        )
        reports = list_order_margin_reports(db)
        if not reports:
            st.info("Нет данных для анализа. Создайте хотя бы один заказ.")
        else:
            total_revenue = sum(report.revenue for report in reports)
            total_direct_cost = sum(report.direct_cost for report in reports)
            total_delivery = sum(report.delivery_cost for report in reports)
            total_margin = sum(report.gross_margin for report in reports)
            margin_percent = total_margin / total_revenue * 100 if total_revenue > 0 else None

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Выручка", f"{total_revenue:,.2f}")
            col2.metric("Прямая себестоимость", f"{total_direct_cost:,.2f}")
            col3.metric("Доставка", f"{total_delivery:,.2f}")
            col4.metric(
                "Валовая маржа",
                f"{total_margin:,.2f}",
                delta=f"{margin_percent:.1f}%" if margin_percent is not None else None,
            )

            st.divider()

            st.subheader("Заказы")
            order_rows = [
                {
                    "Заказ": f"#{report.order_id}",
                    "Дата": report.order_date,
                    "Клиент": report.customer_name,
                    "Выручка": float(report.revenue),
                    "Прямая себестоимость": float(report.direct_cost),
                    "Доставка": float(report.delivery_cost),
                    "Валовая маржа": float(report.gross_margin),
                    "Маржа, %": (
                        float(report.gross_margin_percent)
                        if report.gross_margin_percent is not None
                        else None
                    ),
                    "Статус заказа": report.order_status,
                    "Оплата": report.payment_status,
                    "Резерв": report.reservation_status,
                    "Пока не включено": ", ".join(report.excluded_components),
                }
                for report in reports
            ]
            st.dataframe(pd.DataFrame(order_rows), use_container_width=True, hide_index=True)

            st.subheader("Строки заказов")
            line_rows = [
                {
                    "Заказ": f"#{report.order_id}",
                    "Клиент": report.customer_name,
                    "Продукт": line.product_name,
                    "Партия ГП": f"#{line.output_id}" if line.output_id is not None else "Не выбрана",
                    "Производственная партия": (
                        f"#{line.batch_id}" if line.batch_id is not None else "Не выбрана"
                    ),
                    "Фасовка": f"{line.package_size:,.3f} {line.unit_short_name}",
                    "Кол-во фасовок": line.package_count,
                    "Цена продажи за 1 фасовку": float(line.sale_price_per_package),
                    "Себестоимость 1 фасовки": float(line.direct_cost_per_package),
                    "Маржа на 1 фасовку": float(line.margin_per_package),
                    "Выручка строки": float(line.revenue),
                    "Себестоимость строки": float(line.direct_cost),
                    "Маржа строки": float(line.margin),
                    "Маржа строки, %": (
                        float(line.margin_percent)
                        if line.margin_percent is not None
                        else None
                    ),
                    "Источник себестоимости": line.cost_source,
                }
                for report in reports
                for line in report.lines
            ]
            if line_rows:
                st.dataframe(pd.DataFrame(line_rows), use_container_width=True, hide_index=True)
            else:
                st.warning("В заказах нет строк с выбранной партией готовой продукции для расчёта маржи.")
