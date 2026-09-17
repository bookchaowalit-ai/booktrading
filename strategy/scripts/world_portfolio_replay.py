#!/usr/bin/env python3
"""Replay World Markets into the shared paper portfolio ledger."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

STRATEGY_ROOT = Path(__file__).resolve().parents[1]
if str(STRATEGY_ROOT) not in sys.path:
    sys.path.insert(0, str(STRATEGY_ROOT))

from app.portfolio.integrations import replay_world_to_portfolio  # noqa: E402
from app.world.replay import load_replay_fixture  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path, help="World Markets JSONL replay fixture")
    parser.add_argument("--as-of", help="timezone-aware ISO timestamp for the portfolio snapshot")
    parser.add_argument(
        "--mark",
        action="append",
        default=[],
        metavar="SYMBOL=PRICE",
        help="mark an open normalized World position",
    )
    parser.add_argument("--reporting-currency", default="USD")
    parser.add_argument("--quote-currency", default="USD")
    parser.add_argument("--account-scope", default="paper-world")
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        frames = load_replay_fixture(args.fixture)
        as_of = _parse_timestamp(args.as_of) if args.as_of else None
        marks = {}
        for raw_mark in args.mark:
            symbol, price = _parse_mark(raw_mark)
            marks[symbol] = price
        result = replay_world_to_portfolio(
            frames,
            as_of=as_of,
            marks=marks,
            reporting_currency=args.reporting_currency,
            quote_currency=args.quote_currency,
            account_scope=args.account_scope,
        )
    except (TypeError, ValueError, OSError) as exc:
        print(f"World portfolio replay blocked: {exc}", file=sys.stderr)
        return 2

    if args.as_json:
        print(json.dumps(result.as_dict(), ensure_ascii=False, sort_keys=True, indent=2))
    else:
        snapshot = result.portfolio_snapshot
        print("World Markets — PORTFOLIO PAPER REPLAY")
        print(f"Entries: {result.market_report.entry_count}; resolved: {result.market_report.resolved_entry_count}")
        print(f"Reporting currency: {snapshot.reporting_currency or 'multiple'}")
        print(f"Paper realized P&L: {snapshot.paper_realized_pnl}")
        print(f"Paper unrealized P&L: {snapshot.paper_unrealized_pnl}")
        print(f"Tracked costs: {snapshot.total_costs}")
        print(f"Execution enabled: {snapshot.execution_enabled}")
    return 0


def _parse_mark(value: str) -> tuple[str, float]:
    if "=" not in value:
        raise ValueError("mark must use SYMBOL=PRICE")
    symbol, price = value.split("=", 1)
    if not symbol.strip():
        raise ValueError("mark symbol cannot be empty")
    return symbol.strip(), float(price)


def _parse_timestamp(value: str) -> datetime:
    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("--as-of must include a timezone")
    return timestamp.astimezone(UTC)


if __name__ == "__main__":
    raise SystemExit(main())
