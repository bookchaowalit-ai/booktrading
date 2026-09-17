#!/usr/bin/env python3
"""Replay a World Markets fixture as deterministic, offline paper research."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

STRATEGY_ROOT = Path(__file__).resolve().parents[1]
if str(STRATEGY_ROOT) not in sys.path:
    sys.path.insert(0, str(STRATEGY_ROOT))

from app.world.replay import (  # noqa: E402
    WorldReplayConfig,
    WorldReplayError,
    WorldReplayRunner,
    load_replay_fixture,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path, help="JSONL replay fixture")
    parser.add_argument("--fee-bps-per-leg", type=float, default=50.0)
    parser.add_argument("--slippage-bps-per-leg", type=float, default=0.0)
    parser.add_argument("--min-net-edge", type=float, default=0.0)
    parser.add_argument("--max-open-positions", type=int, default=100)
    parser.add_argument("--max-quote-age-seconds", type=float, default=30.0)
    parser.add_argument("--target-units", type=float, default=1.0)
    parser.add_argument("--unknown-size-fill-ratio", type=float, default=1.0)
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        frames = load_replay_fixture(args.fixture)
        report = WorldReplayRunner(
            config=WorldReplayConfig(
                fee_bps_per_leg=args.fee_bps_per_leg,
                slippage_bps_per_leg=args.slippage_bps_per_leg,
                min_net_edge=args.min_net_edge,
                max_open_positions=args.max_open_positions,
                max_quote_age_seconds=args.max_quote_age_seconds,
                target_units=args.target_units,
                unknown_size_fill_ratio=args.unknown_size_fill_ratio,
            )
        ).run(frames)
    except (OSError, ValueError, WorldReplayError) as exc:
        print(f"World Markets replay blocked: {exc}", file=sys.stderr)
        return 2

    payload = report.as_dict()
    payload["fixture"] = str(args.fixture)
    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
        return 0

    print("World Markets — OFFLINE PAPER REPLAY")
    print(f"Frames: {report.frame_count}")
    print(f"Signals: {report.signal_count}")
    print(f"Hypothetical entries: {report.entry_count}")
    print(f"Resolved entries: {report.resolved_entry_count}")
    print(f"Stale signals skipped: {report.stale_signal_count}")
    print(f"Partial-fill entries: {report.partial_fill_entry_count}")
    print(f"Net P&L (paper units): {report.net_pnl:.6f}")
    print(f"Max drawdown (paper units): {report.max_drawdown:.6f}")
    print("No orders are created; fixture results are not a live profitability claim.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
