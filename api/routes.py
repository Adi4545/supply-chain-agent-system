"""FastAPI routes for the supply chain multi-agent system."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agents.orchestrator import OrchestratorAgent
from api.dependencies import get_env, get_orchestrator
from core.time import utc_now
from environment.disruption import DisruptionEngine
from environment.simulator import SimulatedEnvironment
from experiments.configs import AGENT_CONFIGS
from models.schemas import (
    DisruptionEvent,
    ExecutionStatus,
    PlanRequest,
    PlanResponse,
    Product,
    Supplier,
    UserRequest,
)
from models.state import SupplyChainState

router = APIRouter()

_run_store: dict[str, SupplyChainState] = {}
_latest_results_dir: Path | None = None


class DisruptionRequest(BaseModel):
    """Request to simulate a disruption."""

    run_id: str
    disruption: DisruptionEvent


class ExperimentRequest(BaseModel):
    """Request to run experiments."""

    configs: str = "all"


class InventoryResponse(BaseModel):
    """Inventory snapshot response."""

    product_id: str
    quantity: int
    warehouse_id: str | None = None


class TraceResponse(BaseModel):
    """Execution trace response."""

    run_id: str
    trace_summary: str
    trace: list[dict[str, Any]]
    status: ExecutionStatus


class ExperimentRunResponse(BaseModel):
    """Experiment batch status."""

    status: str
    runs: int = 0
    output_dir: str = ""


class ExperimentResultsResponse(BaseModel):
    """Latest experiment results metadata."""

    status: str
    message: str | None = None
    output_dir: str | None = None
    results: list[dict[str, Any]] | None = None


def _plan_response(orchestrator: OrchestratorAgent, state: SupplyChainState) -> PlanResponse:
    """Build a plan response including KPI snapshot fields."""
    return PlanResponse(
        run_id=state.run_id,
        status=state.execution_status,
        final_decision=state.final_decision,
        trace_summary=orchestrator.get_trace_summary(state),
        inventory=state.inventory,
        demand_forecast=state.demand_forecast,
        reorder_quantity=state.reorder_quantity,
        forecast_confidence=state.forecast_confidence,
    )


@router.post("/plan", response_model=PlanResponse)
async def plan(
    request: PlanRequest,
    orchestrator: OrchestratorAgent = Depends(get_orchestrator),
) -> PlanResponse:
    """Run the planning pipeline."""
    user_request = UserRequest(
        objective=request.objective,
        product_id=request.product_id,
        delivery_deadline_days=request.delivery_deadline_days,
        budget=request.budget,
    )
    state = await orchestrator.run(user_request)
    _run_store[state.run_id] = state
    return _plan_response(orchestrator, state)


@router.get("/inventory/{product_id}", response_model=InventoryResponse)
def get_inventory(
    product_id: str,
    env: SimulatedEnvironment = Depends(get_env),
) -> InventoryResponse:
    """Get current inventory for a product."""
    qty = env.get_inventory(product_id)
    return InventoryResponse(product_id=product_id, quantity=qty)


@router.get("/suppliers", response_model=list[Supplier])
def list_suppliers(
    product_id: str = "P001",
    env: SimulatedEnvironment = Depends(get_env),
) -> list[Supplier]:
    """List suppliers for a product."""
    return env.get_suppliers(product_id)


@router.get("/products", response_model=list[Product])
def list_products(env: SimulatedEnvironment = Depends(get_env)) -> list[Product]:
    """List all products."""
    return env.list_products()


@router.post("/simulate-disruption", response_model=PlanResponse)
async def simulate_disruption(
    request: DisruptionRequest,
    orchestrator: OrchestratorAgent = Depends(get_orchestrator),
    env: SimulatedEnvironment = Depends(get_env),
) -> PlanResponse:
    """Apply disruption and replan."""
    state = _run_store.get(request.run_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Run {request.run_id} not found")

    engine = DisruptionEngine(env)
    mutation = engine.apply(request.disruption)
    state = await orchestrator.replan(state, request.disruption, mutation)
    _run_store[state.run_id] = state
    return _plan_response(orchestrator, state)


@router.post("/run-experiment", response_model=ExperimentRunResponse)
async def run_experiment(request: ExperimentRequest) -> ExperimentRunResponse:
    """Launch experiment batch."""
    global _latest_results_dir
    from experiments.runner import run_all, save_results

    timestamp = utc_now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(f"results/{timestamp}")
    configs = list(AGENT_CONFIGS.keys())
    if request.configs != "all":
        configs = [c.strip() for c in request.configs.split(",")]

    results = await run_all(configs, output_dir)
    save_results(results, output_dir)
    _latest_results_dir = output_dir
    return ExperimentRunResponse(status="completed", runs=len(results), output_dir=str(output_dir))


@router.get("/experiment-results", response_model=ExperimentResultsResponse)
def get_experiment_results() -> ExperimentResultsResponse:
    """Get latest experiment results metadata."""
    if _latest_results_dir is None or not _latest_results_dir.exists():
        return ExperimentResultsResponse(status="no_results", message="No experiments run yet")
    json_path = _latest_results_dir / "results.json"
    if json_path.exists():
        import json

        with open(json_path) as f:
            data = json.load(f)
        return ExperimentResultsResponse(
            status="ok",
            output_dir=str(_latest_results_dir),
            results=data,
        )
    return ExperimentResultsResponse(status="no_results")


@router.get("/execution-trace/{run_id}", response_model=TraceResponse)
def get_execution_trace(
    run_id: str,
    orchestrator: OrchestratorAgent = Depends(get_orchestrator),
) -> TraceResponse:
    """Get execution trace for a run."""
    state = _run_store.get(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return TraceResponse(
        run_id=run_id,
        trace_summary=orchestrator.get_trace_summary(state),
        trace=[t.model_dump(mode="json") for t in state.trace],
        status=state.execution_status,
    )
