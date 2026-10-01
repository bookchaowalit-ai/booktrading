#!/usr/bin/env python3
"""Stdlib unittest suite for walk_forward.py. No network, no pytest."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data import load_csv, save_csv, save_funding_csv  # noqa: E402
from fixtures import generate_bars, generate_funding  # noqa: E402
from futures_backtest import Bar, StrategyConfig, run_backtest  # noqa: E402
from walk_forward import (  # noqa: E402
    RiskGateConfig,
    WalkForwardConfig,
    build_grid,
    evaluate_gate,
    make_windows,
    run_walk_forward,
    select_variant,
)

TRADING = Path(__file__).resolve().parents[1]
FIXTURE = TRADING / "fixtures" / "sample_1h.csv"
FUNDING_FIXTURE = TRADING / "fixtures" / "sample_funding.csv"


def small_grid(wf):
    return build_grid(
        wf,
        ema_pairs=[(9, 21), (12, 26)],
        adx_thresholds=[20.0],
        modes=["long_only"],
        instruments=[("spot", 1), ("futures", 2)],
    )


class WindowTest(unittest.TestCase):
    def test_window_count_matches_formula(self):
        wf = WalkForwardConfig(train_bars=2160, test_bars=720, step_bars=720)
        windows = make_windows(9000, wf)
        expected = (9000 - 2160 - 720) // 720 + 1
        self.assertEqual(len(windows), expected)  # 9
        for trs, tre, ts, te in windows:
            self.assertEqual(tre - trs, 2160)
            self.assertEqual(te - ts, 720)
            self.assertEqual(tre, ts)  # no overlap, no gap
        # consecutive windows slide by step
        self.assertEqual(windows[1][0] - windows[0][0], 720)

    def test_too_little_data_yields_no_windows(self):
        wf = WalkForwardConfig(train_bars=100, test_bars=50, step_bars=50)
        self.assertEqual(make_windows(149, wf), [])


class NoLookAheadTest(unittest.TestCase):
    """Truncating the series must not change anything up to the cut: future
    data cannot alter past trades or past equity."""

    def test_truncated_run_matches_full_run_prefix(self):
        bars = load_csv(FIXTURE)
        k = 5000
        cfg = StrategyConfig(
            ema_fast=12,
            ema_slow=26,
            adx_threshold=25.0,
            mode="long_short",
            instrument="futures",
            leverage=2,
        )
        full = run_backtest(bars, cfg)
        part = run_backtest(bars[:k], cfg)
        # equity curve: one initial point plus one per bar -> k+1 entries
        self.assertEqual(len(part.equity_curve), k + 1)
        self.assertEqual(part.equity_curve, full.equity_curve[: k + 1])
        # trades that closed strictly before the final truncated bar must be
        # an exact prefix of the full run's trades (a trade still open at
        # the cut closes as end_of_data, which is not a look-ahead issue)
        cutoff = bars[k - 1].open_time_ms
        closed = [t for t in part.trades if t.exit_time_ms < cutoff]
        self.assertEqual(closed, full.trades[: len(closed)])
        self.assertGreater(len(closed), 0)


class NoParameterLeakageTest(unittest.TestCase):
    """In select mode the test slice must be invisible to selection."""

    def setUp(self):
        self.bars = load_csv(FIXTURE)[:2000]
        self.wf = WalkForwardConfig(train_bars=400, test_bars=200, step_bars=200)
        self.grid = small_grid(self.wf)

    def test_mutating_only_test_slice_keeps_selection(self):
        report_a = run_walk_forward(
            self.bars, self.wf, RiskGateConfig(), mode="select", grid=self.grid
        )
        selections_a = report_a["variants"][0]["selections"]

        # bars [1800:2000) belong to the last window's TEST slice only:
        # train slices are [s, s+400) for s in 0..1400 -> union [0,1800).
        mutated = list(self.bars)
        for i in range(1800, 2000):
            b = mutated[i]
            mutated[i] = Bar(
                b.open_time_ms,
                b.open * 2.0,
                b.high * 2.0,
                b.low * 2.0,
                b.close * 2.0,
                b.volume,
            )
        report_b = run_walk_forward(
            mutated, self.wf, RiskGateConfig(), mode="select", grid=self.grid
        )
        selections_b = report_b["variants"][0]["selections"]
        self.assertEqual(selections_a, selections_b)

    def test_selection_uses_exactly_the_train_slice(self):
        windows = make_windows(len(self.bars), self.wf)
        report = run_walk_forward(
            self.bars, self.wf, RiskGateConfig(), mode="select", grid=self.grid
        )
        selections = report["variants"][0]["selections"]
        self.assertEqual(len(selections), len(windows))
        for (trs, tre, _, _), name in zip(windows, selections):
            # calling select_variant with ONLY the train slice must
            # reproduce the recorded selection for that window
            chosen = select_variant(self.bars[trs:tre], self.grid, None)
            self.assertEqual(chosen.name, name)


class RiskGateTest(unittest.TestCase):
    def row(self, **kw):
        base = {
            "median_window_return_pct": 5.0,
            "max_drawdown_pct": 10.0,
            "sharpe": 1.0,
            "pct_profitable_windows": 60.0,
        }
        base.update(kw)
        return base

    def test_losing_variant_fails_with_correct_reasons(self):
        gate = RiskGateConfig()
        baseline = self.row(median_window_return_pct=3.0)
        bad = self.row(
            median_window_return_pct=1.0,  # below baseline
            max_drawdown_pct=30.0,  # above 25 limit
            sharpe=-0.5,  # below 0
            pct_profitable_windows=20.0,
        )  # below 40
        verdict = evaluate_gate(bad, baseline, gate)
        self.assertEqual(verdict["verdict"], "FAIL")
        self.assertEqual(len(verdict["reasons"]), 4)
        text = " ".join(verdict["reasons"])
        self.assertIn("does not beat spot baseline", text)
        self.assertIn("max drawdown", text)
        self.assertIn("sharpe", text)
        self.assertIn("profitable windows", text)

    def test_good_variant_passes(self):
        verdict = evaluate_gate(
            self.row(), self.row(median_window_return_pct=3.0), RiskGateConfig()
        )
        self.assertEqual(verdict["verdict"], "PASS")
        self.assertEqual(verdict["reasons"], [])

    def test_gate_overrides(self):
        baseline = self.row(median_window_return_pct=3.0)
        variant = self.row(median_window_return_pct=1.0, max_drawdown_pct=30.0)
        relaxed = RiskGateConfig(max_drawdown_pct=50.0, must_beat_spot=False)
        verdict = evaluate_gate(variant, baseline, relaxed)
        self.assertEqual(verdict["verdict"], "PASS")

    def test_spot_baseline_always_present(self):
        bars = load_csv(FIXTURE)[:2000]
        wf = WalkForwardConfig(train_bars=400, test_bars=200, step_bars=200)
        for mode in ("fixed", "select"):
            report = run_walk_forward(
                bars, wf, RiskGateConfig(), mode=mode, grid=small_grid(wf)
            )
            self.assertEqual(
                report["baseline"]["name"], "spot-buy-and-hold-after-costs"
            )
            self.assertGreater(report["num_windows"], 0)
            for v in report["variants"]:
                self.assertIn(v["gate"]["verdict"], ("PASS", "FAIL"))


class FixtureReproducibilityTest(unittest.TestCase):
    def test_regeneration_matches_committed_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            bar_path = Path(tmp) / "bars.csv"
            fund_path = Path(tmp) / "funding.csv"
            save_csv(bar_path, generate_bars())
            save_funding_csv(fund_path, generate_funding())
            self.assertEqual(bar_path.read_bytes(), FIXTURE.read_bytes())
            self.assertEqual(fund_path.read_bytes(), FUNDING_FIXTURE.read_bytes())


if __name__ == "__main__":
    unittest.main(verbosity=2)
