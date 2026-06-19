from datetime import date
from decimal import Decimal

import pytest

from nutag.db import create_database, create_engine_for_url, create_session_factory
from nutag.services.preparations import PreparationIngredientInput, create_preparation
from nutag.services.production import (
    BatchIngredientInput,
    BatchPackagingInput,
    BatchPreparationInput,
    FinishedProductOutputInput,
    calculate_output_total,
    create_production_batch,
    list_production_batches,
)
from nutag.db.models import PurchaseItemType
from nutag.services.purchases import PurchaseLineInput, create_purchase
from nutag.services.references import create_ingredient, create_packaging, create_product, create_unit


def make_session_factory():
    engine = create_engine_for_url("sqlite:///:memory:")
    create_database(engine)
    return create_session_factory(engine)


def test_calculate_output_total_validates_package_size_and_count() -> None:
    assert calculate_output_total(package_size="0.5", package_count=12) == Decimal("6.0")

    with pytest.raises(ValueError, match="Package size"):
        calculate_output_total(package_size="0", package_count=12)

    with pytest.raises(ValueError, match="Package count"):
        calculate_output_total(package_size="0.5", package_count=0)


def test_create_production_batch_calculates_costs_and_outputs() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        product = create_product(session, name="Пельмени")
        flour = create_ingredient(session, name="Мука", unit=kg)
        meat = create_ingredient(session, name="Фарш", unit=kg)
        preparation = create_preparation(
            session,
            prepared_on=date(2026, 6, 14),
            name="Начинка",
            output_quantity="4",
            output_unit=kg,
            ingredient_uses=[PreparationIngredientInput(ingredient=meat, unit=kg, quantity="4", unit_cost="450")],
        )

        batch = create_production_batch(
            session,
            produced_on=date(2026, 6, 15),
            product=product,
            planned_quantity="5",
            actual_output_quantity="6",
            output_unit=kg,
            ingredient_uses=[BatchIngredientInput(ingredient=flour, unit=kg, quantity="2", unit_cost="92")],
            preparation_uses=[
                BatchPreparationInput(
                    preparation=preparation,
                    unit=kg,
                    quantity="3",
                    unit_cost=preparation.unit_cost,
                )
            ],
            labor_cost="500",
            equipment_depreciation="40",
            allocated_overhead="60",
            outputs=[
                FinishedProductOutputInput(package_size="0.5", package_unit=kg, package_count=8),
                FinishedProductOutputInput(package_size="1", package_unit=kg, package_count=2),
            ],
        )
        session.commit()
        batch_id = batch.id

    with session_factory() as session:
        saved = list_production_batches(session)[0]
        assert saved.id == batch_id
        assert saved.total_cost == Decimal("2134.00")
        assert saved.unit_cost == Decimal("355.6667")
        assert len(saved.ingredient_uses) == 1
        assert saved.ingredient_uses[0].total_cost == Decimal("184.00")
        assert len(saved.preparation_uses) == 1
        assert saved.preparation_uses[0].total_cost == Decimal("1350.00")
        assert [output.total_quantity for output in saved.outputs] == [Decimal("4.000"), Decimal("2.000")]


def test_create_production_batch_rejects_zero_output_quantity() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        product = create_product(session, name="Пельмени")
        with pytest.raises(ValueError, match="actual output"):
            create_production_batch(
                session,
                produced_on=date(2026, 6, 15),
                product=product,
                actual_output_quantity="0",
                output_unit=kg,
                outputs=[FinishedProductOutputInput(package_size="1", package_unit=kg, package_count=1)],
            )


def test_create_production_batch_rejects_empty_outputs() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        product = create_product(session, name="Пельмени")
        with pytest.raises(ValueError, match="finished output"):
            create_production_batch(
                session,
                produced_on=date(2026, 6, 15),
                product=product,
                actual_output_quantity="1",
                output_unit=kg,
                outputs=[],
            )


def test_create_production_batch_persists_selected_source_batch_ids() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        kg = create_unit(session, name="kilogram", short_name="kg")
        piece = create_unit(session, name="piece", short_name="pcs")
        product = create_product(session, name="ÐŸÐµÐ»ÑŒÐ¼ÐµÐ½Ð¸")
        flour = create_ingredient(session, name="ÐœÑƒÐºÐ°", unit=kg)
        meat = create_ingredient(session, name="Ð¤Ð°Ñ€Ñˆ", unit=kg)
        container = create_packaging(session, name="ÐšÐ¾Ð½Ñ‚ÐµÐ¹Ð½ÐµÑ€", unit=piece)

        purchase = create_purchase(
            session,
            purchase_date=date(2026, 6, 13),
            lines=[
                PurchaseLineInput(
                    item_type=PurchaseItemType.INGREDIENT,
                    item_name=flour.name,
                    ingredient=flour,
                    unit=kg,
                    quantity="10",
                    unit_price="92",
                ),
                PurchaseLineInput(
                    item_type=PurchaseItemType.PACKAGING,
                    item_name=container.name,
                    packaging=container,
                    unit=piece,
                    quantity="20",
                    unit_price="5",
                ),
            ],
        )
        ingredient_purchase_item = purchase.items[0]
        packaging_purchase_item = purchase.items[1]
        preparation = create_preparation(
            session,
            prepared_on=date(2026, 6, 14),
            name="ÐÐ°Ñ‡Ð¸Ð½ÐºÐ°",
            output_quantity="4",
            output_unit=kg,
            ingredient_uses=[PreparationIngredientInput(ingredient=meat, unit=kg, quantity="4", unit_cost="450")],
        )

        batch = create_production_batch(
            session,
            produced_on=date(2026, 6, 15),
            product=product,
            actual_output_quantity="6",
            output_unit=kg,
            ingredient_uses=[
                BatchIngredientInput(
                    ingredient=flour,
                    unit=kg,
                    quantity="2",
                    unit_cost="92",
                    purchase_item_id=ingredient_purchase_item.id,
                )
            ],
            preparation_uses=[
                BatchPreparationInput(
                    preparation=preparation,
                    unit=kg,
                    quantity="3",
                    unit_cost=preparation.unit_cost,
                    source_preparation_id=preparation.id,
                )
            ],
            packaging_uses=[
                BatchPackagingInput(
                    packaging=container,
                    unit=piece,
                    quantity="6",
                    unit_cost="5",
                    purchase_item_id=packaging_purchase_item.id,
                )
            ],
            outputs=[FinishedProductOutputInput(package_size="1", package_unit=kg, package_count=6)],
        )
        session.commit()
        batch_id = batch.id

    with session_factory() as session:
        saved = list_production_batches(session)[0]
        assert saved.id == batch_id
        assert saved.ingredient_uses[0].purchase_item_id == ingredient_purchase_item.id
        assert saved.preparation_uses[0].source_preparation_id == preparation.id
        assert saved.packaging_uses[0].purchase_item_id == packaging_purchase_item.id
