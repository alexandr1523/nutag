"""Service functions for final production batches."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nutag.db.models import (
    BatchIngredientUse,
    BatchPreparationUse,
    FinishedProductBulkOutput,
    Ingredient,
    Preparation,
    PreparationIngredientUse,
    Product,
    ProductionBatch,
    PurchaseItem,
    PurchaseItemType,
    Unit,
)
from nutag.services.calculations import calculate_batch_cost, calculate_unit_cost, to_decimal
from nutag.services.inventory import get_available_preparation_batch, get_available_purchase_batch
from nutag.services.preparations import calculate_ingredient_use_total


@dataclass(frozen=True)
class BatchIngredientInput:
    """Ingredient consumed directly by a production batch."""

    ingredient: Ingredient
    unit: Unit
    quantity: Decimal | int | float | str
    unit_cost: Decimal | int | float | str
    purchase_item_id: int | None = None
    comment: str | None = None


@dataclass(frozen=True)
class BatchPreparationInput:
    """Internal preparation consumed by a production batch."""

    preparation: Preparation
    unit: Unit
    quantity: Decimal | int | float | str
    unit_cost: Decimal | int | float | str
    source_preparation_id: int | None = None
    comment: str | None = None


def calculate_output_total(
    *,
    package_size: Decimal | int | float | str,
    package_count: int,
) -> Decimal:
    """Calculate total finished quantity for one packaged output line."""

    package_size_decimal = to_decimal(package_size)
    if package_size_decimal <= 0:
        raise ValueError("Package size must be greater than zero")
    if package_count <= 0:
        raise ValueError("Package count must be greater than zero")

    return package_size_decimal * Decimal(package_count)


def is_production_batch_used(session: Session, production_batch_id: int) -> bool:
    """Return whether a production batch has downstream finished product movements."""

    batch = session.get(ProductionBatch, production_batch_id)
    if batch is None:
        return False
    if batch.outputs:
        return True
    return any(bulk_output.packings for bulk_output in batch.bulk_outputs)


def _get_purchase_unit_cost_for_production_line(
    session: Session,
    *,
    line: BatchIngredientInput,
    quantity: Decimal,
    exclude_production_batch_id: int | None,
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

    used_in_preparations = Decimal(
        str(
            session.query(func.coalesce(func.sum(PreparationIngredientUse.quantity), 0))
            .filter(PreparationIngredientUse.purchase_item_id == line.purchase_item_id)
            .scalar()
        )
    )
    production_query = session.query(func.coalesce(func.sum(BatchIngredientUse.quantity), 0)).filter(
        BatchIngredientUse.purchase_item_id == line.purchase_item_id
    )
    if exclude_production_batch_id is not None:
        production_query = production_query.filter(BatchIngredientUse.batch_id != exclude_production_batch_id)
    used_in_production = Decimal(str(production_query.scalar()))

    available_quantity = purchase_item.quantity - used_in_preparations - used_in_production
    if available_quantity < quantity:
        raise ValueError("Недостаточно остатка в выбранной партии закупки")

    return purchase_item.unit_price


def _get_preparation_unit_cost_for_production_line(
    session: Session,
    *,
    line: BatchPreparationInput,
    quantity: Decimal,
    exclude_production_batch_id: int | None,
) -> Decimal:
    source_preparation = session.get(Preparation, line.source_preparation_id)
    if source_preparation is None:
        raise ValueError("Выбранная заготовка не найдена")
    if source_preparation.name != line.preparation.name:
        raise ValueError("Выбранная заготовка не соответствует списываемой позиции")
    if source_preparation.output_unit.short_name != line.unit.short_name:
        raise ValueError("Единица измерения выбранной заготовки не соответствует списанию")

    production_query = session.query(func.coalesce(func.sum(BatchPreparationUse.quantity), 0)).filter(
        BatchPreparationUse.source_preparation_id == line.source_preparation_id
    )
    if exclude_production_batch_id is not None:
        production_query = production_query.filter(BatchPreparationUse.batch_id != exclude_production_batch_id)
    used_in_production = Decimal(str(production_query.scalar()))

    available_quantity = source_preparation.output_quantity - used_in_production
    if available_quantity < quantity:
        raise ValueError("Недостаточно остатка в выбранной заготовке")

    return source_preparation.unit_cost


def _calculate_production_values(
    session: Session,
    *,
    actual_output_quantity: Decimal | int | float | str,
    ingredient_uses: Iterable[BatchIngredientInput],
    preparation_uses: Iterable[BatchPreparationInput],
    labor_cost: Decimal | int | float | str,
    equipment_depreciation: Decimal | int | float | str,
    allocated_overhead: Decimal | int | float | str,
    exclude_production_batch_id: int | None = None,
) -> tuple[
    Decimal,
    list[BatchIngredientInput],
    list[BatchPreparationInput],
    list[Decimal],
    list[Decimal],
    list[Decimal],
    list[Decimal],
    Decimal,
    Decimal,
]:
    actual_output_decimal = to_decimal(actual_output_quantity)
    if actual_output_decimal <= 0:
        raise ValueError("Production batch actual output must be greater than zero")
    labor_cost_decimal = to_decimal(labor_cost)
    if labor_cost_decimal <= 0:
        raise ValueError("Production batch labor cost must be greater than zero")

    ingredient_inputs = list(ingredient_uses)
    preparation_inputs = list(preparation_uses)

    ingredient_unit_costs = []
    ingredient_quantities = []
    reserved_purchase_quantities: dict[int, Decimal] = {}
    for line in ingredient_inputs:
        quantity_decimal = to_decimal(line.quantity)
        ingredient_quantities.append(quantity_decimal)
        if line.purchase_item_id is None:
            ingredient_unit_costs.append(to_decimal(line.unit_cost))
            continue

        reserved_purchase_quantities[line.purchase_item_id] = reserved_purchase_quantities.get(
            line.purchase_item_id,
            Decimal("0"),
        ) + quantity_decimal
        if exclude_production_batch_id is None:
            batch = get_available_purchase_batch(
                session,
                purchase_item_id=line.purchase_item_id,
                expected_item_type=PurchaseItemType.INGREDIENT,
                expected_item_id=line.ingredient.id,
                expected_unit_short_name=line.unit.short_name,
                quantity=reserved_purchase_quantities[line.purchase_item_id],
            )
            ingredient_unit_costs.append(batch.unit_price)
        else:
            ingredient_unit_costs.append(
                _get_purchase_unit_cost_for_production_line(
                    session,
                    line=line,
                    quantity=reserved_purchase_quantities[line.purchase_item_id],
                    exclude_production_batch_id=exclude_production_batch_id,
                )
            )

    preparation_unit_costs = []
    preparation_quantities = []
    reserved_preparation_quantities: dict[int, Decimal] = {}
    for line in preparation_inputs:
        quantity_decimal = to_decimal(line.quantity)
        preparation_quantities.append(quantity_decimal)
        if line.source_preparation_id is None:
            preparation_unit_costs.append(to_decimal(line.unit_cost))
            continue

        reserved_preparation_quantities[line.source_preparation_id] = reserved_preparation_quantities.get(
            line.source_preparation_id,
            Decimal("0"),
        ) + quantity_decimal
        if exclude_production_batch_id is None:
            batch = get_available_preparation_batch(
                session,
                source_preparation_id=line.source_preparation_id,
                expected_preparation_name=line.preparation.name,
                expected_unit_short_name=line.unit.short_name,
                quantity=reserved_preparation_quantities[line.source_preparation_id],
            )
            preparation_unit_costs.append(batch.unit_price)
        else:
            preparation_unit_costs.append(
                _get_preparation_unit_cost_for_production_line(
                    session,
                    line=line,
                    quantity=reserved_preparation_quantities[line.source_preparation_id],
                    exclude_production_batch_id=exclude_production_batch_id,
                )
            )

    ingredient_total_costs = [
        calculate_ingredient_use_total(quantity=quantity, unit_cost=unit_cost)
        for quantity, unit_cost in zip(ingredient_quantities, ingredient_unit_costs, strict=True)
    ]
    preparation_total_costs = [
        calculate_ingredient_use_total(quantity=quantity, unit_cost=unit_cost)
        for quantity, unit_cost in zip(preparation_quantities, preparation_unit_costs, strict=True)
    ]
    total_cost = calculate_batch_cost(
        raw_material_costs=ingredient_total_costs,
        preparation_costs=preparation_total_costs,
        labor_costs=[labor_cost_decimal],
        equipment_depreciation=equipment_depreciation,
        allocated_overhead=allocated_overhead,
    )
    unit_cost = calculate_unit_cost(total_cost=total_cost, actual_output=actual_output_decimal)

    return (
        actual_output_decimal,
        ingredient_inputs,
        preparation_inputs,
        ingredient_unit_costs,
        preparation_unit_costs,
        ingredient_total_costs,
        preparation_total_costs,
        total_cost,
        unit_cost,
    )


def create_production_batch(
    session: Session,
    *,
    produced_on: date,
    product: Product,
    actual_output_quantity: Decimal | int | float | str,
    output_unit: Unit,
    ingredient_uses: Iterable[BatchIngredientInput] = (),
    preparation_uses: Iterable[BatchPreparationInput] = (),
    planned_quantity: Decimal | int | float | str | None = None,
    labor_cost: Decimal | int | float | str = 0,
    equipment_depreciation: Decimal | int | float | str = 0,
    allocated_overhead: Decimal | int | float | str = 0,
    status: str = "completed",
    comment: str | None = None,
) -> ProductionBatch:
    """Create a production batch that creates unpacked finished product stock."""

    (
        actual_output_decimal,
        ingredient_inputs,
        preparation_inputs,
        ingredient_unit_costs,
        preparation_unit_costs,
        ingredient_total_costs,
        preparation_total_costs,
        total_cost,
        unit_cost,
    ) = _calculate_production_values(
        session,
        actual_output_quantity=actual_output_quantity,
        ingredient_uses=ingredient_uses,
        preparation_uses=preparation_uses,
        labor_cost=labor_cost,
        equipment_depreciation=equipment_depreciation,
        allocated_overhead=allocated_overhead,
    )

    batch = ProductionBatch(
        produced_on=produced_on,
        product=product,
        planned_quantity=to_decimal(planned_quantity) if planned_quantity is not None else None,
        actual_output_quantity=actual_output_decimal,
        output_unit=output_unit,
        labor_cost=to_decimal(labor_cost),
        equipment_depreciation=to_decimal(equipment_depreciation),
        allocated_overhead=to_decimal(allocated_overhead),
        total_cost=total_cost,
        unit_cost=unit_cost,
        status=status,
        comment=comment,
    )

    for line, unit_cost, line_total in zip(ingredient_inputs, ingredient_unit_costs, ingredient_total_costs, strict=True):
        batch.ingredient_uses.append(
            BatchIngredientUse(
                ingredient=line.ingredient,
                purchase_item_id=line.purchase_item_id,
                unit=line.unit,
                quantity=to_decimal(line.quantity),
                unit_cost=unit_cost,
                total_cost=line_total,
                comment=line.comment,
            )
        )

    for line, unit_cost, line_total in zip(
        preparation_inputs,
        preparation_unit_costs,
        preparation_total_costs,
        strict=True,
    ):
        batch.preparation_uses.append(
            BatchPreparationUse(
                preparation=line.preparation,
                source_preparation_id=line.source_preparation_id,
                unit=line.unit,
                quantity=to_decimal(line.quantity),
                unit_cost=unit_cost,
                total_cost=line_total,
                comment=line.comment,
            )
        )
        
    batch.bulk_outputs.append(
        FinishedProductBulkOutput(
            quantity=actual_output_decimal,
            unit=output_unit,
        )
    )

    session.add(batch)
    session.flush()
    return batch


def update_production_batch(
    session: Session,
    production_batch_id: int,
    *,
    produced_on: date,
    product: Product,
    actual_output_quantity: Decimal | int | float | str,
    output_unit: Unit,
    ingredient_uses: Iterable[BatchIngredientInput] = (),
    preparation_uses: Iterable[BatchPreparationInput] = (),
    planned_quantity: Decimal | int | float | str | None = None,
    labor_cost: Decimal | int | float | str = 0,
    equipment_depreciation: Decimal | int | float | str = 0,
    allocated_overhead: Decimal | int | float | str = 0,
    status: str = "completed",
    comment: str | None = None,
) -> ProductionBatch:
    """Update an unused production batch and recalculate costs and bulk output."""

    batch = session.get(ProductionBatch, production_batch_id)
    if batch is None:
        raise ValueError("Производственная партия не найдена")
    if is_production_batch_used(session, production_batch_id):
        raise ValueError("Производственная партия уже использована в фасовке и не может быть изменена")

    (
        actual_output_decimal,
        ingredient_inputs,
        preparation_inputs,
        ingredient_unit_costs,
        preparation_unit_costs,
        ingredient_total_costs,
        preparation_total_costs,
        total_cost,
        unit_cost,
    ) = _calculate_production_values(
        session,
        actual_output_quantity=actual_output_quantity,
        ingredient_uses=ingredient_uses,
        preparation_uses=preparation_uses,
        labor_cost=labor_cost,
        equipment_depreciation=equipment_depreciation,
        allocated_overhead=allocated_overhead,
        exclude_production_batch_id=production_batch_id,
    )

    batch.produced_on = produced_on
    batch.product = product
    batch.planned_quantity = to_decimal(planned_quantity) if planned_quantity is not None else None
    batch.actual_output_quantity = actual_output_decimal
    batch.output_unit = output_unit
    batch.labor_cost = to_decimal(labor_cost)
    batch.equipment_depreciation = to_decimal(equipment_depreciation)
    batch.allocated_overhead = to_decimal(allocated_overhead)
    batch.total_cost = total_cost
    batch.unit_cost = unit_cost
    batch.status = status
    batch.comment = comment
    batch.ingredient_uses.clear()
    batch.preparation_uses.clear()

    for line, unit_cost, line_total in zip(ingredient_inputs, ingredient_unit_costs, ingredient_total_costs, strict=True):
        batch.ingredient_uses.append(
            BatchIngredientUse(
                ingredient=line.ingredient,
                purchase_item_id=line.purchase_item_id,
                unit=line.unit,
                quantity=to_decimal(line.quantity),
                unit_cost=unit_cost,
                total_cost=line_total,
                comment=line.comment,
            )
        )

    for line, unit_cost, line_total in zip(
        preparation_inputs,
        preparation_unit_costs,
        preparation_total_costs,
        strict=True,
    ):
        batch.preparation_uses.append(
            BatchPreparationUse(
                preparation=line.preparation,
                source_preparation_id=line.source_preparation_id,
                unit=line.unit,
                quantity=to_decimal(line.quantity),
                unit_cost=unit_cost,
                total_cost=line_total,
                comment=line.comment,
            )
        )

    if len(batch.bulk_outputs) > 1:
        raise ValueError("Корректировка партий с несколькими нефасованными выпусками пока не поддерживается")
    if batch.bulk_outputs:
        bulk_output = batch.bulk_outputs[0]
        bulk_output.quantity = actual_output_decimal
        bulk_output.unit = output_unit
    else:
        batch.bulk_outputs.append(
            FinishedProductBulkOutput(
                quantity=actual_output_decimal,
                unit=output_unit,
            )
        )

    session.flush()
    return batch


def delete_production_batch(session: Session, production_batch_id: int) -> None:
    """Delete an unused production batch and its stock movements."""

    batch = session.get(ProductionBatch, production_batch_id)
    if batch is None:
        raise ValueError("Производственная партия не найдена")
    if is_production_batch_used(session, production_batch_id):
        raise ValueError("Производственная партия уже использована в фасовке и не может быть удалена")

    session.delete(batch)
    session.flush()


def list_production_batches(session: Session) -> list[ProductionBatch]:
    """Return production batches ordered from newest to oldest."""

    return list(session.scalars(select(ProductionBatch).order_by(ProductionBatch.produced_on.desc(), ProductionBatch.id.desc())))
