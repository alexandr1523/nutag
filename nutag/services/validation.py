"""Service for validating business data and generating control signals."""

from __future__ import annotations

from dataclasses import dataclass
from sqlalchemy.orm import Session
from nutag.services.inventory import list_inventory_balances
from nutag.services.orders import list_orders
from nutag.services.production import list_production_batches


@dataclass(frozen=True)
class ControlSignal:
    """A warning or error signal identified in the system data."""
    
    level: str  # "warning" or "error"
    category: str
    message: str


def get_control_signals(session: Session) -> list[ControlSignal]:
    """Audit the database and return identified issues."""
    
    signals = []
    
    # 1. Negative stocks
    balances = list_inventory_balances(session)
    for b in balances:
        if b.current_quantity < 0:
            signals.append(ControlSignal(
                level="error",
                category="Склад",
                message=f"Отрицательный остаток: {b.item_name} ({b.current_quantity:,.3f} {b.unit_short_name})"
            ))
            
    # 2. Production without output
    batches = list_production_batches(session)
    for b in batches:
        if b.actual_output_quantity <= 0:
            signals.append(ControlSignal(
                level="error",
                category="Производство",
                message=f"Партия #{b.id} ({b.produced_on}) не имеет фактического выхода."
            ))
        if b.unit_cost <= 0:
             signals.append(ControlSignal(
                level="warning",
                category="Производство",
                message=f"Нулевая себестоимость в партии #{b.id} ({b.produced_on}). Проверьте расходы."
            ))
             
    # 3. Orders with problems
    orders = list_orders(session)
    for o in orders:
        if o.has_problem:
            signals.append(ControlSignal(
                level="warning",
                category="Заказы",
                message=f"Заказ #{o.id} ({o.customer_name}) отмечен как проблемный."
            ))
        if o.total_amount <= 0:
            signals.append(ControlSignal(
                level="warning",
                category="Заказы",
                message=f"Заказ #{o.id} ({o.customer_name}) имеет нулевую сумму."
            ))
            
    return signals
