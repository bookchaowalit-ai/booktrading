#!/usr/bin/env python3
"""Stdlib unittest suite for data.py. No network access anywhere here."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data import (  # noqa: E402
    load_csv,
    load_funding_csv,
    parse_funding_rates,
    parse_klines,
    save_csv,
    save_funding_csv,
)
from futures_backtest import Bar  # noqa: E402

# Small hard-coded sample of a real Binance klines API response shape:
# [openTime, open, high, low, close, volume, closeTime, quoteVol,
#  trades, takerBuyBase, takerBuyQuote, ignore]
KLINES_SAMPLE = [
    [
        1704067200000,
        "42000.10",
        "42100.50",
        "41950.00",
        "42050.25",
        "123.456",
        1704070799999,
        "5190000.0",
        4321,
        "60.0",
        "2520000.0",
        "0",
    ],
    [
        1704070800000,
        "42050.25",
        "42200.00",
        "42010.00",
        "42180.75",
        "98.765",
        1704074399999,
        "4160000.0",
        3987,
        "50.0",
        "2100000.0",
        "0",
    ],
]

FUNDING_SAMPLE = [
    {"symbol": "BTCUSDT", "fundingTime": 1704070800000, "fundingRate": "0.00010000"},
    {"symbol": "BTCUSDT", "fundingTime": 1704043200000, "fundingRate": "-0.00005000"},
]


class ParseTest(unittest.TestCase):
    def test_parse_klines(self):
        bars = parse_klines(KLINES_SAMPLE)
        self.assertEqual(len(bars), 2)
        self.assertEqual(
            bars[0], Bar(1704067200000, 42000.10, 42100.50, 41950.00, 42050.25, 123.456)
        )
        self.assertEqual(bars[1].open_time_ms, 1704070800000)
        self.assertEqual(bars[1].close, 42180.75)

    def test_parse_klines_sorts_ascending(self):
        bars = parse_klines(list(reversed(KLINES_SAMPLE)))
        self.assertEqual(bars[0].open_time_ms, 1704067200000)

    def test_parse_funding_rates(self):
        funding = parse_funding_rates(FUNDING_SAMPLE)
        # sorted ascending by time regardless of payload order
        self.assertEqual(funding, [(1704043200000, -0.00005), (1704070800000, 0.0001)])


class CsvRoundTripTest(unittest.TestCase):
    def test_bars_round_trip_exact(self):
        bars = [
            Bar(1704067200000, 42000.1, 42100.5, 41950.0, 42050.25, 123.456),
            Bar(1704070800000, 42050.25, 42200.0, 42010.0, 42180.75, 98.765),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bars.csv"
            save_csv(path, bars)
            self.assertEqual(load_csv(path), bars)

    def test_funding_round_trip_exact(self):
        funding = [(1704043200000, -0.00005), (1704070800000, 0.0001)]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "funding.csv"
            save_funding_csv(path, funding)
            self.assertEqual(load_funding_csv(path), funding)

    def test_bad_header_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.csv"
            path.write_text("a,b,c\n1,2,3\n")
            with self.assertRaises(ValueError):
                load_csv(path)
            with self.assertRaises(ValueError):
                load_funding_csv(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
