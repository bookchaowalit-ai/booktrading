#!/usr/bin/env python3
"""Stdlib unittest suite for futures_backtest.py. No network, no pytest."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from futures_backtest import (  # noqa: E402
    Bar,
    StrategyConfig,
    adx,
    ema,
    run_backtest,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sample_1h.csv"


def mkbar(i, o, h, l, c, v=1.0):
    return Bar(i * 3600 * 1000, float(o), float(h), float(l), float(c), float(v))


class IndicatorTest(unittest.TestCase):
    def test_ema_matches_hand_computed(self):
        values = [float(x) for x in range(1, 11)]  # 1..10
        out = ema(values, 3)
        # seeded by SMA of first 3 closes; alpha = 2/(3+1) = 0.5
        self.assertIsNone(out[0])
        self.assertIsNone(out[1])
        self.assertAlmostEqual(out[2], 2.0)  # (1+2+3)/3
        self.assertAlmostEqual(out[3], 0.5 * 4 + 0.5 * 2.0)  # 3.0
        self.assertAlmostEqual(out[4], 0.5 * 5 + 0.5 * 3.0)  # 4.0
        self.assertAlmostEqual(out[5], 0.5 * 6 + 0.5 * 4.0)  # 5.0

    def test_ema_shorter_than_period_all_none(self):
        self.assertEqual(ema([1.0, 2.0], 5), [None, None])

    def test_adx_monotonic_uptrend_is_100(self):
        # Steadily rising bars: +DM > 0, -DM == 0 -> DX = 100 at every bar,
        # so the first ADX (bar 2*period-1) is exactly 100 and stays 100.
        n, period = 20, 3
        bars = [
            mkbar(i, 100 + i, 100 + 1.2 * i, 100 + 0.8 * i, 100 + i) for i in range(n)
        ]
        out = adx(
            [b.high for b in bars],
            [b.low for b in bars],
            [b.close for b in bars],
            period,
        )
        for i in range(2 * period - 1):
            self.assertIsNone(out[i], f"adx[{i}] should be undefined")
        for i in range(2 * period - 1, n):
            self.assertAlmostEqual(out[i], 100.0, places=9)


class ExecutionTest(unittest.TestCase):
    """Hand-crafted 5-bar scenario with ema 1/2, adx period 1, threshold 0.

    Signal goes long at the close of bar1 and flat at the close of bar3,
    so the fill must happen at the OPEN of bar2 and bar4 respectively.
    """

    def bars(self):
        return [
            mkbar(0, 100, 101, 99, 100),
            mkbar(1, 100, 102, 100, 101),
            mkbar(2, 102, 103, 101, 102),
            mkbar(3, 102, 102, 99, 100),
            mkbar(4, 100, 100, 98, 99),
        ]

    def cfg(self, **kw):
        base = {
            "ema_fast": 1,
            "ema_slow": 2,
            "adx_period": 1,
            "adx_threshold": 0.0,
            "mode": "long_only",
            "instrument": "spot",
            "leverage": 1,
            "taker_fee_bps": 5.0,
            "slippage_bps": 2.0,
            "initial_equity": 10000.0,
        }
        base.update(kw)
        return StrategyConfig(**base)

    def test_entry_at_next_bar_open_not_signal_close(self):
        result = run_backtest(self.bars(), self.cfg())
        self.assertEqual(len(result.trades), 1)
        trade = result.trades[0]
        bars = self.bars()
        # entry fill = open of bar2 (signal bar was bar1, close 101)
        self.assertAlmostEqual(trade.entry_price, bars[2].open * 1.0002)
        self.assertNotAlmostEqual(trade.entry_price, bars[1].close)
        self.assertEqual(trade.entry_time_ms, bars[2].open_time_ms)
        # exit fill = open of bar4 (signal bar was bar3, close 100)
        self.assertAlmostEqual(trade.exit_price, bars[4].open * 0.9998)
        self.assertNotAlmostEqual(trade.exit_price, bars[3].close)
        self.assertEqual(trade.exit_time_ms, bars[4].open_time_ms)
        self.assertEqual(trade.reason, "signal_exit")

    def test_fees_and_slippage_reduce_pnl_by_exact_amount(self):
        result = run_backtest(self.bars(), self.cfg())
        trade = result.trades[0]
        entry_eff = 102.0 * 1.0002  # slippage on the buy
        exit_eff = 100.0 * 0.9998  # slippage on the sell
        qty = 10000.0 / entry_eff
        fee_in = 10000.0 * 0.0005
        fee_out = qty * exit_eff * 0.0005
        self.assertAlmostEqual(trade.qty, qty)
        self.assertAlmostEqual(trade.pnl, qty * (exit_eff - entry_eff))
        self.assertAlmostEqual(trade.fees, fee_in + fee_out)
        expected_equity = -fee_in + qty * exit_eff - fee_out
        self.assertAlmostEqual(result.equity_curve[-1][1], expected_equity)
        # frictionless comparison: costs must account for the difference
        frictionless = 10000.0 * (100.0 / 102.0)
        cost = frictionless - expected_equity
        self.assertGreater(cost, 0.0)
        self.assertAlmostEqual(cost, frictionless - expected_equity, places=9)


class FundingTest(unittest.TestCase):
    """Funding charged once at the 8h boundary with correct sign."""

    def bars(self, rising=True):
        out = []
        for i in range(12):
            c = 100.0 + i if rising else 100.0 - i
            out.append(mkbar(i, c, c + 1.0, c - 1.0, c))
        return out

    def cfg(self, mode):
        return StrategyConfig(
            ema_fast=1,
            ema_slow=2,
            adx_period=1,
            adx_threshold=0.0,
            mode=mode,
            instrument="futures",
            leverage=1,
            taker_fee_bps=0.0,
            slippage_bps=0.0,
            funding_rate_bps_per_8h=100.0,  # 1% per 8h
            initial_equity=10000.0,
        )

    def test_long_pays_funding(self):
        bars = self.bars(rising=True)
        result = run_backtest(bars, self.cfg("long_only"))
        self.assertEqual(len(result.trades), 1)
        trade = result.trades[0]
        qty = 10000.0 / bars[2].open
        # one 8h boundary crossed (between bar7 and bar8), marked at close8
        expected = qty * bars[8].close * 0.01
        self.assertAlmostEqual(trade.funding_paid, expected)  # paid (> 0)
        realized = qty * (bars[-1].close - bars[2].open)
        self.assertAlmostEqual(
            result.equity_curve[-1][1], 10000.0 - expected + realized
        )

    def test_short_receives_funding(self):
        bars = self.bars(rising=False)
        result = run_backtest(bars, self.cfg("long_short"))
        self.assertEqual(len(result.trades), 1)
        trade = result.trades[0]
        self.assertEqual(trade.side, "short")
        qty = 10000.0 / bars[2].open
        expected = qty * bars[8].close * 0.01
        self.assertAlmostEqual(trade.funding_paid, -expected)  # received
        realized = qty * (bars[2].open - bars[-1].close)
        self.assertAlmostEqual(
            result.equity_curve[-1][1], 10000.0 + expected + realized
        )


class LiquidationTest(unittest.TestCase):
    def test_crash_liquidates_and_caps_loss_at_margin(self):
        bars = [
            mkbar(0, 100, 101, 99, 100),
            mkbar(1, 100, 102, 100, 101),
            mkbar(2, 102, 103, 101, 102),
            mkbar(3, 101, 102, 79, 80),  # crash: -21.6% from entry
            mkbar(4, 80, 81, 78, 79),
        ]
        cfg = StrategyConfig(
            ema_fast=1,
            ema_slow=2,
            adx_period=1,
            adx_threshold=0.0,
            mode="long_only",
            instrument="futures",
            leverage=5,
            taker_fee_bps=0.0,
            slippage_bps=0.0,
            maintenance_margin_rate=0.005,
            initial_equity=10000.0,
        )
        result = run_backtest(bars, cfg)
        self.assertEqual(len(result.trades), 1)
        trade = result.trades[0]
        margin = 10000.0  # notional 50000 / leverage 5
        self.assertEqual(trade.reason, "liquidated")
        self.assertEqual(trade.exit_time_ms, bars[3].open_time_ms)
        self.assertAlmostEqual(trade.exit_price, bars[3].close)
        # uncapped loss would be qty*(80-102) < -margin; capped at margin
        self.assertAlmostEqual(trade.pnl, -margin)
        self.assertAlmostEqual(result.equity_curve[-1][1], 0.0)
        self.assertEqual(result.metrics["num_liquidations"], 1)


class SpotLeverageTest(unittest.TestCase):
    def test_spot_ignores_leverage(self):
        from data import load_csv

        bars = load_csv(FIXTURE)[:3000]
        base = {
            "ema_fast": 12,
            "ema_slow": 26,
            "adx_threshold": 25.0,
            "mode": "long_only",
            "instrument": "spot",
        }
        r1 = run_backtest(bars, StrategyConfig(leverage=1, **base))
        r5 = run_backtest(bars, StrategyConfig(leverage=5, **base))
        self.assertEqual(r1.trades, r5.trades)
        self.assertEqual(r1.equity_curve, r5.equity_curve)


class DeterminismTest(unittest.TestCase):
    def test_two_runs_identical(self):
        from data import load_csv

        bars = load_csv(FIXTURE)
        cfg = StrategyConfig(
            ema_fast=12,
            ema_slow=26,
            adx_threshold=25.0,
            mode="long_short",
            instrument="futures",
            leverage=3,
        )
        a = run_backtest(bars, cfg)
        b = run_backtest(bars, cfg)
        self.assertEqual(a.trades, b.trades)
        self.assertEqual(a.equity_curve, b.equity_curve)
        self.assertEqual(a.metrics, b.metrics)


if __name__ == "__main__":
    unittest.main(verbosity=2)
