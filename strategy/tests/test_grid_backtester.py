"""Offline correctness tests for app.backtester.GridBacktester.

Klines are synthetic and injected by replacing ``_fetch_klines``; nothing
touches the network.
"""

import math

import pytest

from app.backtester import (
    TAKER_FEE,
    BacktestConfig,
    GridBacktester,
    _consume_fifo,
    closed_before,
)

HOUR_MS = 3_600_000


def _klines(closes, spread=0.02, volume=10.0):
    out = []
    for n, close in enumerate(closes):
        out.append(
            {
                "timestamp": 1_700_000_000_000 + n * HOUR_MS,
                "open": close,
                "high": close * (1 + spread),
                "low": close * (1 - spread),
                "close": close,
                "volume": volume,
            }
        )
    return out


def _oscillating(n=120, base=100.0, amp=0.03):
    return [base * (1 + amp * math.sin(k / 3.0)) for k in range(n)]


def _backtester(klines, **overrides):
    cfg = BacktestConfig(
        symbol="TESTTHB",
        grid_spacing_pct=1.0,
        grid_levels=3,
        order_size=5.0,
        max_position=100.0,
        initial_capital_thb=10_000.0,
        **overrides,
    )
    bt = GridBacktester(cfg)

    async def fake_fetch(symbol, interval, limit):
        return list(klines)

    bt._fetch_klines = fake_fetch
    return bt


@pytest.mark.asyncio
async def test_fees_on_both_sides_are_reflected_in_net_pnl():
    klines = _klines(_oscillating(24))
    result = await _backtester(klines).run(days=1, interval="1h")

    buys = [t for t in result.trades if t.side == "BUY"]
    sells = [t for t in result.trades if t.side == "SELL"]
    assert buys and sells, "fixture must produce round trips"
    assert result.total_trades <= 50, "all trades must be visible for this check"

    expected_fees = sum(t.fee for t in result.trades)
    assert result.total_fees == pytest.approx(round(expected_fees, 2), abs=0.01)
    assert all(t.fee == pytest.approx(t.price * t.quantity * TAKER_FEE) for t in buys)
    # Gross minus fees is net; fees are never counted twice or dropped.
    assert result.total_pnl - result.total_fees == pytest.approx(result.net_pnl, abs=0.02)


@pytest.mark.asyncio
async def test_entry_gate_only_sees_closed_bars():
    klines = _klines(_oscillating(60))
    bt = _backtester(klines, enable_entry_confluence=True)
    seen = []
    original = bt._check_buy_confluence

    def spy(ks, idx, imbalance=0.5):
        seen.append(idx)
        return original(ks, idx, imbalance)

    bt._check_buy_confluence = spy
    await bt.run(days=3, interval="1h")

    # Bar i may only be gated by bar i-1; the final bar's own data is never used.
    assert seen == list(range(0, len(klines) - 1))


def test_closed_before_excludes_forming_higher_timeframe_candle():
    four_h = 4 * HOUR_MS
    mtf = [{"timestamp": t * four_h, "close": 1.0} for t in range(5)]
    # At 09:00 (bar opened at 08:00 is still forming until 12:00)
    as_of = 2 * four_h + HOUR_MS
    closed = closed_before(mtf, "4h", as_of)
    assert [k["timestamp"] for k in closed] == [0, four_h]
    # Exactly at the close boundary the candle counts as closed.
    assert len(closed_before(mtf, "4h", 3 * four_h)) == 3


def test_consume_fifo_matches_partial_lots_by_quantity():
    lots = [[1.0, 100.0], [2.0, 110.0]]
    cost = _consume_fifo(lots, 1.5, fallback_unit_cost=999.0)
    assert cost == pytest.approx(1.0 * 100.0 + 0.5 * 110.0)
    assert lots == [[1.5, 110.0]]


def test_consume_fifo_unmatched_quantity_uses_fallback():
    lots = [[0.5, 100.0]]
    cost = _consume_fifo(lots, 1.0, fallback_unit_cost=120.0)
    assert cost == pytest.approx(0.5 * 100.0 + 0.5 * 120.0)
    assert lots == []
