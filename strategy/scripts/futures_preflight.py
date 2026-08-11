#!/usr/bin/env python3
"""Read-only leveraged-market preflight and optional ephemeral paper cycle."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.futures_bot import FuturesSafetyError, get_futures_bot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--paper-cycle",
        action="store_true",
        help="Run one ephemeral paper analysis cycle after a successful preflight",
    )
    parser.add_argument(
        "--simulate-entry",
        action="store_true",
        help="Allow the paper cycle to create a simulated in-memory position",
    )
    return parser.parse_args()


async def run(args: argparse.Namespace) -> tuple[dict, int]:
    if args.simulate_entry and not args.paper_cycle:
        return {"ready": False, "error": "--simulate-entry requires --paper-cycle"}, 2

    bot = get_futures_bot()
    report = await bot.preflight()
    if not report["ready"]:
        return report, 2

    if args.paper_cycle:
        try:
            report["paper_cycle"] = await bot.run_paper_cycle(allow_entry=args.simulate_entry)
        except FuturesSafetyError as exc:
            report["paper_cycle"] = {"error": str(exc)}
            return report, 2
    return report, 0


def main() -> int:
    report, exit_code = asyncio.run(run(parse_args()))
    print(json.dumps(report, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
