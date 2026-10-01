#!/usr/bin/env python3
"""EMA/ADX futures backtest engine (Phase 4 research tooling).

READ-ONLY RESEARCH CODE. This module contains NO exchange credentials, NO
order placement and NO network access. It simulates fills against historical
OHLCV bars only. Nothing here is investment advice.

Execution model (no look-ahead):
    * Indicator values at bar ``i`` are computed from bars ``0..i`` only.
    * A signal observed at the CLOSE of bar ``i`` is executed at the OPEN of
      bar ``i+1`` (slippage and taker fees applied to the fill).
    * One position at a time.

Determinism: no randomness, no wall-clock, no global state mutated between
runs. Same inputs -> identical outputs.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import NamedTuple

MS_PER_YEAR = 365 * 24 * 3600 * 1000
FUNDING_INTERVAL_MS = 8 * 3600 * 1000  # 8 hours


class Bar(NamedTuple):
    open_time_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float


def to_bar(row) -> Bar:
    """Accept a Bar, a dict, or any sequence with the Bar field order."""
    if isinstance(row, Bar):
        return row
    if isinstance(row, dict):
        return Bar(
            int(row["open_time_ms"]),
            float(row["open"]),
            float(row["high"]),
            float(row["low"]),
            float(row["close"]),
            float(row.get("volume", 0.0)),
        )
    return Bar(
        int(row[0]),
        float(row[1]),
        float(row[2]),
        float(row[3]),
        float(row[4]),
        float(row[5]) if len(row) > 5 else 0.0,
    )


@dataclass(frozen=True)
class StrategyConfig:
    ema_fast: int = 12
    ema_slow: int = 26
    adx_period: int = 14
    adx_threshold: float = 25.0
    mode: str = "long_only"  # long_only | long_short
    instrument: str = "spot"  # spot | futures
    leverage: int = 1  # futures only: 1, 2, 3, 5
    taker_fee_bps: float = 5.0
    slippage_bps: float = 2.0
    funding_rate_bps_per_8h: float = 1.0  # fallback when no funding series
    maintenance_margin_rate: float = 0.005
    initial_equity: float = 10000.0

    def __post_init__(self):
        if self.mode not in ("long_only", "long_short"):
            raise ValueError(f"bad mode: {self.mode}")
        if self.instrument not in ("spot", "futures"):
            raise ValueError(f"bad instrument: {self.instrument}")
        if self.instrument == "futures" and self.leverage not in (1, 2, 3, 5):
            raise ValueError(f"bad leverage: {self.leverage}")
        if self.ema_fast < 1 or self.ema_slow < 1 or self.adx_period < 1:
            raise ValueError("periods must be >= 1")


@dataclass
class Trade:
    entry_time_ms: int
    exit_time_ms: int
    side: str  # long | short
    entry_price: float  # effective fill price (slippage applied)
    exit_price: float
    qty: float
    pnl: float  # trading pnl after liquidation cap, before fees
    fees: float  # entry + exit taker fees
    funding_paid: float  # > 0 paid by us, < 0 received
    reason: str  # signal_flip | signal_exit | liquidated | end_of_data


@dataclass
class BacktestResult:
    trades: list = field(default_factory=list)
    equity_curve: list = field(default_factory=list)  # [(time_ms, equity)]
    metrics: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Indicators (no look-ahead: value at index i uses bars 0..i only)
# ---------------------------------------------------------------------------


def ema(values: Sequence[float], period: int) -> list:
    """Standard recursive EMA seeded by the SMA of the first ``period`` values.

    Returns a list aligned with ``values``; entries before index
    ``period - 1`` are None.
    """
    out = [None] * len(values)
    if period < 1 or len(values) < period:
        return out
    alpha = 2.0 / (period + 1.0)
    prev = sum(values[:period]) / period
    out[period - 1] = prev
    for i in range(period, len(values)):
        prev = alpha * values[i] + (1.0 - alpha) * prev
        out[i] = prev
    return out


def adx(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> list:
    """Wilder's ADX. Entries are None until the first ADX value is defined.

    Smoothing follows Wilder: first smoothed TR/+DM/-DM are plain sums of the
    first ``period`` values (bars 1..period), then
    ``s[i] = s[i-1] - s[i-1]/period + raw[i]``. The first ADX is the mean of
    the first ``period`` DX values, defined at bar index ``2*period - 1``.
    """
    n = len(closes)
    out = [None] * n
    if n < 2 * period:
        return out
    trs, plus_dm, minus_dm = [], [], []
    for i in range(1, n):
        up = highs[i] - highs[i - 1]
        down = lows[i - 1] - lows[i]
        trs.append(
            max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
        )
        plus_dm.append(up if up > down and up > 0 else 0.0)
        minus_dm.append(down if down > up and down > 0 else 0.0)
    # trs[k] corresponds to bar index k+1.
    atr = sum(trs[:period])
    psm = sum(plus_dm[:period])
    msm = sum(minus_dm[:period])
    dxs = []  # (bar_index, dx)

    def dx_value(atr_v, psm_v, msm_v):
        if atr_v == 0.0:
            return 0.0
        pdi = 100.0 * psm_v / atr_v
        mdi = 100.0 * msm_v / atr_v
        denom = pdi + mdi
        if denom == 0.0:
            return 0.0
        return 100.0 * abs(pdi - mdi) / denom

    dxs.append(dx_value(atr, psm, msm))  # bar index == period
    for k in range(period, len(trs)):
        atr = atr - atr / period + trs[k]
        psm = psm - psm / period + plus_dm[k]
        msm = msm - msm / period + minus_dm[k]
        dxs.append(dx_value(atr, psm, msm))  # bar index == k+1
    # dxs[j] is the DX at bar index period + j.
    if len(dxs) < period:
        return out
    first = sum(dxs[:period]) / period
    first_bar = 2 * period - 1
    out[first_bar] = first
    prev = first
    for j in range(period, len(dxs)):
        prev = (prev * (period - 1) + dxs[j]) / period
        out[period + j] = prev
    return out


def compute_signals(bars: Sequence[Bar], cfg: StrategyConfig) -> list:
    """Target side (+1 long, -1 short, 0 flat) from the CLOSE of each bar."""
    closes = [b.close for b in bars]
    ef = ema(closes, cfg.ema_fast)
    es = ema(closes, cfg.ema_slow)
    ax = adx([b.high for b in bars], [b.low for b in bars], closes, cfg.adx_period)
    allow_short = cfg.mode == "long_short" and cfg.instrument == "futures"
    signals = []
    for i in range(len(bars)):
        if ef[i] is None or es[i] is None or ax[i] is None:
            signals.append(0)
        elif ef[i] > es[i] and ax[i] >= cfg.adx_threshold:
            signals.append(1)
        elif allow_short and ef[i] < es[i] and ax[i] >= cfg.adx_threshold:
            signals.append(-1)
        else:
            signals.append(0)
    return signals


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def median_interval_ms(bars: Sequence[Bar]) -> float:
    if len(bars) < 2:
        return 3600 * 1000.0
    deltas = sorted(
        bars[i + 1].open_time_ms - bars[i].open_time_ms for i in range(len(bars) - 1)
    )
    return deltas[len(deltas) // 2]


def max_drawdown_pct(equity_curve: Sequence) -> float:
    peak = None
    worst = 0.0
    for _, eq in equity_curve:
        if peak is None or eq > peak:
            peak = eq
        if peak > 0:
            worst = max(worst, (peak - eq) / peak * 100.0)
    return worst


def sharpe_ratio(returns: Sequence[float], periods_per_year: float) -> float:
    n = len(returns)
    if n < 2:
        return 0.0
    mean = sum(returns) / n
    var = sum((r - mean) ** 2 for r in returns) / (n - 1)
    if var <= 0.0:
        return 0.0
    return mean / math.sqrt(var) * math.sqrt(periods_per_year)


def profit_factor(pnls: Sequence[float]) -> float:
    wins = sum(p for p in pnls if p > 0)
    losses = -sum(p for p in pnls if p < 0)
    if losses == 0.0:
        return float("inf") if wins > 0 else 0.0
    return wins / losses


def compute_metrics(
    equity_curve: Sequence,
    trades: Sequence[Trade],
    bar_interval_ms: float,
    initial_equity: float,
) -> dict:
    periods_per_year = MS_PER_YEAR / bar_interval_ms
    rets = [
        equity_curve[i][1] / equity_curve[i - 1][1] - 1.0
        for i in range(1, len(equity_curve))
        if equity_curve[i - 1][1] != 0
    ]
    pnls = [t.pnl for t in trades]
    final_eq = equity_curve[-1][1] if equity_curve else initial_equity
    wins = sum(1 for p in pnls if p > 0)
    return {
        "total_return_pct": (final_eq / initial_equity - 1.0) * 100.0,
        "max_drawdown_pct": max_drawdown_pct(equity_curve),
        "sharpe": sharpe_ratio(rets, periods_per_year),
        "profit_factor": profit_factor(pnls),
        "win_rate": wins / len(trades) if trades else 0.0,
        "num_trades": len(trades),
        "num_liquidations": sum(1 for t in trades if t.reason == "liquidated"),
    }


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


def _rate_at(funding: Sequence | None, time_ms: int, fallback_bps: float) -> float:
    """Funding rate (decimal) in force at ``time_ms``.

    Uses the latest series event at or before ``time_ms``; falls back to the
    constant ``funding_rate_bps_per_8h`` when no series or no earlier event.
    """
    if not funding:
        return fallback_bps / 1e4
    rate = None
    for t, r in funding:
        if t <= time_ms:
            rate = r
        else:
            break
    return rate if rate is not None else fallback_bps / 1e4


def run_backtest(
    bars, cfg: StrategyConfig | None = None, funding: Sequence | None = None
) -> BacktestResult:
    """Run the EMA/ADX strategy over ``bars``. Pure: no I/O, no printing.

    ``funding`` is an optional sorted series of ``(time_ms, rate)`` tuples
    (rate as a decimal, e.g. 0.0001 == 1 bp per 8 h).

    Liquidation approximation (futures): checked once per bar at the bar
    close. If the mark-to-market loss reaches ``posted_margin -
    maintenance_margin_rate * entry_notional`` the position is force-closed
    at that bar's close (slippage applied) instead of the exact liquidation
    price, and the realized loss is capped at the posted margin. This is a
    deliberate, documented simplification — real venues liquidate intra-bar
    at a computed bankruptcy-avoiding price.
    """
    if cfg is None:
        cfg = StrategyConfig()
    bars = [to_bar(b) for b in bars]
    fee_rate = cfg.taker_fee_bps / 1e4
    slip = cfg.slippage_bps / 1e4
    signals = compute_signals(bars, cfg)
    is_futures = cfg.instrument == "futures"

    cash = cfg.initial_equity
    pos = None  # dict: side, qty, entry_price, entry_time_ms, margin, notional
    trades: list = []
    equity_curve: list = [(bars[0].open_time_ms, cash)] if bars else []

    def buy_price(p):
        return p * (1.0 + slip)

    def sell_price(p):
        return p * (1.0 - slip)

    def close_position(price_raw, time_ms, reason):
        nonlocal cash, pos
        if pos["side"] == "long":
            fill = sell_price(price_raw)
            realized = pos["qty"] * (fill - pos["entry_price"])
        else:
            fill = buy_price(price_raw)
            realized = pos["qty"] * (pos["entry_price"] - fill)
        if reason == "liquidated":
            realized = max(realized, -pos["margin"])
        exit_fee = pos["qty"] * fill * fee_rate
        # Spot cash was reduced by the full notional at entry, so the exit
        # credits the full sale proceeds; futures only settles the pnl.
        cash += (pos["qty"] * fill if not is_futures else realized) - exit_fee
        trades.append(
            Trade(
                entry_time_ms=pos["entry_time_ms"],
                exit_time_ms=time_ms,
                side=pos["side"],
                entry_price=pos["entry_price"],
                exit_price=fill,
                qty=pos["qty"],
                pnl=realized,
                fees=pos["entry_fee"] + exit_fee,
                funding_paid=pos["funding_paid"],
                reason=reason,
            )
        )
        pos = None

    def open_position(side, price_raw, time_ms):
        nonlocal cash, pos
        if side == 1:
            fill = buy_price(price_raw)
        else:
            fill = sell_price(price_raw)
        if is_futures:
            notional = cash * cfg.leverage
            margin = notional / cfg.leverage
        else:  # spot: notional == equity, no borrowing, long only
            notional = cash
            margin = notional
        qty = notional / fill
        entry_fee = notional * fee_rate
        cash -= (notional if not is_futures else 0.0) + entry_fee
        pos = {
            "side": "long" if side == 1 else "short",
            "qty": qty,
            "entry_price": fill,
            "entry_time_ms": time_ms,
            "margin": margin,
            "notional": notional,
            "entry_fee": entry_fee,
            "funding_paid": 0.0,
        }

    def unrealized(mark):
        if pos["side"] == "long":
            return pos["qty"] * (mark - pos["entry_price"])
        return pos["qty"] * (pos["entry_price"] - mark)

    for i, bar in enumerate(bars):
        # 1) Execute the signal observed at the close of the previous bar,
        #    at THIS bar's open (no look-ahead).
        if i > 0:
            target = signals[i - 1]
            cur = 0 if pos is None else (1 if pos["side"] == "long" else -1)
            if target != cur:
                if pos is not None:
                    reason = "signal_flip" if target != 0 else "signal_exit"
                    close_position(bar.open, bar.open_time_ms, reason)
                if target != 0:
                    open_position(target, bar.open, bar.open_time_ms)

        # 2) Funding: charged when an 8 h boundary is crossed while a
        #    futures position is open. Positive rate costs longs / pays
        #    shorts; notional is marked at this bar's close (approximation).
        if pos is not None and is_futures and i > 0:
            prev_bucket = bars[i - 1].open_time_ms // FUNDING_INTERVAL_MS
            bucket = bar.open_time_ms // FUNDING_INTERVAL_MS
            if bucket > prev_bucket:
                rate = _rate_at(funding, bar.open_time_ms, cfg.funding_rate_bps_per_8h)
                for _ in range(bucket - prev_bucket):
                    amount = pos["qty"] * bar.close * rate
                    if pos["side"] == "long":
                        cash -= amount
                        pos["funding_paid"] += amount
                    else:
                        cash += amount
                        pos["funding_paid"] -= amount

        # 3) Liquidation check at the bar close (futures only).
        if pos is not None and is_futures:
            loss_limit = pos["margin"] - cfg.maintenance_margin_rate * pos["notional"]
            if -unrealized(bar.close) >= loss_limit:
                close_position(bar.close, bar.open_time_ms, "liquidated")

        # 4) Mark equity at the close.
        eq = (
            cash
            if pos is None
            else cash
            + (pos["qty"] * bar.close if not is_futures else unrealized(bar.close))
        )
        equity_curve.append((bar.open_time_ms, eq))

    # 5) Flatten at end of data.
    if pos is not None:
        close_position(bars[-1].close, bars[-1].open_time_ms, "end_of_data")
        eq = cash
        equity_curve.append((bars[-1].open_time_ms, eq))

    interval = median_interval_ms(bars)
    metrics = compute_metrics(equity_curve, trades, interval, cfg.initial_equity)
    return BacktestResult(trades=trades, equity_curve=equity_curve, metrics=metrics)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _jsonable(obj):
    if isinstance(obj, float) and not math.isfinite(obj):
        return "Infinity" if obj > 0 else "-Infinity"
    raise TypeError(type(obj).__name__)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="EMA/ADX backtest engine (read-only research, no orders)."
    )
    ap.add_argument("--csv", required=True, help="bar cache CSV (see data.py)")
    ap.add_argument(
        "--funding-csv", default=None, help="optional funding series CSV (time_ms,rate)"
    )
    ap.add_argument("--ema-fast", type=int, default=12)
    ap.add_argument("--ema-slow", type=int, default=26)
    ap.add_argument("--adx-period", type=int, default=14)
    ap.add_argument("--adx-threshold", type=float, default=25.0)
    ap.add_argument("--mode", choices=["long_only", "long_short"], default="long_only")
    ap.add_argument("--instrument", choices=["spot", "futures"], default="futures")
    ap.add_argument("--leverage", type=int, default=1)
    ap.add_argument("--taker-fee-bps", type=float, default=5.0)
    ap.add_argument("--slippage-bps", type=float, default=2.0)
    ap.add_argument("--funding-bps-per-8h", type=float, default=1.0)
    ap.add_argument("--initial-equity", type=float, default=10000.0)
    args = ap.parse_args(argv)

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from data import load_csv, load_funding_csv  # local import; stdlib only

    bars = load_csv(args.csv)
    funding = load_funding_csv(args.funding_csv) if args.funding_csv else None
    cfg = StrategyConfig(
        ema_fast=args.ema_fast,
        ema_slow=args.ema_slow,
        adx_period=args.adx_period,
        adx_threshold=args.adx_threshold,
        mode=args.mode,
        instrument=args.instrument,
        leverage=args.leverage,
        taker_fee_bps=args.taker_fee_bps,
        slippage_bps=args.slippage_bps,
        funding_rate_bps_per_8h=args.funding_bps_per_8h,
        initial_equity=args.initial_equity,
    )
    result = run_backtest(bars, cfg, funding)
    print(
        json.dumps(
            {
                "config": vars(replace(cfg)),
                "metrics": result.metrics,
                "num_trades": len(result.trades),
            },
            indent=2,
            default=_jsonable,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
