"""Inventory balance calculations built from persisted stock movements.

The current MVP slice only has purchase inflows, so balances are calculated from
purchase lines. Future production, write-off and personal-consumption outflows
can extend this module without changing Streamlit pages directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from nutag.db.models import PurchaseItem, PurchaseItemType
from nutag.services.calculations import calculate_weighted_average_price


@dataclass(frozen=True)
class InventoryBalance:
    """Aggregated balance for one inventory item."""

    item_type: PurchaseItemType
    item_name: str
    unit_short_name: str
    purchased_quantity: Decimal
    purchased_value: Decimal
    weighted_average_price: Decimal


def list_inventory_balances(session: Session) -> list[InventoryBalance]:
    """Return inventory balances aggregated by item type, item name and unit.

    Only purchase inflows are included at this stage. The result is ordered to be
    stable in tests and predictable in UI tables.
    """

    purchase_items = session.scalars(
        select(PurchaseItem).order_by(PurchaseItem.item_type, PurchaseItem.item_name, PurchaseItem.id)
    ).all()

    grouped: dict[tuple[PurchaseItemType, str, str], tuple[Decimal, Decimal]] = {}
    for item in purchase_items:
        key = (item.item_type, item.item_name, item.unit.short_name)
        quantity, value = grouped.get(key, (Decimal("0"), Decimal("0")))
        grouped[key] = (quantity + item.quantity, value + item.total_price)

    balances: list[InventoryBalance] = []
    for (item_type, item_name, unit_short_name), (quantity, value) in grouped.items():
        balances.append(
            InventoryBalance(
                item_type=item_type,
                item_name=item_name,
                unit_short_name=unit_short_name,
                purchased_quantity=quantity,
                purchased_value=value,
                weighted_average_price=calculate_weighted_average_price(
                    opening_quantity=0,
                    opening_value=0,
                    purchased_quantity=quantity,
                    purchased_value=value,
                ),
            )
        )

    return sorted(balances, key=lambda balance: (balance.item_type, balance.item_name, balance.unit_short_name))
