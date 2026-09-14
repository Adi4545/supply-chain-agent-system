"""Risk assessment tools — supplier, transport, demand, overall risk."""

from __future__ import annotations

import statistics
import time

import structlog
from pydantic import BaseModel, Field

from core.exceptions import MissingEntityError
from environment.protocol import Environment
from models.schemas import RiskLevel, RiskScores

logger = structlog.get_logger(__name__)


class SupplierRiskInput(BaseModel):
    """Input for evaluate_supplier_risk tool."""

    product_id: str
    supplier_ids: list[str] = Field(default_factory=list)


class SupplierRiskOutput(BaseModel):
    """Output from evaluate_supplier_risk tool."""

    product_id: str
    supplier_risks: dict[str, float]
    average_supplier_risk: float = Field(ge=0, le=1)


class TransportRiskInput(BaseModel):
    """Input for evaluate_transport_risk tool."""

    option_id: str


class TransportRiskOutput(BaseModel):
    """Output from evaluate_transport_risk tool."""

    option_id: str
    transport_risk: float = Field(ge=0, le=1)
    reliability: float = Field(ge=0, le=1)


class DemandRiskInput(BaseModel):
    """Input for evaluate_demand_risk tool."""

    product_id: str
    forecast_confidence: float = Field(ge=0, le=1)


class DemandRiskOutput(BaseModel):
    """Output from evaluate_demand_risk tool."""

    product_id: str
    demand_risk: float = Field(ge=0, le=1)
    forecast_confidence: float
    demand_variability: float


class OverallRiskInput(BaseModel):
    """Input for calculate_overall_risk tool."""

    supplier_risk: float = Field(ge=0, le=1)
    transport_risk: float = Field(ge=0, le=1)
    demand_risk: float = Field(ge=0, le=1)
    weight_supplier: float = Field(default=0.4, ge=0, le=1)
    weight_transport: float = Field(default=0.3, ge=0, le=1)
    weight_demand: float = Field(default=0.3, ge=0, le=1)


class OverallRiskOutput(BaseModel):
    """Output from calculate_overall_risk tool."""

    risk_scores: RiskScores


def _risk_level(score: float) -> RiskLevel:
    """Map numeric risk score to risk level enum."""
    if score < 0.25:
        return RiskLevel.LOW
    if score < 0.50:
        return RiskLevel.MEDIUM
    if score < 0.75:
        return RiskLevel.HIGH
    return RiskLevel.CRITICAL


def evaluate_supplier_risk(env: Environment, inp: SupplierRiskInput) -> SupplierRiskOutput:
    """Evaluate risk for one or more suppliers."""
    start = time.perf_counter()
    supplier_ids = inp.supplier_ids or [s.supplier_id for s in env.get_suppliers(inp.product_id)]

    risks: dict[str, float] = {}
    for sid in supplier_ids:
        supplier = env.get_supplier(sid)
        # Risk = disruption probability adjusted by low reliability
        risk = supplier.disruption_probability + (1 - supplier.reliability) * 0.3
        risks[sid] = round(min(1.0, risk), 3)

    avg = statistics.mean(risks.values()) if risks else 0.0
    latency = (time.perf_counter() - start) * 1000
    logger.info(
        "tool.evaluate_supplier_risk",
        product_id=inp.product_id,
        avg_risk=avg,
        latency_ms=latency,
    )
    return SupplierRiskOutput(
        product_id=inp.product_id,
        supplier_risks=risks,
        average_supplier_risk=round(avg, 3),
    )


def evaluate_transport_risk(env: Environment, inp: TransportRiskInput) -> TransportRiskOutput:
    """Evaluate transport mode risk based on reliability."""
    start = time.perf_counter()
    option = env.get_transport_option(inp.option_id)
    transport_risk = 1.0 - option.reliability

    latency = (time.perf_counter() - start) * 1000
    logger.info(
        "tool.evaluate_transport_risk",
        option_id=inp.option_id,
        transport_risk=transport_risk,
        latency_ms=latency,
    )
    return TransportRiskOutput(
        option_id=inp.option_id,
        transport_risk=round(transport_risk, 3),
        reliability=option.reliability,
    )


def evaluate_demand_risk(env: Environment, inp: DemandRiskInput) -> DemandRiskOutput:
    """Evaluate demand forecast risk based on variability and confidence."""
    start = time.perf_counter()
    history = env.get_demand_history(inp.product_id)
    quantities = [r.demand_quantity for r in history]
    if not quantities:
        raise MissingEntityError("Demand history for risk", inp.product_id)

    mean = statistics.mean(quantities)
    std = statistics.stdev(quantities) if len(quantities) > 1 else 0
    variability = std / mean if mean > 0 else 1.0
    demand_risk = min(1.0, variability * 0.5 + (1 - inp.forecast_confidence) * 0.5)

    latency = (time.perf_counter() - start) * 1000
    logger.info(
        "tool.evaluate_demand_risk",
        product_id=inp.product_id,
        demand_risk=demand_risk,
        latency_ms=latency,
    )
    return DemandRiskOutput(
        product_id=inp.product_id,
        demand_risk=round(demand_risk, 3),
        forecast_confidence=inp.forecast_confidence,
        demand_variability=round(variability, 3),
    )


def calculate_overall_risk(inp: OverallRiskInput) -> OverallRiskOutput:
    """Calculate weighted overall risk score."""
    start = time.perf_counter()
    overall = (
        inp.weight_supplier * inp.supplier_risk
        + inp.weight_transport * inp.transport_risk
        + inp.weight_demand * inp.demand_risk
    )
    overall = min(1.0, max(0.0, overall))

    scores = RiskScores(
        supplier_risk=inp.supplier_risk,
        transport_risk=inp.transport_risk,
        demand_risk=inp.demand_risk,
        overall_risk=round(overall, 3),
        risk_level=_risk_level(overall),
    )

    latency = (time.perf_counter() - start) * 1000
    logger.info(
        "tool.calculate_overall_risk",
        overall_risk=overall,
        risk_level=scores.risk_level.value,
        latency_ms=latency,
    )
    return OverallRiskOutput(risk_scores=scores)
