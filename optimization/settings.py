"""Optimization engine settings."""

from __future__ import annotations

from pydantic import BaseModel, Field


class OptimizationSettings(BaseModel):
    """Penalty rates and cost factors for the optimizer."""

    holding_cost_rate: float = Field(default=0.02, ge=0)
    stockout_penalty_per_unit: float = Field(default=50.0, ge=0)
    risk_penalty_multiplier: float = Field(default=1000.0, ge=0)
