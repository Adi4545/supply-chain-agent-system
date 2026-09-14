"""Unit tests for inventory tools."""

from __future__ import annotations

from environment.simulator import SimulatedEnvironment
from tools.inventory_tools import (
    InventoryInput,
    ReorderQuantityInput,
    SafetyStockInput,
    WarehouseCapacityInput,
    calculate_reorder_quantity,
    calculate_safety_stock,
    check_warehouse_capacity,
    get_inventory,
)


def test_get_inventory(seeded_env: SimulatedEnvironment) -> None:
    """P001 inventory should be 3500."""
    result = get_inventory(seeded_env, InventoryInput(product_id="P001"))
    assert result.current_inventory == 3500


def test_calculate_safety_stock(seeded_env: SimulatedEnvironment) -> None:
    """Safety stock should be positive."""
    result = calculate_safety_stock(
        seeded_env,
        SafetyStockInput(product_id="P001", forecast_demand=12000, lead_time_days=7),
    )
    assert result.safety_stock > 0


def test_calculate_reorder_quantity_canonical(seeded_env: SimulatedEnvironment) -> None:
    """Canonical scenario: 12000 demand, 3500 inv, ~2000 safety → ~10500 reorder."""
    safety = calculate_safety_stock(
        seeded_env,
        SafetyStockInput(product_id="P001", forecast_demand=12000, lead_time_days=7),
    )
    result = calculate_reorder_quantity(
        seeded_env,
        ReorderQuantityInput(
            product_id="P001",
            forecast_demand=12000,
            current_inventory=3500,
            safety_stock=safety.safety_stock,
        ),
    )
    assert result.recommended_order_quantity > 8000
    assert result.net_requirement == (
        12000 + safety.safety_stock - 3500
    )


def test_check_warehouse_capacity(seeded_env: SimulatedEnvironment) -> None:
    """Warehouse should accommodate typical order."""
    result = check_warehouse_capacity(
        seeded_env,
        WarehouseCapacityInput(product_id="P001", additional_quantity=10500),
    )
    assert result.can_accommodate is True
    assert result.available_capacity > 0
