"""Service for exporting data to Excel."""

from __future__ import annotations

import io
import pandas as pd
from sqlalchemy.orm import Session
from nutag.services.inventory import list_inventory_balances
from nutag.services.orders import list_orders
from nutag.services.production import list_production_batches


def export_inventory_to_excel(session: Session) -> bytes:
    """Export current inventory balances to Excel."""
    
    balances = list_inventory_balances(session)
    data = []
    for b in balances:
        data.append({
            "Тип": b.item_type,
            "Наименование": b.item_name,
            "Закуплено": float(b.purchased_quantity),
            "Использовано": float(b.used_quantity),
            "Остаток": float(b.current_quantity),
            "Ед.изм.": b.unit_short_name,
            "Средняя цена": float(b.weighted_average_price),
            "Стоимость остатка": float(b.current_quantity * b.weighted_average_price)
        })
    
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Inventory')
    return output.getvalue()


def export_orders_to_excel(session: Session) -> bytes:
    """Export all orders to Excel."""
    
    orders = list_orders(session)
    data = []
    for o in orders:
        data.append({
            "ID": o.id,
            "Дата": o.order_date,
            "Клиент": o.customer_name,
            "Статус": o.order_status,
            "Оплата": o.payment_status,
            "Сумма": float(o.total_amount),
            "Доставка": float(o.delivery_cost),
            "Итого": float(o.total_amount + o.delivery_cost),
            "Проблема": "Да" if o.has_problem else "Нет",
            "Комментарий": o.comment
        })
    
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Orders')
    return output.getvalue()


def export_production_to_excel(session: Session) -> bytes:
    """Export production history to Excel."""
    
    batches = list_production_batches(session)
    data = []
    for b in batches:
        data.append({
            "ID": b.id,
            "Дата": b.produced_on,
            "Продукт": b.product.name,
            "Выход (факт)": float(b.actual_output_quantity),
            "Ед.изм.": b.output_unit.short_name,
            "Себестоимость ед.": float(b.unit_cost),
            "Общая стоимость": float(b.total_cost),
            "Статус": b.status,
            "Комментарий": b.comment
        })
    
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Production')
    return output.getvalue()
