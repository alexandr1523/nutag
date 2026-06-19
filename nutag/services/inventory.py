"""Inventory balance calculations built from persisted stock movements.

The current MVP slice only has purchase inflows, so balances are calculated from
purchase lines. Future production, write-off and personal-consumption outflows
can extend this module without changing Streamlit pages directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from datetime import date
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
    INGREDIENT = "Ингредиент"
    PACKAGING = "Упаковка"
    CONSUMABLE = "Расходник"
    PREPARATION = "Заготовка"
    PRODUCT = "Готовый продукт"

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


@dataclass(frozen=True)
class StockBatch:
    """A specific batch of inventory from a purchase or preparation."""
    batch_type: str  # "purchase" or "preparation"
    batch_id: int    # ID of PurchaseItem or Preparation
    item_type: str
    item_id: int | str
    item_name: str
    date: date
    unit_short_name: str
    initial_quantity: Decimal
    current_quantity: Decimal
    unit_price: Decimal


def list_available_stock_batches(session: Session) -> list[StockBatch]:
    """List all batches with positive current quantity.
    
    Correctly handles legacy data (records without source batch IDs) by deducting 
    unlinked outflows from the oldest available batches of that item.
    """
    from nutag.db.models import (
        PurchaseItem,
        Preparation,
        PreparationIngredientUse,
        BatchIngredientUse,
        BatchPreparationUse,
        BatchPackagingUse
    )
    from sqlalchemy import func

    # 1. Gather all purchase inflows
    purchase_items = session.query(PurchaseItem).order_by(PurchaseItem.id).all()
    pi_batches = []
    for pi in purchase_items:
        item_id = 0
        if pi.item_type == PurchaseItemType.INGREDIENT:
            item_id = pi.ingredient_id or 0
        elif pi.item_type == PurchaseItemType.PACKAGING:
            item_id = pi.packaging_id or 0
        elif pi.item_type == PurchaseItemType.CONSUMABLE:
            item_id = pi.consumable_id or 0

        pi_batches.append({
            "id": pi.id,
            "item_type": pi.item_type,
            "item_id": item_id,
            "item_name": pi.item_name,
            "date": pi.purchase.purchase_date,
            "unit": pi.unit.short_name,
            "initial": pi.quantity,
            "remaining": pi.quantity,
            "price": pi.unit_price
        })

    # 2. Gather all preparation inflows
    preps = session.query(Preparation).order_by(Preparation.id).all()
    prep_batches = []
    for p in preps:
        prep_batches.append({
            "id": p.id,
            "item_type": ExtendedItemType.PREPARATION,
            "item_id": p.name,
            "item_name": p.name,
            "date": p.prepared_on,
            "unit": p.output_unit.short_name,
            "initial": p.output_quantity,
            "remaining": p.output_quantity,
            "price": p.unit_cost
        })

    # 3. Deduct linked outflows (NEW logic)
    # Linked Purchases
    for model in [PreparationIngredientUse, BatchIngredientUse, BatchPackagingUse]:
        linked = session.query(model.purchase_item_id, func.sum(model.quantity))\
            .filter(model.purchase_item_id.isnot(None))\
            .group_by(model.purchase_item_id).all()
        for pi_id, qty in linked:
            for b in pi_batches:
                if b["id"] == pi_id:
                    b["remaining"] -= Decimal(str(qty))
                    break

    # Linked Preparations
    linked_preps = session.query(BatchPreparationUse.source_preparation_id, func.sum(BatchPreparationUse.quantity))\
        .filter(BatchPreparationUse.source_preparation_id.isnot(None))\
        .group_by(BatchPreparationUse.source_preparation_id).all()
    for prep_id, qty in linked_preps:
        for b in prep_batches:
            if b["id"] == prep_id:
                b["remaining"] -= Decimal(str(qty))
                break

    # 4. Deduct unlinked (LEGACY) outflows using FIFO
    # Legacy Purchases
    for model, itype_attr, iid_attr in [
        (PreparationIngredientUse, "ingredient", "ingredient_id"),
        (BatchIngredientUse, "ingredient", "ingredient_id"),
        (BatchPackagingUse, "packaging", "packaging_id")
    ]:
        expected_item_type = PurchaseItemType[itype_attr.upper()]
        unlinked = session.query(getattr(model, iid_attr), func.sum(model.quantity))\
            .filter(model.purchase_item_id.is_(None))\
            .group_by(getattr(model, iid_attr)).all()
        
        for item_id, qty in unlinked:
            qty_to_deduct = Decimal(str(qty))
            # Find relevant batches and deduct FIFO
            for b in pi_batches:
                if b["item_type"] == expected_item_type and b["item_id"] == item_id and b["remaining"] > 0:
                    deduct = min(b["remaining"], qty_to_deduct)
                    b["remaining"] -= deduct
                    qty_to_deduct -= deduct
                    if qty_to_deduct <= 0: break

    # Legacy Preparations
    unlinked_preps = session.query(BatchPreparationUse.preparation_id, func.sum(BatchPreparationUse.quantity))\
        .filter(BatchPreparationUse.source_preparation_id.is_(None))\
        .group_by(BatchPreparationUse.preparation_id).all()
    
    for prep_id, qty in unlinked_preps:
        # Note: preparation_id links to Preparation table
        qty_to_deduct = Decimal(str(qty))
        # Find prep by ID to get its name (since we use name as item_id for preps)
        target_prep = session.get(Preparation, prep_id)
        if not target_prep: continue
        
        for b in prep_batches:
            if b["item_name"] == target_prep.name and b["remaining"] > 0:
                deduct = min(b["remaining"], qty_to_deduct)
                b["remaining"] -= deduct
                qty_to_deduct -= deduct
                if qty_to_deduct <= 0: break

    # 5. Convert to StockBatch dataclasses
    result = []
    for b in pi_batches + prep_batches:
        if b["remaining"] > 0:
            result.append(StockBatch(
                batch_type="purchase" if b["item_type"] != ExtendedItemType.PREPARATION else "preparation",
                batch_id=b["id"],
                item_type=b["item_type"],
                item_id=b["item_id"],
                item_name=b["item_name"],
                date=b["date"],
                unit_short_name=b["unit"],
                initial_quantity=b["initial"],
                current_quantity=b["remaining"],
                unit_price=b["price"]
            ))

    return sorted(result, key=lambda x: x.date)


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
