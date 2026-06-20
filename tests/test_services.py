from datetime import date
from decimal import Decimal

import pytest

from nutag.db import create_database, create_engine_for_url, create_session_factory
from nutag.db.models import Consumable, PurchaseItemType
from nutag.services.preparations import PreparationIngredientInput, create_preparation
from nutag.services.purchases import (
    PurchaseLineInput,
    calculate_purchase_line_total,
    create_purchase,
    delete_purchase,
    list_purchases,
    purchase_has_stock_usage,
    update_purchase,
)
from nutag.services.references import (
    create_ingredient,
    create_packaging,
    create_preparation_type,
    create_product,
    create_unit,
    list_ingredients,
    list_packaging,
    list_preparation_types,
    list_products,
    list_units,
)


def make_session_factory():
    engine = create_engine_for_url("sqlite:///:memory:")
    create_database(engine)
    return create_session_factory(engine)


def test_reference_services_create_and_list_records() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        piece = create_unit(session, name="piece", short_name="pcs")
        create_product(session, name="Пельмени")
        create_preparation_type(session, name="Начинка")
        create_ingredient(session, name="Мука", unit=kg)
        create_packaging(session, name="Контейнер 1 кг", unit=piece)
        session.commit()

    with session_factory() as session:
        assert [unit.short_name for unit in list_units(session)] == ["kg", "pcs"]
        assert [product.name for product in list_products(session)] == ["Пельмени"]
        assert [preparation_type.name for preparation_type in list_preparation_types(session)] == ["Начинка"]
        assert [ingredient.name for ingredient in list_ingredients(session)] == ["Мука"]
        assert [packaging.name for packaging in list_packaging(session)] == ["Контейнер 1 кг"]


def test_calculate_purchase_line_total_validates_quantity_and_price() -> None:
    assert calculate_purchase_line_total(quantity="2.5", unit_price="80") == Decimal("200.0")

    with pytest.raises(ValueError, match="quantity"):
        calculate_purchase_line_total(quantity="0", unit_price="80")

    with pytest.raises(ValueError, match="unit price"):
        calculate_purchase_line_total(quantity="1", unit_price="-1")


def test_purchase_service_creates_purchase_with_numbered_lines_and_totals() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        piece = create_unit(session, name="piece", short_name="pcs")
        flour = create_ingredient(session, name="Мука", unit=kg)
        container = create_packaging(session, name="Контейнер 1 кг", unit=piece)

        purchase = create_purchase(
            session,
            purchase_date=date(2026, 6, 14),
            supplier="Тестовый магазин",
            purchased_by="Кристина",
            shopping_minutes=45,
            transport_cost="100",
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
        session.commit()
        purchase_id = purchase.id

    with session_factory() as session:
        purchases = list_purchases(session)
        assert len(purchases) == 1
        assert purchases[0].id == purchase_id
        assert purchases[0].transport_cost == Decimal("100.00")
        assert [item.line_number for item in purchases[0].items] == [1, 2]
        assert [item.total_price for item in purchases[0].items] == [Decimal("160.00"), Decimal("120.00")]


def test_purchase_service_rejects_purchase_without_lines() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        with pytest.raises(ValueError, match="at least one line"):
            create_purchase(
                session,
                purchase_date=date(2026, 6, 14),
                lines=[],
            )


def test_purchase_service_rejects_line_without_item_source() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")

        with pytest.raises(ValueError, match="ровно на один тип"):
            create_purchase(
                session,
                purchase_date=date(2026, 6, 14),
                lines=[
                    PurchaseLineInput(
                        item_type=PurchaseItemType.INGREDIENT,
                        item_name="Мука",
                        unit=kg,
                        quantity="1",
                        unit_price="80",
                    )
                ],
            )


def test_purchase_service_rejects_line_with_wrong_item_source_type() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        piece = create_unit(session, name="piece", short_name="pcs")
        container = create_packaging(session, name="Контейнер", unit=piece)

        with pytest.raises(ValueError, match="не соответствует"):
            create_purchase(
                session,
                purchase_date=date(2026, 6, 14),
                lines=[
                    PurchaseLineInput(
                        item_type=PurchaseItemType.INGREDIENT,
                        item_name=container.name,
                        packaging=container,
                        unit=piece,
                        quantity="10",
                        unit_price="5",
                    )
                ],
            )


def test_purchase_service_rejects_line_with_multiple_item_sources() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        piece = create_unit(session, name="piece", short_name="pcs")
        flour = create_ingredient(session, name="Мука", unit=kg)
        container = create_packaging(session, name="Контейнер", unit=piece)

        with pytest.raises(ValueError, match="ровно на один тип"):
            create_purchase(
                session,
                purchase_date=date(2026, 6, 14),
                lines=[
                    PurchaseLineInput(
                        item_type=PurchaseItemType.INGREDIENT,
                        item_name=flour.name,
                        ingredient=flour,
                        packaging=container,
                        unit=kg,
                        quantity="1",
                        unit_price="80",
                    )
                ],
            )


def test_purchase_service_rejects_line_with_wrong_unit() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        piece = create_unit(session, name="piece", short_name="pcs")
        flour = create_ingredient(session, name="Мука", unit=kg)

        with pytest.raises(ValueError, match="Единица измерения"):
            create_purchase(
                session,
                purchase_date=date(2026, 6, 14),
                lines=[
                    PurchaseLineInput(
                        item_type=PurchaseItemType.INGREDIENT,
                        item_name=flour.name,
                        ingredient=flour,
                        unit=piece,
                        quantity="1",
                        unit_price="80",
                    )
                ],
            )


def test_purchase_service_accepts_consumable_line() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        piece = create_unit(session, name="piece", short_name="pcs")
        gloves = Consumable(name="Перчатки", unit=piece)
        session.add(gloves)
        session.flush()

        purchase = create_purchase(
            session,
            purchase_date=date(2026, 6, 14),
            lines=[
                PurchaseLineInput(
                    item_type=PurchaseItemType.CONSUMABLE,
                    item_name=gloves.name,
                    consumable=gloves,
                    unit=piece,
                    quantity="10",
                    unit_price="3",
                )
            ],
        )
        session.commit()

        assert purchase.items[0].consumable_id == gloves.id
        assert purchase.items[0].ingredient_id is None
        assert purchase.items[0].packaging_id is None


def test_purchase_service_updates_unused_purchase() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        flour = create_ingredient(session, name="Мука", unit=kg)
        purchase = create_purchase(
            session,
            purchase_date=date(2026, 6, 14),
            supplier="Старый поставщик",
            transport_cost="10",
            lines=[
                PurchaseLineInput(
                    item_type=PurchaseItemType.INGREDIENT,
                    ingredient=flour,
                    item_name=flour.name,
                    unit=kg,
                    quantity="2",
                    unit_price="80",
                )
            ],
        )

        update_purchase(
            session,
            purchase.id,
            purchase_date=date(2026, 6, 15),
            supplier="Новый поставщик",
            purchased_by="Кристина",
            transport_cost="25",
            lines=[
                PurchaseLineInput(
                    item_type=PurchaseItemType.INGREDIENT,
                    ingredient=flour,
                    item_name=flour.name,
                    unit=kg,
                    quantity="3",
                    unit_price="90",
                )
            ],
        )
        session.commit()

    with session_factory() as session:
        saved = list_purchases(session)[0]
        assert saved.purchase_date == date(2026, 6, 15)
        assert saved.supplier == "Новый поставщик"
        assert saved.purchased_by == "Кристина"
        assert saved.transport_cost == Decimal("25.00")
        assert saved.items[0].quantity == Decimal("3.000")
        assert saved.items[0].unit_price == Decimal("90.00")
        assert saved.items[0].total_price == Decimal("270.00")


def test_purchase_service_deletes_unused_purchase() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        flour = create_ingredient(session, name="Мука", unit=kg)
        purchase = create_purchase(
            session,
            purchase_date=date(2026, 6, 14),
            lines=[
                PurchaseLineInput(
                    item_type=PurchaseItemType.INGREDIENT,
                    ingredient=flour,
                    item_name=flour.name,
                    unit=kg,
                    quantity="2",
                    unit_price="80",
                )
            ],
        )

        delete_purchase(session, purchase.id)
        session.commit()

    with session_factory() as session:
        assert list_purchases(session) == []


def test_purchase_service_rejects_update_and_delete_for_used_purchase_batch() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        flour = create_ingredient(session, name="Мука", unit=kg)
        dough = create_preparation_type(session, name="Тесто")
        purchase = create_purchase(
            session,
            purchase_date=date(2026, 6, 14),
            lines=[
                PurchaseLineInput(
                    item_type=PurchaseItemType.INGREDIENT,
                    ingredient=flour,
                    item_name=flour.name,
                    unit=kg,
                    quantity="2",
                    unit_price="80",
                )
            ],
        )
        create_preparation(
            session,
            prepared_on=date(2026, 6, 15),
            preparation_type=dough,
            output_quantity="1",
            output_unit=kg,
            ingredient_uses=[
                PreparationIngredientInput(
                    ingredient=flour,
                    unit=kg,
                    quantity="1",
                    unit_cost="80",
                    purchase_item_id=purchase.items[0].id,
                )
            ],
        )

        assert purchase_has_stock_usage(session, purchase)
        with pytest.raises(ValueError, match="использованы"):
            update_purchase(
                session,
                purchase.id,
                purchase_date=date(2026, 6, 16),
                lines=[
                    PurchaseLineInput(
                        item_type=PurchaseItemType.INGREDIENT,
                        ingredient=flour,
                        item_name=flour.name,
                        unit=kg,
                        quantity="2",
                        unit_price="90",
                    )
                ],
            )
        with pytest.raises(ValueError, match="использованы"):
            delete_purchase(session, purchase.id)
