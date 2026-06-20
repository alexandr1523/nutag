"""Service functions for internal preparations/semi-finished products."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from nutag.db.models import (
    BatchIngredientUse,
    BatchPreparationUse,
    Ingredient,
    Preparation,
    PreparationIngredientUse,
    PreparationType,
    PurchaseItem,
    PurchaseItemType,
    Unit,
)
from nutag.services.calculations import calculate_preparation_cost, calculate_unit_cost, to_decimal


@dataclass(frozen=True)
class PreparationIngredientInput:
    """Ingredient consumed by an internal preparation."""

    ingredient: Ingredient
    unit: Unit
    quantity: Decimal | int | float | str
    unit_cost: Decimal | int | float | str
    waste_quantity: Decimal | int | float | str = 0
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


def is_preparation_used(session: Session, preparation_id: int) -> bool:
    """Return whether a preparation is already consumed by production."""

    return session.scalar(
        select(BatchPreparationUse.id)
        .where(
            or_(
                BatchPreparationUse.source_preparation_id == preparation_id,
                BatchPreparationUse.preparation_id == preparation_id,
            )
        )
        .limit(1)
    ) is not None


def _get_purchase_unit_cost_for_preparation_line(
    session: Session,
    *,
    line: PreparationIngredientInput,
    quantity: Decimal,
    exclude_preparation_id: int | None,
) -> Decimal:
    purchase_item = session.get(PurchaseItem, line.purchase_item_id)
    if purchase_item is None:
        raise ValueError("Выбранная партия закупки не найдена")
    if purchase_item.item_type != PurchaseItemType.INGREDIENT:
        raise ValueError("Выбранная партия закупки не соответствует типу ингредиента")
    if purchase_item.ingredient_id != line.ingredient.id:
        raise ValueError("Выбранная партия закупки не соответствует ингредиенту")
    if purchase_item.unit.short_name != line.unit.short_name:
        raise ValueError("Единица измерения выбранной партии закупки не соответствует списанию")

    preparation_query = session.query(func.coalesce(func.sum(PreparationIngredientUse.quantity), 0)).filter(
        PreparationIngredientUse.purchase_item_id == line.purchase_item_id
    )
    if exclude_preparation_id is not None:
        preparation_query = preparation_query.filter(PreparationIngredientUse.preparation_id != exclude_preparation_id)

    used_in_preparations = Decimal(str(preparation_query.scalar()))
    used_in_production = Decimal(
        str(
            session.query(func.coalesce(func.sum(BatchIngredientUse.quantity), 0))
            .filter(BatchIngredientUse.purchase_item_id == line.purchase_item_id)
            .scalar()
        )
    )
    available_quantity = purchase_item.quantity - used_in_preparations - used_in_production
    if available_quantity < quantity:
        raise ValueError("Недостаточно остатка в выбранной партии закупки")

    return purchase_item.unit_price


def _calculate_preparation_values(
    session: Session,
    *,
    ingredient_uses: Iterable[PreparationIngredientInput],
    labor_cost: Decimal | int | float | str,
    other_direct_cost: Decimal | int | float | str,
    output_quantity: Decimal | int | float | str,
    exclude_preparation_id: int | None = None,
) -> tuple[list[PreparationIngredientInput], list[Decimal], list[Decimal], list[Decimal], list[Decimal], Decimal, Decimal]:
    output_quantity_decimal = to_decimal(output_quantity)
    if output_quantity_decimal <= 0:
        raise ValueError("Preparation output quantity must be greater than zero")

    ingredient_inputs = list(ingredient_uses)
    if not ingredient_inputs:
        raise ValueError("Preparation must contain at least one ingredient use")

    ingredient_unit_costs = []
    ingredient_quantities = []
    ingredient_waste_quantities = []
    reserved_purchase_quantities: dict[int, Decimal] = {}
    for line in ingredient_inputs:
        quantity_decimal = to_decimal(line.quantity)
        waste_quantity_decimal = to_decimal(line.waste_quantity)
        if waste_quantity_decimal < 0:
            raise ValueError("Ingredient waste quantity cannot be negative")
        if waste_quantity_decimal > quantity_decimal:
            raise ValueError("Ingredient waste quantity cannot exceed ingredient use quantity")
        ingredient_quantities.append(quantity_decimal)
        ingredient_waste_quantities.append(waste_quantity_decimal)

        if line.purchase_item_id is None:
            ingredient_unit_costs.append(to_decimal(line.unit_cost))
            continue

        reserved_purchase_quantities[line.purchase_item_id] = reserved_purchase_quantities.get(
            line.purchase_item_id,
            Decimal("0"),
        ) + quantity_decimal
        ingredient_unit_costs.append(
            _get_purchase_unit_cost_for_preparation_line(
                session,
                line=line,
                quantity=reserved_purchase_quantities[line.purchase_item_id],
                exclude_preparation_id=exclude_preparation_id,
            )
        )

    ingredient_total_costs = [
        calculate_ingredient_use_total(quantity=quantity, unit_cost=unit_cost)
        for quantity, unit_cost in zip(ingredient_quantities, ingredient_unit_costs, strict=True)
    ]
    total_cost = calculate_preparation_cost(
        ingredient_costs=ingredient_total_costs,
        labor_costs=[labor_cost],
        other_direct_costs=[other_direct_cost],
    )
    unit_cost = calculate_unit_cost(total_cost=total_cost, actual_output=output_quantity_decimal)

    return (
        ingredient_inputs,
        ingredient_quantities,
        ingredient_waste_quantities,
        ingredient_unit_costs,
        ingredient_total_costs,
        total_cost,
        unit_cost,
    )


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
    (
        ingredient_inputs,
        ingredient_quantities,
        ingredient_waste_quantities,
        ingredient_unit_costs,
        ingredient_total_costs,
        total_cost,
        unit_cost,
    ) = _calculate_preparation_values(
        session,
        ingredient_uses=ingredient_uses,
        labor_cost=labor_cost,
        other_direct_cost=other_direct_cost,
        output_quantity=output_quantity,
    )

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

    for line, quantity, waste_quantity, unit_cost, line_total in zip(
        ingredient_inputs,
        ingredient_quantities,
        ingredient_waste_quantities,
        ingredient_unit_costs,
        ingredient_total_costs,
        strict=True,
    ):
        preparation.ingredient_uses.append(
            PreparationIngredientUse(
                ingredient=line.ingredient,
                unit=line.unit,
                purchase_item_id=line.purchase_item_id,
                quantity=quantity,
                waste_quantity=waste_quantity,
                unit_cost=unit_cost,
                total_cost=line_total,
                comment=line.comment,
            )
        )

    session.add(preparation)
    session.flush()
    return preparation


def update_preparation(
    session: Session,
    preparation_id: int,
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
    """Update an unused preparation and recalculate costs."""

    preparation = session.get(Preparation, preparation_id)
    if preparation is None:
        raise ValueError("Заготовка не найдена")
    if is_preparation_used(session, preparation_id):
        raise ValueError("Заготовка уже использована в производстве и не может быть изменена")

    output_quantity_decimal = to_decimal(output_quantity)
    waste_quantity_decimal = to_decimal(waste_quantity)
    (
        ingredient_inputs,
        ingredient_quantities,
        ingredient_waste_quantities,
        ingredient_unit_costs,
        ingredient_total_costs,
        total_cost,
        unit_cost,
    ) = _calculate_preparation_values(
        session,
        ingredient_uses=ingredient_uses,
        labor_cost=labor_cost,
        other_direct_cost=other_direct_cost,
        output_quantity=output_quantity,
        exclude_preparation_id=preparation_id,
    )

    preparation.prepared_on = prepared_on
    preparation.preparation_type = preparation_type
    preparation.name = preparation_type.name
    preparation.output_quantity = output_quantity_decimal
    preparation.waste_quantity = waste_quantity_decimal
    preparation.output_unit = output_unit
    preparation.labor_cost = to_decimal(labor_cost)
    preparation.other_direct_cost = to_decimal(other_direct_cost)
    preparation.total_cost = total_cost
    preparation.unit_cost = unit_cost
    preparation.comment = comment
    preparation.ingredient_uses.clear()

    for line, quantity, waste_quantity, unit_cost, line_total in zip(
        ingredient_inputs,
        ingredient_quantities,
        ingredient_waste_quantities,
        ingredient_unit_costs,
        ingredient_total_costs,
        strict=True,
    ):
        preparation.ingredient_uses.append(
            PreparationIngredientUse(
                ingredient=line.ingredient,
                unit=line.unit,
                purchase_item_id=line.purchase_item_id,
                quantity=quantity,
                waste_quantity=waste_quantity,
                unit_cost=unit_cost,
                total_cost=line_total,
                comment=line.comment,
            )
        )

    session.flush()
    return preparation


def delete_preparation(session: Session, preparation_id: int) -> None:
    """Delete an unused preparation and its ingredient consumption lines."""

    preparation = session.get(Preparation, preparation_id)
    if preparation is None:
        raise ValueError("Заготовка не найдена")
    if is_preparation_used(session, preparation_id):
        raise ValueError("Заготовка уже использована в производстве и не может быть удалена")

    session.delete(preparation)
    session.flush()


def list_preparations(session: Session) -> list[Preparation]:
    """Return preparations ordered from newest to oldest."""

    return list(session.scalars(select(Preparation).order_by(Preparation.prepared_on.desc(), Preparation.id.desc())))
