#!/usr/bin/env python3
"""Print the multi-platform capability registry without contacting providers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

STRATEGY_ROOT = Path(__file__).resolve().parents[1]
if str(STRATEGY_ROOT) not in sys.path:
    sys.path.insert(0, str(STRATEGY_ROOT))

from app.portfolio.registry import default_platform_registry  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", help="show one platform by platform_id")
    parser.add_argument("--paper-ready", action="store_true", help="show only paper-ready platforms")
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    registry = default_platform_registry()
    if args.platform:
        platform = registry.find(args.platform)
        if platform is None:
            print(f"Unknown platform: {args.platform}", file=sys.stderr)
            return 2
        platforms = (platform,)
    elif args.paper_ready:
        platforms = registry.paper_ready()
    else:
        platforms = registry.all()

    payload = {
        "registry_version": 1,
        "execution_enabled": False,
        "platforms": [platform.as_dict() for platform in platforms],
    }
    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
        return 0

    print("Portfolio platform capability registry")
    for platform in platforms:
        print(
            f"- {platform.platform_id}: {platform.status.value}; "
            f"paper_ready={platform.is_paper_ready}; next_gate={platform.next_gate or 'none'}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
