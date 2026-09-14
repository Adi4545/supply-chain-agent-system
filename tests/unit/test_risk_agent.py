"""Unit tests for RiskAgent."""

from __future__ import annotations

import pytest

from agents.risk import RiskAgent
from environment.simulator import SimulatedEnvironment
from llm.mock_provider import MockLLMProvider
from models.schemas import RiskAssessmentMessage, RiskLevel
from models.state import SupplyChainState


@pytest.mark.asyncio
async def test_risk_agent_run(seeded_env: SimulatedEnvironment) -> None:
    """Risk agent should produce risk assessment."""
    agent = RiskAgent(seeded_env)
    state = SupplyChainState()
    llm = MockLLMProvider()

    output = await agent.run(
        state,
        {"product_id": "P001", "forecast_confidence": 0.85},
        llm,
    )

    assert isinstance(output, RiskAssessmentMessage)
    assert 0 <= output.risk_scores.overall_risk <= 1
    assert output.risk_scores.risk_level in RiskLevel
