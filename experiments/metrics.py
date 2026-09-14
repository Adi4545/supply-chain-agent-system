"""Pure metric functions for experiment evaluation."""

from __future__ import annotations

from typing import Any


def compute_total_cost(state: dict[str, Any]) -> float:
    """Extract total cost from run state."""
    return float(state.get("total_cost") or 0)


def compute_fill_rate(state: dict[str, Any]) -> float:
    """Estimate fill rate based on reorder vs demand."""
    demand = state.get("demand_forecast") or 1
    reorder = state.get("reorder_quantity") or 0
    inventory = state.get("inventory") or 0
    filled = min(demand, inventory + reorder)
    return round(filled / demand, 4)


def compute_stockout_rate(state: dict[str, Any]) -> float:
    """Estimate stockout rate."""
    return round(1.0 - compute_fill_rate(state), 4)


def compute_forecast_accuracy(state: dict[str, Any], actual: int = 12000) -> float:
    """Compute forecast accuracy vs actual demand."""
    forecast = state.get("demand_forecast") or actual
    if actual == 0:
        return 0.0
    error = abs(forecast - actual) / actual
    return round(max(0, 1 - error), 4)


def compute_decision_quality_score(state: dict[str, Any]) -> float:
    """Composite decision quality score (0-1)."""
    fill = compute_fill_rate(state)
    confidence = state.get("forecast_confidence") or 0.5
    has_decision = 1.0 if state.get("final_decision") else 0.0
    errors = len(state.get("errors") or [])
    error_penalty = min(0.5, errors * 0.1)
    return round(min(1.0, (fill * 0.4 + confidence * 0.3 + has_decision * 0.3) - error_penalty), 4)


def compute_communication_overhead(messages: list) -> dict[str, int]:
    """Compute message count and approximate bytes."""
    import json

    serialized = json.dumps(messages)
    return {"message_count": len(messages), "bytes": len(serialized)}


def aggregate_run_metrics(
    state: dict[str, Any],
    latency_ms: float,
    tool_calls: int,
    tokens: int,
    messages: list,
) -> dict[str, Any]:
    """Aggregate all metrics for a single run."""
    comm = compute_communication_overhead(messages)
    return {
        "total_cost": compute_total_cost(state),
        "stockout_rate": compute_stockout_rate(state),
        "fill_rate": compute_fill_rate(state),
        "forecast_accuracy": compute_forecast_accuracy(state),
        "decision_latency_ms": round(latency_ms, 2),
        "llm_tokens_used": tokens,
        "tool_calls_count": tool_calls,
        "message_count": comm["message_count"],
        "communication_bytes": comm["bytes"],
        "constraint_violations": len(state.get("errors") or []),
        "decision_quality_score": compute_decision_quality_score(state),
    }
