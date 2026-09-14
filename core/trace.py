"""Build human-readable execution trace strings."""

from __future__ import annotations

from models.state import SupplyChainState


def build_trace_summary(state: SupplyChainState) -> str:
    """Build readable trace: Orchestrator → Agent.tool → ... → FinalDecision."""
    steps: list[str] = ["Orchestrator"]
    for entry in state.trace:
        if entry.tool_called:
            steps.append(f"{entry.agent}.{entry.tool_called}")
        elif entry.step == "emit_output":
            steps.append(entry.agent)
    if state.final_decision:
        steps.append("Optimizer")
        steps.append("FinalDecision")
    return " → ".join(steps)
