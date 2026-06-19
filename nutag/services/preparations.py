"""Service functions for internal preparations/semi-finished products."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from nutag.db.models import Ingredient, Preparation, PreparationIngredientUse, PreparationType, Unit
from nutag.services.calculations import calculate_preparation_cost, calculate_unit_cost, to_decimal


@dataclass(frozen=True)
class PreparationIngredientInput:
    """Ingredient consumed by an internal preparation."""

    ingredient: Ingredient
    unit: Unit
    quantity: Decimal | int | float | str
    unit_cost: Decimal | int | float | str
    purchase_item_id: int | None = None
    comment: str | None = None


def calculate_ingredient_use_total(
    *,
    quantity: Decimal | int | float | str,
    unit_cost: Decimal | int | float | str,
) -> Decimal:
    """Calculate cost of one ingredient use line."""

    quantity_decimal = to_decimal(quantity)
    unit_cost_decimal = to_decimal(unit_cost)
    if quantity_decimal <= 0:
        raise ValueError("Ingredient use quantity must be greater than zero")
    if unit_cost_decimal < 0:
        raise ValueError("Ingredient use unit cost cannot be negative")

    return quantity_decimal * unit_cost_decimal


def create_preparation(
    session: Session,
    *,
    prepared_on: date,
    preparation_type: PreparationType,
    output_quantity: Decimal | int | float | str,
    waste_quantity: Decimal | int | float | str = 0,
    output_unit: Unit,
    ingredient_uses: Iterable[PreparationIngredientInput],
    labor_cost: Decimal | int | float | str = 0,
    other_direct_cost: Decimal | int | float | str = 0,
    comment: str | None = None,
) -> Preparation:
    """Create an internal preparation and calculate its total and unit cost."""

    output_quantity_decimal = to_decimal(output_quantity)
    waste_quantity_decimal = to_decimal(waste_quantity)
    if output_quantity_decimal <= 0:
        raise ValueError("Preparation output quantity must be greater than zero")

    ingredient_inputs = list(ingredient_uses)
    if not ingredient_inputs:
        raise ValueError("Preparation must contain at least one ingredient use")

    ingredient_total_costs = [
        calculate_ingredient_use_total(quantity=line.quantity, unit_cost=line.unit_cost) for line in ingredient_inputs
    ]
    total_cost = calculate_preparation_cost(
        ingredient_costs=ingredient_total_costs,
        labor_costs=[labor_cost],
        other_direct_costs=[other_direct_cost],
    )
    unit_cost = calculate_unit_cost(total_cost=total_cost, actual_output=output_quantity_decimal)

    preparation = Preparation(
        prepared_on=prepared_on,
        preparation_type=preparation_type,
        name=preparation_type.name,
        output_quantity=output_quantity_decimal,
        waste_quantity=waste_quantity_decimal,
        output_unit=output_unit,
        labor_cost=to_decimal(labor_cost),
        other_direct_cost=to_decimal(other_direct_cost),
        total_cost=total_cost,
        unit_cost=unit_cost,
        comment=comment,
    )

    for line, line_total in zip(ingredient_inputs, ingredient_total_costs, strict=True):
        preparation.ingredient_uses.append(
            PreparationIngredientUse(
                ingredient=line.ingredient,
                unit=line.unit,
                purchase_item_id=line.purchase_item_id,
                quantity=to_decimal(line.quantity),
                unit_cost=to_decimal(line.unit_cost),
                total_cost=line_total,
                comment=line.comment,
            )
        )

    session.add(preparation)
    session.flush()
    return preparation


def list_preparations(session: Session) -> list[Preparation]:
    """Return preparations ordered from newest to oldest."""

    return list(session.scalars(select(Preparation).order_by(Preparation.prepared_on.desc(), Preparation.id.desc())))
