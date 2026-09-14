"""Unit tests for demand tools."""

from __future__ import annotations

import pytest

from core.exceptions import MissingEntityError
from environment.simulator import SimulatedEnvironment
from tools.demand_tools import (
    AnomalyInput,
    DemandHistoryInput,
    ForecastInput,
    detect_demand_anomaly,
    forecast_demand,
    get_demand_history,
)


def test_get_demand_history(seeded_env: SimulatedEnvironment) -> None:
    """Should return demand history records."""
    result = get_demand_history(seeded_env, DemandHistoryInput(product_id="P001"))
    assert result.total_days > 0
    assert result.average_daily_demand > 0


def test_forecast_demand(seeded_env: SimulatedEnvironment) -> None:
    """Should produce a positive forecast with confidence."""
    result = forecast_demand(
        seeded_env,
        ForecastInput(product_id="P001", horizon_days=30),
    )
    assert result.forecast_demand > 0
    assert 0 <= result.forecast_confidence <= 1


def test_detect_demand_anomaly(seeded_env: SimulatedEnvironment) -> None:
    """Should detect anomalies without error."""
    result = detect_demand_anomaly(seeded_env, AnomalyInput(product_id="P001"))
    assert isinstance(result.anomaly_detected, bool)
    assert result.latest_demand > 0


def test_missing_product_raises(seeded_env: SimulatedEnvironment) -> None:
    """Missing product should raise."""
    with pytest.raises(MissingEntityError):
        get_demand_history(seeded_env, DemandHistoryInput(product_id="INVALID"))
