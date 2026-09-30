"""Regression tests for GridBot._sync_state fill reconciliation.

_sync_state once referenced an undefined name; the broad ``except`` swallowed
the NameError, so fills were never reconciled and grid profit never moved.
These tests drive it against an in-process mock paper API (no network).
"""

import httpx
import pytest

from app.grid_bot import GridBot, GridConfig, GridState


def _bot_with_paper_orders(open_orders):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/paper/orders"
        return httpx.Response(200, json=open_orders)

    bot = GridBot(configs=[])
    bot._http = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://paper")
    return bot


def _cfg() -> GridConfig:
    return GridConfig(
        symbol="BTCTHB",
        grid_spacing_pct=2.0,
        grid_levels=2,
        order_size=0.00005,
        max_position=0.001,
        max_notional=3000.0,
    )


@pytest.mark.asyncio
async def test_sync_moves_filled_buys_out_of_active_book():
    cfg = _cfg()
    state = GridState(symbol=cfg.symbol, active_buys={2_000_000.0: "b1", 1_960_000.0: "b2"})
    bot = _bot_with_paper_orders([{"id": "b2", "symbol": cfg.symbol, "status": "PENDING"}])

    await bot._sync_state(cfg, state, current_price=1_990_000.0)

    assert state.active_buys == {1_960_000.0: "b2"}
    assert 2_000_000.0 in state.filled_buys
    assert state.filled_buys[2_000_000.0] > 0
    assert state.trades_executed == 1


@pytest.mark.asyncio
async def test_sync_realizes_profit_when_sell_fills_against_oldest_buy():
    cfg = _cfg()
    state = GridState(
        symbol=cfg.symbol,
        active_sells={2_040_000.0: "s1"},
        filled_buys={2_000_000.0: 0.002},
    )
    bot = _bot_with_paper_orders([])

    await bot._sync_state(cfg, state, current_price=2_050_000.0)

    assert state.active_sells == {}
    assert state.filled_buys == {}
    assert 2_040_000.0 in state.filled_sells
    qty = state.filled_sells[2_040_000.0]
    expected = 2_040_000.0 * qty - 2_000_000.0 * 0.002 - 2_040_000.0 * qty * 0.001
    assert state.total_profit == pytest.approx(expected)
    assert state.trades_executed == 1


@pytest.mark.asyncio
async def test_sync_ignores_other_symbols_pending_orders():
    cfg = _cfg()
    state = GridState(symbol=cfg.symbol, active_buys={2_000_000.0: "b1"})
    # Same order id but a different symbol must not count as still pending.
    bot = _bot_with_paper_orders([{"id": "b1", "symbol": "ETHTHB", "status": "PENDING"}])

    await bot._sync_state(cfg, state, current_price=2_000_000.0)

    assert state.active_buys == {}
    assert 2_000_000.0 in state.filled_buys
