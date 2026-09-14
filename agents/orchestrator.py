"""Orchestrator agent — coordinates pipeline without doing agents' work."""

from __future__ import annotations

import time
from typing import Any

import structlog

from agents.demand import DemandAgent
from agents.inventory import InventoryAgent
from agents.logistics import LogisticsAgent
from agents.procurement import ProcurementAgent
from agents.risk import RiskAgent
from config.settings import Settings, get_settings
from core.exceptions import AgentTimeoutError, AgentValidationError, OptimizationInfeasible
from core.trace import build_trace_summary
from environment.disruption import DisruptionEngine
from environment.protocol import Environment
from llm.protocol import LLMProvider
from models.schemas import (
    ConflictResolution,
    ExecutionStatus,
    FinalDecision,
    RiskLevel,
    TraceEntry,
    UserRequest,
)
from models.state import SupplyChainState
from optimization.optimizer import OptimizationInput, optimize

logger = structlog.get_logger(__name__)


class OrchestratorAgent:
    """Coordinates agent pipeline, conflict resolution, and optimization."""

    name = "orchestrator"

    def __init__(self, env: Environment, llm: LLMProvider, settings: Settings | None = None) -> None:
        self.env = env
        self.llm = llm
        self.settings = settings or get_settings()
        self.demand_agent = DemandAgent(env)
        self.inventory_agent = InventoryAgent(env)
        self.procurement_agent = ProcurementAgent(env)
        self.logistics_agent = LogisticsAgent(env)
        self.risk_agent = RiskAgent(env)
        self.agent_map = {
            "demand_agent": self.demand_agent,
            "inventory_agent": self.inventory_agent,
            "procurement_agent": self.procurement_agent,
            "logistics_agent": self.logistics_agent,
            "risk_agent": self.risk_agent,
            "demand_anomaly_agent": self.demand_agent,
            "capacity_agent": self.inventory_agent,
            "reliability_agent": self.procurement_agent,
            "transport_cost_agent": self.logistics_agent,
            "disruption_risk_agent": self.risk_agent,
        }

    def _determine_agents(self, request: UserRequest) -> list[str]:
        """Decide which agents to invoke based on user objective."""
        agents = ["demand_agent", "inventory_agent"]
        objective_lower = request.objective.lower()

        if request.include_procurement or "supplier" in objective_lower or "procure" in objective_lower:
            agents.append("procurement_agent")
        if request.include_logistics or "transport" in objective_lower or "logistics" in objective_lower:
            agents.append("logistics_agent")
        if request.include_risk or "risk" in objective_lower:
            agents.append("risk_agent")

        # Full planning request includes all agents
        if "plan" in objective_lower or "replenish" in objective_lower:
            agents = [
                "demand_agent",
                "inventory_agent",
                "procurement_agent",
                "logistics_agent",
                "risk_agent",
            ]
        return agents

    def _get_state_slice(self, state: SupplyChainState, agent_name: str) -> dict[str, Any]:
        """Return relevant state slice for an agent."""
        slices: dict[str, list[str]] = {
            "demand_agent": ["product", "user_request", "demand_history"],
            "inventory_agent": ["product", "demand_forecast", "forecast_confidence"],
            "procurement_agent": ["product", "reorder_quantity", "suppliers"],
            "logistics_agent": ["product", "reorder_quantity", "supplier_allocation"],
            "risk_agent": ["product", "forecast_confidence", "selected_transport"],
        }
        fields = slices.get(agent_name, [])
        result = state.get_slice(fields)
        if state.product:
            result["product_id"] = state.product.product_id
        elif state.user_request:
            result["product_id"] = state.user_request.product_id
        else:
            result["product_id"] = "P001"
        return result

    def _apply_agent_output(self, state: SupplyChainState, agent_name: str, output: Any) -> None:
        """Write agent output to owned state fields."""
        if agent_name == "demand_agent":
            state.update_slice(
                agent_name,
                {
                    "demand_forecast": output.forecast_demand,
                    "forecast_confidence": output.forecast_confidence,
                },
            )
        elif agent_name == "inventory_agent":
            state.update_slice(
                agent_name,
                {
                    "inventory": output.current_inventory,
                    "safety_stock": output.safety_stock,
                    "reorder_quantity": output.recommended_order_quantity,
                },
            )
        elif agent_name == "procurement_agent":
            state.update_slice(
                agent_name,
                {
                    "suppliers": self.env.get_suppliers(output.product_id),
                    "supplier_scores": output.supplier_scores,
                    "supplier_allocation": output.supplier_allocation,
                },
            )
        elif agent_name == "logistics_agent":
            transport = self.env.get_transport_option(output.selected_transport_id)
            state.update_slice(
                agent_name,
                {
                    "transport_options": self.env.get_transport_options(output.product_id),
                    "selected_transport": transport,
                },
            )
        elif agent_name == "risk_agent":
            state.update_slice(agent_name, {"risk_scores": output.risk_scores})

        state.messages.append(output.model_dump(mode="json"))

    def _resolve_conflicts(self, state: SupplyChainState) -> ConflictResolution | None:
        """Apply weighted scoring when agents provide competing recommendations."""
        if not state.supplier_scores:
            return None

        weights = {
            "cost": self.settings.opt_weights.cost,
            "delivery": self.settings.opt_weights.delivery,
            "reliability": self.settings.opt_weights.reliability,
            "risk": self.settings.opt_weights.risk,
            "inventory": self.settings.opt_weights.inventory,
        }

        recommendations: dict[str, Any] = {}
        scoring: dict[str, float] = {}

        if state.supplier_scores:
            best = max(state.supplier_scores, key=lambda s: s.total_score)
            recommendations["procurement"] = best.supplier_id
            scoring["procurement"] = best.total_score

        if state.selected_transport:
            recommendations["logistics"] = state.selected_transport.option_id
            scoring["logistics"] = state.selected_transport.reliability

        if state.risk_scores:
            recommendations["risk"] = state.risk_scores.risk_level.value
            scoring["risk"] = 1.0 - state.risk_scores.overall_risk

        winner = max(scoring, key=scoring.get) if scoring else "none"
        return ConflictResolution(
            conflicting_agents=list(recommendations.keys()),
            recommendations=recommendations,
            scoring_breakdown=scoring,
            weights=weights,
            winner=winner,
            rationale=f"Selected {winner} based on weighted score",
        )

    def _run_optimizer(self, state: SupplyChainState) -> None:
        """Invoke OR-Tools optimizer and write results to state."""
        if state.reorder_quantity is None or state.reorder_quantity <= 0:
            return

        product_id = state.product.product_id if state.product else "P001"
        suppliers = state.suppliers or self.env.get_suppliers(product_id)
        transport_options = state.transport_options or self.env.get_transport_options(product_id)

        risk_scores = state.risk_scores
        opt_input = OptimizationInput(
            product_id=product_id,
            demand=state.demand_forecast or 12000,
            current_inventory=state.inventory or 3500,
            safety_stock=state.safety_stock or 2000,
            reorder_quantity=state.reorder_quantity,
            suppliers=suppliers,
            transport_options=transport_options,
            selected_transport_id=(
                state.selected_transport.option_id if state.selected_transport else None
            ),
            supplier_risk=risk_scores.supplier_risk if risk_scores else 0.3,
            transport_risk=risk_scores.transport_risk if risk_scores else 0.2,
            budget=(
                state.constraints.budget
                if state.constraints.budget is not None
                else (state.user_request.budget if state.user_request else None)
            ),
            delivery_deadline_days=(
                state.constraints.delivery_deadline_days
                or (state.user_request.delivery_deadline_days if state.user_request else None)
            ),
            warehouse_capacity=state.constraints.warehouse_capacity,
        )

        result = optimize(opt_input)
        if not result.feasible:
            raise OptimizationInfeasible(result.infeasibility_reasons)

        state.update_field("optimizer", "total_cost", result.total_cost)
        state.supplier_allocation = result.supplier_allocation

    def _build_final_decision(
        self,
        state: SupplyChainState,
        conflict: ConflictResolution | None,
    ) -> FinalDecision:
        """Construct final recommendation from state and optimizer output."""
        product_id = state.product.product_id if state.product else "P001"
        order_qty = state.reorder_quantity or 0
        allocation = state.supplier_allocation or []
        transport = state.selected_transport.mode if state.selected_transport else "ground"
        total_cost = state.total_cost or 0.0
        delivery_days = max((a.expected_delivery_days for a in allocation), default=7)
        risk_level = state.risk_scores.risk_level if state.risk_scores else RiskLevel.MEDIUM
        confidence = state.forecast_confidence or 0.8

        requires_approval = True
        assumptions = [
            f"Forecast demand: {state.demand_forecast} units",
            f"Current inventory: {state.inventory} units",
            f"Safety stock target: {state.safety_stock} units",
        ]
        if conflict:
            assumptions.append(f"Conflict resolved: {conflict.rationale}")
        assumptions.extend(state.errors)

        if order_qty > self.settings.safety.max_order_quantity:
            assumptions.append(
                f"Order quantity {order_qty} exceeds max {self.settings.safety.max_order_quantity}"
            )
        if total_cost > self.settings.safety.max_spend:
            assumptions.append(
                f"Total cost {total_cost} exceeds max spend {self.settings.safety.max_spend}"
            )

        return FinalDecision(
            decision=f"Order {order_qty} units of {product_id} from recommended suppliers via {transport}",
            order_quantity=order_qty,
            supplier_allocation=allocation,
            transportation=transport,
            expected_cost=total_cost,
            expected_delivery_days=delivery_days,
            risk_level=risk_level,
            confidence=confidence,
            reasoning_summary=(
                f"Based on forecast demand of {state.demand_forecast}, current inventory "
                f"of {state.inventory}, and safety stock of {state.safety_stock}, "
                f"recommend ordering {order_qty} units."
            ),
            assumptions=assumptions,
            requires_human_approval=requires_approval,
        )

    async def run(
        self,
        request: UserRequest,
        agents: list[str] | None = None,
    ) -> SupplyChainState:
        """Execute full planning pipeline."""
        start = time.perf_counter()
        state = SupplyChainState(seed=self.settings.random_seed)
        state.user_request = request
        state.execution_status = ExecutionStatus.RUNNING
        if request.budget is not None:
            state.constraints.budget = request.budget
        if request.delivery_deadline_days is not None:
            state.constraints.delivery_deadline_days = request.delivery_deadline_days

        try:
            state.product = self.env.get_product(request.product_id)
            agents_to_run = agents or self._determine_agents(request)
            logger.info("orchestrator.start", run_id=state.run_id, agents=agents_to_run)

            for agent_name in agents_to_run:
                elapsed = time.perf_counter() - start
                if elapsed > self.settings.orch.total_timeout_seconds:
                    raise AgentTimeoutError("orchestrator", self.settings.orch.total_timeout_seconds)

                agent = self.agent_map.get(agent_name)
                if agent is None:
                    raise AgentValidationError("orchestrator", f"Unknown agent '{agent_name}'")
                state_slice = self._get_state_slice(state, agent.name)
                output = await agent.run(state, state_slice, self.llm)
                self._apply_agent_output(state, agent.name, output)

            conflict = self._resolve_conflicts(state)
            try:
                self._run_optimizer(state)
            except OptimizationInfeasible as exc:
                state.append_error(str(exc))
                if state.total_cost is None:
                    state.update_field("optimizer", "total_cost", 0.0)
            final = self._build_final_decision(state, conflict)
            state.update_field("orchestrator", "final_decision", final)
            state.execution_status = ExecutionStatus.COMPLETED

            logger.info(
                "orchestrator.complete",
                run_id=state.run_id,
                latency_ms=(time.perf_counter() - start) * 1000,
            )
        except Exception as exc:
            state.execution_status = ExecutionStatus.FAILED
            state.append_error(str(exc))
            logger.error("orchestrator.failed", run_id=state.run_id, error=str(exc))
            raise

        return state

    async def replan(
        self,
        state: SupplyChainState,
        disruption: Any,
        mutation: dict[str, Any],
    ) -> SupplyChainState:
        """Targeted replanning after a disruption event."""
        from models.schemas import DisruptionType

        replan_start = time.perf_counter()
        state.execution_status = ExecutionStatus.REPLANNING
        prior_cost = state.total_cost or 0.0

        disruption_type = DisruptionType(disruption.disruption_type)
        agents_to_reinvoke = DisruptionEngine.get_reinvoke_agents(disruption_type)

        # Apply demand spike to state if needed
        if disruption_type == DisruptionType.DEMAND_SPIKE and state.demand_forecast:
            multiplier = mutation.get("demand_multiplier", 1.4)
            state.update_field(
                "demand_agent",
                "demand_forecast",
                int(state.demand_forecast * multiplier),
            )

        for agent_name in agents_to_reinvoke:
            agent = self.agent_map.get(agent_name)
            if agent:
                state_slice = self._get_state_slice(state, agent.name)
                output = await agent.run(state, state_slice, self.llm)
                self._apply_agent_output(state, agent.name, output)

        try:
            self._run_optimizer(state)
        except OptimizationInfeasible as exc:
            state.append_error(str(exc))
        conflict = self._resolve_conflicts(state)
        final = self._build_final_decision(state, conflict)
        final.revision_reason = f"Replan after {disruption_type.value}"
        final.cost_delta = (state.total_cost or 0) - prior_cost
        state.update_field("orchestrator", "final_decision", final)
        state.execution_status = ExecutionStatus.COMPLETED

        recovery_ms = (time.perf_counter() - replan_start) * 1000
        state.append_trace(
            TraceEntry(
                run_id=state.run_id,
                agent="orchestrator",
                step="replan_complete",
                decision=f"recovery_ms={recovery_ms:.0f}",
                latency_ms=recovery_ms,
            )
        )
        return state

    def get_trace_summary(self, state: SupplyChainState) -> str:
        """Return human-readable trace string."""
        return build_trace_summary(state)
