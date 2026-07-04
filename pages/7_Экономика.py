"""Streamlit page for viewing business economics and reports."""

from __future__ import annotations

import streamlit as st
from sqlalchemy import func
import pandas as pd

from nutag.db.init_db import initialize_database
from nutag.db.models import ProductionBatch
from nutag.db.session import create_engine_for_url, create_session_factory
from nutag.services.economics import list_finished_product_cost_reports
from nutag.services.orders import list_orders


st.set_page_config(page_title="Экономика | Nutag", page_icon="📊", layout="wide")

st.title("📊 Экономика")

# Session management
engine = create_engine_for_url()
initialize_database(engine)
SessionLocal = create_session_factory(engine)

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
        orders = list_orders(db)
        if not orders:
            st.info("Нет данных для анализа. Создайте хотя бы один заказ.")
        else:
        # Simple aggregation for MVP
            total_revenue = sum(o.total_amount for o in orders)
            total_delivery = sum(o.delivery_cost for o in orders)
        
        # Calculate COGS (simplified: sum of COGS for each order item)
        # For each order item, we try to find the unit cost from the linked batch
        # or from the latest batch of that product.
            total_cogs = 0
            for o in orders:
                for item in o.items:
                    unit_cost = 0
                    if item.batch_output and item.batch_output.packing_operation:
                        unit_cost = item.batch_output.packing_operation.unit_cost
                    elif item.batch_output:
                        unit_cost = item.batch_output.batch.unit_cost
                    else:
                    # Fallback to average unit cost for this product
                        avg_cost = db.query(func.avg(ProductionBatch.unit_cost)).filter(ProductionBatch.product_id == item.product_id).scalar()
                        unit_cost = avg_cost or 0
                
                    total_cogs += item.total_quantity * unit_cost

            margin = total_revenue - total_cogs - total_delivery
        
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Выручка", f"{total_revenue:,.2f}")
            col2.metric("Себестоимость (COGS)", f"{total_cogs:,.2f}")
            col3.metric("Доставка", f"{total_delivery:,.2f}")
            col4.metric("Маржа", f"{margin:,.2f}", delta=f"{(margin/total_revenue*100):.1f}%" if total_revenue > 0 else None)

            st.divider()
        
            st.subheader("Детальный отчет по заказам")
            report_data = []
            for o in orders:
                order_cogs = 0
                for item in o.items:
                    if item.batch_output and item.batch_output.packing_operation:
                        unit_cost = item.batch_output.packing_operation.unit_cost
                    elif item.batch_output:
                        unit_cost = item.batch_output.batch.unit_cost
                    else:
                        avg_cost = db.query(func.avg(ProductionBatch.unit_cost)).filter(ProductionBatch.product_id == item.product_id).scalar()
                        unit_cost = avg_cost or 0
                    order_cogs += item.total_quantity * unit_cost
            
                report_data.append({
                    "Дата": o.order_date,
                    "Клиент": o.customer_name,
                    "Выручка": float(o.total_amount),
                    "Себестоимость": float(order_cogs),
                    "Доставка": float(o.delivery_cost),
                    "Маржа": float(o.total_amount - order_cogs - o.delivery_cost),
                    "Статус": o.order_status,
                })
        
            st.dataframe(pd.DataFrame(report_data), use_container_width=True, hide_index=True)
