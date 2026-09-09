"""Regression tests for read-only multi-symbol checks and global real-grid caps."""

from unittest.mock import AsyncMock

import pytest

from app import real_grid_bot as real_grid_module
from app.real_grid_bot import RealGridBot, RealGridConfig, RealGridState
from app.real_grid_preflight import DEFAULT_PREFLIGHT_SYMBOLS, parse_symbols, validate_symbol_snapshot
from app.risk_manager import RiskConfig, RiskManager


def _exchange_symbol(symbol: str, *, status: str = "TRADING") -> dict:
    return {
        "symbol": symbol,
        "status": status,
        "filters": [
            {"filterType": "LOT_SIZE", "minQty": "0.0001", "stepSize": "0.0001"},
            {"filterType": "PRICE_FILTER", "tickSize": "1"},
            {"filterType": "MIN_NOTIONAL", "minNotional": "100"},
        ],
    }


def test_preflight_default_checks_candidates_without_changing_active_symbols(monkeypatch) -> None:
    monkeypatch.delenv("REAL_PREFLIGHT_SYMBOLS", raising=False)
    monkeypatch.setenv("REAL_SYMBOLS", "BTCTHB")

    assert parse_symbols() == list(DEFAULT_PREFLIGHT_SYMBOLS)


def test_preflight_reports_exchange_and_risk_blockers() -> None:
    report = validate_symbol_snapshot(
        "ETHTHB",
        _exchange_symbol("ETHTHB"),
        {"lastPrice": "70000", "quoteVolume": "1000000", "priceChangePercent": "2"},
        {"order_size": 0.002, "grid_levels": 2, "max_position": 0.004, "tick_size": 1},
    )

    assert report["ready"] is True
    assert report["configured"]["order_notional_thb"] == 140.0
    assert report["blockers"] == []

    oversized = validate_symbol_snapshot(
        "BNBTHB",
        _exchange_symbol("BNBTHB"),
        {"lastPrice": "21050", "quoteVolume": "1000000", "priceChangePercent": "2"},
        {"order_size": 0.01, "grid_levels": 1, "max_position": 0.02, "tick_size": 1},
    )
    assert oversized["ready"] is False
    assert "order_above_risk_max_order_size" in oversized["blockers"]


def test_preflight_blocks_below_minimum_notional() -> None:
    report = validate_symbol_snapshot(
        "ZENTTHB",
        {
            **_exchange_symbol("ZENTTHB"),
            "filters": [
                {"filterType": "LOT_SIZE", "minQty": "1", "stepSize": "1"},
                {"filterType": "PRICE_FILTER", "tickSize": "0.0001"},
                {"filterType": "MIN_NOTIONAL", "minNotional": "100"},
            ],
        },
        {"lastPrice": "0.061", "quoteVolume": "200000", "priceChangePercent": "1"},
        {"order_size": 1287, "grid_levels": 1, "max_position": 2600, "tick_size": 0.0001},
    )

    assert report["ready"] is False
    assert "order_below_min_notional" in report["blockers"]


@pytest.mark.asyncio
async def test_global_open_order_cap_applies_across_symbols(monkeypatch) -> None:
    monkeypatch.setattr(real_grid_module, "BINANCE_TH_MAINNET", True)
    config_a = RealGridConfig(symbol="ETHTHB", order_size=0.002)
    config_b = RealGridConfig(symbol="SOLTHB", order_size=0.05)
    bot = RealGridBot(configs=[config_a, config_b])
    bot._risk = RiskManager(RiskConfig(max_open_orders=2))
    bot._http = AsyncMock()
    bot._can_place_buy = AsyncMock(return_value=True)
    bot.states["ETHTHB"] = RealGridState(
        symbol="ETHTHB",
        active_buys={70000: "eth-buy"},
        active_sells={71000: "eth-sell"},
    )
    bot.states["SOLTHB"] = RealGridState(symbol="SOLTHB")

    placed = await bot._place_grid_order(config_b, bot.states["SOLTHB"], "BUY", 2800)

    assert placed is False
    bot._http.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_global_portfolio_cap_blocks_new_buy(monkeypatch) -> None:
    monkeypatch.setattr(real_grid_module, "BINANCE_TH_MAINNET", True)
    monkeypatch.setattr(real_grid_module, "GRID_MAX_PORTFOLIO_NOTIONAL_THB", 100.0)
    config = RealGridConfig(symbol="SOLTHB", order_size=0.2)
    bot = RealGridBot(configs=[config])
    bot._risk = RiskManager(RiskConfig(max_open_orders=10))
    bot._http = AsyncMock()
    bot._can_place_buy = AsyncMock(return_value=True)
    bot.states["SOLTHB"] = RealGridState(
        symbol="SOLTHB",
        current_order_size=0.1,
        active_buys={900: "existing-buy"},
    )

    placed = await bot._place_grid_order(config, bot.states["SOLTHB"], "BUY", 200)

    assert placed is False
    bot._http.post.assert_not_awaited()
