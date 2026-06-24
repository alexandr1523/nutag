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
from nutag.services.calculations import to_decimal


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


@dataclass(frozen=True)
class FinishedProductStock:
    """Available finished product output with remaining quantity for order selection."""

    output_id: int
    product_id: int
    product_name: str
    package_size: Decimal
    unit_short_name: str
    produced_on: date
    total_quantity: Decimal
    physical_quantity: Decimal
    reserved_quantity: Decimal
    available_quantity: Decimal
    current_quantity: Decimal
    current_package_count: Decimal
    available_package_count: Decimal
    unit_cost: Decimal
    output: object


@dataclass(frozen=True)
class BulkFinishedProductStock:
    """Available unpacked finished product stock from a production batch."""

    bulk_output_id: int
    product_id: int
    product_name: str
    produced_on: date
    unit_short_name: str
    initial_quantity: Decimal
    current_quantity: Decimal
    unit_cost: Decimal
    output: object


def get_available_purchase_batch(
    session: Session,
    *,
    purchase_item_id: int,
    expected_item_type: PurchaseItemType,
    expected_item_id: int,
    expected_unit_short_name: str,
    quantity: Decimal | int | float | str,
) -> StockBatch:
    """Return a selected purchase batch and validate it can cover an outflow."""

    quantity_decimal = to_decimal(quantity)
    batch = next(
        (
            stock_batch
            for stock_batch in list_available_stock_batches(session)
            if stock_batch.batch_type == "purchase" and stock_batch.batch_id == purchase_item_id
        ),
        None,
    )
    if batch is None:
        raise ValueError("Выбранная партия закупки недоступна или уже израсходована")
    if batch.item_type != expected_item_type or batch.item_id != expected_item_id:
        raise ValueError("Выбранная партия закупки не соответствует списываемой позиции")
    if batch.unit_short_name != expected_unit_short_name:
        raise ValueError("Единица измерения выбранной партии закупки не соответствует списанию")
    if batch.current_quantity < quantity_decimal:
        raise ValueError("Недостаточно остатка в выбранной партии закупки")

    return batch


def get_available_preparation_batch(
    session: Session,
    *,
    source_preparation_id: int,
    expected_preparation_name: str,
    expected_unit_short_name: str,
    quantity: Decimal | int | float | str,
) -> StockBatch:
    """Return a selected preparation batch and validate it can cover an outflow."""

    quantity_decimal = to_decimal(quantity)
    batch = next(
        (
            stock_batch
            for stock_batch in list_available_stock_batches(session)
            if stock_batch.batch_type == "preparation" and stock_batch.batch_id == source_preparation_id
        ),
        None,
    )
    if batch is None:
        raise ValueError("Выбранная заготовка недоступна или уже израсходована")
    if batch.item_type != ExtendedItemType.PREPARATION or batch.item_name != expected_preparation_name:
        raise ValueError("Выбранная заготовка не соответствует списываемой позиции")
    if batch.unit_short_name != expected_unit_short_name:
        raise ValueError("Единица измерения выбранной заготовки не соответствует списанию")
    if batch.current_quantity < quantity_decimal:
        raise ValueError("Недостаточно остатка в выбранной заготовке")

    return batch


def get_available_bulk_finished_product_output(
    session: Session,
    *,
    bulk_output_id: int,
    expected_unit_short_name: str,
    quantity: Decimal | int | float | str,
    expected_product_id: int | None = None,
) -> BulkFinishedProductStock:
    """Return a selected unpacked finished product output and validate availability."""

    quantity_decimal = to_decimal(quantity)
    batch = next(
        (
            stock
            for stock in list_available_bulk_finished_product_outputs(session)
            if stock.bulk_output_id == bulk_output_id
        ),
        None,
    )
    if batch is None:
        raise ValueError("Выбранный нефасованный остаток готовой продукции недоступен или уже израсходован")
    if expected_product_id is not None and batch.product_id != expected_product_id:
        raise ValueError("Выбранный нефасованный остаток не соответствует продукту")
    if batch.unit_short_name != expected_unit_short_name:
        raise ValueError("Единица измерения нефасованного остатка не соответствует фасовке")
    if batch.current_quantity < quantity_decimal:
        raise ValueError("Недостаточно нефасованного остатка готовой продукции")

    return batch


def get_available_finished_product_output(
    session: Session,
    *,
    batch_output_id: int,
    expected_product_id: int,
    expected_package_size: Decimal | int | float | str,
    expected_unit_short_name: str,
    quantity: Decimal | int | float | str,
):
    """Return a selected finished output and validate it can cover an order outflow."""

    from nutag.db.models import FinishedProductOutput, Order, OrderItem, OrderStatus, ReservationStatus
    from sqlalchemy import func

    quantity_decimal = to_decimal(quantity)
    output = session.get(FinishedProductOutput, batch_output_id)
    if output is None:
        raise ValueError("Выбранная партия готовой продукции не найдена")
    if output.batch is None or output.package_unit is None:
        raise ValueError("Выбранная партия готовой продукции недоступна")
    if output.batch.product_id != expected_product_id:
        raise ValueError("Выбранная партия готовой продукции не соответствует продукту заказа")
    if output.package_size != to_decimal(expected_package_size):
        raise ValueError("Размер упаковки выбранной партии готовой продукции не соответствует заказу")
    if output.package_unit.short_name != expected_unit_short_name:
        raise ValueError("Единица упаковки выбранной партии готовой продукции не соответствует заказу")

    delivered_quantity = session.query(func.coalesce(func.sum(OrderItem.total_quantity), 0))\
        .join(Order, Order.id == OrderItem.order_id)\
        .filter(OrderItem.batch_output_id == batch_output_id)\
        .filter(Order.order_status == OrderStatus.DELIVERED)\
        .scalar()
    physical_quantity = output.total_quantity - Decimal(str(delivered_quantity))
    reserved_quantity = session.query(func.coalesce(func.sum(OrderItem.total_quantity), 0))\
        .join(Order, Order.id == OrderItem.order_id)\
        .filter(OrderItem.batch_output_id == batch_output_id)\
        .filter(Order.order_status.notin_([OrderStatus.DELIVERED, OrderStatus.CANCELLED]))\
        .filter(Order.reservation_status.in_([ReservationStatus.RESERVED, ReservationStatus.PARTIAL]))\
        .scalar()
    available_quantity = physical_quantity - Decimal(str(reserved_quantity))
    if available_quantity < quantity_decimal:
        raise ValueError("Недостаточно остатка в выбранной партии готовой продукции")

    return output


def list_available_finished_product_outputs(session: Session) -> list[FinishedProductStock]:
    """List finished product outputs with positive remaining quantity."""

    from nutag.db.models import FinishedProductOutput, Order, OrderItem, OrderStatus, ReservationStatus
    from sqlalchemy import func

    delivered_rows = session.query(OrderItem.batch_output_id, func.sum(OrderItem.total_quantity))\
        .join(Order, Order.id == OrderItem.order_id)\
        .filter(OrderItem.batch_output_id.isnot(None))\
        .filter(Order.order_status == OrderStatus.DELIVERED)\
        .group_by(OrderItem.batch_output_id)\
        .all()
    delivered_by_output_id = {
        output_id: Decimal(str(quantity))
        for output_id, quantity in delivered_rows
    }
    reserved_rows = session.query(OrderItem.batch_output_id, func.sum(OrderItem.total_quantity))\
        .join(Order, Order.id == OrderItem.order_id)\
        .filter(OrderItem.batch_output_id.isnot(None))\
        .filter(Order.order_status.notin_([OrderStatus.DELIVERED, OrderStatus.CANCELLED]))\
        .filter(Order.reservation_status.in_([ReservationStatus.RESERVED, ReservationStatus.PARTIAL]))\
        .group_by(OrderItem.batch_output_id)\
        .all()
    reserved_by_output_id = {
        output_id: Decimal(str(quantity))
        for output_id, quantity in reserved_rows
    }

    stocks: list[FinishedProductStock] = []
    outputs = session.query(FinishedProductOutput).order_by(FinishedProductOutput.id).all()
    for output in outputs:
        if output.batch is None or output.batch.product is None or output.package_unit is None:
            continue
        if output.package_size <= 0:
            continue
        delivered_quantity = delivered_by_output_id.get(output.id, Decimal("0"))
        physical_quantity = output.total_quantity - delivered_quantity
        reserved_quantity = reserved_by_output_id.get(output.id, Decimal("0"))
        available_quantity = physical_quantity - reserved_quantity
        if available_quantity <= 0:
            continue
        unit_cost = output.packing_operation.unit_cost if output.packing_operation else output.batch.unit_cost

        stocks.append(
            FinishedProductStock(
                output_id=output.id,
                product_id=output.batch.product_id,
                product_name=output.batch.product.name,
                package_size=output.package_size,
                unit_short_name=output.package_unit.short_name,
                produced_on=output.batch.produced_on,
                total_quantity=output.total_quantity,
                physical_quantity=physical_quantity,
                reserved_quantity=reserved_quantity,
                available_quantity=available_quantity,
                current_quantity=available_quantity,
                current_package_count=available_quantity / output.package_size,
                available_package_count=available_quantity / output.package_size,
                unit_cost=unit_cost,
                output=output,
            )
        )

    return sorted(stocks, key=lambda stock: (stock.product_name, stock.produced_on, stock.output_id))


def list_available_bulk_finished_product_outputs(session: Session) -> list[BulkFinishedProductStock]:
    """List unpacked finished product outputs with positive remaining quantity."""

    from nutag.db.models import FinishedProductBulkOutput, FinishedProductPacking

    used_by_output_id: dict[int, Decimal] = {}
    for packing in session.query(FinishedProductPacking).all():
        if packing.finished_output is None:
            continue
        used_by_output_id[packing.source_bulk_output_id] = (
            used_by_output_id.get(packing.source_bulk_output_id, Decimal("0"))
            + packing.finished_output.total_quantity
        )

    stocks: list[BulkFinishedProductStock] = []
    outputs = session.query(FinishedProductBulkOutput).order_by(FinishedProductBulkOutput.id).all()
    for output in outputs:
        if output.batch is None or output.batch.product is None or output.unit is None:
            continue
        used_quantity = used_by_output_id.get(output.id, Decimal("0"))
        current_quantity = output.quantity - used_quantity
        if current_quantity <= 0:
            continue

        stocks.append(
            BulkFinishedProductStock(
                bulk_output_id=output.id,
                product_id=output.batch.product_id,
                product_name=output.batch.product.name,
                produced_on=output.batch.produced_on,
                unit_short_name=output.unit.short_name,
                initial_quantity=output.quantity,
                current_quantity=current_quantity,
                unit_cost=output.batch.unit_cost,
                output=output,
            )
        )

    return sorted(stocks, key=lambda stock: (stock.product_name, stock.produced_on, stock.bulk_output_id))


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
        BatchPackagingUse,
        FinishedProductOutput,
        FinishedProductPacking,
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

    linked_packings = session.query(
        FinishedProductPacking.packaging_purchase_item_id,
        func.sum(FinishedProductPacking.packaging_quantity),
    )\
        .join(FinishedProductOutput, FinishedProductOutput.id == FinishedProductPacking.finished_output_id)\
        .filter(FinishedProductPacking.packaging_purchase_item_id.isnot(None))\
        .group_by(FinishedProductPacking.packaging_purchase_item_id)\
        .all()
    for pi_id, qty in linked_packings:
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
        FinishedProductBulkOutput,
        FinishedProductPacking,
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
            unit_cost = out.packing_operation.unit_cost if out.packing_operation else b.unit_cost
            add_inflow(
                ExtendedItemType.PRODUCT,
                b.product_id,
                b.product.name,
                out.package_unit.short_name,
                out.total_quantity,
                out.total_quantity * unit_cost,
            )

    bulk_outputs = session.scalars(select(FinishedProductBulkOutput)).all()
    for output in bulk_outputs:
        if output.batch is None or output.batch.product is None or output.unit is None:
            continue
        add_inflow(
            ExtendedItemType.PRODUCT,
            output.batch.product_id,
            output.batch.product.name,
            output.unit.short_name,
            output.quantity,
            output.quantity * output.batch.unit_cost,
        )

    packings = session.scalars(select(FinishedProductPacking)).all()
    for packing in packings:
        source_output = packing.source_bulk_output
        if (
            source_output is not None
            and source_output.batch is not None
            and source_output.batch.product is not None
            and source_output.unit is not None
            and packing.finished_output is not None
        ):
            add_outflow(
                ExtendedItemType.PRODUCT,
                source_output.batch.product_id,
                source_output.batch.product.name,
                source_output.unit.short_name,
                packing.finished_output.total_quantity,
            )
        if packing.packaging is not None and packing.packaging_unit is not None:
            add_outflow(
                PurchaseItemType.PACKAGING,
                packing.packaging_id,
                packing.packaging.name,
                packing.packaging_unit.short_name,
                packing.packaging_quantity,
            )

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
