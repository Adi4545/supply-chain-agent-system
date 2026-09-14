"""Runtime disruption simulation engine."""

from __future__ import annotations

import time
from typing import Any

import structlog
from sqlalchemy.orm import Session

from environment.simulator import SimulatedEnvironment
from models.database_models import SupplierORM, TransportOptionORM, WarehouseORM
from models.schemas import DisruptionEvent, DisruptionType

logger = structlog.get_logger(__name__)

# Maps disruption type to affected state fields and agents to re-invoke
DISRUPTION_AFFECTED_FIELDS: dict[DisruptionType, list[str]] = {
    DisruptionType.SUPPLIER_UNAVAILABLE: ["suppliers", "supplier_allocation", "supplier_scores"],
    DisruptionType.DEMAND_SPIKE: ["demand_forecast", "reorder_quantity"],
    DisruptionType.TRANSPORT_COST_UP: ["transport_options", "selected_transport", "total_cost"],
    DisruptionType.LEAD_TIME_DOUBLED: ["suppliers", "supplier_allocation"],
    DisruptionType.WAREHOUSE_CAPACITY_REDUCED: ["inventory", "reorder_quantity"],
    DisruptionType.MULTI_SUPPLIER_OUTAGE: ["suppliers", "supplier_allocation", "supplier_scores"],
}

DISRUPTION_REINVOKE_AGENTS: dict[DisruptionType, list[str]] = {
    DisruptionType.SUPPLIER_UNAVAILABLE: ["procurement_agent", "risk_agent"],
    DisruptionType.DEMAND_SPIKE: ["demand_agent", "inventory_agent"],
    DisruptionType.TRANSPORT_COST_UP: ["logistics_agent", "risk_agent"],
    DisruptionType.LEAD_TIME_DOUBLED: ["procurement_agent", "logistics_agent"],
    DisruptionType.WAREHOUSE_CAPACITY_REDUCED: ["inventory_agent"],
    DisruptionType.MULTI_SUPPLIER_OUTAGE: ["procurement_agent", "logistics_agent", "risk_agent"],
}


class DisruptionEngine:
    """Mutates the simulated environment at runtime."""

    def __init__(self, env: SimulatedEnvironment) -> None:
        self.env = env

    def _session(self) -> Session:
        return self.env._session_factory()

    def apply(self, event: DisruptionEvent) -> dict[str, Any]:
        """Apply disruption to environment and return mutation summary."""
        start = time.perf_counter()
        session = self._session()
        mutation: dict[str, Any] = {"disruption_type": event.disruption_type.value}

        try:
            if event.disruption_type == DisruptionType.SUPPLIER_UNAVAILABLE:
                sid = event.target_id or "SUP_A"
                supplier = session.get(SupplierORM, sid)
                if supplier:
                    supplier.capacity = 0
                    mutation["supplier_id"] = sid
                    mutation["action"] = "capacity_set_to_zero"

            elif event.disruption_type == DisruptionType.DEMAND_SPIKE:
                magnitude = event.magnitude or 0.4
                mutation["demand_multiplier"] = 1 + magnitude
                mutation["action"] = f"demand_increased_{int(magnitude*100)}pct"

            elif event.disruption_type == DisruptionType.TRANSPORT_COST_UP:
                magnitude = event.magnitude or 0.3
                for opt in session.query(TransportOptionORM).all():
                    opt.cost_per_unit *= 1 + magnitude
                mutation["cost_multiplier"] = 1 + magnitude

            elif event.disruption_type == DisruptionType.LEAD_TIME_DOUBLED:
                sid = event.target_id
                query = session.query(SupplierORM)
                if sid:
                    query = query.filter(SupplierORM.supplier_id == sid)
                for s in query.all():
                    s.lead_time_days *= 2
                mutation["action"] = "lead_time_doubled"

            elif event.disruption_type == DisruptionType.WAREHOUSE_CAPACITY_REDUCED:
                magnitude = event.magnitude or 0.3
                for wh in session.query(WarehouseORM).all():
                    wh.capacity = int(wh.capacity * (1 - magnitude))
                mutation["capacity_reduction"] = magnitude

            elif event.disruption_type == DisruptionType.MULTI_SUPPLIER_OUTAGE:
                for sid in ["SUP_A", "SUP_B"]:
                    supplier = session.get(SupplierORM, sid)
                    if supplier:
                        supplier.capacity = 0
                mutation["suppliers_affected"] = ["SUP_A", "SUP_B"]

            session.commit()
        finally:
            session.close()

        mutation["recovery_time_ms"] = (time.perf_counter() - start) * 1000
        mutation["affected_fields"] = DISRUPTION_AFFECTED_FIELDS.get(event.disruption_type, [])
        mutation["reinvoke_agents"] = DISRUPTION_REINVOKE_AGENTS.get(event.disruption_type, [])

        logger.info("disruption.applied", **mutation)
        return mutation

    @staticmethod
    def get_affected_fields(disruption_type: DisruptionType) -> list[str]:
        """Return state fields affected by a disruption type."""
        return DISRUPTION_AFFECTED_FIELDS.get(disruption_type, [])

    @staticmethod
    def get_reinvoke_agents(disruption_type: DisruptionType) -> list[str]:
        """Return agents that should be re-invoked after a disruption."""
        return DISRUPTION_REINVOKE_AGENTS.get(disruption_type, [])
