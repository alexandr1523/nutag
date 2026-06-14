"""Pure calculation helpers for the Nutag accounting MVP.

The functions in this module intentionally do not depend on Streamlit or the
future database layer. Keeping them pure makes the money and inventory logic
straightforward to test before UI and persistence code are added.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

NumberLike = Decimal | int | float | str


@dataclass(frozen=True)
class CostLine:
    """A direct cost component used in preparation or batch costing."""

    amount: Decimal


@dataclass(frozen=True)
class OrderMargin:
    """Calculated order economics."""

    revenue: Decimal
    cost_of_goods_sold: Decimal
    delivery_or_handover_cost: Decimal
    margin: Decimal


def to_decimal(value: NumberLike) -> Decimal:
    """Convert supported numeric input to ``Decimal`` without float artifacts."""

    return Decimal(str(value))


def sum_money(values: Iterable[NumberLike]) -> Decimal:
    """Sum monetary values as ``Decimal``."""

    return sum((to_decimal(value) for value in values), Decimal("0"))


def calculate_weighted_average_price(
    *,
    opening_quantity: NumberLike,
    opening_value: NumberLike,
    purchased_quantity: NumberLike,
    purchased_value: NumberLike,
) -> Decimal:
    """Calculate weighted-average unit price for inventory valuation.

    The formula follows the functional specification:

    ``(opening value + purchased value) / (opening quantity + purchased quantity)``.

    Raises:
        ValueError: if the resulting quantity is zero or negative.
    """

    total_quantity = to_decimal(opening_quantity) + to_decimal(purchased_quantity)
    if total_quantity <= 0:
        raise ValueError("Total quantity must be greater than zero")

    total_value = to_decimal(opening_value) + to_decimal(purchased_value)
    return total_value / total_quantity


def calculate_preparation_cost(
    *,
    ingredient_costs: Iterable[NumberLike] = (),
    material_costs: Iterable[NumberLike] = (),
    labor_costs: Iterable[NumberLike] = (),
    other_direct_costs: Iterable[NumberLike] = (),
) -> Decimal:
    """Calculate total cost of an internal preparation/semi-finished product."""

    return (
        sum_money(ingredient_costs)
        + sum_money(material_costs)
        + sum_money(labor_costs)
        + sum_money(other_direct_costs)
    )


def calculate_unit_cost(*, total_cost: NumberLike, actual_output: NumberLike) -> Decimal:
    """Calculate unit cost using actual output.

    Raises:
        ValueError: if actual output is zero or negative.
    """

    output = to_decimal(actual_output)
    if output <= 0:
        raise ValueError("Actual output must be greater than zero")

    return to_decimal(total_cost) / output


def calculate_batch_cost(
    *,
    raw_material_costs: Iterable[NumberLike] = (),
    preparation_costs: Iterable[NumberLike] = (),
    labor_costs: Iterable[NumberLike] = (),
    equipment_depreciation: NumberLike = 0,
    allocated_overhead: NumberLike = 0,
) -> Decimal:
    """Calculate total production batch cost."""

    return (
        sum_money(raw_material_costs)
        + sum_money(preparation_costs)
        + sum_money(labor_costs)
        + to_decimal(equipment_depreciation)
        + to_decimal(allocated_overhead)
    )


def calculate_order_margin(
    *,
    package_count: NumberLike,
    actual_package_price: NumberLike,
    sold_quantity: NumberLike,
    unit_cost: NumberLike,
    delivery_or_handover_cost: NumberLike = 0,
) -> OrderMargin:
    """Calculate revenue, COGS, delivery/handover cost and margin for an order."""

    revenue = to_decimal(package_count) * to_decimal(actual_package_price)
    cogs = to_decimal(sold_quantity) * to_decimal(unit_cost)
    delivery_cost = to_decimal(delivery_or_handover_cost)

    return OrderMargin(
        revenue=revenue,
        cost_of_goods_sold=cogs,
        delivery_or_handover_cost=delivery_cost,
        margin=revenue - cogs - delivery_cost,
    )


def calculate_result_after_personal_consumption(
    *,
    operating_profit: NumberLike,
    personal_consumption_at_cost: NumberLike,
) -> Decimal:
    """Calculate period result after owner personal consumption at cost."""

    return to_decimal(operating_profit) - to_decimal(personal_consumption_at_cost)
