"""Demand planning tools — history, forecast, anomaly detection."""

from __future__ import annotations

import statistics
import time

import structlog
from pydantic import BaseModel, Field

from core.exceptions import MissingEntityError
from environment.protocol import Environment

logger = structlog.get_logger(__name__)


class DemandHistoryInput(BaseModel):
    """Input for get_demand_history tool."""

    product_id: str
    days: int = Field(default=90, ge=1)


class DemandHistoryOutput(BaseModel):
    """Output from get_demand_history tool."""

    product_id: str
    records: list[dict]
    total_days: int
    average_daily_demand: float


class ForecastInput(BaseModel):
    """Input for forecast_demand tool."""

    product_id: str
    horizon_days: int = Field(default=30, ge=1)
    forecast_method: str = "weighted_moving_average"


class ForecastOutput(BaseModel):
    """Output from forecast_demand tool."""

    product_id: str
    forecast_demand: int = Field(ge=0)
    forecast_confidence: float = Field(ge=0, le=1)
    horizon_days: int
    method: str


class AnomalyInput(BaseModel):
    """Input for detect_demand_anomaly tool."""

    product_id: str
    threshold_std: float = Field(default=2.0, gt=0)


class AnomalyOutput(BaseModel):
    """Output from detect_demand_anomaly tool."""

    product_id: str
    anomaly_detected: bool
    anomaly_dates: list[str]
    latest_demand: int
    mean_demand: float
    std_demand: float


def get_demand_history(env: Environment, inp: DemandHistoryInput) -> DemandHistoryOutput:
    """Retrieve historical demand for a product."""
    start = time.perf_counter()
    records = env.get_demand_history(inp.product_id)
    if len(records) > inp.days:
        records = records[-inp.days:]
    if not records:
        raise MissingEntityError("Demand history", inp.product_id)

    record_dicts = [
        {"date": r.date.isoformat(), "demand_quantity": r.demand_quantity}
        for r in records
    ]
    avg = statistics.mean(r.demand_quantity for r in records)
    latency = (time.perf_counter() - start) * 1000
    logger.info(
        "tool.get_demand_history",
        product_id=inp.product_id,
        records=len(records),
        latency_ms=latency,
    )
    return DemandHistoryOutput(
        product_id=inp.product_id,
        records=record_dicts,
        total_days=len(records),
        average_daily_demand=round(avg, 2),
    )


def forecast_demand(env: Environment, inp: ForecastInput) -> ForecastOutput:
    """Forecast demand using weighted moving average over history."""
    start = time.perf_counter()
    history = env.get_demand_history(inp.product_id)
    quantities = [r.demand_quantity for r in history]

    if len(quantities) < 7:
        raise MissingEntityError("Insufficient demand history", inp.product_id)

    # Weighted moving average: recent days weighted more heavily
    window = min(30, len(quantities))
    recent = quantities[-window:]
    weights = list(range(1, len(recent) + 1))
    weighted_avg = sum(q * w for q, w in zip(recent, weights)) / sum(weights)
    daily_forecast = weighted_avg

    # Scale to horizon (monthly forecast for 30-day horizon)
    forecast_total = int(daily_forecast * inp.horizon_days)

    # Confidence based on coefficient of variation
    std = statistics.stdev(recent) if len(recent) > 1 else 0
    cv = std / weighted_avg if weighted_avg > 0 else 1.0
    confidence = max(0.5, min(0.95, 1.0 - cv * 0.5))

    latency = (time.perf_counter() - start) * 1000
    logger.info(
        "tool.forecast_demand",
        product_id=inp.product_id,
        forecast=forecast_total,
        confidence=confidence,
        latency_ms=latency,
    )
    return ForecastOutput(
        product_id=inp.product_id,
        forecast_demand=forecast_total,
        forecast_confidence=round(confidence, 3),
        horizon_days=inp.horizon_days,
        method=inp.forecast_method,
    )


def detect_demand_anomaly(env: Environment, inp: AnomalyInput) -> AnomalyOutput:
    """Detect demand anomalies using standard deviation threshold."""
    start = time.perf_counter()
    history = env.get_demand_history(inp.product_id)
    quantities = [r.demand_quantity for r in history]

    mean = statistics.mean(quantities)
    std = statistics.stdev(quantities) if len(quantities) > 1 else 0.0
    threshold = mean + inp.threshold_std * std

    anomaly_dates: list[str] = []
    for record in history:
        if record.demand_quantity > threshold:
            anomaly_dates.append(record.date.isoformat())

    latest = quantities[-1] if quantities else 0
    anomaly = latest > threshold or len(anomaly_dates) > 0

    latency = (time.perf_counter() - start) * 1000
    logger.info(
        "tool.detect_demand_anomaly",
        product_id=inp.product_id,
        anomaly_detected=anomaly,
        latency_ms=latency,
    )
    return AnomalyOutput(
        product_id=inp.product_id,
        anomaly_detected=anomaly,
        anomaly_dates=anomaly_dates[-5:],
        latest_demand=latest,
        mean_demand=round(mean, 2),
        std_demand=round(std, 2),
    )
