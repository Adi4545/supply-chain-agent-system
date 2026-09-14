"""Unit tests for logistics tools."""

from __future__ import annotations

import pytest

from core.exceptions import MissingEntityError
from environment.simulator import SimulatedEnvironment
from tools.logistics_tools import (
    DeliveryTimeInput,
    ShippingCostInput,
    TransportOptionsInput,
    calculate_shipping_cost,
    estimate_delivery_time,
    get_transport_options,
)


def test_get_transport_options(seeded_env: SimulatedEnvironment) -> None:
    """Should return transport options for P001."""
    result = get_transport_options(seeded_env, TransportOptionsInput(product_id="P001"))
    assert len(result.options) >= 3


def test_calculate_shipping_cost(seeded_env: SimulatedEnvironment) -> None:
    """Shipping cost should scale with quantity."""
    result = calculate_shipping_cost(
        seeded_env,
        ShippingCostInput(option_id="TRUCK", quantity=10500),
    )
    assert result.total_shipping_cost == pytest.approx(1.50 * 10500, rel=0.01)


def test_estimate_delivery_time(seeded_env: SimulatedEnvironment) -> None:
    """Total delivery = supplier lead + transport days."""
    result = estimate_delivery_time(
        seeded_env,
        DeliveryTimeInput(option_id="TRUCK", supplier_lead_time_days=7),
    )
    assert result.total_delivery_days == 7 + 2  # TRUCK is 2 days


def test_missing_transport_raises(seeded_env: SimulatedEnvironment) -> None:
    """Missing transport option should raise."""
    with pytest.raises(MissingEntityError):
        calculate_shipping_cost(
            seeded_env,
            ShippingCostInput(option_id="INVALID", quantity=100),
        )
