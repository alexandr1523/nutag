"""Unit tests for the customer orders service."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from nutag.db import create_database, create_engine_for_url, create_session_factory
from nutag.db.models import Order, OrderStatus, PaymentStatus, Product, ReservationStatus, Unit
from nutag.services.inventory import list_available_finished_product_outputs
from nutag.services.orders import OrderItemInput, create_order, list_orders
from nutag.services.production import FinishedProductOutputInput, create_production_batch


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


def test_create_order_persists_selected_finished_output() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        unit_kg = Unit(name="Kilogram", short_name="kg")
        session.add(unit_kg)
        product = Product(name="Пельмени")
        session.add(product)
        session.flush()
        batch = create_production_batch(
            session,
            produced_on=date(2026, 6, 14),
            product=product,
            actual_output_quantity="2",
            output_unit=unit_kg,
            outputs=[FinishedProductOutputInput(package_size="0.5", package_unit=unit_kg, package_count=4)],
        )
        output = batch.outputs[0]

        order = create_order(
            session,
            order_date=date(2026, 6, 15),
            customer_name="Клиент",
            items=[
                OrderItemInput(
                    product=product,
                    package_size="0.5",
                    package_unit=unit_kg,
                    package_count=2,
                    unit_price="450",
                    batch_output=output,
                )
            ],
        )
        session.commit()
        order_id = order.id
        output_id = output.id

    with session_factory() as session:
        saved_order = session.get(Order, order_id)
        assert saved_order.items[0].batch_output_id == output_id
        assert saved_order.items[0].total_quantity == Decimal("1.000")
        available_outputs = list_available_finished_product_outputs(session)
        assert len(available_outputs) == 1
        assert available_outputs[0].output_id == output_id
        assert available_outputs[0].current_quantity == Decimal("1.000")


def test_create_order_rejects_selected_finished_output_overdraft() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        unit_kg = Unit(name="Kilogram", short_name="kg")
        session.add(unit_kg)
        product = Product(name="Пельмени")
        session.add(product)
        session.flush()
        batch = create_production_batch(
            session,
            produced_on=date(2026, 6, 14),
            product=product,
            actual_output_quantity="1",
            output_unit=unit_kg,
            outputs=[FinishedProductOutputInput(package_size="0.5", package_unit=unit_kg, package_count=2)],
        )
        output = batch.outputs[0]

        create_order(
            session,
            order_date=date(2026, 6, 15),
            customer_name="Первый",
            items=[
                OrderItemInput(
                    product=product,
                    package_size="0.5",
                    package_unit=unit_kg,
                    package_count=1,
                    unit_price="450",
                    batch_output=output,
                )
            ],
        )

        with pytest.raises(ValueError, match="Недостаточно остатка"):
            create_order(
                session,
                order_date=date(2026, 6, 16),
                customer_name="Второй",
                items=[
                    OrderItemInput(
                        product=product,
                        package_size="0.5",
                        package_unit=unit_kg,
                        package_count=2,
                        unit_price="450",
                        batch_output=output,
                    )
                ],
            )


def test_create_order_rejects_selected_finished_output_wrong_product() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        unit_kg = Unit(name="Kilogram", short_name="kg")
        session.add(unit_kg)
        product = Product(name="Пельмени")
        other_product = Product(name="Вареники")
        session.add_all([product, other_product])
        session.flush()
        batch = create_production_batch(
            session,
            produced_on=date(2026, 6, 14),
            product=product,
            actual_output_quantity="1",
            output_unit=unit_kg,
            outputs=[FinishedProductOutputInput(package_size="0.5", package_unit=unit_kg, package_count=2)],
        )

        with pytest.raises(ValueError, match="не соответствует продукту"):
            create_order(
                session,
                order_date=date(2026, 6, 15),
                customer_name="Клиент",
                items=[
                    OrderItemInput(
                        product=other_product,
                        package_size="0.5",
                        package_unit=unit_kg,
                        package_count=1,
                        unit_price="450",
                        batch_output=batch.outputs[0],
                    )
                ],
            )


def test_create_order_rejects_cumulative_selected_finished_output_overdraft() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        unit_kg = Unit(name="Kilogram", short_name="kg")
        session.add(unit_kg)
        product = Product(name="Пельмени")
        session.add(product)
        session.flush()
        batch = create_production_batch(
            session,
            produced_on=date(2026, 6, 14),
            product=product,
            actual_output_quantity="1",
            output_unit=unit_kg,
            outputs=[FinishedProductOutputInput(package_size="0.5", package_unit=unit_kg, package_count=2)],
        )
        output = batch.outputs[0]

        with pytest.raises(ValueError, match="Недостаточно остатка"):
            create_order(
                session,
                order_date=date(2026, 6, 15),
                customer_name="Клиент",
                items=[
                    OrderItemInput(
                        product=product,
                        package_size="0.5",
                        package_unit=unit_kg,
                        package_count=1,
                        unit_price="450",
                        batch_output=output,
                    ),
                    OrderItemInput(
                        product=product,
                        package_size="0.5",
                        package_unit=unit_kg,
                        package_count=2,
                        unit_price="450",
                        batch_output=output,
                    ),
                ],
            )
