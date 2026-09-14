"""CLI entry point and FastAPI application."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.dependencies import get_env
from config.settings import get_settings
from core.logging import configure_logging

app = FastAPI(
    title="Supply Chain Multi-Agent System",
    version="0.1.0",
    description="Tool-using multi-agent supply chain planning API",
)


@app.on_event("startup")
def _seed_environment() -> None:
    """Warm the environment cache once at process start."""
    get_env()

# Register routes
from api.routes import router  # noqa: E402

app.include_router(router)

# Serve dashboard static files
_frontend = Path(__file__).parent / "frontend"
if _frontend.exists():
    app.mount("/dashboard", StaticFiles(directory=str(_frontend), html=True), name="dashboard")


def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(description="Supply Chain Multi-Agent AI System")
    parser.add_argument("--serve", action="store_true", help="Start the FastAPI server")
    parser.add_argument("--host", default="127.0.0.1", help="Server host")
    parser.add_argument("--port", type=int, default=8742, help="Server port")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point."""
    settings = get_settings()
    configure_logging(settings.log_level)
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.serve:
        import uvicorn

        uvicorn.run("main:app", host=args.host, port=args.port, reload=False)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
