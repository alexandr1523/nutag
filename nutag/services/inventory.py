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


from enum import StrEnum

class ExtendedItemType(StrEnum):
    """Expanded item types for inventory tracking."""
    INGREDIENT = "ingredient"
    PACKAGING = "packaging"
    CONSUMABLE = "consumable"
    PREPARATION = "preparation"
    PRODUCT = "product"

@dataclass(frozen=True)
class InventoryBalance:
    """Aggregated balance for one inventory item."""

    item_type: ExtendedItemType | PurchaseItemType
    item_id: int | str
    item_name: str
    unit_short_name: str
    inflow_quantity: Decimal
    inflow_value: Decimal
    outflow_quantity: Decimal
    current_quantity: Decimal
    weighted_average_price: Decimal


def list_inventory_balances(session: Session) -> list[InventoryBalance]:
    """Return inventory balances aggregated by item type, item name and unit.

    Includes purchase inflows, production/preparation inflows and outflows.
    """
    from nutag.db.models import (
        Order,
        OrderItem,
        Preparation,
        ProductionBatch,
        FinishedProductOutput,
        Product
    )

    # grouped by (item_type, item_id, item_name, unit_short_name)
    # value is (inflow_qty, inflow_val, outflow_qty)
    data: dict[tuple[str, int | str, str, str], list[Decimal]] = {}

    def add_inflow(item_type, item_id, name, unit, qty, val):
        key = (str(item_type), item_id, name, unit)
        if key not in data:
            data[key] = [Decimal("0"), Decimal("0"), Decimal("0")]
        data[key][0] += Decimal(str(qty))
        data[key][1] += Decimal(str(val))

    def add_outflow(item_type, item_id, name, unit, qty):
        key = (str(item_type), item_id, name, unit)
        if key not in data:
            data[key] = [Decimal("0"), Decimal("0"), Decimal("0")]
        data[key][2] += Decimal(str(qty))

    # 1. Purchase inflows
    purchase_items = session.scalars(select(PurchaseItem)).all()
    for item in purchase_items:
        item_id = 0
        if item.item_type == PurchaseItemType.INGREDIENT:
            item_id = item.ingredient_id or 0
        elif item.item_type == PurchaseItemType.PACKAGING:
            item_id = item.packaging_id or 0
        elif item.item_type == PurchaseItemType.CONSUMABLE:
            item_id = item.consumable_id or 0
        
        add_inflow(item.item_type, item_id, item.item_name, item.unit.short_name, item.quantity, item.total_price)

    # 2. Preparation inflows and outflows
    preps = session.scalars(select(Preparation)).all()
    for p in preps:
        add_inflow(ExtendedItemType.PREPARATION, p.name, p.name, p.output_unit.short_name, p.output_quantity, p.total_cost)
    
    # Ingredient usage in preparations (outflow)
    prep_uses = session.scalars(select(PreparationIngredientUse)).all()
    for use in prep_uses:
        add_outflow(PurchaseItemType.INGREDIENT, use.ingredient_id, use.ingredient.name, use.unit.short_name, use.quantity)

    # 3. Batch inflows and outflows
    batches = session.scalars(select(ProductionBatch)).all()
    for b in batches:
        # Ingredient usage in batches
        for use in b.ingredient_uses:
            add_outflow(PurchaseItemType.INGREDIENT, use.ingredient_id, use.ingredient.name, use.unit.short_name, use.quantity)
        # Preparation usage in batches
        for use in b.preparation_uses:
            add_outflow(ExtendedItemType.PREPARATION, use.preparation.name, use.preparation.name, use.unit.short_name, use.quantity)
        # Packaging usage in batches
        for use in b.packaging_uses:
            add_outflow(PurchaseItemType.PACKAGING, use.packaging_id, use.packaging.name, use.unit.short_name, use.quantity)
        
        # Finished product output (inflow)
        for out in b.outputs:
            # We track products by Product ID and Name
            add_inflow(ExtendedItemType.PRODUCT, b.product_id, b.product.name, out.package_unit.short_name, out.total_quantity, out.total_quantity * b.unit_cost)

    # 4. Order outflows (Finished products)
    orders = session.scalars(select(Order)).all()
    for o in orders:
        for item in o.items:
            add_outflow(ExtendedItemType.PRODUCT, item.product_id, item.product.name, item.package_unit.short_name, item.total_quantity)

    # 5. Build final list
    balances: list[InventoryBalance] = []
    for (item_type, item_id, item_name, unit_short_name), (in_qty, in_val, out_qty) in data.items():
        avg_price = (in_val / in_qty) if in_qty > 0 else Decimal("0")
        balances.append(
            InventoryBalance(
                item_type=item_type,
                item_id=item_id,
                item_name=item_name,
                unit_short_name=unit_short_name,
                inflow_quantity=in_qty,
                inflow_value=in_val,
                outflow_quantity=out_qty,
                current_quantity=in_qty - out_qty,
                weighted_average_price=avg_price
            )
        )

    return sorted(balances, key=lambda b: (b.item_type, b.item_name, b.unit_short_name))
