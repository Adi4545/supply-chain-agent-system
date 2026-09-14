"""Unit tests for synthetic data generation."""

from __future__ import annotations

from environment.synthetic_data import (
    generate_canonical_products,
    generate_canonical_suppliers,
    generate_canonical_warehouses,
    generate_demand_history,
)


def test_canonical_products() -> None:
    """Canonical products should include P001."""
    products = generate_canonical_products()
    ids = [p.product_id for p in products]
    assert "P001" in ids


def test_canonical_suppliers_for_p001() -> None:
    """Three suppliers should serve P001 with expected lead times."""
    suppliers = generate_canonical_suppliers()
    assert len(suppliers) == 3
    lead_times = sorted(s.lead_time_days for s in suppliers)
    assert lead_times == [3, 5, 7]


def test_canonical_warehouse_inventory() -> None:
    """P001 inventory should be 3500 in canonical warehouse."""
    warehouses = generate_canonical_warehouses()
    assert warehouses[0].current_inventory["P001"] == 3500


def test_demand_history_deterministic() -> None:
    """Same seed should produce identical demand history."""
    h1 = generate_demand_history("P001", seed=42)
    h2 = generate_demand_history("P001", seed=42)
    assert len(h1) == len(h2) == 90
    assert [r.demand_quantity for r in h1] == [r.demand_quantity for r in h2]


def test_demand_history_different_seeds() -> None:
    """Different seeds should produce different histories."""
    h1 = generate_demand_history("P001", seed=42)
    h2 = generate_demand_history("P001", seed=99)
    assert [r.demand_quantity for r in h1] != [r.demand_quantity for r in h2]
