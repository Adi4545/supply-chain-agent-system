"""Unit tests for application settings."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from config.settings import OptimizerWeights, Settings, get_settings


def test_default_settings_load() -> None:
    """Default settings should load with valid optimizer weights."""
    settings = Settings()
    assert settings.db_url.startswith("sqlite")
    assert settings.random_seed == 42
    assert settings.llm.provider == "mock"
    assert settings.orch.max_iterations == 10


def test_optimizer_weights_sum_validation() -> None:
    """Weights that do not sum to 1.0 should raise."""
    with pytest.raises(ValidationError):
        OptimizerWeights(
            cost=0.5,
            delivery=0.5,
            reliability=0.5,
            risk=0.5,
            inventory=0.5,
        )


def test_optimizer_weights_valid() -> None:
    """Valid weights should pass validation."""
    weights = OptimizerWeights()
    total = (
        weights.cost
        + weights.delivery
        + weights.reliability
        + weights.risk
        + weights.inventory
    )
    assert abs(total - 1.0) < 1e-6


def test_get_settings_cached() -> None:
    """get_settings should return cached instance."""
    get_settings.cache_clear()
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
