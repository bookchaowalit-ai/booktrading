#!/usr/bin/env python3
"""Settle one durable World paper review from a hashed local binary proof."""

import argparse
import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.alpha.durable_journal import DurablePaperJournal
from app.alpha.models import SettlementProof
from app.alpha.world_snapshot import local_object, timestamp


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--journal-db", type=Path, required=True)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--lake-root", type=Path, required=True)
    parser.add_argument("--payout-per-unit", type=float, required=True, choices=(0.0, 1.0))
    parser.add_argument("--evidence-id", required=True)
    parser.add_argument("--evidence-source", required=True)
    parser.add_argument("--evidence-object-key", required=True)
    parser.add_argument("--evidence-sha256", required=True)
    parser.add_argument("--evidence-url", required=True)
    parser.add_argument("--evidence-observed-at", required=True)
    parser.add_argument("--evidence-summary", required=True)
    parser.add_argument("--ticker")
    parser.add_argument("--settled-at")
    args = parser.parse_args()
    try:
        metadata = {} if args.ticker is None else {"ticker": args.ticker}
        proof = SettlementProof(
            evidence_id=args.evidence_id,
            source=args.evidence_source,
            object_key=args.evidence_object_key,
            raw_sha256=args.evidence_sha256,
            source_url=args.evidence_url,
            observed_at=timestamp(args.evidence_observed_at),
            summary=args.evidence_summary,
            metadata=metadata,
        )

        def read_evidence(object_key: str) -> bytes:
            return local_object(args.lake_root, object_key)

        result = DurablePaperJournal(args.journal_db).settle_binary(
            args.request_id,
            payout_per_unit=args.payout_per_unit,
            proof=proof,
            read_evidence=read_evidence,
            settled_at=timestamp(args.settled_at) if args.settled_at else datetime.now(UTC),
        )
    except (KeyError, OSError, TypeError, ValueError, sqlite3.Error):
        print(json.dumps({"action": "WAIT", "execution_enabled": False, "settlement_recorded": False}))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
