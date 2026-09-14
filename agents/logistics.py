"""Logistics and transportation agent."""

from __future__ import annotations

from typing import Any

from agents.base import BaseAgent
from models.schemas import AgentMessage, LogisticsRecommendationMessage
from tools import logistics_tools


class LogisticsAgent(BaseAgent):
    """Selects transport modes and estimates delivery."""

    name = "logistics_agent"
    role = "Logistics Coordinator"
    objective = "Recommend transport mode and estimate delivery time and cost"
    system_instructions = (
        "You are a logistics agent. Use tools to get transport options, "
        "calculate shipping costs and delivery times. Never estimate numbers yourself."
    )
    allowed_tools = {
        "get_transport_options": logistics_tools.get_transport_options,
        "calculate_shipping_cost": logistics_tools.calculate_shipping_cost,
        "estimate_delivery_time": logistics_tools.estimate_delivery_time,
    }
    output_message_type = "logistics_recommendation"

    def build_output(self, tool_results: dict[str, Any], state_slice: dict[str, Any]) -> AgentMessage:
        """Build logistics recommendation from tool results."""
        shipping = tool_results.get("calculate_shipping_cost")
        delivery = tool_results.get("estimate_delivery_time")
        options = tool_results.get("get_transport_options")

        if shipping is None or delivery is None:
            from core.exceptions import AgentValidationError

            raise AgentValidationError(self.name, "Required logistics tool results missing")

        product_id = options.product_id if options else "P001"

        return LogisticsRecommendationMessage(
            product_id=product_id,
            selected_transport_id=shipping.option_id,
            transport_mode=shipping.mode,
            estimated_delivery_days=delivery.total_delivery_days,
            shipping_cost=shipping.total_shipping_cost,
        )
