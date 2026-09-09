#!/usr/bin/env python3
"""Plan or commit one bounded Solana Bronze compaction without deleting data."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

STRATEGY_ROOT = Path(__file__).resolve().parents[1]
if str(STRATEGY_ROOT) not in sys.path:
    sys.path.insert(0, str(STRATEGY_ROOT))

from app.market_intel.onchain_compaction import (  # noqa: E402
    compact_bronze,
    compact_limits_from_env,
    verify_compaction_manifest,
)
from app.market_intel.onchain_landing import OnchainLandingWriter  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--uri",
        required=True,
        help="file:// or s3:// landing URI; use a local file URI for the pilot",
    )
    parser.add_argument("--event-date", help="UTC partition date: YYYY-MM-DD")
    parser.add_argument("--dataset", default=None)
    parser.add_argument("--min-parts", type=int)
    parser.add_argument("--max-parts", type=int)
    parser.add_argument("--max-input-bytes", type=int)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write a new compacted part and commit manifest; never deletes source parts",
    )
    parser.add_argument(
        "--verify-manifest",
        help="verify an existing compaction manifest instead of creating a plan",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        writer = OnchainLandingWriter(args.uri, dataset=args.dataset)
        if args.verify_manifest:
            result = verify_compaction_manifest(writer, args.verify_manifest)
        else:
            if not args.event_date:
                raise ValueError("--event-date is required unless --verify-manifest is used")
            limits = compact_limits_from_env()
            result = compact_bronze(
                writer,
                event_date=args.event_date,
                apply=args.apply,
                min_parts=args.min_parts if args.min_parts is not None else limits["min_parts"],
                max_parts=args.max_parts if args.max_parts is not None else limits["max_parts"],
                max_input_bytes=(
                    args.max_input_bytes if args.max_input_bytes is not None else limits["max_input_bytes"]
                ),
            )
    except Exception as exc:
        payload = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
        if args.as_json:
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        else:
            print(f"Solana Bronze compaction: FAILED — {payload['error']}", file=sys.stderr)
        return 2

    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(f"Solana Bronze compaction: {result['status']} ({result.get('mode', 'verify')})")
        if "source_parts" in result:
            print(f"  source parts: {result['source_parts']}")
        if "output_key" in result:
            print(f"  output: {result['output_key']}")
        if "manifest_key" in result:
            print(f"  manifest: {result['manifest_key']}")
        print("  source deletion: disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
