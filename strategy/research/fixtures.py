#!/usr/bin/env python3
"""Deterministic synthetic market-data generator for Phase 4 tests.

Generates a geometric-Brownian-ish 1h bar series with three regimes
(uptrend, range, downtrend with a crash segment) plus an 8h funding-rate
series. The PRNG is ``random.Random(42)`` and ONLY ``rng.random()`` is
consumed, so output is identical on every platform and Python 3 version.

The generated CSVs are COMMITTED under ``fixtures/`` — tests never
regenerate at runtime; one test asserts that regenerating with the same
seed reproduces the committed files byte-for-byte.

This is synthetic research data, not a market forecast.
"""

from __future__ import annotations

import argparse
import random
from collections.abc import Sequence
from pathlib import Path

from data import save_csv, save_funding_csv
from futures_backtest import Bar

SEED = 42
N_BARS = 9000
START_MS = 1704067200000  # 2024-01-01T00:00:00Z
INTERVAL_MS = 3600 * 1000
START_PRICE = 30000.0

# Regime boundaries (bar index): [0,3000) up, [3000,6000) range,
# [6000,9000) down with a crash near bar 7800.
REGIMES = (
    (0, 3000, 0.0006, 0.006),  # uptrend: drift, vol
    (3000, 6000, 0.0, 0.005),  # range
    (6000, 9000, -0.0007, 0.007),  # downtrend
)
CRASH_START = 7800
CRASH_BARS = 10
CRASH_DRAIN = 0.03  # extra -3% per bar during the crash segment

FUNDING_INTERVAL_MS = 8 * 3600 * 1000
# Base funding per regime (decimal per 8h): positive in uptrends, negative
# in downtrends, so both funding-payment signs are exercised.
REGIME_FUNDING = (0.00010, 0.00005, -0.00005)


def _regime(i: int) -> int:
    for r, (start, end, _, _) in enumerate(REGIMES):
        if start <= i < end:
            return r
    return len(REGIMES) - 1


def generate_bars(seed: int = SEED, n: int = N_BARS) -> list[Bar]:
    rng = random.Random(seed)
    bars: list[Bar] = []
    close = START_PRICE
    for i in range(n):
        r = _regime(i)
        _, _, drift, vol = REGIMES[r]
        # Approx-normal shock from 4 uniforms (deterministic across versions).
        z = (rng.random() + rng.random() + rng.random() + rng.random()) - 2.0
        ret = drift + vol * z
        if CRASH_START <= i < CRASH_START + CRASH_BARS:
            ret -= CRASH_DRAIN
        open_ = close
        close = open_ * (1.0 + ret)
        spread_u = rng.random()
        spread_d = rng.random()
        high = max(open_, close) * (1.0 + spread_u * vol * 0.5)
        low = min(open_, close) * (1.0 - spread_d * vol * 0.5)
        volume = 100.0 * (1.0 + rng.random())
        bars.append(Bar(START_MS + i * INTERVAL_MS, open_, high, low, close, volume))
    return bars


def generate_funding(seed: int = SEED, n: int = N_BARS) -> list[tuple[int, float]]:
    rng = random.Random(seed + 1)
    out: list[tuple[int, float]] = []
    step = FUNDING_INTERVAL_MS // INTERVAL_MS  # bars per funding event
    i = 0
    while i < n:
        base = REGIME_FUNDING[_regime(i)]
        rate = base + (rng.random() - 0.5) * 0.00002
        out.append((START_MS + i * INTERVAL_MS, rate))
        i += step
    return out


def default_paths() -> tuple[Path, Path]:
    here = Path(__file__).resolve().parent / "fixtures"
    return here / "sample_1h.csv", here / "sample_funding.csv"


def main(argv: Sequence[str] | None = None) -> int:
    bar_path, fund_path = default_paths()
    ap = argparse.ArgumentParser(
        description="Regenerate the committed deterministic fixture CSVs."
    )
    ap.add_argument("--out", default=str(bar_path))
    ap.add_argument("--funding-out", default=str(fund_path))
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--bars", type=int, default=N_BARS)
    args = ap.parse_args(argv)
    save_csv(args.out, generate_bars(args.seed, args.bars))
    save_funding_csv(args.funding_out, generate_funding(args.seed, args.bars))
    print(f"wrote {args.out} and {args.funding_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
