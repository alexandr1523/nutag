"""Unit tests for the customer orders service."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from nutag.db import create_database, create_engine_for_url, create_session_factory
from nutag.db.models import Order, OrderStatus, PaymentStatus, Product, PurchaseItemType, ReservationStatus, Unit
from nutag.services.inventory import list_available_finished_product_outputs
from nutag.services.orders import OrderItemInput, create_order, list_orders
from nutag.services.packing import pack_finished_product
from nutag.services.production import create_production_batch
from nutag.services.purchases import PurchaseLineInput, create_purchase
from nutag.services.references import create_packaging


def make_session_factory():
    engine = create_engine_for_url("sqlite:///:memory:")
    create_database(engine)
    return create_session_factory(engine)


def create_packed_output(session: Session, *, product: Product, unit_kg: Unit, quantity: str = "2"):
    piece = Unit(name=f"Piece {product.id}", short_name=f"pcs{product.id}")
    session.add(piece)
    session.flush()
    packaging = create_packaging(session, name=f"Контейнер {product.id}", unit=piece)
    purchase = create_purchase(
        session,
        purchase_date=date(2026, 6, 13),
        lines=[
            PurchaseLineInput(
                item_type=PurchaseItemType.PACKAGING,
                packaging=packaging,
                item_name=packaging.name,
                unit=piece,
                quantity="20",
                unit_price="5",
            )
        ],
    )
    batch = create_production_batch(
        session,
        produced_on=date(2026, 6, 14),
        product=product,
        actual_output_quantity=quantity,
        output_unit=unit_kg,
        labor_cost="1",
    )
    packing = pack_finished_product(
        session,
        packed_on=date(2026, 6, 14),
        source_bulk_output_id=batch.bulk_outputs[0].id,
        packaging=packaging,
        packaging_unit=piece,
        packaging_purchase_item_id=purchase.items[0].id,
        package_size="0.5",
        package_unit=unit_kg,
        package_count=int(Decimal(quantity) / Decimal("0.5")),
    )
    return packing.finished_output


def test_create_order():
    session_factory = make_session_factory()

    with session_factory() as session:
        # Setup: need a product and units
        unit_kg = Unit(name="Kilogram", short_name="kg")
        session.add(unit_kg)
        product = Product(name="Pelmeni")
        session.add(product)
        session.flush()
        output = create_packed_output(session, product=product, unit_kg=unit_kg, quantity="2")

        # Input: one order item
        items = [
            OrderItemInput(
                product=product,
                package_size=Decimal("0.5"),
                package_unit=unit_kg,
                package_count=2,
                unit_price=Decimal("450.00"),
                batch_output=output,
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
        assert saved_order.reservation_status == ReservationStatus.RESERVED


def test_list_orders():
    session_factory = make_session_factory()

    with session_factory() as session:
        # Setup
        unit_kg = Unit(name="Kilogram", short_name="kg")
        session.add(unit_kg)
        product = Product(name="Pelmeni")
        session.add(product)
        session.flush()
        output = create_packed_output(session, product=product, unit_kg=unit_kg, quantity="2")

        item = OrderItemInput(
            product=product,
            package_size=0.5,
            package_unit=unit_kg,
            package_count=1,
            unit_price=500,
            batch_output=output,
        )
        
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
        output = create_packed_output(session, product=product, unit_kg=unit_kg, quantity="2")

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
        assert available_outputs[0].physical_quantity == Decimal("2.000")
        assert available_outputs[0].reserved_quantity == Decimal("1.000")
        assert available_outputs[0].available_quantity == Decimal("1.000")
        assert available_outputs[0].current_quantity == Decimal("1.000")


def test_create_order_rejects_blank_customer_name() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        unit_kg = Unit(name="Kilogram", short_name="kg")
        session.add(unit_kg)
        product = Product(name="Пельмени")
        session.add(product)
        session.flush()
        output = create_packed_output(session, product=product, unit_kg=unit_kg, quantity="1")

        with pytest.raises(ValueError, match="Укажите имя клиента"):
            create_order(
                session,
                order_date=date(2026, 6, 15),
                customer_name="  ",
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


def test_create_order_rejects_missing_finished_output() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        unit_kg = Unit(name="Kilogram", short_name="kg")
        session.add(unit_kg)
        product = Product(name="Пельмени")
        session.add(product)
        session.flush()

        with pytest.raises(ValueError, match="Выберите партию готовой продукции"):
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
                    )
                ],
            )


def test_create_order_rejects_zero_package_size() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        unit_kg = Unit(name="Kilogram", short_name="kg")
        session.add(unit_kg)
        product = Product(name="Пельмени")
        session.add(product)
        session.flush()
        output = create_packed_output(session, product=product, unit_kg=unit_kg, quantity="1")

        with pytest.raises(ValueError, match="Размер упаковки"):
            create_order(
                session,
                order_date=date(2026, 6, 15),
                customer_name="Клиент",
                items=[
                    OrderItemInput(
                        product=product,
                        package_size="0",
                        package_unit=unit_kg,
                        package_count=1,
                        unit_price="450",
                        batch_output=output,
                    )
                ],
            )


def test_create_order_rejects_selected_finished_output_overdraft() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        unit_kg = Unit(name="Kilogram", short_name="kg")
        session.add(unit_kg)
        product = Product(name="Пельмени")
        session.add(product)
        session.flush()
        output = create_packed_output(session, product=product, unit_kg=unit_kg, quantity="1")

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


def test_delivered_order_reduces_physical_finished_output_quantity() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        unit_kg = Unit(name="Kilogram", short_name="kg")
        session.add(unit_kg)
        product = Product(name="Пельмени")
        session.add(product)
        session.flush()
        output = create_packed_output(session, product=product, unit_kg=unit_kg, quantity="2")

        create_order(
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
            order_status=OrderStatus.DELIVERED,
            reservation_status=ReservationStatus.RESERVED,
        )
        session.commit()
        output_id = output.id

    with session_factory() as session:
        available_outputs = list_available_finished_product_outputs(session)

    assert len(available_outputs) == 1
    assert available_outputs[0].output_id == output_id
    assert available_outputs[0].physical_quantity == Decimal("1.000")
    assert available_outputs[0].reserved_quantity == Decimal("0")
    assert available_outputs[0].available_quantity == Decimal("1.000")


def test_cancelled_order_does_not_reserve_finished_output() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        unit_kg = Unit(name="Kilogram", short_name="kg")
        session.add(unit_kg)
        product = Product(name="Пельмени")
        session.add(product)
        session.flush()
        output = create_packed_output(session, product=product, unit_kg=unit_kg, quantity="2")

        create_order(
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
            order_status=OrderStatus.CANCELLED,
            reservation_status=ReservationStatus.RESERVED,
        )
        session.commit()
        output_id = output.id

    with session_factory() as session:
        available_outputs = list_available_finished_product_outputs(session)

    assert len(available_outputs) == 1
    assert available_outputs[0].output_id == output_id
    assert available_outputs[0].physical_quantity == Decimal("2.000")
    assert available_outputs[0].reserved_quantity == Decimal("0")
    assert available_outputs[0].available_quantity == Decimal("2.000")


def test_create_order_rejects_selected_finished_output_wrong_product() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        unit_kg = Unit(name="Kilogram", short_name="kg")
        session.add(unit_kg)
        product = Product(name="Пельмени")
        other_product = Product(name="Вареники")
        session.add_all([product, other_product])
        session.flush()
        output = create_packed_output(session, product=product, unit_kg=unit_kg, quantity="1")

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
                        batch_output=output,
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
        output = create_packed_output(session, product=product, unit_kg=unit_kg, quantity="1")

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
