"""Unit tests for LogisticsAgent."""

from __future__ import annotations

import pytest

from agents.logistics import LogisticsAgent
from environment.simulator import SimulatedEnvironment
from llm.mock_provider import MockLLMProvider
from models.schemas import LogisticsRecommendationMessage
from models.state import SupplyChainState


@pytest.mark.asyncio
async def test_logistics_agent_run(seeded_env: SimulatedEnvironment) -> None:
    """Logistics agent should recommend transport."""
    agent = LogisticsAgent(seeded_env)
    state = SupplyChainState()
    llm = MockLLMProvider()

    output = await agent.run(state, {"product_id": "P001"}, llm)

    assert isinstance(output, LogisticsRecommendationMessage)
    assert output.selected_transport_id == "TRUCK"
    assert output.shipping_cost > 0
    assert output.estimated_delivery_days > 0
