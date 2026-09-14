"""CLI entry point for the supply chain multi-agent system."""

from __future__ import annotations

import argparse
import sys

from config.settings import get_settings
from core.logging import configure_logging


def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Supply Chain Multi-Agent AI System",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start the FastAPI server",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Server host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8742,
        help="Server port (default: 8742)",
    )
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


# FastAPI app placeholder — populated in Phase 14
try:
    from fastapi import FastAPI

    app = FastAPI(
        title="Supply Chain Multi-Agent System",
        version="0.1.0",
        description="Tool-using multi-agent supply chain planning API",
    )
except ImportError:
    app = None  # type: ignore[assignment,misc]


if __name__ == "__main__":
    sys.exit(main())
