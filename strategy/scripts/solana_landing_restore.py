#!/usr/bin/env python3
"""Verify and restore one Solana landing/Bronze manifest without mutation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.market_intel.onchain_landing import OnchainLandingWriter


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uri", required=True, help="file:// or s3:// landing URI")
    parser.add_argument("--manifest-key", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = OnchainLandingWriter(args.uri).restore_manifest(args.manifest_key, args.output)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
