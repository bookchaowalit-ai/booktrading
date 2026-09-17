#!/usr/bin/env python3
"""Replay a selective binary-market alpha thesis in paper mode only."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

STRATEGY_ROOT = Path(__file__).resolve().parents[1]
if str(STRATEGY_ROOT) not in sys.path:
    sys.path.insert(0, str(STRATEGY_ROOT))

from app.alpha import (  # noqa: E402
    AlphaResearchConfig,
    AlphaResearchError,
    RiskBudget,
    load_alpha_cases,
    run_alpha_research,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path, help="versioned alpha-case JSONL fixture")
    parser.add_argument(
        "--forward-start",
        required=True,
        help="UTC or timezone-aware ISO timestamp separating training and forward evaluation",
    )
    parser.add_argument("--starting-capital", type=float, default=1000.0)
    parser.add_argument("--max-total-risk", type=float, default=100.0)
    parser.add_argument("--max-trade-risk", type=float, default=10.0)
    parser.add_argument("--max-open-positions", type=int, default=3)
    parser.add_argument("--min-confidence", type=float, default=0.65)
    parser.add_argument("--min-expected-edge", type=float, default=0.05)
    parser.add_argument("--max-quote-age-seconds", type=float, default=30.0)
    parser.add_argument(
        "--allow-unknown-size",
        action="store_true",
        help="allow paper decisions without a known available size (less conservative)",
    )
    parser.add_argument(
        "--include-journal",
        action="store_true",
        help="include thesis and decision journal events in JSON output",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        config = AlphaResearchConfig(
            forward_start=_parse_timestamp(args.forward_start, "--forward-start"),
            risk_budget=RiskBudget(
                starting_capital=args.starting_capital,
                max_total_risk=args.max_total_risk,
                max_trade_risk=args.max_trade_risk,
                max_open_positions=args.max_open_positions,
                min_confidence=args.min_confidence,
                min_expected_edge=args.min_expected_edge,
                max_quote_age_seconds=args.max_quote_age_seconds,
                require_available_size=not args.allow_unknown_size,
            ),
        )
        cases = load_alpha_cases(args.fixture)
        report = run_alpha_research(cases, config=config)
    except (AlphaResearchError, OSError, TypeError, ValueError) as exc:
        print(f"Selective alpha replay blocked: {exc}", file=sys.stderr)
        return 2

    payload = report.as_dict(include_journal=args.include_journal)
    payload["fixture"] = str(args.fixture)
    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
        return 0

    train = report.train_summary
    forward = report.forward_summary
    print("SELECTIVE ALPHA — OFFLINE PAPER RESEARCH")
    print(f"Cases: {report.case_count} (train={report.train_case_count}, forward={report.forward_case_count})")
    print(f"Train: trades={train.paper_trade_count}, settled={train.settled_trade_count}, P&L={train.realized_pnl:.6f}")
    print(
        "Forward: "
        f"trades={forward.paper_trade_count}, settled={forward.settled_trade_count}, "
        f"P&L={forward.realized_pnl:.6f}, win_rate={_format_rate(forward.win_rate)}"
    )
    print(f"Forward gate: {report.forward_gate}")
    print(f"Journal events: {len(report.journal_events)}")
    print(f"Pending paper risk: {report.open_risk_at_end:.6f}")
    print("No orders are created; positive fixture results are not a live profitability claim.")
    return 0


def _parse_timestamp(value: str, field_name: str) -> datetime:
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO timestamp") from exc
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone")
    return timestamp.astimezone(UTC)


def _format_rate(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2%}"


if __name__ == "__main__":
    raise SystemExit(main())
