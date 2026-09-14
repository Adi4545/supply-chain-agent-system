"""Shared supply chain planning state for a single run."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from core.exceptions import OwnershipViolation
from core.ownership import validate_ownership
from models.schemas import (
    Constraints,
    ExecutionStatus,
    FinalDecision,
    Product,
    RiskScores,
    Supplier,
    SupplierAllocation,
    SupplierScore,
    TraceEntry,
    TransportOption,
    UserRequest,
)


class SupplyChainState(BaseModel):
    """Central mutable state object for one planning run."""

    run_id: str = Field(default_factory=lambda: str(uuid4()))
    seed: int = 42
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    user_request: UserRequest | None = None
    product: Product | None = None

    demand_history: list[dict[str, Any]] = Field(default_factory=list)
    demand_forecast: int | None = None
    forecast_confidence: float | None = None

    inventory: int | None = None
    safety_stock: int | None = None
    reorder_quantity: int | None = None

    suppliers: list[Supplier] = Field(default_factory=list)
    supplier_scores: list[SupplierScore] = Field(default_factory=list)
    supplier_allocation: list[SupplierAllocation] = Field(default_factory=list)

    transport_options: list[TransportOption] = Field(default_factory=list)
    selected_transport: TransportOption | None = None

    risk_scores: RiskScores | None = None
    constraints: Constraints = Field(default_factory=Constraints)
    total_cost: float | None = None

    final_decision: FinalDecision | None = None
    execution_status: ExecutionStatus = ExecutionStatus.PENDING
    trace: list[TraceEntry] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    agent_iterations: dict[str, int] = Field(default_factory=dict)
    messages: list[dict[str, Any]] = Field(default_factory=list)

    def update_field(self, agent: str, field: str, value: Any) -> None:
        """Update a single owned field with ownership validation."""
        validate_ownership(agent, field)
        if not hasattr(self, field):
            raise OwnershipViolation(agent, field)
        setattr(self, field, value)
        self.updated_at = datetime.utcnow()

    def update_slice(self, agent: str, payload: dict[str, Any]) -> None:
        """Update multiple owned fields from a payload dict."""
        for field, value in payload.items():
            self.update_field(agent, field, value)

    def append_trace(self, entry: TraceEntry) -> None:
        """Append an observability trace entry."""
        self.trace.append(entry)
        self.updated_at = datetime.utcnow()

    def append_error(self, error: str) -> None:
        """Record an error message."""
        self.errors.append(error)
        self.updated_at = datetime.utcnow()

    def increment_agent_iteration(self, agent: str) -> int:
        """Increment and return iteration count for an agent."""
        current = self.agent_iterations.get(agent, 0) + 1
        self.agent_iterations[agent] = current
        self.updated_at = datetime.utcnow()
        return current

    def get_slice(self, fields: list[str]) -> dict[str, Any]:
        """Return a read-only slice of state fields."""
        return {field: getattr(self, field) for field in fields}

    def to_serializable(self) -> dict[str, Any]:
        """Return JSON-serializable dict representation."""
        return self.model_dump(mode="json")

    @classmethod
    def from_serializable(cls, data: dict[str, Any]) -> SupplyChainState:
        """Restore state from serialized dict."""
        return cls.model_validate(data)
