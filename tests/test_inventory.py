from datetime import date
from decimal import Decimal

from nutag.db import create_database, create_engine_for_url, create_session_factory
from nutag.db.models import PurchaseItemType
from nutag.services.inventory import list_inventory_balances
from nutag.services.purchases import PurchaseLineInput, create_purchase
from nutag.services.references import create_ingredient, create_packaging, create_unit


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
    assert flour_balance.purchased_quantity == Decimal("5.000")
    assert flour_balance.purchased_value == Decimal("460.00")
    assert flour_balance.weighted_average_price == Decimal("92.00")

    packaging_balance = balances[1]
    assert packaging_balance.unit_short_name == "pcs"
    assert packaging_balance.purchased_quantity == Decimal("10.000")
    assert packaging_balance.purchased_value == Decimal("120.00")
    assert packaging_balance.weighted_average_price == Decimal("12.00")


def test_inventory_balances_are_empty_without_purchases() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        assert list_inventory_balances(session) == []
