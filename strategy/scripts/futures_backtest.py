#!/usr/bin/env python3
"""Run the read-only Spot versus Futures financial engineering comparison.

Examples (from the strategy directory):
    python3 scripts/futures_backtest.py --symbol BTCUSDT --days 90
    python3 scripts/futures_backtest.py --days 30 --json --output /tmp/bt.json

This script uses public market-data endpoints only. It never reads credentials
and never places, cancels, or modifies orders.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

from app.futures_backtest import (
    BacktestError,
    BinancePublicFuturesData,
    FinancialBacktestConfig,
    FinancialEngineeringBacktester,
    recent_window,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only Spot versus leveraged Futures backtest")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--interval", default="1h", choices=("5m", "15m", "1h", "4h", "1d"))
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--base-url", default="https://fapi.binance.com", help="public Futures market-data base URL")
    parser.add_argument("--initial-equity", type=float, default=1_000.0)
    parser.add_argument("--margin-allocation-pct", type=float, default=20.0)
    parser.add_argument("--leverage", default="1,2,3,5", help="comma-separated Futures leverage levels, max 5")
    parser.add_argument("--fee-bps", type=float, default=5.0, help="fee assumption per side in basis points")
    parser.add_argument("--slippage-bps", type=float, default=2.0, help="adverse slippage assumption per side")
    parser.add_argument("--stop-loss-pct", type=float, default=2.0)
    parser.add_argument("--take-profit-pct", type=float, default=4.0)
    parser.add_argument("--maintenance-margin-rate", type=float, default=0.004)
    parser.add_argument("--json", action="store_true", help="print the full JSON report")
    parser.add_argument("--output", type=Path, help="optional path for the JSON report")
    return parser


def _parse_leverage(raw: str) -> tuple[int, ...]:
    try:
        levels = tuple(int(item.strip()) for item in raw.split(",") if item.strip())
    except ValueError as exc:
        raise BacktestError("--leverage must be a comma-separated list of integers") from exc
    if not levels:
        raise BacktestError("--leverage must include at least one level")
    return levels


async def _run(args: argparse.Namespace) -> dict:
    start_time, end_time = recent_window(args.days)
    async with BinancePublicFuturesData(base_url=args.base_url) as data:
        candles = await data.fetch_klines(args.symbol, args.interval, start_time, end_time)
        funding = await data.fetch_funding_rates(args.symbol, start_time, end_time)
    now = int(time.time() * 1_000)
    candles = [candle for candle in candles if candle.close_time < now]
    if not candles:
        raise BacktestError("No closed candles were returned for the requested window")

    config = FinancialBacktestConfig(
        symbol=args.symbol,
        initial_equity_usdt=args.initial_equity,
        margin_allocation_pct=args.margin_allocation_pct,
        leverage_levels=_parse_leverage(args.leverage),
        fee_bps=args.fee_bps,
        slippage_bps=args.slippage_bps,
        stop_loss_pct=args.stop_loss_pct,
        take_profit_pct=args.take_profit_pct,
        maintenance_margin_rate=args.maintenance_margin_rate,
    )
    report = FinancialEngineeringBacktester(config).run_comparison(candles, funding)
    report["data"] = {
        "source": "Binance USDⓈ-M public REST market data",
        "base_url": args.base_url.rstrip("/"),
        "interval": args.interval,
        "requested_days": args.days,
        "closed_candles_used": len(candles),
        "funding_events_used": len(funding),
    }
    return report


def _print_table(report: dict) -> None:
    segment = report["segments"]["out_of_sample"]
    print(
        f"Financial backtest — {report['symbol']} — out-of-sample, "
        f"{report['data']['interval']} ({report['data']['closed_candles_used']} closed candles)"
    )
    print("Assumptions: fee={fee_bps:g} bps/side, slippage={slippage_bps:g} bps/side, "
          "margin allocation={margin_allocation_pct:g}%".format(**report["assumptions"]))
    print(f"{'variant':<14} {'return':>9} {'maxDD':>9} {'Sharpe':>9} {'trades':>8} {'fees':>10} {'funding':>10} {'liq':>5}")
    print("-" * 82)
    for result in segment["results"]:
        print(
            f"{result['label']:<14} {result['total_return_pct']:>8.2f}% "
            f"{result['max_drawdown_pct']:>8.2f}% {result['sharpe_ratio']:>9.2f} "
            f"{result['total_trades']:>8} {result['total_fees']:>10.2f} "
            f"{result['funding_pnl']:>10.2f} {result['liquidations']:>5}"
        )
    print("Ranking: " + " > ".join(segment["ranking_by_return"]))


def main() -> int:
    args = _parser().parse_args()
    try:
        report = asyncio.run(_run(args))
    except (BacktestError, OSError) as exc:
        print(f"ERROR: {exc}")
        return 1
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        print(f"Saved read-only report: {args.output}")
    if args.json:
        print(json.dumps(report, indent=2, allow_nan=False))
    else:
        _print_table(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
