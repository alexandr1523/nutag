"""Unit tests for the customer orders service."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from nutag.db import create_database, create_engine_for_url, create_session_factory
from nutag.db.models import Order, OrderStatus, PaymentStatus, Product, ReservationStatus, Unit
from nutag.services.orders import OrderItemInput, create_order, list_orders


def make_session_factory():
    engine = create_engine_for_url("sqlite:///:memory:")
    create_database(engine)
    return create_session_factory(engine)


def test_create_order():
    session_factory = make_session_factory()

    with session_factory() as session:
        # Setup: need a product and units
        unit_kg = Unit(name="Kilogram", short_name="kg")
        session.add(unit_kg)
        product = Product(name="Pelmeni")
        session.add(product)
        session.flush()

        # Input: one order item
        items = [
            OrderItemInput(
                product=product,
                package_size=Decimal("0.5"),
                package_unit=unit_kg,
                package_count=2,
                unit_price=Decimal("450.00")
            )
        ]

        # Action
        order = create_order(
            session,
            order_date=date(2026, 6, 14),
            customer_name="John Doe",
            items=items,
            delivery_cost=Decimal("150.00")
        )
        session.commit()
        order_id = order.id

    with session_factory() as session:
        saved_order = session.get(Order, order_id)
        assert saved_order is not None
        assert saved_order.customer_name == "John Doe"
        assert saved_order.total_amount == Decimal("900.00") # 2 * 450
        assert saved_order.delivery_cost == Decimal("150.00")
        assert len(saved_order.items) == 1
        assert saved_order.items[0].total_quantity == Decimal("1.000") # 2 * 0.5
        assert saved_order.order_status == OrderStatus.NEW
        assert saved_order.payment_status == PaymentStatus.PENDING


def test_list_orders():
    session_factory = make_session_factory()

    with session_factory() as session:
        # Setup
        unit_kg = Unit(name="Kilogram", short_name="kg")
        session.add(unit_kg)
        product = Product(name="Pelmeni")
        session.add(product)
        session.flush()

        item = OrderItemInput(product=product, package_size=0.5, package_unit=unit_kg, package_count=1, unit_price=500)
        
        create_order(session, order_date=date(2026, 6, 10), customer_name="Old", items=[item])
        create_order(session, order_date=date(2026, 6, 14), customer_name="New", items=[item])
        session.commit()

    with session_factory() as session:
        # Action
        orders = list_orders(session)

        # Verification
        assert len(orders) == 2
        assert orders[0].customer_name == "New" # Ordered by date DESC
        assert orders[1].customer_name == "Old"
