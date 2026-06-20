"""Service functions for final production batches."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from nutag.db.models import (
    BatchIngredientUse,
    BatchPreparationUse,
    BatchPackagingUse,
    FinishedProductOutput,
    Ingredient,
    Packaging,
    Preparation,
    Product,
    ProductionBatch,
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


@dataclass(frozen=True)
class BatchPackagingInput:
    """Packaging consumed by a production batch."""

    packaging: Packaging
    unit: Unit
    quantity: Decimal | int | float | str
    unit_cost: Decimal | int | float | str
    purchase_item_id: int | None = None
    comment: str | None = None


@dataclass(frozen=True)
class FinishedProductOutputInput:
    """Packaged finished product output from a batch."""

    package_size: Decimal | int | float | str
    package_unit: Unit
    package_count: int
    frozen_on: date | None = None
    use_by: date | None = None
    storage_place: str | None = None
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


def create_production_batch(
    session: Session,
    *,
    produced_on: date,
    product: Product,
    actual_output_quantity: Decimal | int | float | str,
    output_unit: Unit,
    outputs: Iterable[FinishedProductOutputInput],
    ingredient_uses: Iterable[BatchIngredientInput] = (),
    preparation_uses: Iterable[BatchPreparationInput] = (),
    packaging_uses: Iterable[BatchPackagingInput] = (),
    planned_quantity: Decimal | int | float | str | None = None,
    labor_cost: Decimal | int | float | str = 0,
    equipment_depreciation: Decimal | int | float | str = 0,
    allocated_overhead: Decimal | int | float | str = 0,
    status: str = "completed",
    comment: str | None = None,
) -> ProductionBatch:
    """Create a production batch with cost and packaged output lines."""

    actual_output_decimal = to_decimal(actual_output_quantity)
    if actual_output_decimal <= 0:
        raise ValueError("Production batch actual output must be greater than zero")

    output_inputs = list(outputs)
    if not output_inputs:
        raise ValueError("Production batch must contain at least one finished output line")

    ingredient_inputs = list(ingredient_uses)
    preparation_inputs = list(preparation_uses)
    packaging_inputs = list(packaging_uses)

    ingredient_unit_costs = []
    reserved_purchase_quantities: dict[int, Decimal] = {}
    for line in ingredient_inputs:
        if line.purchase_item_id is None:
            ingredient_unit_costs.append(to_decimal(line.unit_cost))
            continue

        reserved_purchase_quantities[line.purchase_item_id] = reserved_purchase_quantities.get(
            line.purchase_item_id,
            Decimal("0"),
        ) + to_decimal(line.quantity)
        batch = get_available_purchase_batch(
            session,
            purchase_item_id=line.purchase_item_id,
            expected_item_type=PurchaseItemType.INGREDIENT,
            expected_item_id=line.ingredient.id,
            expected_unit_short_name=line.unit.short_name,
            quantity=reserved_purchase_quantities[line.purchase_item_id],
        )
        ingredient_unit_costs.append(batch.unit_price)

    preparation_unit_costs = []
    reserved_preparation_quantities: dict[int, Decimal] = {}
    for line in preparation_inputs:
        if line.source_preparation_id is None:
            preparation_unit_costs.append(to_decimal(line.unit_cost))
            continue

        reserved_preparation_quantities[line.source_preparation_id] = reserved_preparation_quantities.get(
            line.source_preparation_id,
            Decimal("0"),
        ) + to_decimal(line.quantity)
        batch = get_available_preparation_batch(
            session,
            source_preparation_id=line.source_preparation_id,
            expected_preparation_name=line.preparation.name,
            expected_unit_short_name=line.unit.short_name,
            quantity=reserved_preparation_quantities[line.source_preparation_id],
        )
        preparation_unit_costs.append(batch.unit_price)

    packaging_unit_costs = []
    for line in packaging_inputs:
        if line.purchase_item_id is None:
            packaging_unit_costs.append(to_decimal(line.unit_cost))
            continue

        reserved_purchase_quantities[line.purchase_item_id] = reserved_purchase_quantities.get(
            line.purchase_item_id,
            Decimal("0"),
        ) + to_decimal(line.quantity)
        batch = get_available_purchase_batch(
            session,
            purchase_item_id=line.purchase_item_id,
            expected_item_type=PurchaseItemType.PACKAGING,
            expected_item_id=line.packaging.id,
            expected_unit_short_name=line.unit.short_name,
            quantity=reserved_purchase_quantities[line.purchase_item_id],
        )
        packaging_unit_costs.append(batch.unit_price)

    ingredient_total_costs = [
        calculate_ingredient_use_total(quantity=line.quantity, unit_cost=unit_cost)
        for line, unit_cost in zip(ingredient_inputs, ingredient_unit_costs, strict=True)
    ]
    preparation_total_costs = [
        calculate_ingredient_use_total(quantity=line.quantity, unit_cost=unit_cost)
        for line, unit_cost in zip(preparation_inputs, preparation_unit_costs, strict=True)
    ]
    packaging_total_costs = [
        calculate_ingredient_use_total(quantity=line.quantity, unit_cost=unit_cost)
        for line, unit_cost in zip(packaging_inputs, packaging_unit_costs, strict=True)
    ]
    
    total_cost = calculate_batch_cost(
        raw_material_costs=ingredient_total_costs,
        preparation_costs=preparation_total_costs,
        labor_costs=[labor_cost],
        equipment_depreciation=equipment_depreciation,
        allocated_overhead=allocated_overhead,
    )
    # Add packaging costs to total cost if needed, or if they are in raw_material_costs
    total_cost += sum(packaging_total_costs, Decimal("0"))
    
    unit_cost = calculate_unit_cost(total_cost=total_cost, actual_output=actual_output_decimal)

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
        
    for line, unit_cost, line_total in zip(packaging_inputs, packaging_unit_costs, packaging_total_costs, strict=True):
        batch.packaging_uses.append(
            BatchPackagingUse(
                packaging=line.packaging,
                purchase_item_id=line.purchase_item_id,
                unit=line.unit,
                quantity=to_decimal(line.quantity),
                unit_cost=unit_cost,
                total_cost=line_total,
                comment=line.comment,
            )
        )

    for output in output_inputs:
        total_quantity = calculate_output_total(
            package_size=output.package_size,
            package_count=output.package_count,
        )
        batch.outputs.append(
            FinishedProductOutput(
                package_size=to_decimal(output.package_size),
                package_unit=output.package_unit,
                package_count=output.package_count,
                total_quantity=total_quantity,
                frozen_on=output.frozen_on,
                use_by=output.use_by,
                storage_place=output.storage_place,
                comment=output.comment,
            )
        )

    session.add(batch)
    session.flush()
    return batch


def list_production_batches(session: Session) -> list[ProductionBatch]:
    """Return production batches ordered from newest to oldest."""

    return list(session.scalars(select(ProductionBatch).order_by(ProductionBatch.produced_on.desc(), ProductionBatch.id.desc())))
