#!/usr/bin/env python3
"""
Snapshot cadence: Save daily report to file every 4-6 hours.
Run via cron: 0 */5 * * * cd /path/to/booktrading && docker compose exec -T strategy python3 /app/scripts/snapshot_report.py
"""

import json
import os
import sys
from datetime import datetime, timezone

import httpx

BACKEND_API = "http://backend:8080"
STRATEGY_API = "http://localhost:8000"
REPORTS_DIR = "/app/reports/grid-bot"
ADMIN_EMAIL = "admin@localhost"
ADMIN_PASSWORD = "admin123"


def login():
    """Login to backend and return session token."""
    resp = httpx.post(
        f"{BACKEND_API}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    if resp.status_code == 200:
        return resp.json().get("token")
    raise RuntimeError(f"Login failed: {resp.status_code} {resp.text}")


def main():
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%d_%H%M%S")
    date_str = now.strftime("%Y-%m-%d")

    print(f"=== Snapshot Report ===")
    print(f"Time: {now.isoformat()}")

    # Ensure reports directory exists
    os.makedirs(REPORTS_DIR, exist_ok=True)

    # Get daily report from strategy API
    try:
        resp = httpx.get(
            f"{STRATEGY_API}/api/report/daily",
            params={"symbol": "BTCTHB"},
            timeout=30,
        )
        if resp.status_code != 200:
            print(f"ERROR: Strategy API returned {resp.status_code}")
            sys.exit(1)
        report = resp.json()
    except Exception as e:
        print(f"ERROR: Failed to fetch daily report: {e}")
        sys.exit(1)

    # Add snapshot metadata
    report["_snapshot"] = {
        "taken_at": now.isoformat(),
        "symbol": "BTCTHB",
    }

    # Save to file
    filename = f"daily-BTCTHB-{date_str}.json"
    filepath = os.path.join(REPORTS_DIR, filename)

    # If file exists, append snapshot with timestamp
    if os.path.exists(filepath):
        # Load existing and append snapshot
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
        # Create new file
        report["snapshots"] = [report.pop("_snapshot")]
        with open(filepath, "w") as f:
            json.dump(report, f, indent=2, default=str)
        print(f"Created snapshot: {filepath}")

    # Also save a timestamped copy for archival
    archive_filename = f"BTCTHB-{timestamp}.json"
    archive_filepath = os.path.join(REPORTS_DIR, archive_filename)
    with open(archive_filepath, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"Archived: {archive_filepath}")

    # Print summary
    open_orders = len(report.get("open_orders", []))
    filled_trades = len(report.get("filled_trades", []))
    risk = report.get("risk", {})
    print(f"\nSummary:")
    print(f"  Open orders: {open_orders}")
    print(f"  Filled trades: {filled_trades}")
    print(f"  Daily PnL: {risk.get('daily_pnl', 0)}")
    print(f"  Halted: {risk.get('halted', False)}")
    print(f"Done at: {datetime.now(timezone.utc).isoformat()}")


if __name__ == "__main__":
    main()
