"""Unit tests for tool-argument enrichment."""

from __future__ import annotations

from agents.base import enrich_tool_arguments
from tools.inventory_tools import InventoryOutput, ReorderQuantityOutput, SafetyStockOutput


def test_enrich_reorder_uses_prior_tool_results() -> None:
    """Reorder quantity args should use live inventory and safety stock."""
    results = {
        "get_inventory": InventoryOutput(product_id="P001", current_inventory=3500),
        "calculate_safety_stock": SafetyStockOutput(
            product_id="P001",
            safety_stock=1800,
            lead_time_days=7,
            daily_demand=400,
            demand_std=40,
        ),
    }
    args = enrich_tool_arguments(
        "calculate_reorder_quantity",
        {"product_id": "P001", "forecast_demand": 12000, "current_inventory": 0, "safety_stock": 2000},
        {"product_id": "P001", "demand_forecast": 12000},
        results,
    )
    assert args["current_inventory"] == 3500
    assert args["safety_stock"] == 1800
    assert args["forecast_demand"] == 12000


def test_enrich_capacity_uses_reorder() -> None:
    """Warehouse capacity check should use computed reorder quantity."""
    results = {
        "calculate_reorder_quantity": ReorderQuantityOutput(
            product_id="P001",
            recommended_order_quantity=10300,
            forecast_demand=12000,
            current_inventory=3500,
            safety_stock=1800,
            net_requirement=10300,
        )
    }
    args = enrich_tool_arguments(
        "check_warehouse_capacity",
        {"product_id": "P001", "additional_quantity": 1},
        {"product_id": "P001"},
        results,
    )
    assert args["additional_quantity"] == 10300
