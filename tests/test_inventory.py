from datetime import date
from decimal import Decimal

from sqlalchemy import delete

from nutag.db import create_database, create_engine_for_url, create_session_factory
from nutag.db.models import (
    FinishedProductBulkOutput,
    FinishedProductOutput,
    FinishedProductPacking,
    ProductionBatch,
    PurchaseItemType,
)
from nutag.services.inventory import (
    list_available_bulk_finished_product_outputs,
    list_available_finished_product_outputs,
    list_available_stock_batches,
    list_inventory_balances,
)
from nutag.services.maintenance import reset_operational_data
from nutag.services.packing import pack_finished_product
from nutag.services.purchases import PurchaseLineInput, create_purchase
from nutag.services.production import create_production_batch
from nutag.services.references import create_ingredient, create_packaging, create_product, create_unit


def make_session_factory():
    engine = create_engine_for_url("sqlite:///:memory:")
    create_database(engine)
    return create_session_factory(engine)


def test_inventory_balances_are_aggregated_from_purchase_lines() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        piece = create_unit(session, name="piece", short_name="pcs")
        flour = create_ingredient(session, name="Мука", unit=kg)
        container = create_packaging(session, name="Контейнер 1 кг", unit=piece)

        create_purchase(
            session,
            purchase_date=date(2026, 6, 14),
            supplier="Магазин 1",
            lines=[
                PurchaseLineInput(
                    item_type=PurchaseItemType.INGREDIENT,
                    ingredient=flour,
                    item_name="Мука",
                    unit=kg,
                    quantity="2",
                    unit_price="80",
                ),
                PurchaseLineInput(
                    item_type=PurchaseItemType.PACKAGING,
                    packaging=container,
                    item_name="Контейнер 1 кг",
                    unit=piece,
                    quantity="10",
                    unit_price="12",
                ),
            ],
        )
        create_purchase(
            session,
            purchase_date=date(2026, 6, 15),
            supplier="Магазин 2",
            lines=[
                PurchaseLineInput(
                    item_type=PurchaseItemType.INGREDIENT,
                    ingredient=flour,
                    item_name="Мука",
                    unit=kg,
                    quantity="3",
                    unit_price="100",
                ),
            ],
        )
        session.commit()

    with session_factory() as session:
        balances = list_inventory_balances(session)

    assert [(balance.item_type, balance.item_name) for balance in balances] == [
        (PurchaseItemType.INGREDIENT, "Мука"),
        (PurchaseItemType.PACKAGING, "Контейнер 1 кг"),
    ]

    flour_balance = balances[0]
    assert flour_balance.unit_short_name == "kg"
    assert flour_balance.inflow_quantity == Decimal("5.000")
    assert flour_balance.inflow_value == Decimal("460.00")
    assert flour_balance.weighted_average_price == Decimal("92.00")

    packaging_balance = balances[1]
    assert packaging_balance.unit_short_name == "pcs"
    assert packaging_balance.inflow_quantity == Decimal("10.000")
    assert packaging_balance.inflow_value == Decimal("120.00")
    assert packaging_balance.weighted_average_price == Decimal("12.00")


def test_inventory_balances_are_empty_without_purchases() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        assert list_inventory_balances(session) == []


def test_packing_does_not_consume_ingredient_batches_with_same_id() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        piece = create_unit(session, name="piece", short_name="pcs")
        flour = create_ingredient(session, name="ÐœÑƒÐºÐ°", unit=kg)
        container = create_packaging(session, name="ÐšÐ¾Ð½Ñ‚ÐµÐ¹Ð½ÐµÑ€ 1 ÐºÐ³", unit=piece)
        product = create_product(session, name="ÐŸÐµÐ»ÑŒÐ¼ÐµÐ½Ð¸")

        assert flour.id == container.id == 1

        purchase = create_purchase(
            session,
            purchase_date=date(2026, 6, 14),
            lines=[
                PurchaseLineInput(
                    item_type=PurchaseItemType.INGREDIENT,
                    ingredient=flour,
                    item_name=flour.name,
                    unit=kg,
                    quantity="5",
                    unit_price="80",
                ),
                PurchaseLineInput(
                    item_type=PurchaseItemType.PACKAGING,
                    packaging=container,
                    item_name=container.name,
                    unit=piece,
                    quantity="10",
                    unit_price="12",
                ),
            ],
        )

        batch = create_production_batch(
            session,
            produced_on=date(2026, 6, 15),
            product=product,
            actual_output_quantity="1",
            output_unit=kg,
            labor_cost="1",
        )
        pack_finished_product(
            session,
            packed_on=date(2026, 6, 15),
            source_bulk_output_id=batch.bulk_outputs[0].id,
            packaging=container,
            packaging_unit=piece,
            packaging_purchase_item_id=purchase.items[1].id,
            package_size="0.25",
            package_unit=kg,
            package_count=4,
        )
        session.commit()

    with session_factory() as session:
        batches = list_available_stock_batches(session)

    ingredient_batch = next(batch for batch in batches if batch.item_type == PurchaseItemType.INGREDIENT)
    packaging_batch = next(batch for batch in batches if batch.item_type == PurchaseItemType.PACKAGING)

    assert ingredient_batch.current_quantity == Decimal("5.000")
    assert packaging_batch.current_quantity == Decimal("6.000")


def test_reset_operational_data_removes_finished_product_outputs_and_packings() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        piece = create_unit(session, name="piece", short_name="pcs")
        product = create_product(session, name="Пельмени")
        container = create_packaging(session, name="Контейнер", unit=piece)
        purchase = create_purchase(
            session,
            purchase_date=date(2026, 6, 14),
            lines=[
                PurchaseLineInput(
                    item_type=PurchaseItemType.PACKAGING,
                    packaging=container,
                    item_name=container.name,
                    unit=piece,
                    quantity="10",
                    unit_price="5",
                )
            ],
        )
        batch = create_production_batch(
            session,
            produced_on=date(2026, 6, 15),
            product=product,
            actual_output_quantity="3",
            output_unit=kg,
            labor_cost="300",
        )
        pack_finished_product(
            session,
            packed_on=date(2026, 6, 16),
            source_bulk_output_id=batch.bulk_outputs[0].id,
            packaging=container,
            packaging_unit=piece,
            packaging_purchase_item_id=purchase.items[0].id,
            package_size="0.5",
            package_unit=kg,
            package_count=4,
        )
        session.commit()

        reset_operational_data(session)

        assert session.query(FinishedProductPacking).count() == 0
        assert session.query(FinishedProductOutput).count() == 0
        assert session.query(FinishedProductBulkOutput).count() == 0
        assert session.query(ProductionBatch).count() == 0
        assert list_inventory_balances(session) == []
        assert list_available_finished_product_outputs(session) == []
        assert list_available_bulk_finished_product_outputs(session) == []


def test_inventory_balances_skip_orphan_finished_product_outputs() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        product = create_product(session, name="Пельмени")
        batch = create_production_batch(
            session,
            produced_on=date(2026, 6, 15),
            product=product,
            actual_output_quantity="3",
            output_unit=kg,
            labor_cost="300",
        )
        batch_id = batch.id
        session.commit()

        session.execute(delete(ProductionBatch).where(ProductionBatch.id == batch_id))
        session.commit()
        session.expire_all()

        assert list_inventory_balances(session) == []
        assert list_available_bulk_finished_product_outputs(session) == []


def test_available_bulk_outputs_skip_orphan_packings_without_finished_output() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        piece = create_unit(session, name="piece", short_name="pcs")
        product = create_product(session, name="Пельмени")
        container = create_packaging(session, name="Контейнер", unit=piece)
        purchase = create_purchase(
            session,
            purchase_date=date(2026, 6, 14),
            lines=[
                PurchaseLineInput(
                    item_type=PurchaseItemType.PACKAGING,
                    packaging=container,
                    item_name=container.name,
                    unit=piece,
                    quantity="10",
                    unit_price="5",
                )
            ],
        )
        batch = create_production_batch(
            session,
            produced_on=date(2026, 6, 15),
            product=product,
            actual_output_quantity="3",
            output_unit=kg,
            labor_cost="300",
        )
        packing = pack_finished_product(
            session,
            packed_on=date(2026, 6, 16),
            source_bulk_output_id=batch.bulk_outputs[0].id,
            packaging=container,
            packaging_unit=piece,
            packaging_purchase_item_id=purchase.items[0].id,
            package_size="0.5",
            package_unit=kg,
            package_count=4,
        )
        finished_output_id = packing.finished_output.id
        session.commit()

        session.execute(delete(FinishedProductOutput).where(FinishedProductOutput.id == finished_output_id))
        session.commit()
        session.expire_all()

        bulk_outputs = list_available_bulk_finished_product_outputs(session)
        stock_batches = list_available_stock_batches(session)

        assert len(bulk_outputs) == 1
        assert bulk_outputs[0].current_quantity == Decimal("3.000")
        assert stock_batches[0].current_quantity == Decimal("10.000")
