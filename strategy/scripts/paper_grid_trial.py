#!/usr/bin/env python3
"""
BTCTHB Paper Grid — Supervised Trial Runner
============================================
Standalone 30-minute trial that:
1. Records baseline (price, time, grid config)
2. Runs grid logic against live Binance TH prices
3. Simulates paper fills locally (no Go backend needed)
4. Records all decisions, orders, fills, PnL
5. Outputs summary for EVIDENCE_LOG.md

Usage:
    python scripts/paper_grid_trial.py [--duration 30] [--poll 60]

This is READ-ONLY market interaction — no orders placed on any exchange.
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("paper_grid_trial")

# ── Configuration ─────────────────────────────────────────────────────────────

BINANCE_TH = "https://api.binance.th"
SYMBOL = "BTCTHB"

# Grid params (aligned with grid_bot.py safe defaults + real_grid_bot.py)
GRID_SPACING_PCT = 2.0      # % between levels
GRID_LEVELS = 2             # 2 above + 2 below
ORDER_SIZE = 0.00005        # BTC per order (~฿106)
MAX_POSITION = 0.001        # BTC max exposure (~฿2,120)
MAX_NOTIONAL = 3000.0       # ฿ cap
FEE_RATE = 0.001            # 0.1% per side (0.2% round-trip)


@dataclass
class PaperOrder:
    id: str
    side: str               # BUY or SELL
    price: float
    quantity: float
    timestamp: float
    status: str = "PENDING" # PENDING, FILLED, CANCELLED
    fill_price: float = 0.0
    fill_timestamp: float = 0.0
    fee: float = 0.0


@dataclass
class GridState:
    center_price: float = 0.0
    grid_levels: Dict[float, PaperOrder] = field(default_factory=dict)  # price -> order
    filled_orders: List[PaperOrder] = field(default_factory=list)
    position: float = 0.0     # current BTC position
    cash: float = 10000.0     # starting THB balance (paper)
    total_fees: float = 0.0
    realized_pnl: float = 0.0
    ticks: int = 0
    skipped_ticks: int = 0
    errors: List[str] = field(default_factory=list)


def compute_grid_levels(center: float) -> List[float]:
    """Compute grid level prices around center."""
    spacing = center * (GRID_SPACING_PCT / 100.0)
    levels = []
    for i in range(1, GRID_LEVELS + 1):
        levels.append(round(center - (spacing * i)))  # buy levels (below)
        levels.append(round(center + (spacing * i)))  # sell levels (above)
    return sorted(levels)


def validate_exposure(position: float, price: float) -> bool:
    """Check if position exceeds max notional cap."""
    exposure = position * price
    return exposure <= MAX_NOTIONAL


async def fetch_price(client: httpx.AsyncClient) -> float:
    """Fetch BTCTHB price from Binance TH."""
    try:
        resp = await client.get(
            f"{BINANCE_TH}/api/v1/ticker/price",
            params={"symbol": SYMBOL},
        )
        if resp.status_code == 200:
            data = resp.json()
            return float(data["price"])
        else:
            logger.warning(f"Binance TH returned {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.error(f"Failed to fetch price: {e}")
    return 0.0


async def run_trial(duration_min: int, poll_sec: int, output_json: str):
    """Run the supervised paper grid trial."""
    logger.info(f"=== BTCTHB Paper Grid Trial ===")
    logger.info(f"Duration: {duration_min} min | Poll: {poll_sec} sec")
    logger.info(f"Grid: {GRID_LEVELS} levels × {GRID_SPACING_PCT}% spacing")
    logger.info(f"Order size: {ORDER_SIZE} BTC (~฿{ORDER_SIZE * 2_120_000:,.0f})")
    logger.info(f"Max exposure: ฿{MAX_NOTIONAL:,.0f}")
    logger.info("")

    state = GridState()
    trial_start = time.time()
    trial_end = trial_start + (duration_min * 60)
    order_counter = 0

    async with httpx.AsyncClient(timeout=15.0) as client:
        # ── Phase 1: Record baseline ──────────────────────────────────────────
        logger.info("--- BASELINE ---")
        baseline_price = await fetch_price(client)
        if baseline_price <= 0:
            logger.error("Cannot fetch baseline price. Aborting trial.")
            return None

        state.center_price = baseline_price
        baseline_time = datetime.now(timezone.utc).isoformat()

        logger.info(f"Baseline price: ฿{baseline_price:,.2f}")
        logger.info(f"Baseline time:  {baseline_time}")
        logger.info(f"Grid levels:    {compute_grid_levels(baseline_price)}")
        logger.info("")

        # Initialize grid levels
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
            logger.info(f"  Placed {side} order @ ฿{gp:,.0f} (id={state.grid_levels[gp].id})")

        logger.info(f"Active orders: {len(state.grid_levels)}")
        logger.info("")

        # ── Phase 2: Run grid ticks ──────────────────────────────────────────
        logger.info("--- TRIAL RUNNING ---")
        tick_count = 0

        while time.time() < trial_end:
            tick_count += 1
            state.ticks += 1
            elapsed_min = (time.time() - trial_start) / 60
            remaining_min = (trial_end - time.time()) / 60

            # Fetch live price
            price = await fetch_price(client)
            if price <= 0:
                state.skipped_ticks += 1
                state.errors.append(f"Tick {tick_count}: price fetch failed")
                logger.warning(f"[Tick {tick_count}] Price fetch failed — skipping")
                await asyncio.sleep(poll_sec)
                continue

            # Safety check
            if not validate_exposure(state.position, price):
                state.skipped_ticks += 1
                exposure = state.position * price
                state.errors.append(
                    f"Tick {tick_count}: exposure ฿{exposure:,.0f} > cap ฿{MAX_NOTIONAL:,.0f}"
                )
                logger.warning(
                    f"[Tick {tick_count}] SAFETY: exposure ฿{exposure:,.0f} exceeds cap — skipping"
                )
                await asyncio.sleep(poll_sec)
                continue

            # Check fills: which orders should have filled?
            filled_this_tick = []
            for level_price, order in list(state.grid_levels.items()):
                if order.status != "PENDING":
                    continue

                if order.side == "BUY" and price <= level_price:
                    # Buy filled
                    order.status = "FILLED"
                    order.fill_price = level_price
                    order.fill_timestamp = time.time()
                    order.fee = level_price * ORDER_SIZE * FEE_RATE
                    state.position += ORDER_SIZE
                    state.cash -= (level_price * ORDER_SIZE) + order.fee
                    state.total_fees += order.fee
                    filled_this_tick.append(order)
                    logger.info(
                        f"[Tick {tick_count}] FILLED {order.id} BUY @ ฿{level_price:,.0f} "
                        f"(pos={state.position:.6f} BTC, cash=฿{state.cash:,.2f})"
                    )

                    # Place sell order one level up
                    spacing = state.center_price * (GRID_SPACING_PCT / 100.0)
                    sell_price = round(level_price + spacing)
                    order_counter += 1
                    new_sell = PaperOrder(
                        id=f"ORD-{order_counter:04d}",
                        side="SELL",
                        price=sell_price,
                        quantity=ORDER_SIZE,
                        timestamp=time.time(),
                    )
                    state.grid_levels[sell_price] = new_sell
                    logger.info(f"  → Placed SELL @ ฿{sell_price:,.0f} (id={new_sell.id})")

                elif order.side == "SELL" and price >= level_price:
                    # Sell filled
                    order.status = "FILLED"
                    order.fill_price = level_price
                    order.fill_timestamp = time.time()
                    order.fee = level_price * ORDER_SIZE * FEE_RATE
                    state.position -= ORDER_SIZE
                    state.cash += (level_price * ORDER_SIZE) - order.fee
                    state.total_fees += order.fee
                    # Calculate realized PnL for this round-trip
                    # Find corresponding buy (simplified: use avg entry)
                    gross_profit = (level_price - state.center_price) * ORDER_SIZE
                    state.realized_pnl += gross_profit - order.fee
                    filled_this_tick.append(order)
                    logger.info(
                        f"[Tick {tick_count}] FILLED {order.id} SELL @ ฿{level_price:,.0f} "
                        f"(pos={state.position:.6f} BTC, cash=฿{state.cash:,.2f}, "
                        f"PnL=฿{state.realized_pnl:,.2f})"
                    )

                    # Place buy order one level down
                    spacing = state.center_price * (GRID_SPACING_PCT / 100.0)
                    buy_price = round(level_price - spacing)
                    order_counter += 1
                    new_buy = PaperOrder(
                        id=f"ORD-{order_counter:04d}",
                        side="BUY",
                        price=buy_price,
                        quantity=ORDER_SIZE,
                        timestamp=time.time(),
                    )
                    state.grid_levels[buy_price] = new_buy
                    logger.info(f"  → Placed BUY @ ฿{buy_price:,.0f} (id={new_buy.id})")

            # Remove filled orders from active grid
            state.grid_levels = {
                p: o for p, o in state.grid_levels.items() if o.status == "PENDING"
            }

            # Log tick summary
            pending_buys = sum(1 for o in state.grid_levels.values() if o.side == "BUY")
            pending_sells = sum(1 for o in state.grid_levels.values() if o.side == "SELL")
            logger.info(
                f"[Tick {tick_count}] price=฿{price:,.0f} | "
                f"buys={pending_buys} sells={pending_sells} | "
                f"pos={state.position:.6f} | filled={len(state.filled_orders)} | "
                f"elapsed={elapsed_min:.1f}m remaining={remaining_min:.1f}m"
            )

            # Wait for next poll
            await asyncio.sleep(poll_sec)

        # ── Phase 3: Record results ───────────────────────────────────────────
        logger.info("")
        logger.info("--- TRIAL COMPLETE ---")
        trial_duration = (time.time() - trial_start) / 60
        final_price = await fetch_price(client)

        # Calculate unrealized PnL
        unrealized_pnl = 0.0
        if state.position > 0 and final_price > 0:
            # Average entry price (simplified)
            avg_entry = state.center_price  # approximate
            unrealized_pnl = (final_price - avg_entry) * state.position

        total_pnl = state.realized_pnl + unrealized_pnl
        max_exposure = max(
            [state.position * baseline_price] +
            [o.quantity * o.fill_price for o in state.grid_levels.values() if o.status == "FILLED"] +
            [0.0]
        )

        results = {
            "trial_start": baseline_time,
            "trial_end": datetime.now(timezone.utc).isoformat(),
            "duration_min": round(trial_duration, 1),
            "baseline_price": baseline_price,
            "final_price": final_price,
            "price_change_pct": round((final_price - baseline_price) / baseline_price * 100, 3) if final_price > 0 else None,
            "total_ticks": state.ticks,
            "skipped_ticks": state.skipped_ticks,
            "orders_placed": order_counter,
            "orders_filled": len([o for o in state.grid_levels.values() if o.status == "FILLED"]) + len(state.filled_orders),
            "active_orders": len(state.grid_levels),
            "final_position_btc": state.position,
            "final_cash_thb": round(state.cash, 2),
            "total_fees_thb": round(state.total_fees, 2),
            "realized_pnl_thb": round(state.realized_pnl, 2),
            "unrealized_pnl_thb": round(unrealized_pnl, 2),
            "total_pnl_thb": round(total_pnl, 2),
            "max_exposure_thb": round(max_exposure, 2),
            "safety_violations": state.errors,
            "grid_config": {
                "symbol": SYMBOL,
                "spacing_pct": GRID_SPACING_PCT,
                "levels": GRID_LEVELS,
                "order_size": ORDER_SIZE,
                "max_position": MAX_POSITION,
                "max_notional": MAX_NOTIONAL,
            },
        }

        # Write JSON output
        with open(output_json, "w") as f:
            json.dump(results, f, indent=2)

        logger.info(f"Duration:       {trial_duration:.1f} min")
        logger.info(f"Baseline price: ฿{baseline_price:,.2f}")
        logger.info(f"Final price:    ฿{final_price:,.2f}")
        logger.info(f"Price change:   {results['price_change_pct']}%")
        logger.info(f"Total ticks:    {state.ticks}")
        logger.info(f"Skipped ticks:  {state.skipped_ticks}")
        logger.info(f"Orders placed:  {order_counter}")
        logger.info(f"Orders filled:  {results['orders_filled']}")
        logger.info(f"Final position: {state.position:.6f} BTC")
        logger.info(f"Total fees:     ฿{state.total_fees:,.2f}")
        logger.info(f"Realized PnL:   ฿{state.realized_pnl:,.2f}")
        logger.info(f"Unrealized PnL: ฿{unrealized_pnl:,.2f}")
        logger.info(f"Total PnL:      ฿{total_pnl:,.2f}")
        logger.info(f"Max exposure:   ฿{max_exposure:,.2f}")
        logger.info(f"Safety guards:  {len(state.errors)} violations")
        logger.info("")
        logger.info(f"Results saved to: {output_json}")

        return results


def main():
    parser = argparse.ArgumentParser(description="BTCTHB Paper Grid Supervised Trial")
    parser.add_argument("--duration", type=int, default=30, help="Trial duration in minutes (default: 30)")
    parser.add_argument("--poll", type=int, default=60, help="Poll interval in seconds (default: 60)")
    parser.add_argument("--output", type=str, default="data/paper_grid_trial.json", help="Output JSON path")
    args = parser.parse_args()

    results = asyncio.run(run_trial(args.duration, args.poll, args.output))
    if results is None:
        sys.exit(1)


if __name__ == "__main__":
    main()
