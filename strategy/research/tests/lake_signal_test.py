#!/usr/bin/env python3
"""Tests for lake_source.py and signal_report.py. No network, no pytest."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data import load_csv, load_funding_csv  # noqa: E402
from futures_backtest import Bar  # noqa: E402
from walk_forward import RiskGateConfig, WalkForwardConfig, build_grid  # noqa: E402
import lake_source  # noqa: E402
import signal_report  # noqa: E402

TRADING = Path(__file__).resolve().parents[1]
FIXTURE = TRADING / "fixtures" / "sample_1h.csv"
FUNDING_FIXTURE = TRADING / "fixtures" / "sample_funding.csv"
HOUR = 3_600_000


def small_setup():
    wf = WalkForwardConfig(train_bars=600, test_bars=200, step_bars=200)
    grid = build_grid(
        wf, ema_pairs=[(9, 21), (20, 50)], adx_thresholds=[20.0],
        modes=["long_only"], instruments=[("spot", 1)],
    )
    return wf, grid


class LakeSourceTests(unittest.TestCase):
    def test_bars_from_rows_dedupes_sorts_and_skips_invalid(self):
        rows = [
            {"open_time_ms": "7200000", "open": "2", "high": "3", "low": "1", "close": "2.5", "volume": "1", "quality_status": "valid"},
            {"open_time_ms": "3600000", "open": "1", "high": "2", "low": "0.5", "close": "1.5", "volume": "1", "quality_status": "valid"},
            {"open_time_ms": "7200000", "open": "2", "high": "3", "low": "1", "close": "2.5", "volume": "1", "quality_status": "valid"},
            {"open_time_ms": "10800000", "open": "9", "high": "9", "low": "9", "close": "9", "volume": "1", "quality_status": "invalid"},
        ]
        bars = lake_source.bars_from_rows(rows)
        self.assertEqual([b.open_time_ms for b in bars], [3600000, 7200000])

    def test_assess_reports_gaps(self):
        bars = [Bar(t * HOUR, 1, 1, 1, 1, 1) for t in (0, 1, 2, 5, 6)]
        quality = lake_source.assess(bars, "BTCUSDT", "1h")
        self.assertEqual(quality.gaps, [(2 * HOUR, 2)])
        self.assertEqual(quality.missing_bars, 2)


class SignalReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bars = load_csv(FIXTURE)[:2000]
        cls.funding = load_funding_csv(FUNDING_FIXTURE)

    def _evaluate(self, bars, *, now_ms=None, gate=None, quality=None):
        wf, grid = small_setup()
        now_ms = now_ms or bars[-1].open_time_ms + HOUR + 1
        q = quality or {"gaps": [], "missing_bars": 0}
        return signal_report.evaluate_symbol(
            "BTCUSDT", bars, self.funding, q, interval="1h", now_ms=now_ms,
            wf=wf, gate=gate or RiskGateConfig(), grid=grid,
        )

    def test_insufficient_history_is_no_trade(self):
        result = self._evaluate(self.bars[:300])
        self.assertEqual(result["decision"], "NO_TRADE")
        self.assertTrue(any("walk-forward needs" in r for r in result["reasons"]))

    def test_stale_data_blocks_even_when_gate_passes(self):
        permissive = RiskGateConfig(max_drawdown_pct=100, min_sharpe=-99, min_profitable_windows_pct=0, must_beat_spot=False)
        stale_now = self.bars[-1].open_time_ms + 10 * HOUR
        result = self._evaluate(self.bars, now_ms=stale_now, gate=permissive)
        self.assertEqual(result["decision"], "NO_TRADE")
        self.assertTrue(any("stale" in r for r in result["reasons"]))

    def test_permissive_gate_yields_paper_decision_matching_side(self):
        permissive = RiskGateConfig(max_drawdown_pct=100, min_sharpe=-99, min_profitable_windows_pct=0, must_beat_spot=False)
        result = self._evaluate(self.bars, gate=permissive)
        self.assertEqual(result["gate"]["verdict"], "PASS")
        self.assertIn(result["decision"], ("PAPER_LONG", "PAPER_FLAT"))  # spot long-only grid
        self.assertEqual(result["decision"], result["would_be_side"])
        self.assertEqual(result["reasons"], [])

    def test_recent_gap_blocks(self):
        recent = self.bars[-10].open_time_ms
        result = self._evaluate(self.bars, quality={"gaps": [(recent, 3)], "missing_bars": 3})
        self.assertEqual(result["decision"], "NO_TRADE")
        self.assertTrue(any("gap" in r for r in result["reasons"]))

    def test_journal_is_idempotent_and_scored(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "journal.json"
            day = 86_400_000
            results = [
                {"symbol": "BTCUSDT", "as_of_open_ms": 0, "as_of_close": "d0", "last_close": 100.0, "decision": "PAPER_LONG"},
            ]
            self.assertEqual(signal_report.append_journal(path, results, recorded_at="t0"), 1)
            self.assertEqual(signal_report.append_journal(path, results, recorded_at="t1"), 0)
            later = [
                {"symbol": "BTCUSDT", "as_of_open_ms": 100 * day, "as_of_close": "d100", "last_close": 110.0, "decision": "NO_TRADE"},
            ]
            signal_report.append_journal(path, later, recorded_at="t2")
            journal = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(len(journal), 2)
            record = signal_report.paper_track_record(journal, "BTCUSDT", cost_bps=0)
            self.assertEqual(record["paper_return_pct"], 10.0)
            self.assertEqual(record["buy_and_hold_pct"], 10.0)
            self.assertFalse(record["track_record_met"])  # must beat hold, not tie it
            self.assertEqual(record["days_tracked"], 100.0)

    def test_render_contains_disclaimer_and_no_order_language(self):
        md = signal_report.render(
            [{"symbol": "BTCUSDT", "decision": "NO_TRADE", "reasons": ["x"]}],
            [signal_report.paper_track_record([], "BTCUSDT")],
            generated_at="now",
        )
        self.assertIn("no orders are placed", md)
        self.assertIn("NO_TRADE", md)


class LakeRoundTripTests(unittest.TestCase):
    """Bronze -> Silver -> lake_source using the real shared data_lake runtime."""

    def setUp(self):
        try:
            import duckdb  # noqa: F401
            import pyarrow  # noqa: F401
        except ImportError:
            self.skipTest("duckdb/pyarrow not installed")
        scripts = (lake_source.LAKE_ROOT or lake_source.ROOT) / "infra" / "scripts"
        if not (scripts / "data_lake" / "silver.py").exists():
            self.skipTest("monorepo data_lake runtime not present")
        sys.path.insert(0, str(scripts))

    def test_silver_bars_load_in_order(self):
        from data_lake.ingest import ingest_payload
        from data_lake.silver import SilverProductContract, transform_bronze_to_silver

        records = []
        for i, bar in enumerate(load_csv(FIXTURE)[:50]):
            records.append({
                "id": f"binance_futures:BTCUSDT:1h:{bar.open_time_ms}",
                "venue": "binance_futures", "symbol": "BTCUSDT", "interval": "1h",
                "open_time_ms": bar.open_time_ms, "close_time_ms": bar.open_time_ms + HOUR - 1,
                "open": repr(bar.open), "high": repr(bar.high), "low": repr(bar.low),
                "close": repr(bar.close), "volume": repr(bar.volume), "quote_volume": "0", "trades": i,
                "event_time": signal_report.iso(bar.open_time_ms).replace("Z", ":00Z"),
            })
        with tempfile.TemporaryDirectory() as root:
            ingest_payload(
                b"[]", records, source="book-crypto-data", domain="market", dataset="crypto_ohlcv",
                data_lake_uri=root, input_format="json", event_time_field="event_time", privacy_class="public",
            )
            transform_bronze_to_silver(
                SilverProductContract(
                    source="book-crypto-data", domain="market", bronze_dataset="crypto_ohlcv",
                    silver_dataset="crypto_ohlcv", product_schema_version="crypto-ohlcv.silver.v1",
                    bronze_product_schema_version="crypto.v1", transform_version="crypto-ohlcv-silver.v1",
                    normalizer="crypto_ohlcv", privacy_class="public",
                ),
                data_lake_uri=root,
            )
            bars, quality = lake_source.load_bars("btcusdt", data_lake_uri=root)
        self.assertEqual(bars, load_csv(FIXTURE)[:50])
        self.assertEqual(quality.gaps, [])


if __name__ == "__main__":
    unittest.main()
