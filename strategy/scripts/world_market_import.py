#!/usr/bin/env python3
"""Import a local World Markets JSON response into the paper research lake."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

STRATEGY_ROOT = Path(__file__).resolve().parents[1]
if str(STRATEGY_ROOT) not in sys.path:
    sys.path.insert(0, str(STRATEGY_ROOT))

from app.market_intel.onchain_landing import ObjectStoreError  # noqa: E402
from app.world.importer import import_world_snapshot  # noqa: E402
from app.world.scanner import WorldPaperScanner, WorldScannerConfig  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--payload", type=Path, required=True, help="local JSON response exported from an approved source"
    )
    parser.add_argument(
        "--landing-dir", type=Path, required=True, help="local lake root for immutable landing/Bronze objects"
    )
    parser.add_argument("--endpoint", default="/events", help="relative source endpoint label; no URL or query string")
    parser.add_argument("--received-at", help="timezone-aware ISO timestamp; defaults to current UTC")
    parser.add_argument("--min-liquidity", type=float, default=500.0)
    parser.add_argument("--min-volume", type=float, default=1_000.0)
    parser.add_argument("--min-gap", type=float, default=0.03)
    parser.add_argument("--allow-unknown-metrics", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        received_at = _timestamp(args.received_at) if args.received_at else None
        report = import_world_snapshot(
            args.payload,
            args.landing_dir,
            endpoint=args.endpoint,
            received_at=received_at,
            scanner=WorldPaperScanner(
                WorldScannerConfig(
                    min_liquidity=args.min_liquidity,
                    min_volume=args.min_volume,
                    min_complement_gap=args.min_gap,
                    allow_unknown_metrics=args.allow_unknown_metrics,
                )
            ),
        )
    except (ObjectStoreError, OSError, ValueError) as exc:
        print(f"World Markets local import blocked: {exc}", file=sys.stderr)
        return 2

    payload = report.as_dict()
    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
        return 0

    print("World Markets — LOCAL PAPER IMPORT")
    print(f"Markets scanned: {payload['markets_scanned']}")
    print(f"Quality eligible: {payload['quality_eligible_market_count']}")
    print(f"Signals: {len(payload['signals'])}")
    print(f"Landing: {payload['landing']['status']} ({payload['landing']['manifest_key']})")
    print("No orders are created; signals remain paper-only and require thesis review.")
    for index, signal in enumerate(payload["signals"], start=1):
        print(
            f"{index:>2}. {signal['ticker']} {signal['signal_type']} {signal['side']} score={signal['rank_score']:.3f}"
        )
        print(f"    {signal['reason']}")
    return 0


def _timestamp(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("received_at requires a timezone")
    return result.astimezone(UTC)


if __name__ == "__main__":
    raise SystemExit(main())
