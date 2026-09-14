"""Unit tests for SupplyChainState."""

from __future__ import annotations

import pytest

from core.exceptions import OwnershipViolation
from models.schemas import ExecutionStatus, TraceEntry, UserRequest
from models.state import SupplyChainState


def test_state_defaults() -> None:
    """New state should have expected defaults."""
    state = SupplyChainState()
    assert state.run_id
    assert state.execution_status == ExecutionStatus.PENDING
    assert state.trace == []
    assert state.errors == []


def test_update_field_with_ownership() -> None:
    """Agent should update only owned fields."""
    state = SupplyChainState()
    state.update_field("demand_agent", "demand_forecast", 12000)
    assert state.demand_forecast == 12000


def test_update_field_ownership_violation() -> None:
    """Unauthorized field write should raise."""
    state = SupplyChainState()
    with pytest.raises(OwnershipViolation):
        state.update_field("demand_agent", "inventory", 100)


def test_update_slice() -> None:
    """update_slice should update multiple owned fields."""
    state = SupplyChainState()
    state.update_slice(
        "inventory_agent",
        {
            "inventory": 3500,
            "safety_stock": 2000,
            "reorder_quantity": 10500,
        },
    )
    assert state.inventory == 3500
    assert state.safety_stock == 2000
    assert state.reorder_quantity == 10500


def test_append_trace() -> None:
    """Trace entries should be appended."""
    state = SupplyChainState()
    entry = TraceEntry(run_id=state.run_id, agent="demand_agent", step="forecast")
    state.append_trace(entry)
    assert len(state.trace) == 1


def test_serialization_roundtrip() -> None:
    """State should survive serialize/deserialize."""
    state = SupplyChainState(
        user_request=UserRequest(objective="Plan replenishment"),
        demand_forecast=12000,
    )
    data = state.to_serializable()
    restored = SupplyChainState.from_serializable(data)
    assert restored.run_id == state.run_id
    assert restored.demand_forecast == 12000


def test_increment_agent_iteration() -> None:
    """Agent iteration counter should increment."""
    state = SupplyChainState()
    assert state.increment_agent_iteration("demand_agent") == 1
    assert state.increment_agent_iteration("demand_agent") == 2
