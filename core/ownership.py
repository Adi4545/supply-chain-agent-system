"""Agent field ownership map and validation helpers."""

from __future__ import annotations

from core.exceptions import OwnershipViolation

# Maps agent name to the state fields it is allowed to write.
AGENT_FIELD_OWNERSHIP: dict[str, frozenset[str]] = {
    "orchestrator": frozenset(
        {
            "execution_status",
            "final_decision",
            "agent_iterations",
            "errors",
        }
    ),
    "demand_agent": frozenset({"demand_forecast", "forecast_confidence", "demand_history"}),
    "inventory_agent": frozenset({"inventory", "safety_stock", "reorder_quantity"}),
    "procurement_agent": frozenset({"suppliers", "supplier_scores", "supplier_allocation"}),
    "logistics_agent": frozenset({"transport_options", "selected_transport"}),
    "risk_agent": frozenset({"risk_scores"}),
    "optimizer": frozenset({"total_cost", "constraints"}),
}


def validate_ownership(agent: str, field: str) -> None:
    """Raise OwnershipViolation if agent cannot write the given field."""
    allowed = AGENT_FIELD_OWNERSHIP.get(agent)
    if allowed is None:
        msg = f"Unknown agent: {agent}"
        raise OwnershipViolation(agent, field) from None
    if field not in allowed:
        raise OwnershipViolation(agent, field)


def get_owned_fields(agent: str) -> frozenset[str]:
    """Return the set of fields owned by an agent."""
    allowed = AGENT_FIELD_OWNERSHIP.get(agent)
    if allowed is None:
        msg = f"Unknown agent: {agent}"
        raise KeyError(msg)
    return allowed
