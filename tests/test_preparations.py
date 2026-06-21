from datetime import date
from decimal import Decimal

import pytest

from nutag.db import create_database, create_engine_for_url, create_session_factory
from nutag.db.models import PurchaseItemType
from nutag.services.preparations import (
    PreparationIngredientInput,
    calculate_ingredient_use_total,
    create_preparation,
    delete_preparation,
    is_preparation_used,
    list_preparations,
    update_preparation,
)
from nutag.services.production import BatchPreparationInput, create_production_batch
from nutag.services.purchases import PurchaseLineInput, create_purchase
from nutag.services.references import create_ingredient, create_packaging, create_preparation_type, create_product, create_unit
from nutag.services.inventory import list_available_stock_batches


def make_session_factory():
    engine = create_engine_for_url("sqlite:///:memory:")
    create_database(engine)
    return create_session_factory(engine)


def test_calculate_ingredient_use_total_validates_quantity_and_cost() -> None:
    assert calculate_ingredient_use_total(quantity="2.5", unit_cost="92") == Decimal("230.0")

    with pytest.raises(ValueError, match="quantity"):
        calculate_ingredient_use_total(quantity="0", unit_cost="92")

    with pytest.raises(ValueError, match="unit cost"):
        calculate_ingredient_use_total(quantity="1", unit_cost="-1")


def test_create_preparation_calculates_total_and_unit_cost() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        flour = create_ingredient(session, name="Мука", unit=kg)
        meat = create_ingredient(session, name="Фарш", unit=kg)
        filling = create_preparation_type(session, name="Начинка")

        preparation = create_preparation(
            session,
            prepared_on=date(2026, 6, 14),
            preparation_type=filling,
            output_quantity="4",
            output_unit=kg,
            ingredient_uses=[
                PreparationIngredientInput(ingredient=flour, unit=kg, quantity="1", unit_cost="92"),
                PreparationIngredientInput(ingredient=meat, unit=kg, quantity="3", unit_cost="465"),
            ],
            labor_cost="300",
            other_direct_cost="20",
        )
        session.commit()
        preparation_id = preparation.id

    with session_factory() as session:
        saved = list_preparations(session)[0]
        assert saved.id == preparation_id
        assert saved.total_cost == Decimal("1807.00")
        assert saved.unit_cost == Decimal("451.7500")
        assert len(saved.ingredient_uses) == 2
        assert [line.total_cost for line in saved.ingredient_uses] == [Decimal("92.00"), Decimal("1395.00")]
        assert [line.waste_quantity for line in saved.ingredient_uses] == [Decimal("0.000"), Decimal("0.000")]


def test_create_preparation_tracks_waste_by_ingredient_use() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        meat = create_ingredient(session, name="Фарш", unit=kg)
        onion = create_ingredient(session, name="Лук", unit=kg)
        filling = create_preparation_type(session, name="Начинка")

        preparation = create_preparation(
            session,
            prepared_on=date(2026, 6, 14),
            preparation_type=filling,
            output_quantity="4",
            output_unit=kg,
            ingredient_uses=[
                PreparationIngredientInput(
                    ingredient=meat,
                    unit=kg,
                    quantity="3",
                    waste_quantity="0.2",
                    unit_cost="465",
                ),
                PreparationIngredientInput(
                    ingredient=onion,
                    unit=kg,
                    quantity="0.5",
                    waste_quantity="0.05",
                    unit_cost="100",
                ),
            ],
        )
        session.commit()
        preparation_id = preparation.id

    with session_factory() as session:
        saved = list_preparations(session)[0]
        assert saved.id == preparation_id
        assert [line.quantity for line in saved.ingredient_uses] == [Decimal("3.000"), Decimal("0.500")]
        assert [line.waste_quantity for line in saved.ingredient_uses] == [Decimal("0.200"), Decimal("0.050")]
        assert [line.total_cost for line in saved.ingredient_uses] == [Decimal("1395.00"), Decimal("50.00")]
        assert saved.total_cost == Decimal("1445.00")


def test_create_preparation_rejects_negative_ingredient_waste() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        flour = create_ingredient(session, name="Мука", unit=kg)
        filling = create_preparation_type(session, name="Тесто")

        with pytest.raises(ValueError, match="waste quantity"):
            create_preparation(
                session,
                prepared_on=date(2026, 6, 14),
                preparation_type=filling,
                output_quantity="1",
                output_unit=kg,
                ingredient_uses=[
                    PreparationIngredientInput(
                        ingredient=flour,
                        unit=kg,
                        quantity="1",
                        waste_quantity="-0.1",
                        unit_cost="92",
                    )
                ],
            )


def test_create_preparation_rejects_ingredient_waste_greater_than_quantity() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        flour = create_ingredient(session, name="Мука", unit=kg)
        filling = create_preparation_type(session, name="Тесто")

        with pytest.raises(ValueError, match="cannot exceed"):
            create_preparation(
                session,
                prepared_on=date(2026, 6, 14),
                preparation_type=filling,
                output_quantity="1",
                output_unit=kg,
                ingredient_uses=[
                    PreparationIngredientInput(
                        ingredient=flour,
                        unit=kg,
                        quantity="1",
                        waste_quantity="1.1",
                        unit_cost="92",
                    )
                ],
            )


def test_create_preparation_uses_selected_purchase_batch_price() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        flour = create_ingredient(session, name="Мука", unit=kg)
        filling = create_preparation_type(session, name="Тесто")
        purchase = create_purchase(
            session,
            purchase_date=date(2026, 6, 14),
            lines=[
                PurchaseLineInput(
                    item_type=PurchaseItemType.INGREDIENT,
                    ingredient=flour,
                    item_name=flour.name,
                    unit=kg,
                    quantity="10",
                    unit_price="80",
                )
            ],
        )

        preparation = create_preparation(
            session,
            prepared_on=date(2026, 6, 15),
            preparation_type=filling,
            output_quantity="2",
            output_unit=kg,
            ingredient_uses=[
                PreparationIngredientInput(
                    ingredient=flour,
                    unit=kg,
                    quantity="2",
                    waste_quantity="0.5",
                    unit_cost="999",
                    purchase_item_id=purchase.items[0].id,
                )
            ],
        )
        session.commit()

        assert preparation.ingredient_uses[0].unit_cost == Decimal("80.0000")
        assert preparation.ingredient_uses[0].quantity == Decimal("2.000")
        assert preparation.ingredient_uses[0].waste_quantity == Decimal("0.500")
        assert preparation.ingredient_uses[0].total_cost == Decimal("160.00")
        assert preparation.total_cost == Decimal("160.00")


def test_update_preparation_recalculates_unused_preparation() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        flour = create_ingredient(session, name="Мука", unit=kg)
        dough = create_preparation_type(session, name="Тесто")
        thick_dough = create_preparation_type(session, name="Плотное тесто")
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
        preparation = create_preparation(
            session,
            prepared_on=date(2026, 6, 15),
            preparation_type=dough,
            output_quantity="1",
            output_unit=kg,
            ingredient_uses=[
                PreparationIngredientInput(
                    ingredient=flour,
                    unit=kg,
                    quantity="2",
                    unit_cost="999",
                    purchase_item_id=purchase.items[0].id,
                )
            ],
            labor_cost="10",
        )
        preparation_id = preparation.id

        updated = update_preparation(
            session,
            preparation_id,
            prepared_on=date(2026, 6, 16),
            preparation_type=thick_dough,
            output_quantity="1.5",
            output_unit=kg,
            ingredient_uses=[
                PreparationIngredientInput(
                    ingredient=flour,
                    unit=kg,
                    quantity="2",
                    waste_quantity="0.25",
                    unit_cost="999",
                    purchase_item_id=purchase.items[0].id,
                )
            ],
            labor_cost="20",
            other_direct_cost="5",
            comment="Исправлено",
        )
        session.commit()

        assert updated.id == preparation_id
        assert updated.prepared_on == date(2026, 6, 16)
        assert updated.preparation_type == thick_dough
        assert updated.name == "Плотное тесто"
        assert updated.total_cost == Decimal("185.00")
        assert updated.unit_cost.quantize(Decimal("0.0001")) == Decimal("123.3333")
        assert updated.comment == "Исправлено"
        assert len(updated.ingredient_uses) == 1
        assert updated.ingredient_uses[0].unit_cost == Decimal("80.0000")
        assert updated.ingredient_uses[0].quantity == Decimal("2.000")
        assert updated.ingredient_uses[0].waste_quantity == Decimal("0.250")


def test_update_preparation_rejects_used_preparation() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        meat = create_ingredient(session, name="Фарш", unit=kg)
        filling = create_preparation_type(session, name="Начинка")
        product = create_product(session, name="Пельмени")
        preparation = create_preparation(
            session,
            prepared_on=date(2026, 6, 14),
            preparation_type=filling,
            output_quantity="4",
            output_unit=kg,
            ingredient_uses=[PreparationIngredientInput(ingredient=meat, unit=kg, quantity="4", unit_cost="450")],
        )
        create_production_batch(
            session,
            produced_on=date(2026, 6, 15),
            product=product,
            actual_output_quantity="2",
            output_unit=kg,
            preparation_uses=[
                BatchPreparationInput(
                    preparation=preparation,
                    unit=kg,
                    quantity="1",
                    unit_cost=preparation.unit_cost,
                    source_preparation_id=preparation.id,
                )
            ],
            labor_cost="1",
        )

        assert is_preparation_used(session, preparation.id)
        with pytest.raises(ValueError, match="использована в производстве"):
            update_preparation(
                session,
                preparation.id,
                prepared_on=date(2026, 6, 16),
                preparation_type=filling,
                output_quantity="4",
                output_unit=kg,
                ingredient_uses=[
                    PreparationIngredientInput(ingredient=meat, unit=kg, quantity="4", unit_cost="450")
                ],
            )


def test_delete_preparation_removes_unused_preparation_and_restores_ingredient_stock() -> None:
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
                    quantity="5",
                    unit_price="80",
                )
            ],
        )
        preparation = create_preparation(
            session,
            prepared_on=date(2026, 6, 15),
            preparation_type=dough,
            output_quantity="2",
            output_unit=kg,
            ingredient_uses=[
                PreparationIngredientInput(
                    ingredient=flour,
                    unit=kg,
                    quantity="2",
                    unit_cost="999",
                    purchase_item_id=purchase.items[0].id,
                )
            ],
        )
        preparation_id = preparation.id

        stock_before_delete = [
            batch
            for batch in list_available_stock_batches(session)
            if batch.batch_type == "purchase" and batch.batch_id == purchase.items[0].id
        ][0]
        assert stock_before_delete.current_quantity == Decimal("3.000")

        delete_preparation(session, preparation_id)
        session.commit()

        assert list_preparations(session) == []
        stock_after_delete = [
            batch
            for batch in list_available_stock_batches(session)
            if batch.batch_type == "purchase" and batch.batch_id == purchase.items[0].id
        ][0]
        assert stock_after_delete.current_quantity == Decimal("5.000")


def test_delete_preparation_rejects_used_preparation() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        meat = create_ingredient(session, name="Фарш", unit=kg)
        filling = create_preparation_type(session, name="Начинка")
        product = create_product(session, name="Пельмени")
        preparation = create_preparation(
            session,
            prepared_on=date(2026, 6, 14),
            preparation_type=filling,
            output_quantity="4",
            output_unit=kg,
            ingredient_uses=[PreparationIngredientInput(ingredient=meat, unit=kg, quantity="4", unit_cost="450")],
        )
        create_production_batch(
            session,
            produced_on=date(2026, 6, 15),
            product=product,
            actual_output_quantity="2",
            output_unit=kg,
            preparation_uses=[
                BatchPreparationInput(
                    preparation=preparation,
                    unit=kg,
                    quantity="1",
                    unit_cost=preparation.unit_cost,
                    source_preparation_id=preparation.id,
                )
            ],
            labor_cost="1",
        )

        with pytest.raises(ValueError, match="использована в производстве"):
            delete_preparation(session, preparation.id)


def test_create_preparation_rejects_selected_purchase_batch_overdraft() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        flour = create_ingredient(session, name="Мука", unit=kg)
        filling = create_preparation_type(session, name="Тесто")
        purchase = create_purchase(
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
                )
            ],
        )

        with pytest.raises(ValueError, match="Недостаточно остатка"):
            create_preparation(
                session,
                prepared_on=date(2026, 6, 15),
                preparation_type=filling,
                output_quantity="1",
                output_unit=kg,
                ingredient_uses=[
                    PreparationIngredientInput(
                        ingredient=flour,
                        unit=kg,
                        quantity="2",
                        unit_cost="80",
                        purchase_item_id=purchase.items[0].id,
                    )
                ],
            )


def test_create_preparation_rejects_cumulative_selected_purchase_batch_overdraft() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        flour = create_ingredient(session, name="Мука", unit=kg)
        filling = create_preparation_type(session, name="Тесто")
        purchase = create_purchase(
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
                )
            ],
        )

        with pytest.raises(ValueError, match="Недостаточно остатка"):
            create_preparation(
                session,
                prepared_on=date(2026, 6, 15),
                preparation_type=filling,
                output_quantity="1",
                output_unit=kg,
                ingredient_uses=[
                    PreparationIngredientInput(
                        ingredient=flour,
                        unit=kg,
                        quantity="0.6",
                        unit_cost="80",
                        purchase_item_id=purchase.items[0].id,
                    ),
                    PreparationIngredientInput(
                        ingredient=flour,
                        unit=kg,
                        quantity="0.6",
                        unit_cost="80",
                        purchase_item_id=purchase.items[0].id,
                    ),
                ],
            )


def test_create_preparation_rejects_selected_purchase_batch_wrong_type() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        piece = create_unit(session, name="piece", short_name="pcs")
        flour = create_ingredient(session, name="Мука", unit=kg)
        container = create_packaging(session, name="Контейнер", unit=piece)
        filling = create_preparation_type(session, name="Тесто")
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

        with pytest.raises(ValueError, match="не соответствует"):
            create_preparation(
                session,
                prepared_on=date(2026, 6, 15),
                preparation_type=filling,
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


def test_create_preparation_rejects_empty_ingredient_uses() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        empty_type = create_preparation_type(session, name="Пустая заготовка")
        with pytest.raises(ValueError, match="at least one ingredient use"):
            create_preparation(
                session,
                prepared_on=date(2026, 6, 14),
                preparation_type=empty_type,
                output_quantity="1",
                output_unit=kg,
                ingredient_uses=[],
            )


def test_create_preparation_rejects_zero_output() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        flour = create_ingredient(session, name="Мука", unit=kg)
        empty_type = create_preparation_type(session, name="Пустая заготовка")
        with pytest.raises(ValueError, match="output quantity"):
            create_preparation(
                session,
                prepared_on=date(2026, 6, 14),
                preparation_type=empty_type,
                output_quantity="0",
                output_unit=kg,
                ingredient_uses=[PreparationIngredientInput(ingredient=flour, unit=kg, quantity="1", unit_cost="92")],
            )
