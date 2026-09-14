"""Unit tests for DemandAgent."""

from __future__ import annotations

import pytest

from agents.demand import DemandAgent
from environment.simulator import SimulatedEnvironment
from llm.mock_provider import MockLLMProvider
from models.schemas import DemandForecastMessage
from models.state import SupplyChainState


@pytest.fixture
def demand_agent(seeded_env: SimulatedEnvironment) -> DemandAgent:
    """Create demand agent with seeded environment."""
    return DemandAgent(seeded_env)


@pytest.mark.asyncio
async def test_demand_agent_run(demand_agent: DemandAgent) -> None:
    """Demand agent should produce valid forecast message."""
    state = SupplyChainState()
    llm = MockLLMProvider()
    state_slice = {"product_id": "P001"}

    output = await demand_agent.run(state, state_slice, llm)

    assert isinstance(output, DemandForecastMessage)
    assert output.forecast_demand > 0
    assert 0 <= output.forecast_confidence <= 1
    assert len(state.trace) >= 3


@pytest.mark.asyncio
async def test_demand_agent_writes_state(demand_agent: DemandAgent) -> None:
    """Demand agent output fields should be usable for state update."""
    state = SupplyChainState()
    llm = MockLLMProvider()
    output = await demand_agent.run(state, {"product_id": "P001"}, llm)

    state.update_slice(
        "demand_agent",
        {
            "demand_forecast": output.forecast_demand,
            "forecast_confidence": output.forecast_confidence,
        },
    )
    assert state.demand_forecast == output.forecast_demand
