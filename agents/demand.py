"""Demand forecasting agent."""

from __future__ import annotations

from typing import Any

from agents.base import BaseAgent
from models.schemas import AgentMessage, DemandForecastMessage
from tools import demand_tools


class DemandAgent(BaseAgent):
    """Forecasts demand and detects anomalies."""

    name = "demand_agent"
    role = "Demand Analyst"
    objective = "Forecast product demand and detect demand anomalies"
    system_instructions = (
        "You are a demand planning agent. Use tools to retrieve history, "
        "forecast demand, and detect anomalies. Never estimate numbers yourself."
    )
    allowed_tools = {
        "get_demand_history": demand_tools.get_demand_history,
        "forecast_demand": demand_tools.forecast_demand,
        "detect_demand_anomaly": demand_tools.detect_demand_anomaly,
    }
    output_message_type = "demand_forecast"

    def build_output(self, tool_results: dict[str, Any], state_slice: dict[str, Any]) -> AgentMessage:
        """Build demand forecast message from tool results."""
        forecast = tool_results.get("forecast_demand")
        anomaly = tool_results.get("detect_demand_anomaly")
        product_id = state_slice.get("product_id", "P001")
        if isinstance(product_id, dict):
            product_id = "P001"
        elif hasattr(state_slice.get("product"), "product_id"):
            product_id = state_slice["product"].product_id

        if forecast is None:
            from core.exceptions import AgentValidationError

            raise AgentValidationError(self.name, "forecast_demand tool result missing")

        return DemandForecastMessage(
            product_id=str(product_id),
            forecast_demand=forecast.forecast_demand,
            forecast_confidence=forecast.forecast_confidence,
            anomaly_detected=anomaly.anomaly_detected if anomaly else False,
        )
