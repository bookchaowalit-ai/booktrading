#!/usr/bin/env python3
"""
Backfill trade_journal from real open orders on exchange.
Matches real_trades (by price+side) with actual exchange orders to get exchange_order_id.
Runs inside the strategy container via: docker compose exec strategy python3 scripts/backfill_journal.py
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

import httpx

BACKEND_API = os.getenv("BACKEND_API", "http://backend:8080")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")


def login():
    """Login to backend and return session token."""
    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        raise RuntimeError("ADMIN_EMAIL and ADMIN_PASSWORD must be set")
    resp = httpx.post(
        f"{BACKEND_API}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    if resp.status_code == 200:
        return resp.json().get("token")
    raise RuntimeError(f"Login failed: {resp.status_code} {resp.text}")


def main():
    print("=== Backfill trade_journal ===")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")

    # 0. Login to get session token
    print("Logging in...")
    token = login()
    headers = {"Authorization": f"Bearer {token}"}
    print(f"Logged in, token: {token[:12]}...")

    # 1. Fetch open orders from exchange
    resp = httpx.get(f"{BACKEND_API}/api/trade/open-orders", params={"symbol": "BTCTHB"}, timeout=15)
    if resp.status_code != 200:
        print(f"ERROR: Failed to fetch open orders: {resp.status_code}")
        sys.exit(1)

    exchange_orders = resp.json().get("orders", [])
    print(f"Exchange open orders: {len(exchange_orders)}")

    # Build lookup: (side, price_int) -> orderId
    order_lookup = {}
    for o in exchange_orders:
        side = o["side"]
        price = int(float(o["price"]))
        order_id = str(o["orderId"])
        order_lookup[(side, price)] = order_id
        print(f"  {side:4} @ {price:>10}  orderId={order_id}")

    # 2. Fetch existing journal entries to avoid duplicates
    resp2 = httpx.get(
        f"{BACKEND_API}/api/journal/list",
        params={"limit": "500"},
        headers=headers,
        timeout=15,
    )
    existing_journal = []
    if resp2.status_code == 200:
        existing_journal = resp2.json() if isinstance(resp2.json(), list) else []
    print(f"\nExisting journal entries: {len(existing_journal)}")

    # 3. For each exchange order, insert into journal if not exists
    inserted = 0
    skipped = 0
    errors = 0

    for (side, price), order_id in order_lookup.items():
        # Check if already in journal (by exchange_order_id)
        already_exists = any(
            str(e.get("exchange_order_id", "")) == order_id
            for e in existing_journal
        )
        if already_exists:
            skipped += 1
            continue

        # Calculate expected risk/reward
        notional = 0.00005 * price  # qty * price
        expected_risk = notional * 0.02  # 2% risk estimate
        spacing_pct = 1.5
        expected_reward = notional * (spacing_pct / 100)

        entry = {
            "symbol": "BTCTHB",
            "side": side,
            "strategy": "grid_bot_v2",
            "entry_reason": f"Backfill: Grid {side.lower()} @ price={price}, spacing={spacing_pct}%",
            "entry_price": price,
            "quantity": 0.00005,
            "expected_risk_thb": expected_risk,
            "expected_reward_thb": expected_reward,
            "stop_loss_price": 0,
            "take_profit_price": 0,
            "exit_price": 0,
            "exit_reason": "",
            "actual_pnl": 0,
            "fee": 0,
            "drawdown_impact_pct": 0,
            "exchange_order_id": order_id,
            "status": "OPEN",
        }

        resp3 = httpx.post(
            f"{BACKEND_API}/api/journal/entry",
            json=entry,
            headers=headers,
            timeout=15,
        )
        if resp3.status_code == 201:
            inserted += 1
            print(f"  INSERTED: {side} @ {price} orderId={order_id}")
        else:
            errors += 1
            print(f"  ERROR: {side} @ {price} -> {resp3.status_code}: {resp3.text}")

    # 4. Also update real_trades with exchange_order_id where missing
    print(f"\n=== Updating real_trades with exchange_order_id ===")
    # Fetch real_trades that have empty exchange_order_id
    resp4 = httpx.get(f"{BACKEND_API}/api/trade/history", params={"limit": "100"}, timeout=15)
    if resp4.status_code == 200:
        trades = resp4.json()
        btcthb_trades = [t for t in trades if t.get("symbol") == "BTCTHB" and not t.get("exchange_order_id")]
        print(f"BTCTHB trades missing exchange_order_id: {len(btcthb_trades)}")

    print(f"\n=== Summary ===")
    print(f"Inserted into journal: {inserted}")
    print(f"Skipped (already exists): {skipped}")
    print(f"Errors: {errors}")
    print(f"Done at: {datetime.now(timezone.utc).isoformat()}")


if __name__ == "__main__":
    main()
