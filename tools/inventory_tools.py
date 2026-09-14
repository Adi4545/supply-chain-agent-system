"""Inventory management tools — stock levels, safety stock, reorder quantity."""

from __future__ import annotations

import time

import structlog
from pydantic import BaseModel, Field

from core.exceptions import MissingEntityError
from environment.protocol import Environment

logger = structlog.get_logger(__name__)

DEFAULT_SERVICE_LEVEL_Z = 1.65  # ~95% service level


class InventoryInput(BaseModel):
    """Input for get_inventory tool."""

    product_id: str
    warehouse_id: str | None = None


class InventoryOutput(BaseModel):
    """Output from get_inventory tool."""

    product_id: str
    current_inventory: int = Field(ge=0)
    warehouse_id: str | None = None


class SafetyStockInput(BaseModel):
    """Input for calculate_safety_stock tool."""

    product_id: str
    forecast_demand: int = Field(ge=0)
    lead_time_days: int = Field(default=7, ge=1)
    service_level_z: float = Field(default=DEFAULT_SERVICE_LEVEL_Z, gt=0)


class SafetyStockOutput(BaseModel):
    """Output from calculate_safety_stock tool."""

    product_id: str
    safety_stock: int = Field(ge=0)
    lead_time_days: int
    daily_demand: float
    demand_std: float


class ReorderQuantityInput(BaseModel):
    """Input for calculate_reorder_quantity tool."""

    product_id: str
    forecast_demand: int = Field(ge=0)
    current_inventory: int = Field(ge=0)
    safety_stock: int = Field(ge=0)


class ReorderQuantityOutput(BaseModel):
    """Output from calculate_reorder_quantity tool."""

    product_id: str
    recommended_order_quantity: int = Field(ge=0)
    forecast_demand: int
    current_inventory: int
    safety_stock: int
    net_requirement: int


class WarehouseCapacityInput(BaseModel):
    """Input for check_warehouse_capacity tool."""

    product_id: str
    additional_quantity: int = Field(ge=0)
    warehouse_id: str | None = None


class WarehouseCapacityOutput(BaseModel):
    """Output from check_warehouse_capacity tool."""

    product_id: str
    warehouse_id: str
    current_inventory: int
    capacity: int
    available_capacity: int
    can_accommodate: bool
    additional_quantity: int


def get_inventory(env: Environment, inp: InventoryInput) -> InventoryOutput:
    """Get current inventory level for a product."""
    start = time.perf_counter()
    qty = env.get_inventory(inp.product_id, inp.warehouse_id)
    latency = (time.perf_counter() - start) * 1000
    logger.info(
        "tool.get_inventory",
        product_id=inp.product_id,
        quantity=qty,
        latency_ms=latency,
    )
    return InventoryOutput(
        product_id=inp.product_id,
        current_inventory=qty,
        warehouse_id=inp.warehouse_id,
    )


def calculate_safety_stock(env: Environment, inp: SafetyStockInput) -> SafetyStockOutput:
    """Calculate safety stock using demand variability and lead time."""
    start = time.perf_counter()
    history = env.get_demand_history(inp.product_id)
    quantities = [r.demand_quantity for r in history]

    if not quantities:
        raise MissingEntityError("Demand history for safety stock", inp.product_id)

    daily_demand = sum(quantities) / len(quantities)
    if len(quantities) > 1:
        variance = sum((q - daily_demand) ** 2 for q in quantities) / (len(quantities) - 1)
        demand_std = variance**0.5
    else:
        demand_std = daily_demand * 0.2

    # Safety stock = Z * σ_demand * sqrt(lead_time)
    safety = int(inp.service_level_z * demand_std * (inp.lead_time_days**0.5))
    safety = max(safety, int(daily_demand * 0.1))  # minimum buffer

    latency = (time.perf_counter() - start) * 1000
    logger.info(
        "tool.calculate_safety_stock",
        product_id=inp.product_id,
        safety_stock=safety,
        latency_ms=latency,
    )
    return SafetyStockOutput(
        product_id=inp.product_id,
        safety_stock=safety,
        lead_time_days=inp.lead_time_days,
        daily_demand=round(daily_demand, 2),
        demand_std=round(demand_std, 2),
    )


def calculate_reorder_quantity(
    env: Environment,
    inp: ReorderQuantityInput,
) -> ReorderQuantityOutput:
    """Calculate recommended reorder quantity."""
    start = time.perf_counter()
    env.get_product(inp.product_id)  # validate product exists

    net_requirement = inp.forecast_demand + inp.safety_stock - inp.current_inventory
    reorder_qty = max(0, net_requirement)

    latency = (time.perf_counter() - start) * 1000
    logger.info(
        "tool.calculate_reorder_quantity",
        product_id=inp.product_id,
        reorder_qty=reorder_qty,
        latency_ms=latency,
    )
    return ReorderQuantityOutput(
        product_id=inp.product_id,
        recommended_order_quantity=reorder_qty,
        forecast_demand=inp.forecast_demand,
        current_inventory=inp.current_inventory,
        safety_stock=inp.safety_stock,
        net_requirement=net_requirement,
    )


def check_warehouse_capacity(
    env: Environment,
    inp: WarehouseCapacityInput,
) -> WarehouseCapacityOutput:
    """Check if warehouse can accommodate additional inventory."""
    start = time.perf_counter()
    warehouses = env.get_warehouses()
    if not warehouses:
        raise MissingEntityError("Warehouse", "any")

    warehouse = (
        env.get_warehouse(inp.warehouse_id)
        if inp.warehouse_id
        else warehouses[0]
    )
    current = warehouse.current_inventory.get(inp.product_id, 0)
    total_used = sum(warehouse.current_inventory.values())
    available = warehouse.capacity - total_used
    can_fit = available >= inp.additional_quantity

    latency = (time.perf_counter() - start) * 1000
    logger.info(
        "tool.check_warehouse_capacity",
        product_id=inp.product_id,
        can_accommodate=can_fit,
        latency_ms=latency,
    )
    return WarehouseCapacityOutput(
        product_id=inp.product_id,
        warehouse_id=warehouse.warehouse_id,
        current_inventory=current,
        capacity=warehouse.capacity,
        available_capacity=available,
        can_accommodate=can_fit,
        additional_quantity=inp.additional_quantity,
    )
