#!/usr/bin/env python3
"""Read-only World Markets research scanner.

This command never signs, submits, or simulates a wallet transaction.  It
fetches event pages, optionally persists the exact responses to the configured
lake, and prints gross complement-gap watches for manual paper review.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

STRATEGY_ROOT = Path(__file__).resolve().parents[1]
if str(STRATEGY_ROOT) not in sys.path:
    sys.path.insert(0, str(STRATEGY_ROOT))

from app.market_intel.sources.world import WorldSource  # noqa: E402
from app.world.client import WorldApiError, WorldMarketsClient, WorldMarketsConfig  # noqa: E402
from app.world.landing import WorldLandingWriter  # noqa: E402
from app.world.scanner import WorldPaperScanner, WorldScannerConfig  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", help="override WORLD_MARKETS_API_BASE; never include credentials")
    parser.add_argument("--ws-url", help="override WORLD_MARKETS_WS_URL")
    parser.add_argument("--category", help="provider category filter, e.g. crypto")
    parser.add_argument("--tag", action="append", default=[], help="provider tag filter; repeatable")
    parser.add_argument("--limit", type=int, default=200, help="events per page (default: 200)")
    parser.add_argument("--max-pages", type=int, default=5, help="maximum cursor pages (default: 5)")
    parser.add_argument("--min-liquidity", type=float, default=500.0)
    parser.add_argument("--min-volume", type=float, default=1_000.0)
    parser.add_argument("--min-gap", type=float, default=0.03)
    parser.add_argument("--landing-dir", type=Path, help="local lake root; otherwise WORLD_MARKETS_LANDING_DIR")
    parser.add_argument(
        "--no-lake",
        action="store_true",
        help="explicitly allow an ephemeral read-only scan without raw/Bronze persistence",
    )
    parser.add_argument("--allow-unknown-metrics", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


async def run(args: argparse.Namespace) -> dict[str, Any]:
    config = WorldMarketsConfig.from_env()
    overrides: dict[str, Any] = {}
    if args.api_base:
        overrides["api_base"] = args.api_base
    if args.ws_url:
        overrides["ws_url"] = args.ws_url
    if overrides:
        config = replace(config, **overrides)

    landing_writer = None
    if not args.no_lake:
        landing_writer = WorldLandingWriter(str(args.landing_dir)) if args.landing_dir else WorldLandingWriter.from_env()
        if landing_writer is None:
            raise ValueError("set WORLD_MARKETS_LANDING_DIR or pass --landing-dir; use --no-lake only for an explicit ephemeral scan")

    scanner = WorldPaperScanner(
        WorldScannerConfig(
            min_liquidity=args.min_liquidity,
            min_volume=args.min_volume,
            min_complement_gap=args.min_gap,
            allow_unknown_metrics=args.allow_unknown_metrics,
        )
    )
    async with WorldMarketsClient(config) as client:
        source = WorldSource(
            config=config,
            client=client,
            landing_writer=landing_writer,
            scanner=scanner,
            page_limit=args.limit,
            max_pages=args.max_pages,
            category=args.category,
            tags=args.tag,
            use_env_landing=not args.no_lake,
            require_landing=not args.no_lake,
        )
        markets = await source.fetch_markets()
        signals = scanner.scan(markets)

    return {
        "source": "world_xyz",
        "mode": "read_only_paper_research",
        "execution_enabled": False,
        "lake_persisted": landing_writer is not None,
        "markets_scanned": len(markets),
        "signals": [
            {
                "ticker": signal.ticker,
                "signal_type": signal.signal_type,
                "side": signal.side,
                "rank_score": signal.rank_score,
                "data_confidence": signal.data_confidence,
                "reason": signal.reason,
                "metadata": signal.metadata,
            }
            for signal in signals
        ],
        "markets": [_market_dict(market) for market in markets],
    }


def main() -> int:
    args = build_parser().parse_args()
    try:
        report = asyncio.run(run(args))
    except (WorldApiError, ValueError) as exc:
        print(f"World Markets scan blocked: {exc}", file=sys.stderr)
        return 2

    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
        return 0

    print("World Markets — READ-ONLY PAPER RESEARCH")
    print(f"Markets scanned: {report['markets_scanned']}")
    print(f"Signals: {len(report['signals'])}")
    print(f"Lake persisted: {report['lake_persisted']}")
    print("No orders are created; every gap is gross and requires manual validation.")
    for index, signal in enumerate(report["signals"], start=1):
        print(f"{index:>2}. {signal['ticker']} {signal['signal_type']} {signal['side']} score={signal['rank_score']:.3f}")
        print(f"    {signal['reason']}")
    return 0


def _market_dict(market: Any) -> dict[str, Any]:
    return {
        "ticker": market.ticker,
        "title": market.title,
        "question": market.question,
        "category": market.category,
        "tags": list(market.tags),
        "status": market.status,
        "yes_bid": market.yes_bid,
        "yes_ask": market.yes_ask,
        "no_bid": market.no_bid,
        "no_ask": market.no_ask,
        "yes_ask_size": market.yes_ask_size,
        "no_ask_size": market.no_ask_size,
        "yes_mid": market.yes_mid,
        "no_mid": market.no_mid,
        "volume": market.volume,
        "liquidity": market.liquidity,
        "close_time": market.close_time,
        "strike_date": market.strike_date,
        "resolution_source": market.resolution_source,
        "updated_at": market.updated_at.isoformat() if market.updated_at else None,
        "validation_errors": list(market.validation_errors),
        "resolution_errors": list(market.resolution_errors),
    }


if __name__ == "__main__":
    raise SystemExit(main())
