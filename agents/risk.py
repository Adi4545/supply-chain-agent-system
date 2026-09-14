"""Risk assessment agent."""

from __future__ import annotations

from typing import Any

from agents.base import BaseAgent
from models.schemas import AgentMessage, RiskAssessmentMessage, RiskScores
from tools import risk_tools


class RiskAgent(BaseAgent):
    """Evaluates supply chain risks across suppliers, transport, and demand."""

    name = "risk_agent"
    role = "Risk Analyst"
    objective = "Assess overall supply chain risk and classify risk level"
    system_instructions = (
        "You are a risk assessment agent. Use tools to evaluate supplier, "
        "transport, and demand risks. Never compute risk scores yourself."
    )
    allowed_tools = {
        "evaluate_supplier_risk": risk_tools.evaluate_supplier_risk,
        "evaluate_transport_risk": risk_tools.evaluate_transport_risk,
        "evaluate_demand_risk": risk_tools.evaluate_demand_risk,
        "calculate_overall_risk": risk_tools.calculate_overall_risk,
    }
    output_message_type = "risk_assessment"

    def build_output(self, tool_results: dict[str, Any], state_slice: dict[str, Any]) -> AgentMessage:
        """Build risk assessment from tool results."""
        supplier_risk = tool_results.get("evaluate_supplier_risk")
        transport_risk = tool_results.get("evaluate_transport_risk")
        demand_risk = tool_results.get("evaluate_demand_risk")

        if not all([supplier_risk, transport_risk, demand_risk]):
            from core.exceptions import AgentValidationError

            raise AgentValidationError(self.name, "Required risk tool results missing")

        overall = risk_tools.calculate_overall_risk(
            risk_tools.OverallRiskInput(
                supplier_risk=supplier_risk.average_supplier_risk,
                transport_risk=transport_risk.transport_risk,
                demand_risk=demand_risk.demand_risk,
            )
        )

        product_id = supplier_risk.product_id
        return RiskAssessmentMessage(
            product_id=product_id,
            risk_scores=overall.risk_scores,
        )
