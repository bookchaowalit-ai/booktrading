"""Deterministic spot-versus-futures financial engineering backtest.

The module consumes public historical market data only. It never authenticates,
places orders, or calls an account endpoint. Execution costs and margin rules are
explicit assumptions so a report cannot be mistaken for guaranteed performance.
"""

from __future__ import annotations

import math
import statistics
import time
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from itertools import pairwise
from typing import Any

import httpx

PUBLIC_FUTURES_BASE = "https://fapi.binance.com"
HARD_MAX_BACKTEST_LEVERAGE = 5
MILLISECONDS_PER_DAY = 86_400_000
SECONDS_PER_YEAR = 365.25 * 24 * 60 * 60


class BacktestError(RuntimeError):
    """Raised when data or assumptions cannot produce a trustworthy report."""


@dataclass(frozen=True)
class Candle:
    open_time: int
    close_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass(frozen=True)
class FundingEvent:
    timestamp: int
    rate: float


@dataclass
class FinancialBacktestConfig:
    symbol: str = "BTCUSDT"
    initial_equity_usdt: float = 1_000.0
    margin_allocation_pct: float = 20.0
    leverage_levels: tuple[int, ...] = (1, 2, 3, 5)
    fee_bps: float = 5.0
    slippage_bps: float = 2.0
    stop_loss_pct: float = 2.0
    take_profit_pct: float = 4.0
    maintenance_margin_rate: float = 0.004
    ema_fast: int = 9
    ema_slow: int = 21
    adx_period: int = 14
    adx_threshold: float = 20.0
    out_of_sample_fraction: float = 0.30

    def validate(self) -> None:
        errors: list[str] = []
        if not self.symbol or not self.symbol.isalnum():
            errors.append("symbol must be alphanumeric")
        if self.initial_equity_usdt <= 0:
            errors.append("initial_equity_usdt must be > 0")
        if not 0 < self.margin_allocation_pct <= 100:
            errors.append("margin_allocation_pct must be > 0 and <= 100")
        if not self.leverage_levels:
            errors.append("at least one leverage level is required")
        if any(level < 1 or level > HARD_MAX_BACKTEST_LEVERAGE for level in self.leverage_levels):
            errors.append(f"leverage levels must be between 1 and {HARD_MAX_BACKTEST_LEVERAGE}")
        if len(set(self.leverage_levels)) != len(self.leverage_levels):
            errors.append("leverage levels must be unique")
        if self.fee_bps < 0 or self.slippage_bps < 0:
            errors.append("fee_bps and slippage_bps cannot be negative")
        if not 0 < self.stop_loss_pct < 100:
            errors.append("stop_loss_pct must be between 0 and 100")
        if self.take_profit_pct <= 0:
            errors.append("take_profit_pct must be > 0")
        if not 0 <= self.maintenance_margin_rate < 1:
            errors.append("maintenance_margin_rate must be >= 0 and < 1")
        if self.ema_fast <= 0 or self.ema_slow <= self.ema_fast:
            errors.append("EMA periods must satisfy 0 < ema_fast < ema_slow")
        if self.adx_period <= 1 or self.adx_threshold < 0:
            errors.append("ADX period must be > 1 and threshold cannot be negative")
        if not 0.1 <= self.out_of_sample_fraction <= 0.5:
            errors.append("out_of_sample_fraction must be between 0.1 and 0.5")
        if errors:
            raise BacktestError("Invalid financial backtest config: " + "; ".join(errors))


@dataclass
class BacktestTrade:
    market: str
    leverage: int
    side: str
    entry_time: int
    exit_time: int
    entry_price: float
    exit_price: float
    quantity: float
    gross_pnl: float
    fees: float
    funding_pnl: float
    net_pnl: float
    exit_reason: str


@dataclass
class VariantResult:
    market: str
    leverage: int
    start_time: int
    end_time: int
    initial_equity: float
    final_equity: float
    net_pnl: float
    total_return_pct: float
    annualized_return_pct: float
    annualized_volatility_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    profit_factor: float
    total_fees: float
    funding_pnl: float
    liquidations: int
    turnover_multiple: float
    exposure_pct: float
    trades: list[BacktestTrade] = field(default_factory=list)


@dataclass
class _OpenPosition:
    direction: int
    quantity: float
    entry_price: float
    entry_time: int
    entry_fee: float
    funding_pnl: float = 0.0


class BinancePublicFuturesData:
    """Read-only Binance USDⓈ-M market-data client with pagination."""

    def __init__(self, base_url: str = PUBLIC_FUTURES_BASE, http_client: httpx.AsyncClient | None = None):
        self.base_url = base_url.rstrip("/")
        self._http = http_client
        self._owns_http = http_client is None

    async def __aenter__(self) -> BinancePublicFuturesData:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=30)
        return self

    async def __aexit__(self, *_args: object) -> None:
        if self._http is not None and self._owns_http:
            await self._http.aclose()
            self._http = None

    async def _get(self, path: str, params: dict[str, Any]) -> Any:
        if self._http is None:
            raise BacktestError("market-data client is not initialized")
        try:
            response = await self._http.get(f"{self.base_url}{path}", params=params)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise BacktestError(f"Public market-data request failed for {path}: {exc}") from exc

    async def fetch_klines(
        self,
        symbol: str,
        interval: str,
        start_time: int,
        end_time: int,
    ) -> list[Candle]:
        rows: list[Candle] = []
        cursor = start_time
        while cursor < end_time:
            payload = await self._get(
                "/fapi/v1/klines",
                {
                    "symbol": symbol.upper(),
                    "interval": interval,
                    "startTime": cursor,
                    "endTime": end_time,
                    "limit": 1_500,
                },
            )
            if not isinstance(payload, list) or not payload:
                break
            batch = [
                Candle(
                    open_time=int(row[0]),
                    close_time=int(row[6]),
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                )
                for row in payload
            ]
            rows.extend(batch)
            next_cursor = batch[-1].close_time + 1
            if next_cursor <= cursor:
                raise BacktestError("Kline pagination did not advance")
            cursor = next_cursor
            if len(payload) < 1_500:
                break
        return _deduplicate_candles(rows)

    async def fetch_funding_rates(self, symbol: str, start_time: int, end_time: int) -> list[FundingEvent]:
        events: list[FundingEvent] = []
        cursor = start_time
        while cursor < end_time:
            payload = await self._get(
                "/fapi/v1/fundingRate",
                {
                    "symbol": symbol.upper(),
                    "startTime": cursor,
                    "endTime": end_time,
                    "limit": 1_000,
                },
            )
            if not isinstance(payload, list) or not payload:
                break
            batch = [FundingEvent(timestamp=int(row["fundingTime"]), rate=float(row["fundingRate"])) for row in payload]
            events.extend(batch)
            next_cursor = batch[-1].timestamp + 1
            if next_cursor <= cursor:
                raise BacktestError("Funding pagination did not advance")
            cursor = next_cursor
            if len(payload) < 1_000:
                break
        return sorted({event.timestamp: event for event in events}.values(), key=lambda event: event.timestamp)


def _deduplicate_candles(candles: Iterable[Candle]) -> list[Candle]:
    ordered = sorted({candle.open_time: candle for candle in candles}.values(), key=lambda candle: candle.open_time)
    for previous, current in pairwise(ordered):
        if current.open_time <= previous.open_time:
            raise BacktestError("Candle timestamps must be strictly increasing")
    return ordered


class FinancialEngineeringBacktester:
    """Compare spot with long/short perpetual futures at bounded leverage."""

    def __init__(self, config: FinancialBacktestConfig):
        config.symbol = config.symbol.strip().upper()
        config.validate()
        self.config = config

    @property
    def warmup_bars(self) -> int:
        return max(self.config.ema_slow, self.config.adx_period * 2) + 2

    @staticmethod
    def _ema(values: list[float], period: int) -> float:
        if not values:
            return 0.0
        if len(values) < period:
            return sum(values) / len(values)
        multiplier = 2 / (period + 1)
        ema = sum(values[:period]) / period
        for value in values[period:]:
            ema += (value - ema) * multiplier
        return ema

    @staticmethod
    def _adx(candles: list[Candle], period: int) -> float:
        if len(candles) < period + 1:
            return 0.0
        plus_dm: list[float] = []
        minus_dm: list[float] = []
        true_ranges: list[float] = []
        for current, previous in zip(candles[1:], candles, strict=False):
            up = current.high - previous.high
            down = previous.low - current.low
            plus_dm.append(up if up > down and up > 0 else 0.0)
            minus_dm.append(down if down > up and down > 0 else 0.0)
            true_ranges.append(max(current.high - current.low, abs(current.high - previous.close), abs(current.low - previous.close)))
        if len(true_ranges) < period:
            return 0.0
        atr = sum(true_ranges[:period]) / period
        plus_smooth = sum(plus_dm[:period]) / period
        minus_smooth = sum(minus_dm[:period]) / period
        dx_values: list[float] = []
        for index in range(period, len(true_ranges)):
            atr = (atr * (period - 1) + true_ranges[index]) / period
            plus_smooth = (plus_smooth * (period - 1) + plus_dm[index]) / period
            minus_smooth = (minus_smooth * (period - 1) + minus_dm[index]) / period
            if atr <= 0:
                continue
            plus_di = plus_smooth / atr * 100
            minus_di = minus_smooth / atr * 100
            denominator = plus_di + minus_di
            dx_values.append(abs(plus_di - minus_di) / denominator * 100 if denominator else 0.0)
        return sum(dx_values) / len(dx_values) if dx_values else 0.0

    def generate_signals(self, candles: list[Candle]) -> list[str]:
        """Generate close-of-bar signals; execution always happens on the next bar."""
        signals: list[str] = []
        for index in range(len(candles)):
            history = candles[max(0, index - 99) : index + 1]
            closes = [candle.close for candle in history]
            if len(history) < self.warmup_bars:
                signals.append("NEUTRAL")
                continue
            fast = self._ema(closes, self.config.ema_fast)
            slow = self._ema(closes, self.config.ema_slow)
            adx = self._adx(history, self.config.adx_period)
            if adx < self.config.adx_threshold:
                signals.append("NEUTRAL")
            else:
                signals.append("LONG" if fast > slow else "SHORT")
        return signals

    def run_comparison(
        self,
        candles: list[Candle],
        funding_events: list[FundingEvent] | None = None,
    ) -> dict[str, Any]:
        candles = _deduplicate_candles(candles)
        minimum = self.warmup_bars * 2 + 4
        if len(candles) < minimum:
            raise BacktestError(f"At least {minimum} closed candles are required; received {len(candles)}")
        if any(candle.low <= 0 or candle.high < candle.low or candle.open <= 0 or candle.close <= 0 for candle in candles):
            raise BacktestError("Candles contain invalid OHLC prices")

        funding = sorted(funding_events or [], key=lambda event: event.timestamp)
        signals = self.generate_signals(candles)
        split_index = int(len(candles) * (1 - self.config.out_of_sample_fraction))
        split_index = min(max(split_index, self.warmup_bars + 2), len(candles) - self.warmup_bars - 2)
        variants = [("spot", 1), *(("futures", level) for level in self.config.leverage_levels)]

        segments: dict[str, Any] = {}
        segment_bounds = {
            "full": (self.warmup_bars + 1, len(candles)),
            "in_sample": (self.warmup_bars + 1, split_index),
            "out_of_sample": (split_index, len(candles)),
        }
        for segment, (start_index, end_index) in segment_bounds.items():
            results = [
                self._run_variant(
                    candles,
                    signals,
                    funding,
                    market=market,
                    leverage=leverage,
                    start_index=start_index,
                    end_index=end_index,
                )
                for market, leverage in variants
            ]
            ranked = sorted(results, key=lambda item: (item.total_return_pct, item.sharpe_ratio), reverse=True)
            spot = next(item for item in results if item.market == "spot")
            segments[segment] = {
                "start_time": candles[start_index].open_time,
                "end_time": candles[end_index - 1].close_time,
                "ranking_by_return": [self._label(item.market, item.leverage) for item in ranked],
                "leverage_outperformed_spot": [
                    self._label(item.market, item.leverage)
                    for item in results
                    if item.market == "futures" and item.total_return_pct > spot.total_return_pct
                ],
                "results": [self._result_dict(item) for item in results],
            }

        return {
            "report_version": "bookfinance.financial-backtest.v1",
            "generated_at": int(time.time() * 1000),
            "read_only": True,
            "places_orders": False,
            "symbol": self.config.symbol,
            "candle_count": len(candles),
            "funding_event_count": len(funding),
            "split": {
                "in_sample_fraction": round(1 - self.config.out_of_sample_fraction, 4),
                "out_of_sample_fraction": self.config.out_of_sample_fraction,
                "split_time": candles[split_index].open_time,
                "parameter_optimization_performed": False,
            },
            "assumptions": {
                **asdict(self.config),
                "fee_note": "Configurable taker-fee assumption; verify against the intended account tier.",
                "slippage_note": "Configurable adverse fill assumption applied on entry and exit.",
                "liquidation_note": "Isolated-margin approximation, not Binance's account-specific liquidation engine.",
                "intrabar_note": "When multiple barriers occur in one candle, liquidation then stop-loss is evaluated before take-profit.",
                "signal_note": "EMA/ADX is computed at candle close and executed at the next candle open to avoid look-ahead bias.",
                "comparison_note": "Spot is long/cash; futures is long/short. Futures 1x isolates short access before added leverage.",
            },
            "segments": segments,
        }

    @staticmethod
    def _label(market: str, leverage: int) -> str:
        return "spot" if market == "spot" else f"futures_{leverage}x"

    @staticmethod
    def _result_dict(result: VariantResult) -> dict[str, Any]:
        payload = asdict(result)
        payload["label"] = FinancialEngineeringBacktester._label(result.market, result.leverage)
        return payload

    def _run_variant(
        self,
        candles: list[Candle],
        signals: list[str],
        funding_events: list[FundingEvent],
        *,
        market: str,
        leverage: int,
        start_index: int,
        end_index: int,
    ) -> VariantResult:
        if market not in {"spot", "futures"}:
            raise BacktestError("market must be spot or futures")
        if market == "spot" and leverage != 1:
            raise BacktestError("spot leverage must be 1")

        cfg = self.config
        fee_rate = cfg.fee_bps / 10_000
        slippage_rate = cfg.slippage_bps / 10_000
        balance = cfg.initial_equity_usdt
        position: _OpenPosition | None = None
        trades: list[BacktestTrade] = []
        equity_curve: list[float] = [balance]
        exposure_bars = 0
        total_fees = 0.0
        funding_total = 0.0
        liquidations = 0
        turnover = 0.0
        funding_index = 0
        while funding_index < len(funding_events) and funding_events[funding_index].timestamp < candles[start_index].open_time:
            funding_index += 1

        def exit_position(reference_price: float, timestamp: int, reason: str) -> None:
            nonlocal balance, position, total_fees, turnover, liquidations
            if position is None:
                return
            exit_price = reference_price * (1 - slippage_rate * position.direction)
            gross_pnl = (exit_price - position.entry_price) * position.quantity * position.direction
            exit_notional = abs(exit_price * position.quantity)
            exit_fee = exit_notional * fee_rate
            balance += gross_pnl - exit_fee
            total_fees += exit_fee
            turnover += exit_notional
            net_pnl = gross_pnl - position.entry_fee - exit_fee + position.funding_pnl
            trades.append(
                BacktestTrade(
                    market=market,
                    leverage=leverage,
                    side="LONG" if position.direction > 0 else "SHORT",
                    entry_time=position.entry_time,
                    exit_time=timestamp,
                    entry_price=position.entry_price,
                    exit_price=exit_price,
                    quantity=position.quantity,
                    gross_pnl=gross_pnl,
                    fees=position.entry_fee + exit_fee,
                    funding_pnl=position.funding_pnl,
                    net_pnl=net_pnl,
                    exit_reason=reason,
                )
            )
            liquidations += int(reason == "LIQUIDATION")
            position = None

        def open_position(direction: int, reference_price: float, timestamp: int) -> None:
            nonlocal balance, position, total_fees, turnover
            if direction == 0 or balance <= 0:
                return
            effective_leverage = leverage if market == "futures" else 1
            notional = balance * cfg.margin_allocation_pct / 100 * effective_leverage
            entry_price = reference_price * (1 + slippage_rate * direction)
            quantity = notional / entry_price
            entry_fee = notional * fee_rate
            if notional <= 0 or entry_fee >= balance:
                return
            balance -= entry_fee
            total_fees += entry_fee
            turnover += notional
            position = _OpenPosition(
                direction=direction,
                quantity=quantity,
                entry_price=entry_price,
                entry_time=timestamp,
                entry_fee=entry_fee,
            )

        for index in range(start_index, end_index):
            candle = candles[index]
            signal = signals[index - 1]
            if signal == "LONG":
                desired_direction = 1
            elif signal == "SHORT":
                desired_direction = 0 if market == "spot" else -1
            else:
                desired_direction = position.direction if position else 0

            if position is not None and desired_direction != position.direction:
                exit_position(candle.open, candle.open_time, "SIGNAL_REVERSAL")
            if position is None and desired_direction != 0:
                open_position(desired_direction, candle.open, candle.open_time)

            if position is not None:
                exposure_bars += 1
                direction = position.direction
                stop_price = position.entry_price * (1 - direction * cfg.stop_loss_pct / 100)
                take_price = position.entry_price * (1 + direction * cfg.take_profit_pct / 100)
                liquidation_price: float | None = None
                if market == "futures":
                    if direction > 0:
                        liquidation_price = position.entry_price * (1 - 1 / leverage + cfg.maintenance_margin_rate)
                    else:
                        liquidation_price = position.entry_price * (1 + 1 / leverage - cfg.maintenance_margin_rate)

                liquidation_hit = liquidation_price is not None and (
                    (direction > 0 and candle.low <= liquidation_price)
                    or (direction < 0 and candle.high >= liquidation_price)
                )
                stop_hit = (direction > 0 and candle.low <= stop_price) or (direction < 0 and candle.high >= stop_price)
                take_hit = (direction > 0 and candle.high >= take_price) or (direction < 0 and candle.low <= take_price)
                if liquidation_hit:
                    exit_position(float(liquidation_price), candle.close_time, "LIQUIDATION")
                elif stop_hit:
                    exit_position(stop_price, candle.close_time, "STOP_LOSS")
                elif take_hit:
                    exit_position(take_price, candle.close_time, "TAKE_PROFIT")

            while funding_index < len(funding_events) and funding_events[funding_index].timestamp <= candle.close_time:
                event = funding_events[funding_index]
                if event.timestamp >= candle.open_time and position is not None and market == "futures":
                    mark_notional = abs(position.quantity * candle.close)
                    funding_pnl = -position.direction * mark_notional * event.rate
                    balance += funding_pnl
                    position.funding_pnl += funding_pnl
                    funding_total += funding_pnl
                funding_index += 1

            unrealized = 0.0
            if position is not None:
                unrealized = (candle.close - position.entry_price) * position.quantity * position.direction
            equity_curve.append(max(0.0, balance + unrealized))
            if equity_curve[-1] <= 0:
                position = None
                break

        final_candle = candles[end_index - 1]
        if position is not None:
            exit_position(final_candle.close, final_candle.close_time, "END_OF_TEST")
            equity_curve[-1] = max(0.0, balance)

        return self._metrics(
            market=market,
            leverage=leverage,
            start_time=candles[start_index].open_time,
            end_time=final_candle.close_time,
            equity_curve=equity_curve,
            trades=trades,
            total_fees=total_fees,
            funding_total=funding_total,
            liquidations=liquidations,
            turnover=turnover,
            exposure_bars=exposure_bars,
            total_bars=end_index - start_index,
        )

    def _metrics(
        self,
        *,
        market: str,
        leverage: int,
        start_time: int,
        end_time: int,
        equity_curve: list[float],
        trades: list[BacktestTrade],
        total_fees: float,
        funding_total: float,
        liquidations: int,
        turnover: float,
        exposure_bars: int,
        total_bars: int,
    ) -> VariantResult:
        initial = self.config.initial_equity_usdt
        final = equity_curve[-1]
        total_return = final / initial - 1
        elapsed_seconds = max((end_time - start_time) / 1_000, 1)
        annualized_return = (final / initial) ** (SECONDS_PER_YEAR / elapsed_seconds) - 1 if final > 0 else -1.0
        returns = [current / previous - 1 for previous, current in pairwise(equity_curve) if previous > 0]
        seconds_per_bar = elapsed_seconds / max(total_bars, 1)
        periods_per_year = SECONDS_PER_YEAR / max(seconds_per_bar, 1)
        mean_return = statistics.fmean(returns) if returns else 0.0
        volatility = statistics.pstdev(returns) if len(returns) > 1 else 0.0
        downside = [min(value, 0.0) for value in returns]
        downside_deviation = math.sqrt(statistics.fmean(value * value for value in downside)) if downside else 0.0
        sharpe = mean_return / volatility * math.sqrt(periods_per_year) if volatility > 0 else 0.0
        sortino = mean_return / downside_deviation * math.sqrt(periods_per_year) if downside_deviation > 0 else 0.0

        peak = equity_curve[0]
        max_drawdown = 0.0
        for equity in equity_curve:
            peak = max(peak, equity)
            drawdown = (peak - equity) / peak if peak > 0 else 0.0
            max_drawdown = max(max_drawdown, drawdown)
        calmar = annualized_return / max_drawdown if max_drawdown > 0 else 0.0

        winners = [trade.net_pnl for trade in trades if trade.net_pnl > 0]
        losers = [trade.net_pnl for trade in trades if trade.net_pnl <= 0]
        gross_profit = sum(winners)
        gross_loss = abs(sum(losers))
        # Keep the report strict-JSON compatible. A no-loss run is represented
        # by zero here; gross profit and the win/loss counts remain available.
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0
        return VariantResult(
            market=market,
            leverage=leverage,
            start_time=start_time,
            end_time=end_time,
            initial_equity=initial,
            final_equity=final,
            net_pnl=final - initial,
            total_return_pct=total_return * 100,
            annualized_return_pct=annualized_return * 100,
            annualized_volatility_pct=volatility * math.sqrt(periods_per_year) * 100,
            max_drawdown_pct=max_drawdown * 100,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            total_trades=len(trades),
            winning_trades=len(winners),
            losing_trades=len(losers),
            win_rate_pct=len(winners) / len(trades) * 100 if trades else 0.0,
            profit_factor=profit_factor,
            total_fees=total_fees,
            funding_pnl=funding_total,
            liquidations=liquidations,
            turnover_multiple=turnover / initial,
            exposure_pct=exposure_bars / max(total_bars, 1) * 100,
            trades=trades,
        )


def recent_window(days: int) -> tuple[int, int]:
    if days <= 0:
        raise BacktestError("days must be > 0")
    end_time = int(time.time() * 1_000)
    return end_time - days * MILLISECONDS_PER_DAY, end_time
