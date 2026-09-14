"""Procurement and supplier selection agent."""

from __future__ import annotations

from typing import Any

from agents.base import BaseAgent
from models.schemas import AgentMessage, ProcurementRecommendationMessage, SupplierAllocation
from tools import supplier_tools


class ProcurementAgent(BaseAgent):
    """Evaluates and recommends suppliers for procurement."""

    name = "procurement_agent"
    role = "Procurement Specialist"
    objective = "Compare suppliers and recommend optimal procurement strategy"
    system_instructions = (
        "You are a procurement agent. Use tools to compare suppliers, "
        "check capacity and reliability. Never compute scores yourself."
    )
    allowed_tools = {
        "get_supplier_data": supplier_tools.get_supplier_data,
        "compare_suppliers": supplier_tools.compare_suppliers,
        "check_supplier_capacity": supplier_tools.check_supplier_capacity,
        "evaluate_supplier_reliability": supplier_tools.evaluate_supplier_reliability,
    }
    output_message_type = "procurement_recommendation"

    def build_output(self, tool_results: dict[str, Any], state_slice: dict[str, Any]) -> AgentMessage:
        """Build procurement recommendation from tool results."""
        comparison = tool_results.get("compare_suppliers")
        supplier_data = tool_results.get("get_supplier_data")
        capacity = tool_results.get("check_supplier_capacity")

        if comparison is None:
            from core.exceptions import AgentValidationError

            raise AgentValidationError(self.name, "compare_suppliers tool result missing")

        reorder_qty = state_slice.get("reorder_quantity", 10500)
        best_id = comparison.best_supplier_id
        best_supplier = next(
            (s for s in (supplier_data.suppliers if supplier_data else []) if s.supplier_id == best_id),
            None,
        )
        unit_price = best_supplier.unit_price if best_supplier else 22.0
        lead_time = best_supplier.lead_time_days if best_supplier else 7

        allocation = [
            SupplierAllocation(
                supplier_id=best_id,
                quantity=int(reorder_qty),
                unit_price=unit_price,
                expected_delivery_days=lead_time,
            )
        ]

        return ProcurementRecommendationMessage(
            product_id=comparison.product_id,
            recommended_suppliers=comparison.ranked_supplier_ids[:2],
            supplier_scores=comparison.supplier_scores,
            supplier_allocation=allocation,
        )
