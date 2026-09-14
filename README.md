# Supply Chain Multi-Agent AI System

Production-quality, tool-using, stateful multi-agent system for supply chain planning. Agents call deterministic Python tools, communicate via typed Pydantic messages, and produce recommendations that always require human approval.

## Repository

- Browse: https://cursor.com/codebase/aditya-sharma-1/supply-chain-agent-system
- Visibility: Private (changeable in settings on that page)

### Clone to your machine

```bash
# Install the Origin CLI
curl -fsSL https://downloads.cursor.com/origin/install.sh | sh

# Sign in (also sets up git credentials)
origin auth login

# Clone the repository
origin repo clone aditya-sharma-1/supply-chain-agent-system
```

If `origin` is not found after install, persist `~/.local/bin` on PATH:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

Origin CLI docs: https://cursor.com/docs/origin/cli

## Architecture

```
User/API → Orchestrator → [Demand | Inventory | Procurement | Logistics | Risk]
         → each agent calls deterministic tools → Environment (SQLAlchemy)
         → Conflict Resolution → OR-Tools Optimizer → FinalDecision
```

Agents read/write only their owned slice of `SupplyChainState`. The LLM (mock by default) selects tools — it never performs arithmetic or optimization.

## Canonical Scenario

| Parameter | Value |
|-----------|-------|
| Product | P001 |
| Demand forecast | 12,000 units |
| Current inventory | 3,500 units |
| Supplier A | Low cost, 7-day lead |
| Supplier B | Higher cost, 3-day lead |
| Supplier C | Medium cost, 5-day lead |

## Quick Start

```bash
# Install dependencies
pip install -e ".[dev]"

# Copy environment config
cp .env.example .env

# Run tests
pytest

# Start API server
python main.py --serve --port 8742

# Open dashboard
open http://127.0.0.1:8742/dashboard/

# Run experiments
python -m experiments.runner --configs all
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/plan` | Run planning pipeline |
| GET | `/inventory/{product_id}` | Inventory snapshot |
| GET | `/suppliers` | Supplier list |
| GET | `/products` | Product list |
| POST | `/simulate-disruption` | Trigger disruption + replan |
| POST | `/run-experiment` | Launch experiment batch |
| GET | `/experiment-results` | Latest experiment results |
| GET | `/execution-trace/{run_id}` | Agent execution trace |

### Example

```bash
curl -X POST http://127.0.0.1:8742/plan \
  -H "Content-Type: application/json" \
  -d '{"objective": "Plan replenishment for product P001", "product_id": "P001"}'
```

## Project Structure

```
agents/          Orchestrator + 5 domain agents
tools/           Deterministic tool functions
models/          Pydantic schemas + SupplyChainState
optimization/    OR-Tools MILP optimizer
memory/          Pluggable MemoryManager (SQLite)
environment/     SimulatedEnvironment + DisruptionEngine
experiments/     Benchmark runner (1/2/3/5/10-agent configs)
api/             FastAPI routes
frontend/        Dashboard UI
llm/             Swappable LLM providers (mock default)
core/            Logging, ownership, trace, exceptions
config/          pydantic-settings
tests/           Unit + integration tests
```

## Configuration

See [`.env.example`](.env.example). Key settings:

- `LLM__PROVIDER=mock` — deterministic CI mode (no network)
- `ORCH__MAX_ITERATIONS`, `ORCH__AGENT_TIMEOUT_SECONDS`, `ORCH__TOTAL_TIMEOUT_SECONDS`
- `OPT__WEIGHT_*` — conflict resolution weights (must sum to 1.0)
- `SAFETY__MAX_ORDER_QUANTITY`, `SAFETY__MAX_SPEND` — hard caps
- `DB__URL` — SQLite default; set to Postgres URL for production

## Safety

- Recommendation-only: no real POs are placed
- Every `FinalDecision` has `requires_human_approval: true` (enforced by schema)
- Hard caps on order quantity and spend flag violations in assumptions

## Extension Points

- Replace `SimulatedEnvironment` with real ERP via `Environment` Protocol
- Swap `SQLiteMemoryStore` for vector DB without changing agent code
- Set `LLM__PROVIDER=openai` for live LLM tool selection
