"""Streamlit page for viewing business economics and reports."""

from __future__ import annotations

import streamlit as st
from sqlalchemy.orm import Session
from sqlalchemy import func
from nutag.db.models import Order, OrderItem, ProductionBatch
from nutag.db.session import create_engine_for_url, create_session_factory
from nutag.services.orders import list_orders


st.set_page_config(page_title="Экономика | Nutag", page_icon="📊", layout="wide")

st.title("📊 Экономика")

# Session management
engine = create_engine_for_url()
SessionLocal = create_session_factory(engine)

with SessionLocal() as db:
    orders = list_orders(db)
    batches = db.query(ProductionBatch).all()
    
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
                if item.batch_output:
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
                if item.batch_output:
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
                "Статус": o.order_status
            })
        
        import pandas as pd
        st.dataframe(pd.DataFrame(report_data))
