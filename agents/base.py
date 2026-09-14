"""Base agent with bounded tool-calling reasoning loop."""

from __future__ import annotations

import inspect
import time
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Any, Callable, get_type_hints

import structlog
from pydantic import BaseModel

from config.settings import get_settings
from core.exceptions import AgentTimeoutError, AgentValidationError
from environment.protocol import Environment
from llm.protocol import LLMProvider
from models.schemas import AgentMessage, TraceEntry
from models.state import SupplyChainState

logger = structlog.get_logger(__name__)


@lru_cache(maxsize=64)
def _tool_signature(tool_fn: Callable[..., Any]) -> tuple[frozenset[str], type[BaseModel] | None]:
    """Cache inspect results for tool call dispatch."""
    params = inspect.signature(tool_fn).parameters
    hints = get_type_hints(tool_fn)
    input_cls = hints.get("inp")
    if input_cls is not None and isinstance(input_cls, type) and issubclass(input_cls, BaseModel):
        return frozenset(params.keys()), input_cls
    return frozenset(params.keys()), None


def enrich_tool_arguments(
    tool_name: str,
    arguments: dict[str, Any],
    state_slice: dict[str, Any],
    tool_results: dict[str, Any],
) -> dict[str, Any]:
    """Fill tool arguments from prior tool results and the state slice.

    The LLM may propose placeholder args; numerics always come from tools/state.
    """
    merged = dict(arguments)
    product_id = state_slice.get("product_id") or merged.get("product_id") or "P001"
    merged.setdefault("product_id", product_id)

    inventory = tool_results.get("get_inventory")
    safety = tool_results.get("calculate_safety_stock")
    reorder = tool_results.get("calculate_reorder_quantity")
    forecast = tool_results.get("forecast_demand")
    comparison = tool_results.get("compare_suppliers")
    transport = tool_results.get("get_transport_options")

    if tool_name == "calculate_safety_stock":
        if state_slice.get("demand_forecast") is not None:
            merged["forecast_demand"] = int(state_slice["demand_forecast"])
        elif forecast is not None:
            merged["forecast_demand"] = forecast.forecast_demand

    if tool_name == "calculate_reorder_quantity":
        if forecast is not None:
            merged["forecast_demand"] = forecast.forecast_demand
        elif state_slice.get("demand_forecast") is not None:
            merged["forecast_demand"] = int(state_slice["demand_forecast"])
        if inventory is not None:
            merged["current_inventory"] = inventory.current_inventory
        if safety is not None:
            merged["safety_stock"] = safety.safety_stock

    if tool_name == "check_warehouse_capacity":
        if reorder is not None:
            merged["additional_quantity"] = reorder.recommended_order_quantity
        elif state_slice.get("reorder_quantity") is not None:
            merged["additional_quantity"] = int(state_slice["reorder_quantity"])

    if tool_name in {"compare_suppliers", "check_supplier_capacity"}:
        qty = state_slice.get("reorder_quantity")
        if qty is not None:
            merged["required_quantity"] = int(qty)
        if comparison is not None and tool_name == "check_supplier_capacity":
            merged.setdefault("supplier_id", comparison.best_supplier_id)

    if tool_name == "evaluate_supplier_reliability" and comparison is not None:
        merged.setdefault("supplier_id", comparison.best_supplier_id)

    if tool_name == "calculate_shipping_cost":
        if state_slice.get("reorder_quantity") is not None:
            merged["quantity"] = int(state_slice["reorder_quantity"])
        if transport is not None and transport.options:
            cheapest = min(transport.options, key=lambda o: o.cost_per_unit)
            merged.setdefault("option_id", cheapest.option_id)

    if tool_name == "estimate_delivery_time":
        allocation = state_slice.get("supplier_allocation") or []
        if allocation:
            first = allocation[0]
            lead = getattr(first, "expected_delivery_days", None)
            if lead is not None:
                merged["supplier_lead_time_days"] = int(lead)

    if tool_name == "evaluate_demand_risk":
        confidence = state_slice.get("forecast_confidence")
        if confidence is not None:
            merged["forecast_confidence"] = float(confidence)
        elif forecast is not None:
            merged["forecast_confidence"] = forecast.forecast_confidence

    if tool_name == "evaluate_transport_risk":
        selected = state_slice.get("selected_transport")
        if selected is not None:
            merged["option_id"] = getattr(selected, "option_id", merged.get("option_id"))

    return merged


class BaseAgent(ABC):
    """Abstract base for all supply chain agents."""

    name: str
    role: str
    objective: str
    system_instructions: str
    allowed_tools: dict[str, Callable[..., Any]]
    output_message_type: str

    def __init__(self, env: Environment) -> None:
        self.env = env
        self.settings = get_settings()

    @abstractmethod
    def build_output(self, tool_results: dict[str, Any], state_slice: dict[str, Any]) -> AgentMessage:
        """Build typed output message from tool results."""
        ...

    def _execute_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Execute a named tool with Pydantic-validated arguments."""
        if tool_name not in self.allowed_tools:
            msg = f"Tool '{tool_name}' not allowed for {self.name}"
            raise AgentValidationError(self.name, msg)

        tool_fn = self.allowed_tools[tool_name]
        param_names, input_cls = _tool_signature(tool_fn)

        if input_cls is not None and "inp" in param_names:
            inp = input_cls(**arguments)
            if "env" in param_names:
                return tool_fn(self.env, inp)
            return tool_fn(inp)

        if "env" in param_names:
            return tool_fn(self.env, **arguments)
        return tool_fn(**arguments)

    async def run(
        self,
        state: SupplyChainState,
        state_slice: dict[str, Any],
        llm: LLMProvider,
    ) -> AgentMessage:
        """Run bounded reasoning loop: LLM selects tools, tools compute, emit output."""
        start_time = time.perf_counter()
        timeout = self.settings.orch.agent_timeout_seconds
        tool_results: dict[str, Any] = {}
        max_iterations = self.settings.orch.max_iterations

        reset_agent = getattr(llm, "reset_agent", None)
        if callable(reset_agent):
            reset_agent(self.name)

        logger.info("agent.start", agent=self.name, run_id=state.run_id)

        for _iteration in range(max_iterations):
            elapsed = time.perf_counter() - start_time
            if elapsed > timeout:
                raise AgentTimeoutError(self.name, timeout)

            state.increment_agent_iteration(self.name)
            response = await llm.complete(
                system_prompt=self.system_instructions,
                user_prompt=(
                    f"Objective: {self.objective}\nState: {state_slice}\n"
                    f"Results: {list(tool_results.keys())}"
                ),
                available_tools=list(self.allowed_tools.keys()),
                agent_name=self.name,
            )

            if not response.tool_calls:
                break

            for tc in response.tool_calls:
                step_start = time.perf_counter()
                args = enrich_tool_arguments(tc.tool_name, tc.arguments, state_slice, tool_results)
                try:
                    result = self._execute_tool(tc.tool_name, args)
                    tool_results[tc.tool_name] = result
                    latency = (time.perf_counter() - step_start) * 1000
                    state.append_trace(
                        TraceEntry(
                            run_id=state.run_id,
                            agent=self.name,
                            step=tc.tool_name,
                            tool_called=tc.tool_name,
                            tool_args=args,
                            tool_result=result.model_dump() if hasattr(result, "model_dump") else {},
                            latency_ms=latency,
                        )
                    )
                except Exception as exc:
                    state.append_error(f"{self.name}.{tc.tool_name}: {exc}")
                    state.append_trace(
                        TraceEntry(
                            run_id=state.run_id,
                            agent=self.name,
                            step=tc.tool_name,
                            tool_called=tc.tool_name,
                            tool_args=args,
                            error=str(exc),
                        )
                    )
                    raise

        output = self.build_output(tool_results, state_slice)
        total_latency = (time.perf_counter() - start_time) * 1000
        state.append_trace(
            TraceEntry(
                run_id=state.run_id,
                agent=self.name,
                step="emit_output",
                decision=output.message_type,
                latency_ms=total_latency,
            )
        )
        logger.info("agent.complete", agent=self.name, latency_ms=total_latency)
        return output
