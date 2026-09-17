#!/usr/bin/env python3
"""Evaluate a committed local World snapshot with a reviewed thesis."""

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.alpha import RiskBudget, SelectiveAlphaEvaluator
from app.alpha.durable_journal import DurablePaperJournal
from app.alpha.world_snapshot import (
    ReviewedMapping,
    evaluate_world_snapshot,
    load_thesis,
    local_object,
    timestamp,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lake-root", type=Path, required=True)
    parser.add_argument("--manifest-key", required=True)
    parser.add_argument("--thesis", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True, help="mapping and explicit paper risk/cost policy JSON")
    parser.add_argument("--open-risk", type=float)
    parser.add_argument("--open-positions", type=int)
    parser.add_argument("--journal-db", type=Path, help="persistent paper lane; derives exposure atomically")
    parser.add_argument("--as-of", help="historical replay timestamp; default is actual current UTC")
    args = parser.parse_args()
    try:
        if args.journal_db:
            if args.open_risk is not None or args.open_positions is not None:
                raise ValueError("journal mode derives exposure; manual overrides are not allowed")
        elif args.open_risk is None or args.open_positions is None:
            raise ValueError("provide journal-db or both manual exposure values")
        review = json.loads(local_object(args.review.parent, args.review.name))
        mapping = dict(review["mapping"])
        mapping["reviewed_at"] = timestamp(mapping["reviewed_at"])
        account_scope = str(review.get("account_scope") or "paper-world")
        quote_currency = str(review.get("quote_currency") or "USD")
        starting_capital = review.get("starting_capital")
        thesis = load_thesis(args.thesis)
        budget = RiskBudget(**review["risk_budget"])

        def evaluate(open_risk, open_positions):
            return evaluate_world_snapshot(
                args.lake_root,
                args.manifest_key,
                thesis,
                ReviewedMapping(**mapping),
                SelectiveAlphaEvaluator(budget, strategy_version=thesis.strategy_version),
                now=timestamp(args.as_of) if args.as_of else datetime.now(UTC),
                cost_per_unit=review.get("cost_per_unit"),
                open_risk=open_risk,
                open_positions=open_positions,
            )

        if args.journal_db:
            request = {
                "manifest_sha256": hashlib.sha256(local_object(args.lake_root, args.manifest_key)).hexdigest(),
                "thesis": thesis.as_dict(),
                "review": review,
                "as_of": args.as_of,
            }
            result = DurablePaperJournal(args.journal_db).review(
                request,
                {"schema_version": 1, "risk_budget": budget.as_dict(), "historical_replay": args.as_of is not None},
                evaluate,
                account_scope=account_scope,
                quote_currency=quote_currency,
                starting_capital=starting_capital,
            )
        else:
            result = evaluate(args.open_risk, args.open_positions)
            result["portfolio"] = {
                "scope": "manual_exposure_input",
                "account_scope": account_scope,
                "quote_currency": quote_currency,
                "activity_mode": "paper",
                "starting_capital": starting_capital,
                "open_risk_before": args.open_risk,
                "open_risk_after": args.open_risk
                + (result["decision"]["risk_amount"] if result["decision"]["action"] == "TRADE_PAPER" else 0.0),
                "open_positions_after": args.open_positions + int(result["decision"]["action"] == "TRADE_PAPER"),
                "settlement_supported": False,
            }
        result["historical_replay"] = args.as_of is not None
    except (ValueError, TypeError, KeyError, OSError, sqlite3.Error) as exc:
        print(json.dumps({"action": "WAIT", "execution_enabled": False, "error_class": type(exc).__name__}))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
