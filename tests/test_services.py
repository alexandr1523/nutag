from datetime import date
from decimal import Decimal

import pytest

from nutag.db import create_database, create_engine_for_url, create_session_factory
from nutag.db.models import Consumable, Preparation, ProductionBatch, PurchaseItemType
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
    create_consumable,
    create_ingredient,
    create_packaging,
    create_preparation_type,
    create_product,
    create_unit,
    delete_consumable,
    delete_ingredient,
    delete_packaging,
    delete_preparation_type,
    delete_product,
    delete_unit,
    list_consumables,
    list_ingredients,
    list_packaging,
    list_preparation_types,
    list_products,
    list_units,
    update_consumable,
    update_ingredient,
    update_packaging,
    update_preparation_type,
    update_product,
    update_unit,
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
        create_consumable(session, name="Перчатки", unit=piece)
        session.commit()

    with session_factory() as session:
        assert [unit.short_name for unit in list_units(session)] == ["kg", "pcs"]
        assert [product.name for product in list_products(session)] == ["Пельмени"]
        assert [preparation_type.name for preparation_type in list_preparation_types(session)] == ["Начинка"]
        assert [ingredient.name for ingredient in list_ingredients(session)] == ["Мука"]
        assert [packaging.name for packaging in list_packaging(session)] == ["Контейнер 1 кг"]
        assert [consumable.name for consumable in list_consumables(session)] == ["Перчатки"]


def test_create_unit_normalizes_values_and_rejects_duplicates() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name=" Килограмм ", short_name=" Кг ", comment=" основной ")
        session.commit()

        assert kg.name == "Килограмм"
        assert kg.short_name == "Кг"
        assert kg.comment == "основной"

        with pytest.raises(ValueError, match="таким сокращением"):
            create_unit(session, name="Килограмм новый", short_name="кг")

        with pytest.raises(ValueError, match="таким названием"):
            create_unit(session, name="килограмм", short_name="kg")

        with pytest.raises(ValueError, match="Название обязательно"):
            create_unit(session, name="   ", short_name="шт")


def test_create_ingredient_normalizes_values_and_rejects_duplicates() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="Килограмм", short_name="кг")
        oil = create_ingredient(session, name=" Растительное масло ", unit=kg, comment="  для жарки  ")
        session.commit()

        assert oil.name == "Растительное масло"
        assert oil.comment == "для жарки"

        with pytest.raises(ValueError, match="Ингредиент с таким названием уже существует"):
            create_ingredient(session, name="растительное масло", unit=kg)

        with pytest.raises(ValueError, match="Название обязательно"):
            create_ingredient(session, name="   ", unit=kg)


def test_reference_create_services_normalize_values_and_reject_duplicates() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        piece = create_unit(session, name="Штука", short_name="шт")
        product = create_product(session, name=" Пельмени ", comment="  основной продукт  ")
        preparation_type = create_preparation_type(session, name=" Фарш ", comment="  мясная заготовка  ")
        packaging = create_packaging(session, name=" Контейнер 0,5 ", unit=piece, comment="  фасовка  ")
        consumable = create_consumable(session, name=" Перчатки ", unit=piece, comment="  одноразовые  ")

        assert product.name == "Пельмени"
        assert product.comment == "основной продукт"
        assert preparation_type.name == "Фарш"
        assert preparation_type.comment == "мясная заготовка"
        assert packaging.name == "Контейнер 0,5"
        assert packaging.comment == "фасовка"
        assert consumable.name == "Перчатки"
        assert consumable.comment == "одноразовые"

        with pytest.raises(ValueError, match="Продукт с таким названием"):
            create_product(session, name="пельмени")
        with pytest.raises(ValueError, match="Вид заготовки с таким названием"):
            create_preparation_type(session, name="фарш")
        with pytest.raises(ValueError, match="Упаковка с таким названием"):
            create_packaging(session, name="контейнер 0,5", unit=piece)
        with pytest.raises(ValueError, match="Расходник с таким названием"):
            create_consumable(session, name="перчатки", unit=piece)


def test_reference_update_services_preserve_ids_and_reject_duplicates() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="Килограмм", short_name="кг")
        piece = create_unit(session, name="Штука", short_name="шт")
        flour = create_ingredient(session, name="Мука", unit=kg)
        sugar = create_ingredient(session, name="Сахар", unit=kg)
        container = create_packaging(session, name="Контейнер", unit=piece)
        bag = create_packaging(session, name="Пакет", unit=piece)
        gloves = create_consumable(session, name="Перчатки", unit=piece)
        wipes = create_consumable(session, name="Салфетки", unit=piece)
        product = create_product(session, name="Пельмени")
        other_product = create_product(session, name="Вареники")
        preparation_type = create_preparation_type(session, name="Фарш")
        other_preparation_type = create_preparation_type(session, name="Тесто")
        session.commit()

        update_unit(session, kg.id, name=" Килограмм основной ", short_name=" кг ", comment="  масса  ")
        update_ingredient(session, flour.id, name=" Мука пшеничная ", unit=kg, comment="  в/с  ")
        update_packaging(session, container.id, name=" Контейнер 0,5 ", unit=piece, comment="  пластик  ")
        update_consumable(session, gloves.id, name=" Перчатки нитриловые ", unit=piece, comment="  M  ")
        update_product(session, product.id, name=" Пельмени мясные ", comment="  хит  ")
        update_preparation_type(session, preparation_type.id, name=" Фарш мясной ", comment="  база  ")

        assert kg.id == 1
        assert kg.name == "Килограмм основной"
        assert kg.short_name == "кг"
        assert flour.id == 1
        assert flour.name == "Мука пшеничная"
        assert container.id == 1
        assert container.name == "Контейнер 0,5"
        assert gloves.id == 1
        assert gloves.name == "Перчатки нитриловые"
        assert product.id == 1
        assert product.name == "Пельмени мясные"
        assert preparation_type.id == 1
        assert preparation_type.name == "Фарш мясной"

        with pytest.raises(ValueError, match="Ингредиент с таким названием"):
            update_ingredient(session, flour.id, name=sugar.name, unit=kg)
        with pytest.raises(ValueError, match="Упаковка с таким названием"):
            update_packaging(session, container.id, name=bag.name, unit=piece)
        with pytest.raises(ValueError, match="Расходник с таким названием"):
            update_consumable(session, gloves.id, name=wipes.name, unit=piece)
        with pytest.raises(ValueError, match="Продукт с таким названием"):
            update_product(session, product.id, name=other_product.name)
        with pytest.raises(ValueError, match="Вид заготовки с таким названием"):
            update_preparation_type(session, preparation_type.id, name=other_preparation_type.name)


def test_reference_update_blocks_unit_change_after_stock_usage() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="Килограмм", short_name="кг")
        piece = create_unit(session, name="Штука", short_name="шт")
        flour = create_ingredient(session, name="Мука", unit=kg)
        container = create_packaging(session, name="Контейнер", unit=piece)
        gloves = create_consumable(session, name="Перчатки", unit=piece)

        create_purchase(
            session,
            purchase_date=date(2026, 6, 14),
            lines=[
                PurchaseLineInput(
                    item_type=PurchaseItemType.INGREDIENT,
                    ingredient=flour,
                    item_name=flour.name,
                    unit=kg,
                    quantity="1",
                    unit_price="80",
                ),
                PurchaseLineInput(
                    item_type=PurchaseItemType.PACKAGING,
                    packaging=container,
                    item_name=container.name,
                    unit=piece,
                    quantity="10",
                    unit_price="5",
                ),
                PurchaseLineInput(
                    item_type=PurchaseItemType.CONSUMABLE,
                    consumable=gloves,
                    item_name=gloves.name,
                    unit=piece,
                    quantity="5",
                    unit_price="2",
                ),
            ],
        )

        with pytest.raises(ValueError, match="ингредиент уже использовался"):
            update_ingredient(session, flour.id, name="Мука", unit=piece)
        with pytest.raises(ValueError, match="упаковка уже использовалась"):
            update_packaging(session, container.id, name="Контейнер", unit=kg)
        with pytest.raises(ValueError, match="расходник уже использовался"):
            update_consumable(session, gloves.id, name="Перчатки", unit=kg)

        assert update_ingredient(session, flour.id, name="Мука пшеничная", unit=kg).name == "Мука пшеничная"
        assert update_packaging(session, container.id, name="Контейнер 0,5", unit=piece).name == "Контейнер 0,5"
        assert update_consumable(session, gloves.id, name="Перчатки нитриловые", unit=piece).name == "Перчатки нитриловые"


def test_reference_delete_services_delete_unused_records() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="Килограмм", short_name="кг")
        piece = create_unit(session, name="Штука", short_name="шт")
        ingredient = create_ingredient(session, name="Мука", unit=kg)
        packaging = create_packaging(session, name="Контейнер", unit=piece)
        consumable = create_consumable(session, name="Перчатки", unit=piece)
        product = create_product(session, name="Пельмени")
        preparation_type = create_preparation_type(session, name="Фарш")

        delete_ingredient(session, ingredient.id)
        delete_packaging(session, packaging.id)
        delete_consumable(session, consumable.id)
        delete_product(session, product.id)
        delete_preparation_type(session, preparation_type.id)
        delete_unit(session, kg.id)
        delete_unit(session, piece.id)
        session.commit()

    with session_factory() as session:
        assert list_units(session) == []
        assert list_ingredients(session) == []
        assert list_packaging(session) == []
        assert list_consumables(session) == []
        assert list_products(session) == []
        assert list_preparation_types(session) == []


def test_reference_delete_services_block_used_records() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="Килограмм", short_name="кг")
        piece = create_unit(session, name="Штука", short_name="шт")
        flour = create_ingredient(session, name="Мука", unit=kg)
        container = create_packaging(session, name="Контейнер", unit=piece)
        gloves = create_consumable(session, name="Перчатки", unit=piece)
        product = create_product(session, name="Пельмени")
        preparation_type = create_preparation_type(session, name="Фарш")

        create_purchase(
            session,
            purchase_date=date(2026, 6, 14),
            lines=[
                PurchaseLineInput(
                    item_type=PurchaseItemType.INGREDIENT,
                    ingredient=flour,
                    item_name=flour.name,
                    unit=kg,
                    quantity="1",
                    unit_price="80",
                ),
                PurchaseLineInput(
                    item_type=PurchaseItemType.PACKAGING,
                    packaging=container,
                    item_name=container.name,
                    unit=piece,
                    quantity="10",
                    unit_price="5",
                ),
                PurchaseLineInput(
                    item_type=PurchaseItemType.CONSUMABLE,
                    consumable=gloves,
                    item_name=gloves.name,
                    unit=piece,
                    quantity="5",
                    unit_price="2",
                ),
            ],
        )
        session.add(
            ProductionBatch(
                produced_on=date(2026, 6, 15),
                product=product,
                actual_output_quantity=Decimal("1"),
                output_unit=kg,
                total_cost=Decimal("100"),
                unit_cost=Decimal("100"),
            )
        )
        session.add(
            Preparation(
                prepared_on=date(2026, 6, 15),
                preparation_type=preparation_type,
                name=preparation_type.name,
                output_quantity=Decimal("1"),
                output_unit=kg,
                total_cost=Decimal("100"),
                unit_cost=Decimal("100"),
            )
        )
        session.flush()

        with pytest.raises(ValueError, match="Единицу измерения нельзя удалить"):
            delete_unit(session, kg.id)
        with pytest.raises(ValueError, match="Ингредиент нельзя удалить"):
            delete_ingredient(session, flour.id)
        with pytest.raises(ValueError, match="Упаковку нельзя удалить"):
            delete_packaging(session, container.id)
        with pytest.raises(ValueError, match="Расходник нельзя удалить"):
            delete_consumable(session, gloves.id)
        with pytest.raises(ValueError, match="Продукт нельзя удалить"):
            delete_product(session, product.id)
        with pytest.raises(ValueError, match="Вид заготовки нельзя удалить"):
            delete_preparation_type(session, preparation_type.id)


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
