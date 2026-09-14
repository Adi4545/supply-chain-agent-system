"""Agent configuration definitions for benchmarking."""

from __future__ import annotations

AGENT_CONFIGS: dict[str, list[str]] = {
    "1-agent": ["demand_agent"],
    "2-agent": ["demand_agent", "inventory_agent"],
    "3-agent": ["demand_agent", "inventory_agent", "procurement_agent"],
    "5-agent": [
        "demand_agent",
        "inventory_agent",
        "procurement_agent",
        "logistics_agent",
        "risk_agent",
    ],
    "10-agent": [
        "demand_agent",
        "inventory_agent",
        "procurement_agent",
        "logistics_agent",
        "risk_agent",
        "demand_anomaly_agent",
        "capacity_agent",
        "reliability_agent",
        "transport_cost_agent",
        "disruption_risk_agent",
    ],
}
