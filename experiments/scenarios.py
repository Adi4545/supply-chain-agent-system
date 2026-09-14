"""Deterministic experiment scenarios."""

from __future__ import annotations

from dataclasses import dataclass

from models.schemas import UserRequest


@dataclass
class Scenario:
    """A single experiment scenario."""

    name: str
    request: UserRequest
    seed: int = 42


CANONICAL_SCENARIOS: list[Scenario] = [
    Scenario(
        name="canonical_replenishment",
        request=UserRequest(
            objective="Plan replenishment for product P001",
            product_id="P001",
        ),
    ),
    Scenario(
        name="inventory_check",
        request=UserRequest(
            objective="Check inventory levels only",
            product_id="P001",
            include_procurement=False,
            include_logistics=False,
            include_risk=False,
        ),
    ),
    Scenario(
        name="budget_constrained",
        request=UserRequest(
            objective="Plan replenishment for product P001",
            product_id="P001",
            budget=250000.0,
        ),
    ),
]
