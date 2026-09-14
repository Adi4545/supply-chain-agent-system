"""Supplier/procurement tools — data, comparison, capacity, reliability."""

from __future__ import annotations

import time

import structlog
from pydantic import BaseModel, Field

from core.exceptions import MissingEntityError
from environment.protocol import Environment
from models.schemas import Supplier, SupplierScore

logger = structlog.get_logger(__name__)


class SupplierDataInput(BaseModel):
    """Input for get_supplier_data tool."""

    product_id: str


class SupplierDataOutput(BaseModel):
    """Output from get_supplier_data tool."""

    product_id: str
    suppliers: list[Supplier]


class CompareSuppliersInput(BaseModel):
    """Input for compare_suppliers tool."""

    product_id: str
    required_quantity: int = Field(ge=0)
    weight_cost: float = Field(default=0.4, ge=0, le=1)
    weight_delivery: float = Field(default=0.3, ge=0, le=1)
    weight_reliability: float = Field(default=0.3, ge=0, le=1)


class CompareSuppliersOutput(BaseModel):
    """Output from compare_suppliers tool."""

    product_id: str
    supplier_scores: list[SupplierScore]
    ranked_supplier_ids: list[str]
    best_supplier_id: str


class SupplierCapacityInput(BaseModel):
    """Input for check_supplier_capacity tool."""

    supplier_id: str
    required_quantity: int = Field(ge=0)


class SupplierCapacityOutput(BaseModel):
    """Output from check_supplier_capacity tool."""

    supplier_id: str
    capacity: int
    required_quantity: int
    can_fulfill: bool
    utilization_pct: float


class SupplierReliabilityInput(BaseModel):
    """Input for evaluate_supplier_reliability tool."""

    supplier_id: str


class SupplierReliabilityOutput(BaseModel):
    """Output from evaluate_supplier_reliability tool."""

    supplier_id: str
    reliability_score: float = Field(ge=0, le=1)
    disruption_probability: float = Field(ge=0, le=1)
    risk_adjusted_score: float = Field(ge=0, le=1)


def get_supplier_data(env: Environment, inp: SupplierDataInput) -> SupplierDataOutput:
    """Retrieve all suppliers for a product."""
    start = time.perf_counter()
    suppliers = env.get_suppliers(inp.product_id)
    if not suppliers:
        raise MissingEntityError("Suppliers", inp.product_id)
    latency = (time.perf_counter() - start) * 1000
    logger.info(
        "tool.get_supplier_data",
        product_id=inp.product_id,
        count=len(suppliers),
        latency_ms=latency,
    )
    return SupplierDataOutput(product_id=inp.product_id, suppliers=suppliers)


def compare_suppliers(env: Environment, inp: CompareSuppliersInput) -> CompareSuppliersOutput:
    """Score and rank suppliers by cost, delivery, and reliability."""
    start = time.perf_counter()
    suppliers = env.get_suppliers(inp.product_id)
    if not suppliers:
        raise MissingEntityError("Suppliers", inp.product_id)

    max_price = max(s.unit_price for s in suppliers)
    min_price = min(s.unit_price for s in suppliers)
    max_lead = max(s.lead_time_days for s in suppliers)
    min_lead = min(s.lead_time_days for s in suppliers)

    scores: list[SupplierScore] = []
    for s in suppliers:
        # Normalize: lower cost/lead is better (higher score)
        cost_norm = (
            (max_price - s.unit_price) / (max_price - min_price)
            if max_price != min_price
            else 1.0
        )
        delivery_norm = (
            (max_lead - s.lead_time_days) / (max_lead - min_lead)
            if max_lead != min_lead
            else 1.0
        )
        reliability_norm = s.reliability

        total = (
            inp.weight_cost * cost_norm
            + inp.weight_delivery * delivery_norm
            + inp.weight_reliability * reliability_norm
        )
        scores.append(
            SupplierScore(
                supplier_id=s.supplier_id,
                cost_score=round(cost_norm, 3),
                delivery_score=round(delivery_norm, 3),
                reliability_score=round(reliability_norm, 3),
                total_score=round(total, 3),
            )
        )

    scores.sort(key=lambda x: x.total_score, reverse=True)
    ranked = [s.supplier_id for s in scores]

    latency = (time.perf_counter() - start) * 1000
    logger.info(
        "tool.compare_suppliers",
        product_id=inp.product_id,
        best=ranked[0],
        latency_ms=latency,
    )
    return CompareSuppliersOutput(
        product_id=inp.product_id,
        supplier_scores=scores,
        ranked_supplier_ids=ranked,
        best_supplier_id=ranked[0],
    )


def check_supplier_capacity(
    env: Environment,
    inp: SupplierCapacityInput,
) -> SupplierCapacityOutput:
    """Check if supplier can fulfill required quantity."""
    start = time.perf_counter()
    supplier = env.get_supplier(inp.supplier_id)
    can_fulfill = supplier.capacity >= inp.required_quantity
    utilization = (
        (inp.required_quantity / supplier.capacity * 100) if supplier.capacity > 0 else 100.0
    )

    latency = (time.perf_counter() - start) * 1000
    logger.info(
        "tool.check_supplier_capacity",
        supplier_id=inp.supplier_id,
        can_fulfill=can_fulfill,
        latency_ms=latency,
    )
    return SupplierCapacityOutput(
        supplier_id=inp.supplier_id,
        capacity=supplier.capacity,
        required_quantity=inp.required_quantity,
        can_fulfill=can_fulfill,
        utilization_pct=round(utilization, 2),
    )


def evaluate_supplier_reliability(
    env: Environment,
    inp: SupplierReliabilityInput,
) -> SupplierReliabilityOutput:
    """Evaluate supplier reliability with disruption risk adjustment."""
    start = time.perf_counter()
    supplier = env.get_supplier(inp.supplier_id)
    risk_adjusted = supplier.reliability * (1 - supplier.disruption_probability)

    latency = (time.perf_counter() - start) * 1000
    logger.info(
        "tool.evaluate_supplier_reliability",
        supplier_id=inp.supplier_id,
        reliability=supplier.reliability,
        latency_ms=latency,
    )
    return SupplierReliabilityOutput(
        supplier_id=inp.supplier_id,
        reliability_score=supplier.reliability,
        disruption_probability=supplier.disruption_probability,
        risk_adjusted_score=round(risk_adjusted, 3),
    )
