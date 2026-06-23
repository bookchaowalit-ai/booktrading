#!/usr/bin/env python3
"""
BTCTHB Paper Grid — 1-Day Observation
======================================
24-hour supervised paper grid observation with periodic snapshots.

Config: BTCTHB, 2% spacing, 2 levels, 0.00005 BTC/order
Poll: every 5 minutes (288 ticks)
Snapshots: every 6 hours
Auto-stop: safety violation, 5+ consecutive API errors, exposure > cap

Usage:
    python scripts/paper_grid_1day.py [--poll 300] [--output data/paper_grid_1day.json]
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("paper_grid_1day")

# ── Configuration ─────────────────────────────────────────────────────────────

BINANCE_TH = "https://api.binance.th"
SYMBOL = "BTCTHB"

GRID_SPACING_PCT = 2.0
GRID_LEVELS = 2
ORDER_SIZE = 0.00005
MAX_POSITION = 0.001
MAX_NOTIONAL = 3000.0
FEE_RATE = 0.001

DURATION_HOURS = 24
SNAPSHOT_INTERVAL_HOURS = 6
MAX_CONSECUTIVE_ERRORS = 5


@dataclass
class PaperOrder:
    id: str
    side: str
    price: float
    quantity: float
    timestamp: float
    status: str = "PENDING"
    fill_price: float = 0.0
    fill_timestamp: float = 0.0
    fee: float = 0.0


@dataclass
class GridState:
    center_price: float = 0.0
    grid_levels: Dict[float, PaperOrder] = field(default_factory=dict)
    filled_orders: List[PaperOrder] = field(default_factory=list)
    position: float = 0.0
    cash: float = 10000.0
    total_fees: float = 0.0
    realized_pnl: float = 0.0
    ticks: int = 0
    skipped_ticks: int = 0
    consecutive_errors: int = 0
    errors: List[str] = field(default_factory=list)
    price_history: List[Dict] = field(default_factory=list)
    snapshots: List[Dict] = field(default_factory=list)


def compute_grid_levels(center: float) -> List[float]:
    spacing = center * (GRID_SPACING_PCT / 100.0)
    levels = []
    for i in range(1, GRID_LEVELS + 1):
        levels.append(round(center - (spacing * i)))
        levels.append(round(center + (spacing * i)))
    return sorted(levels)


def validate_exposure(position: float, price: float) -> bool:
    exposure = position * price
    return exposure <= MAX_NOTIONAL


async def fetch_price(client: httpx.AsyncClient) -> float:
    try:
        resp = await client.get(
            f"{BINANCE_TH}/api/v1/ticker/price",
            params={"symbol": SYMBOL},
        )
        if resp.status_code == 200:
            data = resp.json()
            return float(data["price"])
        else:
            logger.warning(f"Binance TH returned {resp.status_code}")
    except Exception as e:
        logger.error(f"Price fetch failed: {e}")
    return 0.0


def take_snapshot(state: GridState, current_price: float, elapsed_min: float) -> Dict:
    pending_buys = sum(1 for o in state.grid_levels.values() if o.side == "BUY")
    pending_sells = sum(1 for o in state.grid_levels.values() if o.side == "SELL")
    exposure = state.position * current_price

    snapshot = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "elapsed_min": round(elapsed_min, 1),
        "price": current_price,
        "position_btc": state.position,
        "cash_thb": round(state.cash, 2),
        "exposure_thb": round(exposure, 2),
        "pending_buys": pending_buys,
        "pending_sells": pending_sells,
        "total_filled": len(state.filled_orders),
        "realized_pnl_thb": round(state.realized_pnl, 2),
        "total_fees_thb": round(state.total_fees, 2),
        "ticks": state.ticks,
        "skipped_ticks": state.skipped_ticks,
    }
    state.snapshots.append(snapshot)
    return snapshot


async def run_observation(poll_sec: int, output_path: str):
    logger.info(f"=== BTCTHB Paper Grid — 1-Day Observation ===")
    logger.info(f"Duration: {DURATION_HOURS}h | Poll: {poll_sec}s | Snapshot: every {SNAPSHOT_INTERVAL_HOURS}h")
    logger.info(f"Grid: {GRID_LEVELS} levels × {GRID_SPACING_PCT}% | Order: {ORDER_SIZE} BTC (~฿{ORDER_SIZE * 2_120_000:,.0f})")
    logger.info(f"Max exposure: ฿{MAX_NOTIONAL:,.0f}")
    logger.info("")

    state = GridState()
    trial_start = time.time()
    trial_end = trial_start + (DURATION_HOURS * 3600)
    order_counter = 0
    last_snapshot_time = trial_start

    async with httpx.AsyncClient(timeout=15.0) as client:
        # ── Baseline ──────────────────────────────────────────────────────────
        logger.info("--- BASELINE ---")
        baseline_price = await fetch_price(client)
        if baseline_price <= 0:
            logger.error("Cannot fetch baseline price. Aborting.")
            return None

        state.center_price = baseline_price
        baseline_time = datetime.now(timezone.utc).isoformat()

        logger.info(f"Baseline price: ฿{baseline_price:,.2f}")
        logger.info(f"Baseline time:  {baseline_time}")

        grid_prices = compute_grid_levels(baseline_price)
        for gp in grid_prices:
            side = "BUY" if gp < baseline_price else "SELL"
            order_counter += 1
            state.grid_levels[gp] = PaperOrder(
                id=f"ORD-{order_counter:04d}",
                side=side,
                price=gp,
                quantity=ORDER_SIZE,
                timestamp=time.time(),
            )
            logger.info(f"  {side} @ ฿{gp:,.0f} ({state.grid_levels[gp].id})")

        logger.info(f"Active orders: {len(state.grid_levels)}")
        logger.info("")

        # Initial snapshot
        take_snapshot(state, baseline_price, 0)

        # ── Observation loop ──────────────────────────────────────────────────
        logger.info("--- OBSERVATION RUNNING ---")

        while time.time() < trial_end:
            state.ticks += 1
            elapsed_min = (time.time() - trial_start) / 60
            remaining_min = (trial_end - time.time()) / 60

            # Fetch price
            price = await fetch_price(client)
            if price <= 0:
                state.consecutive_errors += 1
                state.skipped_ticks += 1
                state.errors.append(f"Tick {state.ticks}: price fetch failed")
                logger.warning(f"[Tick {state.ticks}] Price fetch failed (consecutive: {state.consecutive_errors})")

                if state.consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    logger.error(f"ABORT: {MAX_CONSECUTIVE_ERRORS} consecutive errors")
                    break
                await asyncio.sleep(poll_sec)
                continue

            state.consecutive_errors = 0  # Reset on success

            # Record price history (keep last 288 = 24h at 5min intervals)
            state.price_history.append({
                "timestamp": time.time(),
                "price": price,
            })
            if len(state.price_history) > 288:
                state.price_history = state.price_history[-288:]

            # Safety check
            if not validate_exposure(state.position, price):
                state.skipped_ticks += 1
                exposure = state.position * price
                state.errors.append(
                    f"Tick {state.ticks}: exposure ฿{exposure:,.0f} > cap ฿{MAX_NOTIONAL:,.0f}"
                )
                logger.error(f"[Tick {state.ticks}] SAFETY VIOLATION: exposure exceeds cap — ABORT")
                break

            # Check fills
            filled_this_tick = []
            for level_price, order in list(state.grid_levels.items()):
                if order.status != "PENDING":
                    continue

                if order.side == "BUY" and price <= level_price:
                    order.status = "FILLED"
                    order.fill_price = level_price
                    order.fill_timestamp = time.time()
                    order.fee = level_price * ORDER_SIZE * FEE_RATE
                    state.position += ORDER_SIZE
                    state.cash -= (level_price * ORDER_SIZE) + order.fee
                    state.total_fees += order.fee
                    filled_this_tick.append(order)
                    logger.info(
                        f"[Tick {state.ticks}] FILL {order.id} BUY @ ฿{level_price:,.0f} "
                        f"(pos={state.position:.6f} BTC, cash=฿{state.cash:,.2f})"
                    )

                    # Place sell one level up
                    spacing = state.center_price * (GRID_SPACING_PCT / 100.0)
                    sell_price = round(level_price + spacing)
                    order_counter += 1
                    state.grid_levels[sell_price] = PaperOrder(
                        id=f"ORD-{order_counter:04d}",
                        side="SELL",
                        price=sell_price,
                        quantity=ORDER_SIZE,
                        timestamp=time.time(),
                    )
                    logger.info(f"  → SELL @ ฿{sell_price:,.0f}")

                elif order.side == "SELL" and price >= level_price:
                    order.status = "FILLED"
                    order.fill_price = level_price
                    order.fill_timestamp = time.time()
                    order.fee = level_price * ORDER_SIZE * FEE_RATE
                    state.position -= ORDER_SIZE
                    state.cash += (level_price * ORDER_SIZE) - order.fee
                    state.total_fees += order.fee
                    gross_profit = (level_price - state.center_price) * ORDER_SIZE
                    state.realized_pnl += gross_profit - order.fee
                    filled_this_tick.append(order)
                    logger.info(
                        f"[Tick {state.ticks}] FILL {order.id} SELL @ ฿{level_price:,.0f} "
                        f"(pos={state.position:.6f} BTC, cash=฿{state.cash:,.2f}, PnL=฿{state.realized_pnl:,.2f})"
                    )

                    # Place buy one level down
                    spacing = state.center_price * (GRID_SPACING_PCT / 100.0)
                    buy_price = round(level_price - spacing)
                    order_counter += 1
                    state.grid_levels[buy_price] = PaperOrder(
                        id=f"ORD-{order_counter:04d}",
                        side="BUY",
                        price=buy_price,
                        quantity=ORDER_SIZE,
                        timestamp=time.time(),
                    )
                    logger.info(f"  → BUY @ ฿{buy_price:,.0f}")

            # Remove filled from active
            state.grid_levels = {p: o for p, o in state.grid_levels.items() if o.status == "PENDING"}

            # Periodic snapshot
            time_since_snapshot = time.time() - last_snapshot_time
            if time_since_snapshot >= (SNAPSHOT_INTERVAL_HOURS * 3600):
                snap = take_snapshot(state, price, elapsed_min)
                logger.info(
                    f"[Snapshot] elapsed={snap['elapsed_min']}m | price=฿{price:,.0f} | "
                    f"pos={state.position:.6f} | filled={len(state.filled_orders)} | "
                    f"PnL=฿{state.realized_pnl:,.2f}"
                )
                last_snapshot_time = time.time()

            # Log tick (every 12th tick = hourly summary)
            if state.ticks % 12 == 0:
                pending_buys = sum(1 for o in state.grid_levels.values() if o.side == "BUY")
                pending_sells = sum(1 for o in state.grid_levels.values() if o.side == "SELL")
                prices = [p["price"] for p in state.price_history[-12:]]
                price_range = f"฿{min(prices):,.0f}–฿{max(prices):,.0f}" if prices else "N/A"
                logger.info(
                    f"[Hourly] tick={state.ticks} | price=฿{price:,.0f} | range={price_range} | "
                    f"buys={pending_buys} sells={pending_sells} | pos={state.position:.6f} | "
                    f"filled={len(state.filled_orders)} | remaining={remaining_min:.0f}m"
                )

            await asyncio.sleep(poll_sec)

        # ── Final results ─────────────────────────────────────────────────────
        logger.info("")
        logger.info("--- OBSERVATION COMPLETE ---")
        trial_duration = (time.time() - trial_start) / 60
        final_price = await fetch_price(client)

        unrealized_pnl = 0.0
        if state.position > 0 and final_price > 0:
            avg_entry = state.center_price
            unrealized_pnl = (final_price - avg_entry) * state.position

        total_pnl = state.realized_pnl + unrealized_pnl

        prices = [p["price"] for p in state.price_history] if state.price_history else [baseline_price]
        min_price = min(prices)
        max_price = max(prices)

        results = {
            "trial_start": baseline_time,
            "trial_end": datetime.now(timezone.utc).isoformat(),
            "duration_hours": round(trial_duration / 60, 2),
            "baseline_price": baseline_price,
            "final_price": final_price,
            "min_price": min_price,
            "max_price": max_price,
            "price_change_pct": round((final_price - baseline_price) / baseline_price * 100, 3) if final_price > 0 else None,
            "total_ticks": state.ticks,
            "skipped_ticks": state.skipped_ticks,
            "orders_placed": order_counter,
            "orders_filled": len(state.filled_orders),
            "active_orders": len(state.grid_levels),
            "final_position_btc": state.position,
            "final_cash_thb": round(state.cash, 2),
            "total_fees_thb": round(state.total_fees, 2),
            "realized_pnl_thb": round(state.realized_pnl, 2),
            "unrealized_pnl_thb": round(unrealized_pnl, 2),
            "total_pnl_thb": round(total_pnl, 2),
            "safety_violations": [e for e in state.errors if "SAFETY" in e or "exposure" in e],
            "all_errors": state.errors,
            "snapshots": state.snapshots,
            "grid_config": {
                "symbol": SYMBOL,
                "spacing_pct": GRID_SPACING_PCT,
                "levels": GRID_LEVELS,
                "order_size": ORDER_SIZE,
                "max_position": MAX_POSITION,
                "max_notional": MAX_NOTIONAL,
            },
        }

        # Write JSON
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)

        logger.info(f"Duration:       {trial_duration / 60:.2f} hours")
        logger.info(f"Baseline price: ฿{baseline_price:,.2f}")
        logger.info(f"Final price:    ฿{final_price:,.2f}")
        logger.info(f"Price range:    ฿{min_price:,.0f} – ฿{max_price:,.0f}")
        logger.info(f"Price change:   {results['price_change_pct']}%")
        logger.info(f"Total ticks:    {state.ticks}")
        logger.info(f"Skipped ticks:  {state.skipped_ticks}")
        logger.info(f"Orders placed:  {order_counter}")
        logger.info(f"Orders filled:  {len(state.filled_orders)}")
        logger.info(f"Final position: {state.position:.6f} BTC")
        logger.info(f"Total fees:     ฿{state.total_fees:,.2f}")
        logger.info(f"Realized PnL:   ฿{state.realized_pnl:,.2f}")
        logger.info(f"Unrealized PnL: ฿{unrealized_pnl:,.2f}")
        logger.info(f"Total PnL:      ฿{total_pnl:,.2f}")
        logger.info(f"Safety guards:  {len(results['safety_violations'])} violations")
        logger.info(f"Results saved:  {output_path}")

        return results


def main():
    parser = argparse.ArgumentParser(description="BTCTHB Paper Grid — 1-Day Observation")
    parser.add_argument("--poll", type=int, default=300, help="Poll interval in seconds (default: 300)")
    parser.add_argument("--output", type=str, default="data/paper_grid_1day.json", help="Output JSON path")
    args = parser.parse_args()

    results = asyncio.run(run_observation(args.poll, args.output))
    if results is None:
        sys.exit(1)


if __name__ == "__main__":
    main()
