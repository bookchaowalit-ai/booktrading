#!/usr/bin/env python3
"""Inspect one durable World paper reservation after review or settlement."""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.alpha.durable_journal import DurablePaperJournal


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--journal-db", type=Path, required=True)
    parser.add_argument("--request-id", required=True)
    args = parser.parse_args()
    try:
        result = DurablePaperJournal(args.journal_db).reconcile(args.request_id)
    except (KeyError, OSError, TypeError, ValueError, sqlite3.Error):
        print(json.dumps({"action": "WAIT", "execution_enabled": False, "reconciled": False}))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
