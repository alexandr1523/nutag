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

from nutag.db.models import (
    BatchIngredientUse,
    BatchPackagingUse,
    Ingredient,
    Packaging,
    Consumable,
    PreparationIngredientUse,
    PurchaseItem,
    PurchaseItemType,
)
from nutag.services.calculations import calculate_weighted_average_price


@dataclass(frozen=True)
class InventoryBalance:
    """Aggregated balance for one inventory item."""

    item_type: PurchaseItemType
    item_id: int
    item_name: str
    unit_short_name: str
    purchased_quantity: Decimal
    purchased_value: Decimal
    used_quantity: Decimal
    current_quantity: Decimal
    weighted_average_price: Decimal


def list_inventory_balances(session: Session) -> list[InventoryBalance]:
    """Return inventory balances aggregated by item type, item name and unit.

    Includes purchase inflows and production/preparation outflows.
    """

    # 1. Get purchase inflows
    purchase_items = session.scalars(
        select(PurchaseItem).order_by(PurchaseItem.item_type, PurchaseItem.item_name, PurchaseItem.id)
    ).all()

    # grouped by (item_type, item_id, item_name, unit_short_name)
    inflows: dict[tuple[PurchaseItemType, int, str, str], tuple[Decimal, Decimal]] = {}
    for item in purchase_items:
        # Determine item_id based on type
        item_id = 0
        if item.item_type == PurchaseItemType.INGREDIENT:
            item_id = item.ingredient_id or 0
        elif item.item_type == PurchaseItemType.PACKAGING:
            item_id = item.packaging_id or 0
        elif item.item_type == PurchaseItemType.CONSUMABLE:
            item_id = item.consumable_id or 0
            
        key = (item.item_type, item_id, item.item_name, item.unit.short_name)
        quantity, value = inflows.get(key, (Decimal("0"), Decimal("0")))
        inflows[key] = (quantity + item.quantity, value + item.total_price)

    # 2. Get outflows
    outflows: dict[tuple[PurchaseItemType, int, str, str], Decimal] = {}
    
    # Ingredient usage in preparations
    prep_uses = session.scalars(select(PreparationIngredientUse)).all()
    for use in prep_uses:
        key = (PurchaseItemType.INGREDIENT, use.ingredient_id, use.ingredient.name, use.unit.short_name)
        outflows[key] = outflows.get(key, Decimal("0")) + use.quantity
        
    # Ingredient usage in batches
    batch_ing_uses = session.scalars(select(BatchIngredientUse)).all()
    for use in batch_ing_uses:
        key = (PurchaseItemType.INGREDIENT, use.ingredient_id, use.ingredient.name, use.unit.short_name)
        outflows[key] = outflows.get(key, Decimal("0")) + use.quantity
        
    # Packaging usage in batches
    batch_pkg_uses = session.scalars(select(BatchPackagingUse)).all()
    for use in batch_pkg_uses:
        key = (PurchaseItemType.PACKAGING, use.packaging_id, use.packaging.name, use.unit.short_name)
        outflows[key] = outflows.get(key, Decimal("0")) + use.quantity

    # 3. Combine
    balances: list[InventoryBalance] = []
    # Use inflows keys and outflows keys to cover all items
    all_keys = set(inflows.keys()) | set(outflows.keys())
    
    for key in all_keys:
        item_type, item_id, item_name, unit_short_name = key
        p_quantity, p_value = inflows.get(key, (Decimal("0"), Decimal("0")))
        u_quantity = outflows.get(key, Decimal("0"))
        
        balances.append(
            InventoryBalance(
                item_type=item_type,
                item_id=item_id,
                item_name=item_name,
                unit_short_name=unit_short_name,
                purchased_quantity=p_quantity,
                purchased_value=p_value,
                used_quantity=u_quantity,
                current_quantity=p_quantity - u_quantity,
                weighted_average_price=calculate_weighted_average_price(
                    opening_quantity=0,
                    opening_value=0,
                    purchased_quantity=p_quantity,
                    purchased_value=p_value,
                ) if p_quantity > 0 else Decimal("0"),
            )
        )

    return sorted(balances, key=lambda b: (b.item_type, b.item_name, b.unit_short_name))
