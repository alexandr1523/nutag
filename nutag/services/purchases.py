"""Service functions for purchase documents."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from nutag.db.models import (
    BatchIngredientUse,
    BatchPackagingUse,
    Consumable,
    Ingredient,
    Packaging,
    PreparationIngredientUse,
    Purchase,
    PurchaseItem,
    PurchaseItemType,
    Unit,
)
from nutag.services.calculations import to_decimal


@dataclass(frozen=True)
class PurchaseLineInput:
    """Input data for a purchase line."""

    item_type: PurchaseItemType
    item_name: str
    unit: Unit
    quantity: Decimal | int | float | str
    unit_price: Decimal | int | float | str
    ingredient: Ingredient | None = None
    packaging: Packaging | None = None
    consumable: Consumable | None = None
    expires_on: date | None = None
    comment: str | None = None


def validate_purchase_line_source(line: PurchaseLineInput) -> None:
    """Validate that the purchase line has exactly one source matching item_type."""

    sources = {
        PurchaseItemType.INGREDIENT: line.ingredient,
        PurchaseItemType.PACKAGING: line.packaging,
        PurchaseItemType.CONSUMABLE: line.consumable,
    }
    selected_sources = [source for source in sources.values() if source is not None]
    if len(selected_sources) != 1:
        raise ValueError("Строка закупки должна ссылаться ровно на один тип позиции")

    expected_source = sources.get(line.item_type)
    if expected_source is None:
        raise ValueError("Тип строки закупки не соответствует выбранной позиции")

    if expected_source.unit_id != line.unit.id:
        raise ValueError("Единица измерения строки закупки не соответствует выбранной позиции")


def calculate_purchase_line_total(
    *,
    quantity: Decimal | int | float | str,
    unit_price: Decimal | int | float | str,
) -> Decimal:
    """Calculate total amount for a purchase line."""

    quantity_decimal = to_decimal(quantity)
    unit_price_decimal = to_decimal(unit_price)
    if quantity_decimal <= 0:
        raise ValueError("Purchase line quantity must be greater than zero")
    if unit_price_decimal < 0:
        raise ValueError("Purchase line unit price cannot be negative")

    return quantity_decimal * unit_price_decimal


def create_purchase(
    session: Session,
    *,
    purchase_date: date,
    lines: Iterable[PurchaseLineInput],
    supplier: str | None = None,
    purchased_by: str | None = None,
    shopping_minutes: int | None = None,
    transport_cost: Decimal | int | float | str = 0,
    comment: str | None = None,
) -> Purchase:
    """Create a purchase with validated purchase lines."""

    line_inputs = list(lines)
    if not line_inputs:
        raise ValueError("Purchase must contain at least one line")

    purchase = Purchase(
        purchase_date=purchase_date,
        supplier=supplier,
        purchased_by=purchased_by,
        shopping_minutes=shopping_minutes,
        transport_cost=to_decimal(transport_cost),
        comment=comment,
    )

    for index, line in enumerate(line_inputs, start=1):
        validate_purchase_line_source(line)
        total_price = calculate_purchase_line_total(
            quantity=line.quantity,
            unit_price=line.unit_price,
        )
        purchase.items.append(
            PurchaseItem(
                line_number=index,
                item_type=line.item_type,
                ingredient=line.ingredient,
                packaging=line.packaging,
                consumable=line.consumable,
                item_name=line.item_name,
                unit=line.unit,
                quantity=to_decimal(line.quantity),
                unit_price=to_decimal(line.unit_price),
                total_price=total_price,
                expires_on=line.expires_on,
                comment=line.comment,
            )
        )

    session.add(purchase)
    session.flush()
    return purchase


def purchase_item_has_stock_usage(session: Session, item: PurchaseItem) -> bool:
    """Return whether a purchase item is already consumed by stock operations."""

    if item.id is None:
        return False

    linked_queries = [
        select(PreparationIngredientUse.id).where(PreparationIngredientUse.purchase_item_id == item.id),
        select(BatchIngredientUse.id).where(BatchIngredientUse.purchase_item_id == item.id),
        select(BatchPackagingUse.id).where(BatchPackagingUse.purchase_item_id == item.id),
    ]
    if any(session.scalar(query.limit(1)) is not None for query in linked_queries):
        return True

    item_type = PurchaseItemType(item.item_type)
    if item_type == PurchaseItemType.INGREDIENT and item.ingredient_id is not None:
        legacy_queries = [
            select(PreparationIngredientUse.id).where(
                PreparationIngredientUse.purchase_item_id.is_(None),
                PreparationIngredientUse.ingredient_id == item.ingredient_id,
            ),
            select(BatchIngredientUse.id).where(
                BatchIngredientUse.purchase_item_id.is_(None),
                BatchIngredientUse.ingredient_id == item.ingredient_id,
            ),
        ]
        return any(session.scalar(query.limit(1)) is not None for query in legacy_queries)

    if item_type == PurchaseItemType.PACKAGING and item.packaging_id is not None:
        return (
            session.scalar(
                select(BatchPackagingUse.id)
                .where(
                    BatchPackagingUse.purchase_item_id.is_(None),
                    BatchPackagingUse.packaging_id == item.packaging_id,
                )
                .limit(1)
            )
            is not None
        )

    return False


def purchase_has_stock_usage(session: Session, purchase: Purchase) -> bool:
    """Return whether any purchase batch is already consumed."""

    return any(purchase_item_has_stock_usage(session, item) for item in purchase.items)


def update_purchase(
    session: Session,
    purchase_id: int,
    *,
    purchase_date: date,
    lines: Iterable[PurchaseLineInput],
    supplier: str | None = None,
    purchased_by: str | None = None,
    shopping_minutes: int | None = None,
    transport_cost: Decimal | int | float | str = 0,
    comment: str | None = None,
) -> Purchase:
    """Update an unused purchase while preserving batch traceability."""

    purchase = session.get(Purchase, purchase_id)
    if purchase is None:
        raise ValueError("Закупка не найдена")
    if purchase_has_stock_usage(session, purchase):
        raise ValueError("Нельзя редактировать закупку: одна или несколько партий уже использованы")

    line_inputs = list(lines)
    if not line_inputs:
        raise ValueError("Закупка должна содержать хотя бы одну позицию")

    new_items = []
    for index, line in enumerate(line_inputs, start=1):
        validate_purchase_line_source(line)
        total_price = calculate_purchase_line_total(
            quantity=line.quantity,
            unit_price=line.unit_price,
        )
        new_items.append(
            PurchaseItem(
                line_number=index,
                item_type=line.item_type,
                ingredient_id=line.ingredient.id if line.ingredient else None,
                packaging_id=line.packaging.id if line.packaging else None,
                consumable_id=line.consumable.id if line.consumable else None,
                item_name=line.item_name,
                unit_id=line.unit.id,
                quantity=to_decimal(line.quantity),
                unit_price=to_decimal(line.unit_price),
                total_price=total_price,
                expires_on=line.expires_on,
                comment=line.comment,
            )
        )

    purchase.purchase_date = purchase_date
    purchase.supplier = supplier
    purchase.purchased_by = purchased_by
    purchase.shopping_minutes = shopping_minutes
    purchase.transport_cost = to_decimal(transport_cost)
    purchase.comment = comment
    purchase.items.clear()
    session.flush()
    purchase.items.extend(new_items)
    session.flush()
    return purchase


def delete_purchase(session: Session, purchase_id: int) -> None:
    """Delete an unused purchase while protecting consumed batches."""

    purchase = session.get(Purchase, purchase_id)
    if purchase is None:
        raise ValueError("Закупка не найдена")
    if purchase_has_stock_usage(session, purchase):
        raise ValueError("Нельзя удалить закупку: одна или несколько партий уже использованы")

    session.delete(purchase)
    session.flush()


def list_purchases(session: Session) -> list[Purchase]:
    """Return purchases ordered from newest to oldest."""

    return list(session.scalars(select(Purchase).order_by(Purchase.purchase_date.desc(), Purchase.id.desc())))
