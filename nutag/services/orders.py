"""Service functions for customer orders."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from nutag.db.models import Order, OrderItem, OrderStatus, PaymentStatus, Product, ReservationStatus, Unit, FinishedProductOutput
from nutag.services.calculations import to_decimal
from nutag.services.inventory import get_available_finished_product_output


@dataclass(frozen=True)
class OrderItemInput:
    """Input data for an order line."""

    product: Product
    package_size: Decimal | int | float | str
    package_unit: Unit
    package_count: int
    unit_price: Decimal | int | float | str
    batch_output: FinishedProductOutput | None = None
    comment: str | None = None


def calculate_order_item_total(
    *,
    package_count: int,
    unit_price: Decimal | int | float | str,
) -> Decimal:
    """Calculate total amount for an order line."""

    count = int(package_count)
    price = to_decimal(unit_price)
    if count <= 0:
        raise ValueError("Order item package count must be greater than zero")
    if price < 0:
        raise ValueError("Order item unit price cannot be negative")

    return Decimal(count) * price


def create_order(
    session: Session,
    *,
    order_date: date,
    customer_name: str,
    items: Iterable[OrderItemInput],
    customer_contact: str | None = None,
    delivery_cost: Decimal | int | float | str = 0,
    order_status: OrderStatus = OrderStatus.NEW,
    payment_status: PaymentStatus = PaymentStatus.PENDING,
    reservation_status: ReservationStatus = ReservationStatus.NOT_RESERVED,
    comment: str | None = None,
) -> Order:
    """Create a customer order with items and calculate total amount."""

    if not customer_name.strip():
        raise ValueError("Укажите имя клиента")

    item_inputs = list(items)
    if not item_inputs:
        raise ValueError("Order must contain at least one item")

    total_amount = Decimal("0")
    order_items = []
    reserved_output_quantities: dict[int, Decimal] = {}

    for line in item_inputs:
        line_total = calculate_order_item_total(
            package_count=line.package_count,
            unit_price=line.unit_price,
        )
        total_amount += line_total

        package_size = to_decimal(line.package_size)
        if package_size <= 0:
            raise ValueError("Размер упаковки должен быть больше нуля")
        if line.batch_output is None:
            raise ValueError("Выберите партию готовой продукции")

        total_quantity = package_size * Decimal(line.package_count)
        reserved_output_quantities[line.batch_output.id] = reserved_output_quantities.get(
            line.batch_output.id,
            Decimal("0"),
        ) + total_quantity
        get_available_finished_product_output(
            session,
            batch_output_id=line.batch_output.id,
            expected_product_id=line.product.id,
            expected_package_size=line.package_size,
            expected_unit_short_name=line.package_unit.short_name,
            quantity=reserved_output_quantities[line.batch_output.id],
        )
        
        order_items.append(
            OrderItem(
                product=line.product,
                batch_output=line.batch_output,
                package_size=package_size,
                package_unit=line.package_unit,
                package_count=line.package_count,
                total_quantity=total_quantity,
                unit_price=to_decimal(line.unit_price),
                total_price=line_total,
                comment=line.comment,
            )
        )

    order = Order(
        order_date=order_date,
        customer_name=customer_name,
        customer_contact=customer_contact,
        order_status=order_status,
        payment_status=payment_status,
        reservation_status=reservation_status,
        total_amount=total_amount,
        delivery_cost=to_decimal(delivery_cost),
        comment=comment,
        items=order_items,
    )

    session.add(order)
    session.flush()
    return order


def list_orders(session: Session) -> list[Order]:
    """Return orders ordered from newest to oldest."""

    return list(session.scalars(select(Order).order_by(Order.order_date.desc(), Order.id.desc())))
