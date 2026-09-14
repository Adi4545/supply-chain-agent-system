"""Inventory management agent."""

from __future__ import annotations

from typing import Any

from agents.base import BaseAgent
from models.schemas import AgentMessage, InventoryRecommendationMessage
from tools import inventory_tools


class InventoryAgent(BaseAgent):
    """Manages inventory levels, safety stock, and reorder quantities."""

    name = "inventory_agent"
    role = "Inventory Planner"
    objective = "Assess inventory levels and recommend reorder quantities"
    system_instructions = (
        "You are an inventory planning agent. Use tools to check stock, "
        "calculate safety stock and reorder quantity. Never compute numbers yourself."
    )
    allowed_tools = {
        "get_inventory": inventory_tools.get_inventory,
        "calculate_safety_stock": inventory_tools.calculate_safety_stock,
        "calculate_reorder_quantity": inventory_tools.calculate_reorder_quantity,
        "check_warehouse_capacity": inventory_tools.check_warehouse_capacity,
    }
    output_message_type = "inventory_recommendation"

    def build_output(self, tool_results: dict[str, Any], state_slice: dict[str, Any]) -> AgentMessage:
        """Build inventory recommendation from tool results."""
        inventory = tool_results.get("get_inventory")
        safety = tool_results.get("calculate_safety_stock")
        reorder = tool_results.get("calculate_reorder_quantity")
        capacity = tool_results.get("check_warehouse_capacity")

        if not all([inventory, safety, reorder]):
            from core.exceptions import AgentValidationError

            raise AgentValidationError(self.name, "Required inventory tool results missing")

        forecast = state_slice.get("demand_forecast", reorder.forecast_demand)
        product_id = inventory.product_id

        return InventoryRecommendationMessage(
            product_id=product_id,
            current_inventory=inventory.current_inventory,
            forecast_demand=int(forecast) if forecast else reorder.forecast_demand,
            safety_stock=safety.safety_stock,
            recommended_order_quantity=reorder.recommended_order_quantity,
            warehouse_capacity_ok=capacity.can_accommodate if capacity else True,
        )
