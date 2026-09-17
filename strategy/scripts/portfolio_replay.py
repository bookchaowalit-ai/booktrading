#!/usr/bin/env python3
"""Replay paper trades and rewards from a bounded JSONL fixture."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

STRATEGY_ROOT = Path(__file__).resolve().parents[1]
if str(STRATEGY_ROOT) not in sys.path:
    sys.path.insert(0, str(STRATEGY_ROOT))

from app.portfolio.replay import replay_portfolio_fixture  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path, help="versioned portfolio JSONL fixture")
    parser.add_argument("--as-of", help="timezone-aware ISO timestamp for the snapshot")
    parser.add_argument(
        "--reporting-currency", help="select one currency when the fixture contains multiple currencies"
    )
    parser.add_argument(
        "--mark",
        action="append",
        default=[],
        metavar="SYMBOL=PRICE",
        help="mark an open paper trade; platform:symbol=price is more specific",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        as_of = _parse_timestamp(args.as_of) if args.as_of else None
        marks = {}
        for value in args.mark:
            symbol, price = _parse_mark(value)
            marks[symbol] = price
        report = replay_portfolio_fixture(
            args.fixture,
            as_of=as_of,
            marks=marks,
            reporting_currency=args.reporting_currency,
        )
    except (TypeError, ValueError, OSError) as exc:
        print(f"Portfolio replay blocked: {exc}", file=sys.stderr)
        return 2

    if args.as_json:
        print(json.dumps(report.as_dict(), ensure_ascii=False, sort_keys=True, indent=2))
    else:
        snapshot = report.snapshot
        print("Portfolio — OFFLINE PAPER + REWARDS REPLAY")
        print(f"Events: {report.event_count} (paper trades={report.paper_trade_count}, rewards={report.reward_count})")
        print(f"Paper realized P&L: {snapshot.paper_realized_pnl:.10f}")
        print(f"Paper unrealized P&L: {snapshot.paper_unrealized_pnl:.10f}")
        print(f"Rewards realized net: {snapshot.rewards_realized_net:.10f}")
        print(f"Rewards pending estimate (not cash): {snapshot.rewards_pending_estimate:.10f}")
        print(f"Total tracked costs: {snapshot.total_costs:.10f}")
        print(f"Execution enabled: {snapshot.execution_enabled}")
    return 0


def _parse_mark(value: str) -> tuple[str, float]:
    if "=" not in value:
        raise ValueError("mark must use SYMBOL=PRICE")
    symbol, price = value.split("=", 1)
    symbol = symbol.strip()
    if not symbol:
        raise ValueError("mark symbol cannot be empty")
    return symbol, float(price)


def _parse_timestamp(value: str) -> datetime:
    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("--as-of must include a timezone")
    return timestamp.astimezone(UTC)


if __name__ == "__main__":
    raise SystemExit(main())
