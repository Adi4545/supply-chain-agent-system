"""Application settings loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class OptimizerWeights(BaseSettings):
    """Weighted scoring coefficients for conflict resolution."""

    model_config = SettingsConfigDict(env_prefix="OPT__WEIGHT_")

    cost: float = Field(default=0.30, alias="COST")
    delivery: float = Field(default=0.20, alias="DELIVERY")
    reliability: float = Field(default=0.20, alias="RELIABILITY")
    risk: float = Field(default=0.15, alias="RISK")
    inventory: float = Field(default=0.15, alias="INVENTORY")

    @model_validator(mode="after")
    def validate_sum(self) -> OptimizerWeights:
        """Ensure weights sum to 1.0 within tolerance."""
        total = self.cost + self.delivery + self.reliability + self.risk + self.inventory
        if abs(total - 1.0) > 1e-6:
            msg = f"Optimizer weights must sum to 1.0, got {total}"
            raise ValueError(msg)
        return self


class OrchestratorSettings(BaseSettings):
    """Orchestrator runtime limits."""

    model_config = SettingsConfigDict(env_prefix="ORCH__")

    max_iterations: int = Field(default=10, alias="MAX_ITERATIONS")
    agent_timeout_seconds: int = Field(default=60, alias="AGENT_TIMEOUT_SECONDS")
    total_timeout_seconds: int = Field(default=300, alias="TOTAL_TIMEOUT_SECONDS")


class SafetySettings(BaseSettings):
    """Hard caps for autonomous recommendations."""

    model_config = SettingsConfigDict(env_prefix="SAFETY__")

    max_order_quantity: int = Field(default=50000, alias="MAX_ORDER_QUANTITY")
    max_spend: float = Field(default=1_000_000.0, alias="MAX_SPEND")


class LLMSettings(BaseSettings):
    """LLM provider configuration."""

    model_config = SettingsConfigDict(env_prefix="LLM__")

    provider: Literal["mock", "openai"] = Field(default="mock", alias="PROVIDER")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")


class Settings(BaseSettings):
    """Root application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db_url: str = Field(default="sqlite:///./supply_chain.db", alias="DB__URL")
    random_seed: int = Field(default=42, alias="RANDOM__SEED")
    log_level: str = Field(default="INFO", alias="LOG__LEVEL")

    orch: OrchestratorSettings = Field(default_factory=OrchestratorSettings)
    opt_weights: OptimizerWeights = Field(default_factory=OptimizerWeights)
    safety: SafetySettings = Field(default_factory=SafetySettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        """Normalize log level to uppercase."""
        return value.upper()


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
