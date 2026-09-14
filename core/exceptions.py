"""Custom exceptions for the supply chain multi-agent system."""

from __future__ import annotations


class SupplyChainError(Exception):
    """Base exception for supply chain system errors."""


class MissingEntityError(SupplyChainError):
    """Raised when a requested entity does not exist in the environment."""

    def __init__(self, entity_type: str, entity_id: str) -> None:
        self.entity_type = entity_type
        self.entity_id = entity_id
        super().__init__(f"{entity_type} '{entity_id}' not found")


class OwnershipViolation(SupplyChainError):
    """Raised when an agent attempts to write fields it does not own."""

    def __init__(self, agent: str, field: str) -> None:
        self.agent = agent
        self.field = field
        super().__init__(f"Agent '{agent}' cannot write field '{field}'")


class OptimizationInfeasible(SupplyChainError):
    """Raised when the optimization solver finds no feasible solution."""

    def __init__(self, reasons: list[str]) -> None:
        self.reasons = reasons
        super().__init__(f"Optimization infeasible: {', '.join(reasons)}")


class AgentTimeoutError(SupplyChainError):
    """Raised when an agent exceeds its wall-clock timeout."""

    def __init__(self, agent: str, timeout_seconds: int) -> None:
        self.agent = agent
        self.timeout_seconds = timeout_seconds
        super().__init__(f"Agent '{agent}' timed out after {timeout_seconds}s")


class AgentValidationError(SupplyChainError):
    """Raised when an agent output fails schema validation."""

    def __init__(self, agent: str, detail: str) -> None:
        self.agent = agent
        self.detail = detail
        super().__init__(f"Agent '{agent}' validation failed: {detail}")
