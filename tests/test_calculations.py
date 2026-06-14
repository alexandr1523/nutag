from decimal import Decimal

import pytest

from nutag.services.calculations import (
    calculate_batch_cost,
    calculate_order_margin,
    calculate_preparation_cost,
    calculate_result_after_personal_consumption,
    calculate_unit_cost,
    calculate_weighted_average_price,
)


def test_weighted_average_price_with_opening_stock_and_purchase() -> None:
    price = calculate_weighted_average_price(
        opening_quantity="1",
        opening_value="70",
        purchased_quantity="4",
        purchased_value="360",
    )

    assert price == Decimal("86")


def test_weighted_average_price_with_zero_opening_stock() -> None:
    price = calculate_weighted_average_price(
        opening_quantity="0",
        opening_value="0",
        purchased_quantity="5",
        purchased_value="500",
    )

    assert price == Decimal("100")


def test_weighted_average_price_with_multiple_purchase_prices() -> None:
    price = calculate_weighted_average_price(
        opening_quantity="0",
        opening_value="0",
        purchased_quantity="10",
        purchased_value="4650",
    )

    assert price == Decimal("465")


def test_weighted_average_price_rejects_zero_total_quantity() -> None:
    with pytest.raises(ValueError, match="Total quantity"):
        calculate_weighted_average_price(
            opening_quantity="0",
            opening_value="0",
            purchased_quantity="0",
            purchased_value="0",
        )


def test_preparation_cost_includes_direct_components() -> None:
    cost = calculate_preparation_cost(
        ingredient_costs=["120", "80"],
        material_costs=["15"],
        labor_costs=["200"],
        other_direct_costs=["25"],
    )

    assert cost == Decimal("440")


def test_unit_cost_uses_actual_output() -> None:
    unit_cost = calculate_unit_cost(total_cost="440", actual_output="2.2")

    assert unit_cost == Decimal("200")


def test_unit_cost_rejects_zero_actual_output() -> None:
    with pytest.raises(ValueError, match="Actual output"):
        calculate_unit_cost(total_cost="440", actual_output="0")


def test_batch_cost_includes_materials_preparations_labor_and_allocations() -> None:
    cost = calculate_batch_cost(
        raw_material_costs=["500", "180"],
        preparation_costs=["320"],
        labor_costs=["600"],
        equipment_depreciation="40",
        allocated_overhead="60",
    )

    assert cost == Decimal("1700")


def test_order_margin_subtracts_cogs_and_delivery_or_handover_cost() -> None:
    margin = calculate_order_margin(
        package_count="3",
        actual_package_price="550",
        sold_quantity="1.5",
        unit_cost="300",
        delivery_or_handover_cost="100",
    )

    assert margin.revenue == Decimal("1650")
    assert margin.cost_of_goods_sold == Decimal("450.0")
    assert margin.delivery_or_handover_cost == Decimal("100")
    assert margin.margin == Decimal("1100.0")


def test_personal_consumption_reduces_result_after_operating_profit() -> None:
    result = calculate_result_after_personal_consumption(
        operating_profit="6000",
        personal_consumption_at_cost="2500",
    )

    assert result == Decimal("3500")
