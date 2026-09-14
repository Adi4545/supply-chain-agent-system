"""FastAPI dependency providers with a process-wide environment singleton."""

from __future__ import annotations

from agents.orchestrator import OrchestratorAgent
from config.settings import get_settings
from environment.simulator import SimulatedEnvironment
from llm.mock_provider import MockLLMProvider

_env: SimulatedEnvironment | None = None


def get_env() -> SimulatedEnvironment:
    """Return a seeded environment, creating it once per process."""
    global _env
    cfg = get_settings()
    if _env is None:
        _env = SimulatedEnvironment(db_url=cfg.db_url, seed=cfg.random_seed)
        _env.seed_if_needed()
    return _env


def get_orchestrator() -> OrchestratorAgent:
    """Create an orchestrator bound to the shared environment."""
    return OrchestratorAgent(get_env(), MockLLMProvider())


def reset_env() -> None:
    """Drop the singleton — used by tests that need a clean database."""
    global _env
    _env = None
