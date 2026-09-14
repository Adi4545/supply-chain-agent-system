"""Experiment runner CLI."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import time
from datetime import datetime
from pathlib import Path

from agents.orchestrator import OrchestratorAgent
from config.settings import get_settings
from environment.simulator import SimulatedEnvironment
from experiments.configs import AGENT_CONFIGS
from experiments.metrics import aggregate_run_metrics
from experiments.scenarios import CANONICAL_SCENARIOS
from llm.mock_provider import MockLLMProvider


async def run_single(
    env: SimulatedEnvironment,
    scenario_name: str,
    config_name: str,
    seed: int,
) -> dict:
    """Run a single experiment configuration."""
    llm = MockLLMProvider()
    orchestrator = OrchestratorAgent(env, llm)
    scenario = next(s for s in CANONICAL_SCENARIOS if s.name == scenario_name)

    start = time.perf_counter()
    try:
        state = await orchestrator.run(scenario.request)
        status = "completed"
    except Exception as exc:
        from models.schemas import ExecutionStatus
        from models.state import SupplyChainState

        state = SupplyChainState(seed=seed)
        state.execution_status = ExecutionStatus.FAILED
        state.append_error(str(exc))
        status = "failed"
    latency = (time.perf_counter() - start) * 1000

    tool_calls = len([t for t in state.trace if t.tool_called])
    metrics = aggregate_run_metrics(
        state.to_serializable(),
        latency,
        tool_calls,
        llm.total_tokens,
        state.messages,
    )
    metrics["scenario"] = scenario_name
    metrics["config"] = config_name
    metrics["seed"] = seed
    metrics["status"] = status
    metrics["agents"] = AGENT_CONFIGS[config_name]
    return metrics


async def run_all(configs: list[str], output_dir: Path) -> list[dict]:
    """Run all scenarios against specified configs."""
    settings = get_settings()
    results: list[dict] = []

    for config_name in configs:
        for scenario in CANONICAL_SCENARIOS:
            output_dir.mkdir(parents=True, exist_ok=True)
            db_path = output_dir / f"exp_{config_name}_{scenario.name}.db"
            env = SimulatedEnvironment(db_url=f"sqlite:///{db_path}", seed=settings.random_seed)
            env.seed()
            result = await run_single(env, scenario.name, config_name, settings.random_seed)
            results.append(result)

    return results


def save_results(results: list[dict], output_dir: Path) -> None:
    """Save results to CSV and JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "results.json"
    csv_path = output_dir / "results.csv"

    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)

    if results:
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Run supply chain experiments")
    parser.add_argument(
        "--configs",
        default="all",
        help="Comma-separated config names or 'all'",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output directory (default: results/<timestamp>)",
    )
    args = parser.parse_args()

    if args.configs == "all":
        configs = list(AGENT_CONFIGS.keys())
    else:
        configs = [c.strip() for c in args.configs.split(",")]

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output or f"results/{timestamp}")

    results = asyncio.run(run_all(configs, output_dir))
    save_results(results, output_dir)
    print(f"Completed {len(results)} runs. Results saved to {output_dir}")


if __name__ == "__main__":
    main()
