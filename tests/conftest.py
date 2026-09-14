"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from environment.simulator import SimulatedEnvironment


@pytest.fixture
def seeded_env(tmp_path) -> SimulatedEnvironment:
    """Provide a seeded simulated environment."""
    db_path = tmp_path / "supply_chain_test.db"
    env = SimulatedEnvironment(db_url=f"sqlite:///{db_path}", seed=42)
    env.seed()
    return env
