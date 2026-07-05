"""Economic reports based on traceable production and packing batches."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from nutag.db.models import FinishedProductPacking, Order


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


@dataclass(frozen=True)
class OrderMarginLineReport:
    """Direct margin for one order line based on the selected finished product batch."""

    order_id: int
    order_date: date
    customer_name: str
    product_name: str
    output_id: int | None
    batch_id: int | None
    package_count: int
    package_size: Decimal
    unit_short_name: str
    sale_price_per_package: Decimal
    revenue: Decimal
    direct_cost_per_package: Decimal
    direct_cost: Decimal
    margin_per_package: Decimal
    margin: Decimal
    margin_percent: Decimal | None
    cost_source: str


@dataclass(frozen=True)
class OrderMarginReport:
    """Direct margin summary for a customer order."""

    order_id: int
    order_date: date
    customer_name: str
    order_status: str
    payment_status: str
    reservation_status: str
    revenue: Decimal
    direct_cost: Decimal
    delivery_cost: Decimal
    gross_margin: Decimal
    gross_margin_percent: Decimal | None
    lines: tuple[OrderMarginLineReport, ...]
    excluded_components: tuple[str, ...]


def _allocated(value: Decimal, ratio: Decimal) -> Decimal:
    return Decimal(str(value)) * ratio


def _percent(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    if denominator == 0:
        return None
    return numerator / denominator * Decimal("100")


def _status_value(value: object) -> str:
    return value.value if hasattr(value, "value") else str(value)


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


def list_order_margin_reports(session: Session) -> list[OrderMarginReport]:
    """Return order margin reports using only the selected finished product batches."""

    orders = session.query(Order).order_by(Order.order_date.desc(), Order.id.desc()).all()
    reports: list[OrderMarginReport] = []
    excluded_components = ("Амортизация", "Расходные материалы", "Постоянные расходы")

    for order in orders:
        line_reports: list[OrderMarginLineReport] = []

        for item in order.items:
            output = item.batch_output
            if output is None or output.package_unit is None or item.product is None:
                continue

            package_count = int(item.package_count)
            revenue = Decimal(str(item.total_price))
            sale_price_per_package = Decimal(str(item.unit_price))

            if output.packing_operation is not None and output.package_count > 0:
                direct_cost_per_package = Decimal(str(output.packing_operation.total_cost)) / Decimal(
                    output.package_count
                )
                cost_source = "Фасованная партия ГП"
            elif output.batch is not None:
                direct_cost_per_package = Decimal(str(output.batch.unit_cost)) * Decimal(str(item.package_size))
                cost_source = "Производственная партия ГП без отдельной фасовки"
            else:
                continue

            direct_cost = direct_cost_per_package * Decimal(package_count)
            margin_per_package = sale_price_per_package - direct_cost_per_package
            margin = revenue - direct_cost

            line_reports.append(
                OrderMarginLineReport(
                    order_id=order.id,
                    order_date=order.order_date,
                    customer_name=order.customer_name,
                    product_name=item.product.name,
                    output_id=output.id,
                    batch_id=output.batch_id,
                    package_count=package_count,
                    package_size=item.package_size,
                    unit_short_name=output.package_unit.short_name,
                    sale_price_per_package=sale_price_per_package,
                    revenue=revenue,
                    direct_cost_per_package=direct_cost_per_package,
                    direct_cost=direct_cost,
                    margin_per_package=margin_per_package,
                    margin=margin,
                    margin_percent=_percent(margin, revenue),
                    cost_source=cost_source,
                )
            )

        revenue = Decimal(str(order.total_amount))
        direct_cost = sum((line.direct_cost for line in line_reports), Decimal("0"))
        delivery_cost = Decimal(str(order.delivery_cost))
        gross_margin = revenue - direct_cost - delivery_cost

        reports.append(
            OrderMarginReport(
                order_id=order.id,
                order_date=order.order_date,
                customer_name=order.customer_name,
                order_status=_status_value(order.order_status),
                payment_status=_status_value(order.payment_status),
                reservation_status=_status_value(order.reservation_status),
                revenue=revenue,
                direct_cost=direct_cost,
                delivery_cost=delivery_cost,
                gross_margin=gross_margin,
                gross_margin_percent=_percent(gross_margin, revenue),
                lines=tuple(line_reports),
                excluded_components=excluded_components,
            )
        )

    return reports
