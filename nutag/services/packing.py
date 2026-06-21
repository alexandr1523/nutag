"""Service functions for packing unpacked finished product stock."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from nutag.db.models import (
    FinishedProductOutput,
    FinishedProductPacking,
    OrderItem,
    Packaging,
    PurchaseItemType,
    Unit,
)
from nutag.services.calculations import calculate_unit_cost, to_decimal
from nutag.services.inventory import get_available_bulk_finished_product_output, get_available_purchase_batch
from nutag.services.preparations import calculate_ingredient_use_total
from nutag.services.production import calculate_output_total


def pack_finished_product(
    session: Session,
    *,
    packed_on: date,
    source_bulk_output_id: int,
    packaging: Packaging,
    packaging_unit: Unit,
    packaging_purchase_item_id: int,
    package_size: Decimal | int | float | str,
    package_unit: Unit,
    package_count: int,
    frozen_on: date | None = None,
    use_by: date | None = None,
    storage_place: str | None = None,
    comment: str | None = None,
) -> FinishedProductPacking:
    """Convert unpacked finished product stock into a packaged finished output."""

    total_quantity = calculate_output_total(package_size=package_size, package_count=package_count)
    bulk_stock = get_available_bulk_finished_product_output(
        session,
        bulk_output_id=source_bulk_output_id,
        expected_unit_short_name=package_unit.short_name,
        quantity=total_quantity,
    )
    packaging_quantity = Decimal(package_count)
    packaging_stock = get_available_purchase_batch(
        session,
        purchase_item_id=packaging_purchase_item_id,
        expected_item_type=PurchaseItemType.PACKAGING,
        expected_item_id=packaging.id,
        expected_unit_short_name=packaging_unit.short_name,
        quantity=packaging_quantity,
    )

    bulk_value = calculate_ingredient_use_total(
        quantity=total_quantity,
        unit_cost=bulk_stock.unit_cost,
    )
    packaging_total = calculate_ingredient_use_total(
        quantity=packaging_quantity,
        unit_cost=packaging_stock.unit_price,
    )
    total_cost = bulk_value + packaging_total
    unit_cost = calculate_unit_cost(total_cost=total_cost, actual_output=total_quantity)

    finished_output = FinishedProductOutput(
        batch=bulk_stock.output.batch,
        package_size=to_decimal(package_size),
        package_unit=package_unit,
        package_count=package_count,
        total_quantity=total_quantity,
        frozen_on=frozen_on,
        use_by=use_by,
        storage_place=storage_place,
        comment=comment,
    )
    packing = FinishedProductPacking(
        packed_on=packed_on,
        source_bulk_output=bulk_stock.output,
        finished_output=finished_output,
        packaging=packaging,
        packaging_purchase_item_id=packaging_purchase_item_id,
        packaging_unit=packaging_unit,
        packaging_quantity=packaging_quantity,
        packaging_unit_cost=packaging_stock.unit_price,
        packaging_total_cost=packaging_total,
        total_cost=total_cost,
        unit_cost=unit_cost,
        comment=comment,
    )

    session.add(packing)
    session.flush()
    return packing


def is_finished_product_packing_used(session: Session, packing_id: int) -> bool:
    """Return whether a packing output is already referenced by an order."""

    packing = session.get(FinishedProductPacking, packing_id)
    if packing is None:
        return False

    return (
        session.query(OrderItem.id)
        .filter(OrderItem.batch_output_id == packing.finished_output_id)
        .first()
        is not None
    )


def delete_finished_product_packing(session: Session, packing_id: int) -> None:
    """Delete an unused packing operation and its generated finished product output."""

    packing = session.get(FinishedProductPacking, packing_id)
    if packing is None:
        raise ValueError("Фасовка не найдена")
    if is_finished_product_packing_used(session, packing_id):
        raise ValueError("Фасовка уже использована в заказах и не может быть удалена")

    finished_output = packing.finished_output
    session.delete(packing)
    session.flush()
    if finished_output is not None:
        session.delete(finished_output)
        session.flush()
