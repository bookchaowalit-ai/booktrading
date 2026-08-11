from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from app.futures_backtest import (
    BacktestError,
    BinancePublicFuturesData,
    Candle,
    FinancialBacktestConfig,
    FinancialEngineeringBacktester,
    FundingEvent,
)


def _candles(count: int = 120, *, step: float = 1.0) -> list[Candle]:
    start = int(datetime(2025, 1, 1, tzinfo=UTC).timestamp() * 1_000)
    return [
        Candle(
            open_time=start + index * 3_600_000,
            close_time=start + (index + 1) * 3_600_000 - 1,
            open=100 + index * step,
            high=101 + index * step,
            low=99 + index * step,
            close=100 + index * step,
        )
        for index in range(count)
    ]


def _config(**kwargs) -> FinancialBacktestConfig:
    return FinancialBacktestConfig(
        ema_fast=2,
        ema_slow=3,
        adx_period=2,
        adx_threshold=0,
        stop_loss_pct=50,
        take_profit_pct=100,
        **kwargs,
    )


def test_backtest_rejects_unsafe_leverage_and_costs() -> None:
    with pytest.raises(BacktestError, match="between 1 and 5"):
        FinancialBacktestConfig(leverage_levels=(1, 6)).validate()
    with pytest.raises(BacktestError, match="cannot be negative"):
        FinancialBacktestConfig(fee_bps=-1).validate()


def test_leverage_effect_is_visible_after_same_signal_and_capital() -> None:
    candles = _candles()
    signals = ["LONG"] * len(candles)
    backtester = FinancialEngineeringBacktester(_config())
    one_x = backtester._run_variant(candles, signals, [], market="futures", leverage=1, start_index=1, end_index=len(candles))
    five_x = backtester._run_variant(candles, signals, [], market="futures", leverage=5, start_index=1, end_index=len(candles))

    assert five_x.total_return_pct > one_x.total_return_pct > 0
    # Entry fee and adverse slippage create a small, realistic initial dip.
    assert five_x.max_drawdown_pct < 1
    assert five_x.liquidations == 0


def test_fee_and_funding_are_included_in_trade_economics() -> None:
    candles = _candles(step=0)
    signals = ["LONG"] * len(candles)
    backtester = FinancialEngineeringBacktester(_config(fee_bps=25, slippage_bps=0))
    result = backtester._run_variant(
        candles,
        signals,
        [FundingEvent(timestamp=candles[10].close_time, rate=0.001)],
        market="futures",
        leverage=1,
        start_index=1,
        end_index=len(candles),
    )

    assert result.total_fees > 0
    assert result.funding_pnl < 0
    assert result.net_pnl < 0
    assert result.total_trades == 1


def test_liquidation_is_counted_and_equity_cannot_go_negative() -> None:
    candles = _candles(count=8, step=0)
    candles[3] = Candle(
        open_time=candles[3].open_time,
        close_time=candles[3].close_time,
        open=100,
        high=101,
        low=10,
        close=90,
    )
    result = FinancialEngineeringBacktester(_config())._run_variant(
        candles,
        ["LONG"] * len(candles),
        [],
        market="futures",
        leverage=5,
        start_index=1,
        end_index=len(candles),
    )

    assert result.liquidations == 1
    assert result.final_equity >= 0
    assert result.trades[0].exit_reason == "LIQUIDATION"


def test_comparison_has_holdout_segment_and_explicit_read_only_contract() -> None:
    candles = _candles()
    report = FinancialEngineeringBacktester(_config(leverage_levels=(1, 2, 3, 5))).run_comparison(candles)

    assert report["read_only"] is True
    assert report["places_orders"] is False
    assert report["split"]["parameter_optimization_performed"] is False
    assert {result["label"] for result in report["segments"]["out_of_sample"]["results"]} == {
        "spot",
        "futures_1x",
        "futures_2x",
        "futures_3x",
        "futures_5x",
    }


@pytest.mark.asyncio
async def test_public_data_client_is_read_only_and_paginates_expected_routes() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path.endswith("/klines"):
            row = [1, "100", "101", "99", "100", "10", 3_599_999, "1000", 2, "5", "500", "0"]
            return httpx.Response(200, json=[row])
        if request.url.path.endswith("/fundingRate"):
            return httpx.Response(200, json=[{"fundingTime": 2, "fundingRate": "0.0001"}])
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    data = BinancePublicFuturesData(base_url="https://example.test", http_client=client)
    candles = await data.fetch_klines("BTCUSDT", "1h", 1, 10)
    funding = await data.fetch_funding_rates("BTCUSDT", 1, 10)
    await client.aclose()

    assert len(candles) == 1
    assert funding[0].rate == pytest.approx(0.0001)
    assert calls == ["/fapi/v1/klines", "/fapi/v1/fundingRate"]
