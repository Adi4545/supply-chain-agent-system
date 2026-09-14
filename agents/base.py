"""Base agent with bounded tool-calling reasoning loop."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, Callable

import structlog
from pydantic import BaseModel

from config.settings import get_settings
from core.exceptions import AgentTimeoutError, AgentValidationError
from environment.protocol import Environment
from llm.protocol import LLMProvider
from models.schemas import AgentMessage, TraceEntry
from models.state import SupplyChainState

logger = structlog.get_logger(__name__)


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
        import inspect
        from typing import get_type_hints

        hints = get_type_hints(tool_fn)
        params = inspect.signature(tool_fn).parameters

        if "inp" in params:
            input_cls = hints.get("inp")
            if input_cls is not None and isinstance(input_cls, type) and issubclass(input_cls, BaseModel):
                inp = input_cls(**arguments)
                if "env" in params:
                    return tool_fn(self.env, inp)
                return tool_fn(inp)

        if "env" in params:
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

        logger.info("agent.start", agent=self.name, run_id=state.run_id)

        for iteration in range(max_iterations):
            elapsed = time.perf_counter() - start_time
            if elapsed > timeout:
                raise AgentTimeoutError(self.name, timeout)

            state.increment_agent_iteration(self.name)
            response = await llm.complete(
                system_prompt=self.system_instructions,
                user_prompt=f"Objective: {self.objective}\nState: {state_slice}\nResults: {list(tool_results.keys())}",
                available_tools=list(self.allowed_tools.keys()),
                agent_name=self.name,
            )

            if not response.tool_calls:
                break

            for tc in response.tool_calls:
                step_start = time.perf_counter()
                try:
                    result = self._execute_tool(tc.tool_name, tc.arguments)
                    tool_results[tc.tool_name] = result
                    latency = (time.perf_counter() - step_start) * 1000
                    state.append_trace(
                        TraceEntry(
                            run_id=state.run_id,
                            agent=self.name,
                            step=tc.tool_name,
                            tool_called=tc.tool_name,
                            tool_args=tc.arguments,
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
                            tool_args=tc.arguments,
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
