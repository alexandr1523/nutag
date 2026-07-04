"""Economic reports based on traceable production and packing batches."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from nutag.db.models import FinishedProductPacking


@dataclass(frozen=True)
class FinishedProductCostReport:
    """Direct cost breakdown for a packaged finished product batch."""

    packing_id: int
    output_id: int
    product_name: str
    produced_on: date
    packed_on: date
    package_count: int
    package_size: Decimal
    unit_short_name: str
    total_quantity: Decimal
    ingredient_cost: Decimal
    preparation_cost: Decimal
    labor_cost: Decimal
    unpacked_output_cost: Decimal
    packaging_cost: Decimal
    total_direct_cost: Decimal
    cost_per_package: Decimal
    cost_per_base_unit: Decimal
    excluded_depreciation: Decimal
    excluded_overhead: Decimal
    excluded_components: tuple[str, ...]


def _allocated(value: Decimal, ratio: Decimal) -> Decimal:
    return Decimal(str(value)) * ratio


def list_finished_product_cost_reports(session: Session) -> list[FinishedProductCostReport]:
    """Return direct cost breakdown for valid packaged finished product batches."""

    packings = (
        session.query(FinishedProductPacking)
        .order_by(FinishedProductPacking.packed_on.desc(), FinishedProductPacking.id.desc())
        .all()
    )
    reports: list[FinishedProductCostReport] = []

    for packing in packings:
        output = packing.finished_output
        if (
            output is None
            or output.batch is None
            or output.batch.product is None
            or output.package_unit is None
            or output.total_quantity <= 0
            or output.package_count <= 0
            or output.batch.actual_output_quantity <= 0
        ):
            continue

        batch = output.batch
        ratio = Decimal(str(output.total_quantity)) / Decimal(str(batch.actual_output_quantity))
        ingredient_cost = sum((_allocated(use.total_cost, ratio) for use in batch.ingredient_uses), Decimal("0"))
        preparation_cost = sum((_allocated(use.total_cost, ratio) for use in batch.preparation_uses), Decimal("0"))
        labor_cost = _allocated(batch.labor_cost, ratio)
        unpacked_output_cost = ingredient_cost + preparation_cost + labor_cost
        packaging_cost = Decimal(str(packing.packaging_total_cost))
        total_direct_cost = unpacked_output_cost + packaging_cost
        excluded_depreciation = _allocated(batch.equipment_depreciation, ratio)
        excluded_overhead = _allocated(batch.allocated_overhead, ratio)
        excluded_components = ("Амортизация", "Расходные материалы", "Постоянные расходы")

        reports.append(
            FinishedProductCostReport(
                packing_id=packing.id,
                output_id=output.id,
                product_name=batch.product.name,
                produced_on=batch.produced_on,
                packed_on=packing.packed_on,
                package_count=output.package_count,
                package_size=output.package_size,
                unit_short_name=output.package_unit.short_name,
                total_quantity=output.total_quantity,
                ingredient_cost=ingredient_cost,
                preparation_cost=preparation_cost,
                labor_cost=labor_cost,
                unpacked_output_cost=unpacked_output_cost,
                packaging_cost=packaging_cost,
                total_direct_cost=total_direct_cost,
                cost_per_package=total_direct_cost / Decimal(output.package_count),
                cost_per_base_unit=total_direct_cost / Decimal(str(output.total_quantity)),
                excluded_depreciation=excluded_depreciation,
                excluded_overhead=excluded_overhead,
                excluded_components=excluded_components,
            )
        )

    return reports
