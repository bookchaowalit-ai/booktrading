#!/usr/bin/env python3
"""
Backtest matrix: evaluate the live grid parameters against alternatives
over recent history, per actively-traded symbol.

Run inside the strategy container:
    docker compose exec -T -w /app strategy python3 /app/scripts/backtest_matrix.py
or pipe via stdin:
    docker compose exec -T -w /app strategy python3 - < strategy/scripts/backtest_matrix.py

Read-only: fetches public klines, places no orders.
"""

import asyncio
import json
import os
from datetime import datetime, timezone

from app.backtester import BacktestConfig, GridBacktester

DAYS = 30
INTERVAL = "1h"
REPORTS_DIR = "/app/reports"

# Live per-symbol settings (mirrors SYMBOL_DEFAULTS in real_grid_bot.py).
# BTCTHB is excluded: it's buy_only (DCA-managed), grid round trips can't happen.
LIVE = {
    "ETHTHB": {"spacing": 2.0, "levels": 1, "order_size": 0.002, "max_position": 0.004},
    "SOLTHB": {"spacing": 3.0, "levels": 1, "order_size": 0.05, "max_position": 0.10},
    "XRPTHB": {"spacing": 2.0, "levels": 1, "order_size": 3.0, "max_position": 6.0},
}


def make_configs(symbol: str, live: dict) -> dict:
    base = dict(
        symbol=symbol,
        order_size=live["order_size"],
        max_position=live["max_position"] * 3,  # allow the grid to breathe in backtest
        max_open_orders=10,
        initial_capital_thb=1200.0,  # roughly live per-symbol capital
    )
    return {
        "live": BacktestConfig(
            **base, grid_spacing_pct=live["spacing"], grid_levels=live["levels"],
        ),
        "tight-0.7%": BacktestConfig(
            **base, grid_spacing_pct=0.7, grid_levels=2,
        ),
        "atr-dynamic": BacktestConfig(
            **base, grid_spacing_pct=live["spacing"], grid_levels=2,
            volatility_mode="atr", atr_multiplier=1.5, min_spacing_pct=0.5,
        ),
        "tight+confluence": BacktestConfig(
            **base, grid_spacing_pct=0.7, grid_levels=2,
            enable_entry_confluence=True,
        ),
    }


async def main():
    all_results = {}
    print(f"Backtest matrix — {DAYS}d of {INTERVAL} klines, fee 0.1%/side")
    print(f"{'symbol':<8} {'config':<18} {'trades':>6} {'win%':>6} {'net_pnl':>9} "
          f"{'fees':>7} {'maxDD%':>7} {'t/day':>6}")
    print("-" * 74)

    for symbol, live in LIVE.items():
        all_results[symbol] = {}
        for name, cfg in make_configs(symbol, live).items():
            bt = GridBacktester(cfg)
            try:
                r = await bt.run(days=DAYS, interval=INTERVAL)
                all_results[symbol][name] = {
                    "trades": r.total_trades,
                    "win_rate": r.win_rate,
                    "net_pnl": r.net_pnl,
                    "total_fees": r.total_fees,
                    "max_drawdown_pct": r.max_drawdown_pct,
                    "trades_per_day": r.trades_per_day,
                    "profit_factor": r.profit_factor,
                    "config": {
                        "spacing": cfg.grid_spacing_pct,
                        "levels": cfg.grid_levels,
                        "mode": cfg.volatility_mode,
                        "confluence": cfg.enable_entry_confluence,
                    },
                }
                print(f"{symbol:<8} {name:<18} {r.total_trades:>6} {r.win_rate:>5.0f}% "
                      f"{r.net_pnl:>9.2f} {r.total_fees:>7.2f} "
                      f"{r.max_drawdown_pct:>6.1f}% {r.trades_per_day:>6.1f}")
            except Exception as e:
                print(f"{symbol:<8} {name:<18} ERROR: {e}")
                all_results[symbol][name] = {"error": str(e)}
            finally:
                await bt.close()

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "days": DAYS,
        "interval": INTERVAL,
        "results": all_results,
    }
    os.makedirs(REPORTS_DIR, exist_ok=True)
    path = os.path.join(REPORTS_DIR, f"backtest-matrix-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nSaved: {path}")


if __name__ == "__main__":
    asyncio.run(main())
