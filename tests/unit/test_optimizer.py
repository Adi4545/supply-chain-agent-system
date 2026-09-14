"""Unit tests for OR-Tools optimizer."""

from __future__ import annotations

from environment.simulator import SimulatedEnvironment
from optimization.optimizer import OptimizationInput, optimize


def test_optimizer_canonical_scenario(seeded_env: SimulatedEnvironment) -> None:
    """Canonical scenario should yield feasible allocation."""
    suppliers = seeded_env.get_suppliers("P001")
    transport = seeded_env.get_transport_options("P001")

    result = optimize(
        OptimizationInput(
            product_id="P001",
            demand=12000,
            current_inventory=3500,
            safety_stock=2000,
            reorder_quantity=10500,
            suppliers=suppliers,
            transport_options=transport,
            selected_transport_id="TRUCK",
        )
    )

    assert result.feasible is True
    assert len(result.supplier_allocation) >= 1
    assert result.total_cost > 0
    assert result.cost_breakdown.procurement_cost > 0


def test_optimizer_infeasible_budget(seeded_env: SimulatedEnvironment) -> None:
    """Tight budget should cause infeasibility."""
    suppliers = seeded_env.get_suppliers("P001")
    transport = seeded_env.get_transport_options("P001")

    result = optimize(
        OptimizationInput(
            product_id="P001",
            demand=12000,
            current_inventory=3500,
            safety_stock=2000,
            reorder_quantity=10500,
            suppliers=suppliers,
            transport_options=transport,
            budget=100.0,
        )
    )

    assert result.feasible is False
    assert len(result.infeasibility_reasons) > 0


def test_optimizer_zero_reorder(seeded_env: SimulatedEnvironment) -> None:
    """Zero reorder should return trivial feasible result."""
    result = optimize(
        OptimizationInput(
            product_id="P001",
            demand=1000,
            current_inventory=5000,
            safety_stock=500,
            reorder_quantity=0,
            suppliers=seeded_env.get_suppliers("P001"),
            transport_options=seeded_env.get_transport_options("P001"),
        )
    )
    assert result.feasible is True
    assert result.total_cost == 0.0
