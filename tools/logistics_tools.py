"""Logistics tools — transport options, shipping cost, delivery time."""

from __future__ import annotations

import time

import structlog
from pydantic import BaseModel, Field

from core.exceptions import MissingEntityError
from environment.protocol import Environment
from models.schemas import TransportOption

logger = structlog.get_logger(__name__)


class TransportOptionsInput(BaseModel):
    """Input for get_transport_options tool."""

    product_id: str


class TransportOptionsOutput(BaseModel):
    """Output from get_transport_options tool."""

    product_id: str
    options: list[TransportOption]


class ShippingCostInput(BaseModel):
    """Input for calculate_shipping_cost tool."""

    option_id: str
    quantity: int = Field(ge=0)


class ShippingCostOutput(BaseModel):
    """Output from calculate_shipping_cost tool."""

    option_id: str
    quantity: int
    cost_per_unit: float
    total_shipping_cost: float
    mode: str
    carrier: str


class DeliveryTimeInput(BaseModel):
    """Input for estimate_delivery_time tool."""

    option_id: str
    supplier_lead_time_days: int = Field(ge=0)


class DeliveryTimeOutput(BaseModel):
    """Output from estimate_delivery_time tool."""

    option_id: str
    transport_days: int
    supplier_lead_time_days: int
    total_delivery_days: int
    mode: str


def get_transport_options(
    env: Environment,
    inp: TransportOptionsInput,
) -> TransportOptionsOutput:
    """Retrieve available transport options for a product."""
    start = time.perf_counter()
    options = env.get_transport_options(inp.product_id)
    if not options:
        raise MissingEntityError("Transport options", inp.product_id)
    latency = (time.perf_counter() - start) * 1000
    logger.info(
        "tool.get_transport_options",
        product_id=inp.product_id,
        count=len(options),
        latency_ms=latency,
    )
    return TransportOptionsOutput(product_id=inp.product_id, options=options)


def calculate_shipping_cost(
    env: Environment,
    inp: ShippingCostInput,
) -> ShippingCostOutput:
    """Calculate total shipping cost for a quantity."""
    start = time.perf_counter()
    option = env.get_transport_option(inp.option_id)
    total = option.cost_per_unit * inp.quantity

    latency = (time.perf_counter() - start) * 1000
    logger.info(
        "tool.calculate_shipping_cost",
        option_id=inp.option_id,
        total_cost=total,
        latency_ms=latency,
    )
    return ShippingCostOutput(
        option_id=inp.option_id,
        quantity=inp.quantity,
        cost_per_unit=option.cost_per_unit,
        total_shipping_cost=round(total, 2),
        mode=option.mode,
        carrier=option.carrier,
    )


def estimate_delivery_time(
    env: Environment,
    inp: DeliveryTimeInput,
) -> DeliveryTimeOutput:
    """Estimate total delivery time including supplier lead time."""
    start = time.perf_counter()
    option = env.get_transport_option(inp.option_id)
    total_days = inp.supplier_lead_time_days + option.delivery_time_days

    latency = (time.perf_counter() - start) * 1000
    logger.info(
        "tool.estimate_delivery_time",
        option_id=inp.option_id,
        total_days=total_days,
        latency_ms=latency,
    )
    return DeliveryTimeOutput(
        option_id=inp.option_id,
        transport_days=option.delivery_time_days,
        supplier_lead_time_days=inp.supplier_lead_time_days,
        total_delivery_days=total_days,
        mode=option.mode,
    )
