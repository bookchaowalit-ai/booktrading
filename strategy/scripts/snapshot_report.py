#!/usr/bin/env python3
"""
Snapshot cadence: Save daily report to file every 4-6 hours.
Run via cron: 0 */5 * * * cd /path/to/booktrading && docker compose exec -T strategy python3 /app/scripts/snapshot_report.py

Covers every actively traded symbol (SNAPSHOT_SYMBOLS env var, comma-separated,
defaults to all four THB pairs) — previously this hardcoded BTCTHB only, which
was the one symbol with no trading activity, so the daily report never showed
what the bot was actually doing on ETHTHB/SOLTHB/XRPTHB.
"""

import json
import os
import sys
from datetime import datetime, timezone

import httpx

BACKEND_API = "http://backend:8080"
STRATEGY_API = "http://localhost:8000"
REPORTS_DIR = "/app/reports/grid-bot"

DEFAULT_SYMBOLS = "BTCTHB,ETHTHB,SOLTHB,XRPTHB"
SYMBOLS = [
    s.strip().upper()
    for s in os.environ.get("SNAPSHOT_SYMBOLS", DEFAULT_SYMBOLS).split(",")
    if s.strip()
]


def snapshot_symbol(symbol: str, now: datetime, timestamp: str, date_str: str) -> dict | None:
    """Fetch and persist the daily report for one symbol. Returns summary or None on failure."""
    try:
        resp = httpx.get(
            f"{STRATEGY_API}/api/report/daily",
            params={"symbol": symbol},
            timeout=30,
        )
        if resp.status_code != 200:
            print(f"ERROR [{symbol}]: Strategy API returned {resp.status_code}")
            return None
        report = resp.json()
    except Exception as e:
        print(f"ERROR [{symbol}]: Failed to fetch daily report: {e}")
        return None

    report["_snapshot"] = {
        "taken_at": now.isoformat(),
        "symbol": symbol,
    }

    filepath = os.path.join(REPORTS_DIR, f"daily-{symbol}-{date_str}.json")

    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            existing = json.load(f)
        if "snapshots" not in existing:
            existing["snapshots"] = [existing.pop("_snapshot", None) or {"taken_at": "initial"}]
        existing["snapshots"].append(report["_snapshot"])
        existing["latest"] = report
        with open(filepath, "w") as f:
            json.dump(existing, f, indent=2, default=str)
        print(f"Appended snapshot to: {filepath}")
    else:
        report["snapshots"] = [report.pop("_snapshot")]
        with open(filepath, "w") as f:
            json.dump(report, f, indent=2, default=str)
        print(f"Created snapshot: {filepath}")

    archive_filepath = os.path.join(REPORTS_DIR, f"{symbol}-{timestamp}.json")
    with open(archive_filepath, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"Archived: {archive_filepath}")

    risk = report.get("risk", {})
    journal = report.get("journal_stats", {})
    return {
        "symbol": symbol,
        "open_orders": len(report.get("open_orders", [])),
        "filled_trades": len(report.get("filled_trades", [])),
        "daily_pnl": risk.get("daily_pnl", 0),
        "halted": risk.get("halted", False),
        "win_rate": journal.get("win_rate", 0),
        "total_pnl": journal.get("total_pnl", 0),
    }


def main():
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%d_%H%M%S")
    date_str = now.strftime("%Y-%m-%d")

    print("=== Snapshot Report ===")
    print(f"Time: {now.isoformat()}")
    print(f"Symbols: {', '.join(SYMBOLS)}")

    os.makedirs(REPORTS_DIR, exist_ok=True)

    summaries = []
    for symbol in SYMBOLS:
        summary = snapshot_symbol(symbol, now, timestamp, date_str)
        if summary:
            summaries.append(summary)

    if not summaries:
        print("ERROR: All symbols failed.")
        sys.exit(1)

    print("\nSummary:")
    for s in summaries:
        print(
            f"  {s['symbol']}: orders={s['open_orders']} fills={s['filled_trades']} "
            f"daily_pnl={s['daily_pnl']} total_pnl={s['total_pnl']} "
            f"win_rate={s['win_rate']:.0f}% halted={s['halted']}"
        )
    print(f"Done at: {datetime.now(timezone.utc).isoformat()}")


if __name__ == "__main__":
    main()
