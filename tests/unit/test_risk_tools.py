"""Unit tests for risk tools."""

from __future__ import annotations

import pytest

from environment.simulator import SimulatedEnvironment
from models.schemas import RiskLevel
from tools.risk_tools import (
    DemandRiskInput,
    OverallRiskInput,
    SupplierRiskInput,
    TransportRiskInput,
    calculate_overall_risk,
    evaluate_demand_risk,
    evaluate_supplier_risk,
    evaluate_transport_risk,
)


def test_evaluate_supplier_risk(seeded_env: SimulatedEnvironment) -> None:
    """Should score all suppliers."""
    result = evaluate_supplier_risk(
        seeded_env,
        SupplierRiskInput(product_id="P001"),
    )
    assert len(result.supplier_risks) == 3
    assert 0 <= result.average_supplier_risk <= 1


def test_evaluate_transport_risk(seeded_env: SimulatedEnvironment) -> None:
    """Transport risk should be inverse of reliability."""
    result = evaluate_transport_risk(
        seeded_env,
        TransportRiskInput(option_id="AIR"),
    )
    assert result.transport_risk == pytest.approx(1 - result.reliability, abs=0.01)


def test_evaluate_demand_risk(seeded_env: SimulatedEnvironment) -> None:
    """Demand risk should reflect forecast confidence."""
    result = evaluate_demand_risk(
        seeded_env,
        DemandRiskInput(product_id="P001", forecast_confidence=0.85),
    )
    assert 0 <= result.demand_risk <= 1


def test_calculate_overall_risk() -> None:
    """Overall risk should combine component risks."""
    result = calculate_overall_risk(
        OverallRiskInput(
            supplier_risk=0.3,
            transport_risk=0.2,
            demand_risk=0.4,
        )
    )
    assert 0 <= result.risk_scores.overall_risk <= 1
    assert result.risk_scores.risk_level in RiskLevel
