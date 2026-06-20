"""Service functions for purchase documents."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from nutag.db.models import Ingredient, Packaging, Consumable, Purchase, PurchaseItem, PurchaseItemType, Unit
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


def list_purchases(session: Session) -> list[Purchase]:
    """Return purchases ordered from newest to oldest."""

    return list(session.scalars(select(Purchase).order_by(Purchase.purchase_date.desc(), Purchase.id.desc())))
