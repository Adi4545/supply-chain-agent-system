"""Unit tests for ProcurementAgent."""

from __future__ import annotations

import pytest

from agents.procurement import ProcurementAgent
from environment.simulator import SimulatedEnvironment
from llm.mock_provider import MockLLMProvider
from models.schemas import ProcurementRecommendationMessage
from models.state import SupplyChainState


@pytest.mark.asyncio
async def test_procurement_agent_run(seeded_env: SimulatedEnvironment) -> None:
    """Procurement agent should rank suppliers and allocate."""
    agent = ProcurementAgent(seeded_env)
    state = SupplyChainState()
    llm = MockLLMProvider()

    output = await agent.run(
        state,
        {"product_id": "P001", "reorder_quantity": 10500},
        llm,
    )

    assert isinstance(output, ProcurementRecommendationMessage)
    assert len(output.supplier_scores) == 3
    assert len(output.supplier_allocation) == 1
    assert output.supplier_allocation[0].quantity == 10500
