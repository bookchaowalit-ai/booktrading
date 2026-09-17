#!/usr/bin/env python3
"""Run a bounded, read-only World Markets live-data readiness check."""

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

from app.market_intel.sources.world import WorldSource  # noqa: E402,F401
from app.world.client import WorldMarketsConfig  # noqa: E402
from app.world.landing import WorldLandingWriter  # noqa: E402
from app.world.readiness import check_world_readiness  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", help="override WORLD_MARKETS_API_BASE; never include credentials")
    parser.add_argument("--ws-url", help="override WORLD_MARKETS_WS_URL")
    parser.add_argument("--category", help="provider category filter")
    parser.add_argument("--tag", action="append", default=[], help="provider tag filter; repeatable")
    parser.add_argument("--limit", type=int, default=1, help="bounded events per page (default: 1)")
    parser.add_argument("--landing-dir", type=Path, help="local lake root; otherwise WORLD_MARKETS_LANDING_DIR")
    parser.add_argument(
        "--no-lake",
        action="store_true",
        help="run only the access/parser probe; paper readiness remains false",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


async def run(args: argparse.Namespace):
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
    return await check_world_readiness(
        config,
        landing_writer=landing_writer,
        page_limit=args.limit,
        category=args.category,
        tags=args.tag,
        require_landing=not args.no_lake,
    )


def main() -> int:
    args = build_parser().parse_args()
    try:
        report = asyncio.run(run(args))
    except (ValueError, OSError) as exc:
        print(f"World Markets readiness blocked: {exc}", file=sys.stderr)
        return 2

    payload = report.as_dict()
    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
    else:
        print("World Markets — LIVE READINESS CHECK")
        print(f"API: {report.api_status} ({report.api_status_code or 'n/a'})")
        print(f"Lake: {report.lake_status}")
        print(f"Parser: {report.parser_status}")
        print(f"Markets: {report.market_count}; quality eligible: {report.quality_eligible_market_count}")
        print(f"Paper signals: {report.paper_signal_count}")
        print(f"Ready for paper evaluation: {report.ready_for_paper}")
        if report.error_class:
            print(f"Reason: {report.error_class}")
    return 0 if report.ready_for_paper else 2


if __name__ == "__main__":
    raise SystemExit(main())
