"""LLM provider protocol for swappable backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    """LLM-requested tool invocation."""

    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class LLMResponse(BaseModel):
    """Response from an LLM provider."""

    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tokens_used: int = 0
    finish_reason: str = "stop"


class LLMProvider(ABC):
    """Abstract LLM provider interface."""

    @abstractmethod
    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        available_tools: list[str] | None = None,
        agent_name: str | None = None,
    ) -> LLMResponse:
        """Generate a completion, optionally selecting a tool."""
        ...
