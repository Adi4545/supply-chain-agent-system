"""Unit tests for SimulatedEnvironment."""

from __future__ import annotations

import pytest

from core.exceptions import MissingEntityError
from environment.simulator import SimulatedEnvironment


@pytest.fixture
def env(tmp_path) -> SimulatedEnvironment:
    """Create a seeded simulated environment with temp database."""
    db_path = tmp_path / "test.db"
    environment = SimulatedEnvironment(db_url=f"sqlite:///{db_path}", seed=42)
    environment.seed()
    return environment


def test_seed_creates_products(env: SimulatedEnvironment) -> None:
    """Seeding should create canonical products."""
    products = env.list_products()
    assert len(products) >= 1
    assert any(p.product_id == "P001" for p in products)


def test_get_product(env: SimulatedEnvironment) -> None:
    """Should retrieve P001 product."""
    product = env.get_product("P001")
    assert product.product_id == "P001"
    assert product.unit_cost > 0


def test_missing_product_raises(env: SimulatedEnvironment) -> None:
    """Missing product should raise MissingEntityError."""
    with pytest.raises(MissingEntityError):
        env.get_product("INVALID")


def test_get_suppliers(env: SimulatedEnvironment) -> None:
    """Should return three suppliers for P001."""
    suppliers = env.get_suppliers("P001")
    assert len(suppliers) == 3
    ids = {s.supplier_id for s in suppliers}
    assert ids == {"SUP_A", "SUP_B", "SUP_C"}


def test_get_inventory(env: SimulatedEnvironment) -> None:
    """P001 inventory should be 3500."""
    qty = env.get_inventory("P001")
    assert qty == 3500


def test_get_demand_history(env: SimulatedEnvironment) -> None:
    """Should return 90 days of demand history."""
    history = env.get_demand_history("P001")
    assert len(history) == 90


def test_get_transport_options(env: SimulatedEnvironment) -> None:
    """Should return transport options for P001."""
    options = env.get_transport_options("P001")
    assert len(options) >= 3
    modes = {o.mode for o in options}
    assert "ground" in modes


def test_reproducible_seed(env: SimulatedEnvironment, tmp_path) -> None:
    """Two environments with same seed should have identical demand."""
    env2 = SimulatedEnvironment(
        db_url=f"sqlite:///{tmp_path / 'test2.db'}",
        seed=42,
    )
    env2.seed()
    h1 = env.get_demand_history("P001")
    h2 = env2.get_demand_history("P001")
    assert [r.demand_quantity for r in h1] == [r.demand_quantity for r in h2]
