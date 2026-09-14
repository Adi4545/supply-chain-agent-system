"""Deterministic mock LLM provider for CI and testing."""

from __future__ import annotations

from llm.protocol import LLMProvider, LLMResponse, ToolCall

# Predefined tool-call sequences per agent for deterministic runs.
MOCK_TOOL_SEQUENCES: dict[str, list[ToolCall]] = {
    "demand_agent": [
        ToolCall(tool_name="get_demand_history", arguments={"product_id": "P001", "days": 90}),
        ToolCall(tool_name="forecast_demand", arguments={"product_id": "P001", "horizon_days": 30}),
        ToolCall(tool_name="detect_demand_anomaly", arguments={"product_id": "P001"}),
    ],
    "inventory_agent": [
        ToolCall(tool_name="get_inventory", arguments={"product_id": "P001"}),
        ToolCall(
            tool_name="calculate_safety_stock",
            arguments={"product_id": "P001", "forecast_demand": 12000, "lead_time_days": 7},
        ),
        ToolCall(
            tool_name="calculate_reorder_quantity",
            arguments={
                "product_id": "P001",
                "forecast_demand": 12000,
                "current_inventory": 3500,
                "safety_stock": 2000,
            },
        ),
        ToolCall(
            tool_name="check_warehouse_capacity",
            arguments={"product_id": "P001", "additional_quantity": 10500},
        ),
    ],
    "procurement_agent": [
        ToolCall(tool_name="get_supplier_data", arguments={"product_id": "P001"}),
        ToolCall(
            tool_name="compare_suppliers",
            arguments={"product_id": "P001", "required_quantity": 10500},
        ),
        ToolCall(
            tool_name="check_supplier_capacity",
            arguments={"supplier_id": "SUP_A", "required_quantity": 10500},
        ),
        ToolCall(tool_name="evaluate_supplier_reliability", arguments={"supplier_id": "SUP_A"}),
    ],
    "logistics_agent": [
        ToolCall(tool_name="get_transport_options", arguments={"product_id": "P001"}),
        ToolCall(tool_name="calculate_shipping_cost", arguments={"option_id": "TRUCK", "quantity": 10500}),
        ToolCall(
            tool_name="estimate_delivery_time",
            arguments={"option_id": "TRUCK", "supplier_lead_time_days": 7},
        ),
    ],
    "risk_agent": [
        ToolCall(tool_name="evaluate_supplier_risk", arguments={"product_id": "P001"}),
        ToolCall(tool_name="evaluate_transport_risk", arguments={"option_id": "TRUCK"}),
        ToolCall(
            tool_name="evaluate_demand_risk",
            arguments={"product_id": "P001", "forecast_confidence": 0.85},
        ),
    ],
}


class MockLLMProvider(LLMProvider):
    """Returns predetermined tool calls for each agent."""

    def __init__(self) -> None:
        self._call_index: dict[str, int] = {}
        self.total_tokens: int = 0

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        available_tools: list[str] | None = None,
        agent_name: str | None = None,
    ) -> LLMResponse:
        """Return next tool call in sequence, or stop signal when done."""
        agent = agent_name or "unknown"
        idx = self._call_index.get(agent, 0)
        sequence = MOCK_TOOL_SEQUENCES.get(agent, [])

        if idx < len(sequence):
            tool_call = sequence[idx]
            self._call_index[agent] = idx + 1
            self.total_tokens += 50
            return LLMResponse(
                content=f"Calling {tool_call.tool_name}",
                tool_calls=[tool_call],
                tokens_used=50,
                finish_reason="tool_calls",
            )

        self.total_tokens += 20
        return LLMResponse(
            content="Analysis complete.",
            tool_calls=[],
            tokens_used=20,
            finish_reason="stop",
        )

    def reset(self) -> None:
        """Reset call indices for a new run."""
        self._call_index.clear()
        self.total_tokens = 0

    def reset_agent(self, agent_name: str) -> None:
        """Reset the tool-call cursor for one agent so it can be re-invoked."""
        self._call_index.pop(agent_name, None)
