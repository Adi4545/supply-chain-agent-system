"""Pydantic schemas for domain entities, messages, and decisions."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from core.time import utc_now


class RiskLevel(str, Enum):
    """Overall risk classification."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ExecutionStatus(str, Enum):
    """Pipeline execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    REPLANNING = "replanning"


class Product(BaseModel):
    """Product master data."""

    product_id: str
    name: str
    category: str
    unit_cost: float = Field(ge=0)
    selling_price: float = Field(ge=0)


class Supplier(BaseModel):
    """Supplier master data."""

    supplier_id: str
    name: str
    product_ids: list[str]
    unit_price: float = Field(ge=0)
    capacity: int = Field(ge=0)
    lead_time_days: int = Field(ge=0)
    reliability: float = Field(ge=0, le=1)
    disruption_probability: float = Field(ge=0, le=1, default=0.05)


class Warehouse(BaseModel):
    """Warehouse capacity and inventory snapshot."""

    warehouse_id: str
    location: str
    capacity: int = Field(ge=0)
    current_inventory: dict[str, int] = Field(default_factory=dict)


class DemandRecord(BaseModel):
    """Historical demand data point."""

    date: datetime
    product_id: str
    demand_quantity: int = Field(ge=0)


class TransportOption(BaseModel):
    """Transportation mode option."""

    option_id: str
    mode: str
    carrier: str
    cost_per_unit: float = Field(ge=0)
    delivery_time_days: int = Field(ge=0)
    capacity: int = Field(ge=0)
    reliability: float = Field(ge=0, le=1)


class SupplierAllocation(BaseModel):
    """Quantity allocated to a supplier."""

    supplier_id: str
    quantity: int = Field(ge=0)
    unit_price: float = Field(ge=0)
    expected_delivery_days: int = Field(ge=0)


class SupplierScore(BaseModel):
    """Scored supplier recommendation."""

    supplier_id: str
    cost_score: float
    delivery_score: float
    reliability_score: float
    total_score: float


class RiskScores(BaseModel):
    """Risk assessment breakdown."""

    supplier_risk: float = Field(ge=0, le=1)
    transport_risk: float = Field(ge=0, le=1)
    demand_risk: float = Field(ge=0, le=1)
    overall_risk: float = Field(ge=0, le=1)
    risk_level: RiskLevel


class Constraints(BaseModel):
    """Active planning constraints."""

    budget: float | None = None
    delivery_deadline_days: int | None = None
    min_safety_stock: int | None = None
    max_order_quantity: int | None = None
    warehouse_capacity: int | None = None


class TraceEntry(BaseModel):
    """Single observability trace record."""

    timestamp: datetime = Field(default_factory=utc_now)
    run_id: str
    agent: str
    step: str
    input_data: dict[str, Any] = Field(default_factory=dict)
    tool_called: str | None = None
    tool_args: dict[str, Any] = Field(default_factory=dict)
    tool_result: dict[str, Any] | None = None
    decision: str | None = None
    confidence: float | None = None
    latency_ms: float | None = None
    error: str | None = None


class AgentMessage(BaseModel):
    """Base typed inter-agent message."""

    correlation_id: str = Field(default_factory=lambda: str(uuid4()))
    agent: str
    message_type: str
    timestamp: datetime = Field(default_factory=utc_now)


class DemandForecastMessage(AgentMessage):
    """Demand agent output message."""

    agent: str = "demand_agent"
    message_type: str = "demand_forecast"
    product_id: str
    forecast_demand: int = Field(ge=0)
    forecast_confidence: float = Field(ge=0, le=1)
    anomaly_detected: bool = False


class InventoryRecommendationMessage(AgentMessage):
    """Inventory agent output message."""

    agent: str = "inventory_agent"
    message_type: str = "inventory_recommendation"
    product_id: str
    current_inventory: int = Field(ge=0)
    forecast_demand: int = Field(ge=0)
    safety_stock: int = Field(ge=0)
    recommended_order_quantity: int = Field(ge=0)
    warehouse_capacity_ok: bool = True


class ProcurementRecommendationMessage(AgentMessage):
    """Procurement agent output message."""

    agent: str = "procurement_agent"
    message_type: str = "procurement_recommendation"
    product_id: str
    recommended_suppliers: list[str]
    supplier_scores: list[SupplierScore]
    supplier_allocation: list[SupplierAllocation] = Field(default_factory=list)


class LogisticsRecommendationMessage(AgentMessage):
    """Logistics agent output message."""

    agent: str = "logistics_agent"
    message_type: str = "logistics_recommendation"
    product_id: str
    selected_transport_id: str
    transport_mode: str
    estimated_delivery_days: int = Field(ge=0)
    shipping_cost: float = Field(ge=0)


class RiskAssessmentMessage(AgentMessage):
    """Risk agent output message."""

    agent: str = "risk_agent"
    message_type: str = "risk_assessment"
    product_id: str
    risk_scores: RiskScores


class ConflictResolution(BaseModel):
    """Record of orchestrator conflict resolution."""

    conflicting_agents: list[str]
    recommendations: dict[str, Any]
    scoring_breakdown: dict[str, float]
    weights: dict[str, float]
    winner: str
    rationale: str


class FinalDecision(BaseModel):
    """Final planning recommendation — always requires human approval."""

    decision: str
    order_quantity: int = Field(ge=0)
    supplier_allocation: list[SupplierAllocation]
    transportation: str
    expected_cost: float = Field(ge=0)
    expected_delivery_days: int = Field(ge=0)
    risk_level: RiskLevel
    confidence: float = Field(ge=0, le=1)
    reasoning_summary: str
    assumptions: list[str] = Field(default_factory=list)
    requires_human_approval: bool = True
    revision_reason: str | None = None
    cost_delta: float | None = None

    @field_validator("requires_human_approval")
    @classmethod
    def must_require_approval(cls, value: bool) -> bool:
        """Enforce recommendation-only mode."""
        if not value:
            msg = "requires_human_approval must always be True"
            raise ValueError(msg)
        return value


class UserRequest(BaseModel):
    """Parsed user planning objective."""

    objective: str
    product_id: str = "P001"
    include_logistics: bool = True
    include_risk: bool = True
    include_procurement: bool = True
    delivery_deadline_days: int | None = None
    budget: float | None = None


class PlanRequest(BaseModel):
    """API request to run planning pipeline."""

    objective: str = "Plan replenishment for product P001"
    product_id: str = "P001"
    delivery_deadline_days: int | None = None
    budget: float | None = None


class PlanResponse(BaseModel):
    """API response from planning pipeline."""

    run_id: str
    status: ExecutionStatus
    final_decision: FinalDecision | None = None
    trace_summary: str = ""
    inventory: int | None = None
    demand_forecast: int | None = None
    reorder_quantity: int | None = None
    forecast_confidence: float | None = None


class DisruptionType(str, Enum):
    """Supported disruption event types."""

    SUPPLIER_UNAVAILABLE = "supplier_unavailable"
    DEMAND_SPIKE = "demand_spike"
    TRANSPORT_COST_UP = "transport_cost_up"
    LEAD_TIME_DOUBLED = "lead_time_doubled"
    WAREHOUSE_CAPACITY_REDUCED = "warehouse_capacity_reduced"
    MULTI_SUPPLIER_OUTAGE = "multi_supplier_outage"


class DisruptionEvent(BaseModel):
    """Disruption simulation event."""

    disruption_type: DisruptionType
    target_id: str | None = None
    magnitude: float | None = None
    description: str = ""
