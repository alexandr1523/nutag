from datetime import date
from decimal import Decimal

import pytest

from nutag.db import create_database, create_engine_for_url, create_session_factory
from nutag.services.preparations import (
    PreparationIngredientInput,
    calculate_ingredient_use_total,
    create_preparation,
    list_preparations,
)
from nutag.services.references import create_ingredient, create_preparation_type, create_unit


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
