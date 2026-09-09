#!/usr/bin/env python3
"""Run read-only Binance TH preflight checks for real-grid symbols."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.real_grid_preflight import parse_symbols, run_preflight


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--symbols",
        default=None,
        help="Comma-separated Binance TH symbols (default: configured preflight set)",
    )
    return parser.parse_args()


async def run(args: argparse.Namespace) -> tuple[dict, int]:
    report = await run_preflight(parse_symbols(args.symbols))
    return report, 0 if report.get("ready") else 2


def main() -> int:
    report, exit_code = asyncio.run(run(parse_args()))
    print(json.dumps(report, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
