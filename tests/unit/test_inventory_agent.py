"""Unit tests for InventoryAgent."""

from __future__ import annotations

import pytest

from agents.inventory import InventoryAgent
from environment.simulator import SimulatedEnvironment
from llm.mock_provider import MockLLMProvider
from models.schemas import InventoryRecommendationMessage
from models.state import SupplyChainState


@pytest.fixture
def inventory_agent(seeded_env: SimulatedEnvironment) -> InventoryAgent:
    """Create inventory agent."""
    return InventoryAgent(seeded_env)


@pytest.mark.asyncio
async def test_inventory_agent_run(inventory_agent: InventoryAgent) -> None:
    """Inventory agent should produce valid recommendation."""
    state = SupplyChainState()
    llm = MockLLMProvider()
    state_slice = {"product_id": "P001", "demand_forecast": 12000}

    output = await inventory_agent.run(state, state_slice, llm)

    assert isinstance(output, InventoryRecommendationMessage)
    assert output.current_inventory == 3500
    assert output.recommended_order_quantity > 0
    assert output.safety_stock > 0


@pytest.mark.asyncio
async def test_inventory_canonical_reorder(inventory_agent: InventoryAgent) -> None:
    """With 12k demand and 3500 inventory, reorder should exceed 8000."""
    state = SupplyChainState()
    llm = MockLLMProvider()
    output = await inventory_agent.run(
        state,
        {"product_id": "P001", "demand_forecast": 12000},
        llm,
    )
    assert output.recommended_order_quantity > 8000
