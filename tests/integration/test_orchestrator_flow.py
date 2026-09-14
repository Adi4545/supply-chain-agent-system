"""Integration tests for orchestrator pipeline."""

from __future__ import annotations

import pytest

from agents.orchestrator import OrchestratorAgent
from environment.simulator import SimulatedEnvironment
from llm.mock_provider import MockLLMProvider
from models.schemas import ExecutionStatus, UserRequest


@pytest.fixture
def orchestrator(seeded_env: SimulatedEnvironment) -> OrchestratorAgent:
    """Create orchestrator with mock LLM."""
    return OrchestratorAgent(seeded_env, MockLLMProvider())


@pytest.mark.asyncio
async def test_full_pipeline(orchestrator: OrchestratorAgent) -> None:
    """Full planning pipeline should complete with FinalDecision."""
    request = UserRequest(
        objective="Plan replenishment for product P001",
        product_id="P001",
    )
    state = await orchestrator.run(request)

    assert state.execution_status == ExecutionStatus.COMPLETED
    assert state.final_decision is not None
    assert state.final_decision.requires_human_approval is True
    assert state.demand_forecast is not None
    assert state.inventory == 3500
    assert state.reorder_quantity > 0
    assert state.total_cost is not None


@pytest.mark.asyncio
async def test_trace_summary(orchestrator: OrchestratorAgent) -> None:
    """Trace should show agent tool path."""
    state = await orchestrator.run(
        UserRequest(objective="Plan replenishment for product P001", product_id="P001")
    )
    trace = orchestrator.get_trace_summary(state)
    assert "Orchestrator" in trace
    assert "demand_agent" in trace
    assert "FinalDecision" in trace


@pytest.mark.asyncio
async def test_inventory_only_skips_logistics(orchestrator: OrchestratorAgent) -> None:
    """Inventory-only query should skip logistics and risk agents."""
    state = await orchestrator.run(
        UserRequest(
            objective="Check inventory levels only",
            product_id="P001",
            include_logistics=False,
            include_risk=False,
            include_procurement=False,
        )
    )
    assert state.execution_status == ExecutionStatus.COMPLETED
    assert state.selected_transport is None
