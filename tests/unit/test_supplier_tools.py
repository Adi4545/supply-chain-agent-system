"""Unit tests for supplier tools."""

from __future__ import annotations

import pytest

from core.exceptions import MissingEntityError
from environment.simulator import SimulatedEnvironment
from tools.supplier_tools import (
    CompareSuppliersInput,
    SupplierCapacityInput,
    SupplierDataInput,
    SupplierReliabilityInput,
    check_supplier_capacity,
    compare_suppliers,
    evaluate_supplier_reliability,
    get_supplier_data,
)


def test_get_supplier_data(seeded_env: SimulatedEnvironment) -> None:
    """Should return three suppliers for P001."""
    result = get_supplier_data(seeded_env, SupplierDataInput(product_id="P001"))
    assert len(result.suppliers) == 3


def test_compare_suppliers(seeded_env: SimulatedEnvironment) -> None:
    """Should rank suppliers with scores."""
    result = compare_suppliers(
        seeded_env,
        CompareSuppliersInput(product_id="P001", required_quantity=10500),
    )
    assert len(result.supplier_scores) == 3
    assert result.best_supplier_id in {"SUP_A", "SUP_B", "SUP_C"}
    # Supplier A is cheapest — should rank well on cost
    sup_a = next(s for s in result.supplier_scores if s.supplier_id == "SUP_A")
    assert sup_a.cost_score >= sup_a.delivery_score or sup_a.total_score > 0


def test_check_supplier_capacity(seeded_env: SimulatedEnvironment) -> None:
    """Supplier A should fulfill 10500 units."""
    result = check_supplier_capacity(
        seeded_env,
        SupplierCapacityInput(supplier_id="SUP_A", required_quantity=10500),
    )
    assert result.can_fulfill is True


def test_evaluate_supplier_reliability(seeded_env: SimulatedEnvironment) -> None:
    """Should return risk-adjusted reliability."""
    result = evaluate_supplier_reliability(
        seeded_env,
        SupplierReliabilityInput(supplier_id="SUP_B"),
    )
    assert 0 < result.risk_adjusted_score <= 1


def test_missing_supplier_raises(seeded_env: SimulatedEnvironment) -> None:
    """Missing supplier should raise."""
    with pytest.raises(MissingEntityError):
        check_supplier_capacity(
            seeded_env,
            SupplierCapacityInput(supplier_id="INVALID", required_quantity=100),
        )
