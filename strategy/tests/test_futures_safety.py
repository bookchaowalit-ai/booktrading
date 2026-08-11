from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app import futures_bot as futures_module
from app.futures_bot import (
    HARD_MAX_LEVERAGE,
    FuturesAPIError,
    FuturesBot,
    FuturesConfig,
    FuturesSafetyError,
    FuturesState,
    SymbolRules,
)


def test_mainnet_execution_mode_is_refused() -> None:
    with pytest.raises(FuturesSafetyError, match="mainnet is disabled"):
        FuturesBot(execution_mode="mainnet")


def test_config_rejects_leverage_above_hard_cap() -> None:
    with pytest.raises(FuturesSafetyError, match="leverage"):
        FuturesConfig(symbol="BTCUSDT", leverage=HARD_MAX_LEVERAGE + 1).validate()


def test_testnet_requires_demo_credentials() -> None:
    bot = FuturesBot(execution_mode="testnet", api_key="", api_secret="")
    bot.add_config(FuturesConfig(symbol="BTCUSDT"))

    with pytest.raises(FuturesSafetyError, match="requires BINANCE_FUTURES"):
        bot.validate_startup()


def test_position_sizing_honors_risk_margin_and_notional_caps() -> None:
    cfg = FuturesConfig(
        symbol="BTCUSDT",
        leverage=3,
        risk_per_trade_pct=1,
        max_margin_usdt=25,
        max_notional_usdt=70,
        stop_loss_pct=2,
    )

    # Risk cap = 500 USDT, margin cap = 75 USDT, explicit cap = 70 USDT.
    assert FuturesBot.calculate_notional(1000, cfg) == 70


def test_quantity_rounds_down_to_exchange_step() -> None:
    rules = SymbolRules(
        step_size=Decimal("0.001"),
        min_qty=Decimal("0.001"),
        max_qty=Decimal("100"),
        min_notional=Decimal("5"),
        tick_size=Decimal("0.10"),
    )

    assert FuturesBot.round_quantity(0.1239, rules) == 0.123
    assert FuturesBot.round_price(61234.19, rules) == 61234.1
    assert FuturesBot.round_price(61234.11, rules, round_up=True) == 61234.2


@pytest.mark.asyncio
async def test_leverage_must_be_confirmed_by_exchange() -> None:
    bot = FuturesBot(execution_mode="testnet", api_key="key", api_secret="secret")
    bot._request = AsyncMock(return_value={"leverage": 2})

    with pytest.raises(FuturesSafetyError, match="did not confirm"):
        await bot._set_leverage("BTCUSDT", 3)


@pytest.mark.asyncio
async def test_hedge_mode_is_refused() -> None:
    bot = FuturesBot(execution_mode="testnet", api_key="key", api_secret="secret")
    bot._request = AsyncMock(return_value={"dualSidePosition": True})

    with pytest.raises(FuturesSafetyError, match="One-way Mode"):
        await bot._assert_one_way_mode()


@pytest.mark.asyncio
async def test_account_wide_notional_cap_blocks_another_position() -> None:
    bot = FuturesBot(execution_mode="paper", max_total_notional_usdt=75)
    bot.add_config(FuturesConfig(symbol="BTCUSDT"))
    bot.add_config(FuturesConfig(symbol="ETHUSDT"))
    bot.states["BTCUSDT"].position_amt = 0.001
    bot.states["BTCUSDT"].notional = 75
    bot._get_available_balance = AsyncMock(return_value=1000)
    bot._rules["ETHUSDT"] = SymbolRules(
        step_size=Decimal("0.001"),
        min_qty=Decimal("0.001"),
        max_qty=Decimal("100"),
        min_notional=Decimal("5"),
        tick_size=Decimal("0.01"),
    )

    with pytest.raises(FuturesSafetyError, match="Account-wide"):
        await bot._calculate_quantity(bot.configs[1], 3000)


def test_position_reconciliation_exposes_liquidation_and_margin() -> None:
    bot = FuturesBot(execution_mode="paper")
    state = FuturesState(symbol="BTCUSDT")

    bot._sync_state(
        state,
        {
            "positionAmt": "-0.01",
            "entryPrice": "60000",
            "markPrice": "59000",
            "liquidationPrice": "70000",
            "notional": "-590",
            "initialMargin": "196.67",
            "maintMargin": "2.36",
            "unRealizedProfit": "10",
        },
    )

    assert state.position_side == "SHORT"
    assert state.notional == 590
    assert state.initial_margin == 196.67
    assert state.maintenance_margin == 2.36
    assert state.liquidation_buffer_pct == pytest.approx(18.644, rel=1e-3)


@pytest.mark.asyncio
async def test_failed_entry_halts_symbol_without_creating_position(monkeypatch) -> None:
    bot = FuturesBot(execution_mode="paper")
    cfg = FuturesConfig(symbol="BTCUSDT", check_interval_sec=5)
    bot.add_config(cfg)
    state = bot.states[cfg.symbol]
    bot._running = True
    bot._get_position = AsyncMock(return_value={"positionAmt": "0"})
    bot._get_funding = AsyncMock(return_value=0.0)
    bot._get_price = AsyncMock(return_value=60000.0)
    bot._analyze_signal = AsyncMock(return_value="LONG")
    bot._open_position = AsyncMock(side_effect=FuturesAPIError("order rejected"))
    bot._save_state = AsyncMock()

    async def stop_after_iteration(_seconds: float) -> None:
        bot._running = False

    monkeypatch.setattr(futures_module.asyncio, "sleep", stop_after_iteration)
    await bot._run_symbol(cfg)

    assert state.halted is True
    assert "order rejected" in state.halt_reason
    assert state.position_amt == 0
    assert state.total_trades == 0


@pytest.mark.asyncio
async def test_protection_failure_emergency_closes_paper_position() -> None:
    bot = FuturesBot(execution_mode="paper")
    cfg = FuturesConfig(symbol="BTCUSDT")
    bot.add_config(cfg)
    state = bot.states[cfg.symbol]
    bot._calculate_quantity = AsyncMock(return_value=0.001)
    bot._place_order = AsyncMock(return_value={"status": "FILLED"})
    bot._place_protection = AsyncMock(side_effect=FuturesAPIError("stop rejected"))

    with pytest.raises(FuturesAPIError, match="stop rejected"):
        await bot._open_position(cfg, state, "LONG", 60000)

    assert bot._place_order.await_count == 2
    assert bot._place_order.await_args_list[-1].kwargs["reduce_only"] is True
    assert state.position_amt == 0
    assert state.total_trades == 0


@pytest.mark.asyncio
async def test_paper_preflight_is_read_only() -> None:
    bot = FuturesBot(execution_mode="paper", http_client=AsyncMock())
    bot.add_config(FuturesConfig(symbol="BTCUSDT"))
    bot._load_symbol_rules = AsyncMock(
        return_value=SymbolRules(
            step_size=Decimal("0.001"),
            min_qty=Decimal("0.001"),
            max_qty=Decimal("100"),
            min_notional=Decimal("5"),
            tick_size=Decimal("0.10"),
        )
    )
    bot._get_price = AsyncMock(return_value=60000.0)
    bot._get_funding = AsyncMock(return_value=0.0001)
    bot._place_order = AsyncMock()

    report = await bot.preflight()

    assert report["ready"] is True
    assert report["execution_mode"] == "paper"
    assert report["symbols"]["BTCUSDT"]["ready"] is True
    bot._place_order.assert_not_awaited()


@pytest.mark.asyncio
async def test_testnet_private_preflight_reads_account_without_orders() -> None:
    bot = FuturesBot(
        execution_mode="testnet",
        api_key="demo-key",
        api_secret="demo-secret",
        http_client=AsyncMock(),
    )
    bot.add_config(FuturesConfig(symbol="BTCUSDT"))
    bot._assert_one_way_mode = AsyncMock()
    bot._get_available_balance = AsyncMock(return_value=1000.0)
    bot._load_symbol_rules = AsyncMock(
        return_value=SymbolRules(
            step_size=Decimal("0.001"),
            min_qty=Decimal("0.001"),
            max_qty=Decimal("100"),
            min_notional=Decimal("5"),
            tick_size=Decimal("0.10"),
        )
    )
    bot._get_price = AsyncMock(return_value=60000.0)
    bot._get_funding = AsyncMock(return_value=0.0001)
    bot._place_order = AsyncMock()

    report = await bot.preflight()

    assert report["ready"] is True
    assert report["available_balance_usdt"] == 1000.0
    assert next(check for check in report["checks"] if check["name"] == "position_mode")["ok"] is True
    bot._assert_one_way_mode.assert_awaited_once()
    bot._get_available_balance.assert_awaited_once()
    bot._place_order.assert_not_awaited()


@pytest.mark.asyncio
async def test_observe_only_paper_cycle_does_not_open_signal() -> None:
    bot = FuturesBot(execution_mode="paper", http_client=AsyncMock())
    cfg = FuturesConfig(symbol="BTCUSDT")
    bot.add_config(cfg)
    bot._get_position = AsyncMock(return_value={"positionAmt": "0"})
    bot._get_funding = AsyncMock(return_value=0.0001)
    bot._get_price = AsyncMock(return_value=60000.0)
    bot._analyze_signal = AsyncMock(return_value="LONG")
    bot._open_position = AsyncMock()
    bot._save_state = AsyncMock()

    report = await bot.run_paper_cycle()

    assert report["allow_entry"] is False
    assert report["results"][0]["action"] == "OBSERVE"
    assert report["results"][0]["signal"] == "LONG"
    bot._open_position.assert_not_awaited()


@pytest.mark.asyncio
async def test_single_cycle_is_refused_in_testnet_mode() -> None:
    bot = FuturesBot(execution_mode="testnet", api_key="key", api_secret="secret")
    bot.add_config(FuturesConfig(symbol="BTCUSDT"))

    with pytest.raises(FuturesSafetyError, match="restricted to paper"):
        await bot.run_paper_cycle()
