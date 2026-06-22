"""
Grid Trading Backtester
========================
Simulates grid trading strategy against historical kline data.

Usage:
    backtester = GridBacktester(
        symbol="BTCTHB",
        grid_spacing_pct=1.5,
        grid_levels=2,
        order_size=0.00005,
    )
    results = await backtester.run(days=30)
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger("backtester")

BINANCE_PUBLIC_REST = "https://api.binance.th"


@dataclass
class BacktestConfig:
    symbol: str
    grid_spacing_pct: float = 1.5       # % between grid levels
    grid_levels: int = 2                # number of levels above/below
    order_size: float = 0.00005         # base quantity per grid order
    max_position: float = 0.001         # max position size
    max_open_orders: int = 10           # max simultaneous open orders
    initial_capital_thb: float = 10000.0  # starting capital
    # ATR-based dynamic spacing (mirrors real bot)
    volatility_mode: str = "fixed"      # "fixed" or "atr"
    atr_period: int = 14                # ATR calculation period
    atr_multiplier: float = 1.5         # ATR multiplier for spacing
    min_spacing_pct: float = 0.5        # min spacing floor
    max_spacing_pct: float = 5.0        # max spacing ceiling


@dataclass
class BacktestTrade:
    timestamp: int
    side: str  # BUY or SELL
    price: float
    quantity: float
    pnl: float = 0.0  # realized P&L (for sells)
    fee: float = 0.0


@dataclass
class BacktestResult:
    symbol: str
    start_time: int
    end_time: int
    duration_days: float
    # Performance metrics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    total_fees: float
    net_pnl: float
    max_drawdown: float
    max_drawdown_pct: float
    # Trade details
    avg_win: float
    avg_loss: float
    profit_factor: float
    # Grid stats
    avg_grid_spacing_pct: float
    trades_per_day: float
    # Configuration used
    config: Dict
    # ATR-specific metrics
    atr_spacing_avg: float = 0.0
    atr_spacing_min: float = 0.0
    atr_spacing_max: float = 0.0
    volatility_mode: str = "fixed"
    # Trade history (sample)
    trades: List[BacktestTrade] = field(default_factory=list)


class GridBacktester:
    """
    Simulates grid trading on historical kline data.
    """

    def __init__(self, config: BacktestConfig):
        self.config = config
        self._http: Optional[httpx.AsyncClient] = None

    async def _fetch_klines(self, symbol: str, interval: str, limit: int) -> List[Dict]:
        """Fetch historical klines from Binance TH."""
        if not self._http:
            self._http = httpx.AsyncClient(timeout=15.0)

        try:
            resp = await self._http.get(
                f"{BINANCE_PUBLIC_REST}/api/v1/klines",
                params={"symbol": symbol, "interval": interval, "limit": limit},
            )
            if resp.status_code == 200:
                raw = resp.json()
                return [
                    {
                        "timestamp": k[0],
                        "open": float(k[1]),
                        "high": float(k[2]),
                        "low": float(k[3]),
                        "close": float(k[4]),
                        "volume": float(k[5]),
                    }
                    for k in raw
                ]
        except Exception as e:
            logger.error("Failed to fetch klines: %s", e)

        return []

    def _calc_atr_from_klines(self, klines_slice: List[Dict], period: int) -> float:
        """Calculate ATR from a slice of klines (same logic as real bot)."""
        true_ranges = []
        for i in range(1, len(klines_slice)):
            high = klines_slice[i]["high"]
            low = klines_slice[i]["low"]
            prev_close = klines_slice[i - 1]["close"]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            true_ranges.append(tr)
        if not true_ranges:
            return 0.0
        return sum(true_ranges[-period:]) / min(period, len(true_ranges))

    async def run(self, days: int = 30, interval: str = "1h") -> BacktestResult:
        """
        Run backtest simulation.
        
        Args:
            days: Number of days to backtest
            interval: Kline interval (1m, 5m, 15m, 1h, 4h, 1d)
        
        Returns:
            BacktestResult with performance metrics
        """
        logger.info(
            "Starting backtest: %s, %d days, mode=%s, spacing=%.2f%%, levels=%d",
            self.config.symbol, days, self.config.volatility_mode,
            self.config.grid_spacing_pct, self.config.grid_levels,
        )

        # Calculate how many klines we need
        intervals_per_day = {
            "1m": 1440, "5m": 288, "15m": 96,
            "1h": 24, "4h": 6, "1d": 1,
        }
        klines_needed = days * intervals_per_day.get(interval, 24)
        klines_needed = min(klines_needed, 1000)  # Binance TH limit

        # Fetch historical data
        klines = await self._fetch_klines(self.config.symbol, interval, klines_needed)
        if not klines:
            raise ValueError(f"No kline data available for {self.config.symbol}")

        logger.info("Fetched %d klines from %s to %s",
                    len(klines),
                    time.strftime("%Y-%m-%d", time.gmtime(klines[0]["timestamp"] / 1000)),
                    time.strftime("%Y-%m-%d", time.gmtime(klines[-1]["timestamp"] / 1000)))

        # Simulation state
        active_buys: Dict[float, float] = {}  # price -> quantity
        active_sells: Dict[float, float] = {}  # price -> quantity
        position: float = 0.0
        capital: float = self.config.initial_capital_thb
        trades: List[BacktestTrade] = []
        peak_capital: float = capital
        max_drawdown: float = 0.0
        atr_spacing_values: List[float] = []  # track ATR spacing over time

        # Simulate grid trading
        for i, kline in enumerate(klines):
            price = kline["close"]
            timestamp = kline["timestamp"]

            # Determine spacing based on volatility mode
            if self.config.volatility_mode == "atr" and i >= self.config.atr_period:
                # Calculate ATR from lookback window
                lookback_start = max(0, i - self.config.atr_period - 1)
                atr_klines = klines[lookback_start:i + 1]
                atr = self._calc_atr_from_klines(atr_klines, self.config.atr_period)
                atr_pct = (atr / price) * 100 * self.config.atr_multiplier
                spacing_pct = max(self.config.min_spacing_pct, min(self.config.max_spacing_pct, atr_pct))
                atr_spacing_values.append(spacing_pct)
            else:
                spacing_pct = self.config.grid_spacing_pct

            spacing = price * (spacing_pct / 100.0)

            # Check if any buy orders filled (price dropped to buy level)
            buys_to_fill = [p for p in active_buys if price <= p]
            for buy_price in buys_to_fill:
                qty = active_buys.pop(buy_price)
                cost = buy_price * qty
                capital -= cost
                position += qty
                trades.append(BacktestTrade(
                    timestamp=timestamp,
                    side="BUY",
                    price=buy_price,
                    quantity=qty,
                ))

            # Check if any sell orders filled (price rose to sell level)
            sells_to_fill = [p for p in active_sells if price >= p]
            for sell_price in sells_to_fill:
                qty = active_sells.pop(sell_price)
                if position >= qty:
                    revenue = sell_price * qty
                    capital += revenue
                    position -= qty
                    
                    # Calculate P&L (approximate: sell_price - avg_buy_price)
                    profit = spacing * qty
                    fee = revenue * 0.001  # 0.1% fee estimate
                    trades[-1].pnl = profit - fee if trades and trades[-1].side == "BUY" else profit
                    
                    trades.append(BacktestTrade(
                        timestamp=timestamp,
                        side="SELL",
                        price=sell_price,
                        quantity=qty,
                        pnl=profit,
                        fee=fee,
                    ))

            # Place new grid orders if we have capacity
            total_orders = len(active_buys) + len(active_sells)
            if total_orders < self.config.max_open_orders and position < self.config.max_position:
                for level in range(1, self.config.grid_levels + 1):
                    buy_price = int(price - (spacing * level))
                    sell_price = int(price + (spacing * level))

                    # Place buy order if not already active
                    if buy_price not in active_buys and buy_price > 0:
                        active_buys[buy_price] = self.config.order_size

                    # Place sell order if not already active and we have position
                    if sell_price not in active_sells and position > 0:
                        active_sells[sell_price] = self.config.order_size

            # Track drawdown
            current_value = capital + (position * price)
            if current_value > peak_capital:
                peak_capital = current_value
            drawdown = peak_capital - current_value
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        # Calculate final metrics
        final_value = capital + (position * klines[-1]["close"])
        total_pnl = final_value - self.config.initial_capital_thb
        total_fees = sum(t.fee for t in trades if t.side == "SELL")
        net_pnl = total_pnl - total_fees

        sell_trades = [t for t in trades if t.side == "SELL"]
        winning_trades = [t for t in sell_trades if t.pnl > 0]
        losing_trades = [t for t in sell_trades if t.pnl <= 0]

        avg_win = sum(t.pnl for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(t.pnl for t in losing_trades) / len(losing_trades) if losing_trades else 0
        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else 0

        duration_days = (klines[-1]["timestamp"] - klines[0]["timestamp"]) / (1000 * 86400)
        trades_per_day = len(sell_trades) / duration_days if duration_days > 0 else 0

        # ATR spacing summary
        atr_avg = sum(atr_spacing_values) / len(atr_spacing_values) if atr_spacing_values else 0
        atr_min = min(atr_spacing_values) if atr_spacing_values else 0
        atr_max = max(atr_spacing_values) if atr_spacing_values else 0

        result = BacktestResult(
            symbol=self.config.symbol,
            start_time=klines[0]["timestamp"],
            end_time=klines[-1]["timestamp"],
            duration_days=duration_days,
            total_trades=len(trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=(len(winning_trades) / len(sell_trades) * 100) if sell_trades else 0,
            total_pnl=round(total_pnl, 2),
            total_fees=round(total_fees, 2),
            net_pnl=round(net_pnl, 2),
            max_drawdown=round(max_drawdown, 2),
            max_drawdown_pct=round((max_drawdown / peak_capital) * 100, 2),
            avg_win=round(avg_win, 2),
            avg_loss=round(avg_loss, 2),
            profit_factor=round(profit_factor, 2),
            avg_grid_spacing_pct=round(atr_avg if atr_spacing_values else self.config.grid_spacing_pct, 4),
            trades_per_day=round(trades_per_day, 2),
            config={
                "symbol": self.config.symbol,
                "grid_spacing_pct": self.config.grid_spacing_pct,
                "grid_levels": self.config.grid_levels,
                "order_size": self.config.order_size,
                "max_position": self.config.max_position,
                "initial_capital": self.config.initial_capital_thb,
                "volatility_mode": self.config.volatility_mode,
                "atr_period": self.config.atr_period,
                "atr_multiplier": self.config.atr_multiplier,
            },
            atr_spacing_avg=round(atr_avg, 4),
            atr_spacing_min=round(atr_min, 4),
            atr_spacing_max=round(atr_max, 4),
            volatility_mode=self.config.volatility_mode,
            trades=trades[-50:],  # Last 50 trades for display
        )

        logger.info(
            "Backtest complete: %d trades, PnL=%.2f THB, Win Rate=%.1f%%, mode=%s",
            len(trades), net_pnl, result.win_rate, self.config.volatility_mode,
        )

        return result

    async def close(self):
        """Clean up HTTP client."""
        if self._http:
            await self._http.aclose()


# ── Parameter Sweep ────────────────────────────────────────────────────────────

@dataclass
class SweepResult:
    """One backtest result within a parameter sweep."""
    grid_spacing_pct: float
    grid_levels: int
    net_pnl: float
    win_rate: float
    trades_per_day: float
    max_drawdown_pct: float
    profit_factor: float
    total_trades: int
    atr_spacing_avg: float


@dataclass
class ParameterSweepResult:
    """Result of a parameter sweep across multiple configs."""
    symbol: str
    days: int
    interval: str
    volatility_mode: str
    results: List[SweepResult]
    best_config: Dict  # the config with highest net_pnl
    worst_config: Dict  # the config with lowest net_pnl


async def run_parameter_sweep(
    symbol: str,
    days: int = 30,
    interval: str = "1h",
    volatility_mode: str = "fixed",
    spacing_range: Optional[List[float]] = None,
    levels_range: Optional[List[int]] = None,
    atr_period: int = 14,
    atr_multiplier: float = 1.5,
    min_spacing_pct: float = 0.5,
    max_spacing_pct: float = 5.0,
    order_size: float = 0.00005,
    initial_capital_thb: float = 10000.0,
) -> ParameterSweepResult:
    """
    Run backtest across multiple grid parameter combinations.
    
    Default sweep: spacing [0.5, 1.0, 1.5, 2.0, 3.0] x levels [1, 2, 3, 4]
    = 20 combinations.
    """
    if spacing_range is None:
        spacing_range = [0.5, 1.0, 1.5, 2.0, 3.0]
    if levels_range is None:
        levels_range = [1, 2, 3, 4]

    sweep_results: List[SweepResult] = []
    total = len(spacing_range) * len(levels_range)
    logger.info("Starting parameter sweep: %s, %d combinations, mode=%s", symbol, total, volatility_mode)

    for spacing in spacing_range:
        for levels in levels_range:
            config = BacktestConfig(
                symbol=symbol,
                grid_spacing_pct=spacing,
                grid_levels=levels,
                order_size=order_size,
                max_position=order_size * levels * 2,  # scale position cap with levels
                max_open_orders=levels * 2 + 2,
                initial_capital_thb=initial_capital_thb,
                volatility_mode=volatility_mode,
                atr_period=atr_period,
                atr_multiplier=atr_multiplier,
                min_spacing_pct=min_spacing_pct,
                max_spacing_pct=max_spacing_pct,
            )
            backtester = GridBacktester(config)
            try:
                result = await backtester.run(days=days, interval=interval)
                sweep_results.append(SweepResult(
                    grid_spacing_pct=spacing,
                    grid_levels=levels,
                    net_pnl=result.net_pnl,
                    win_rate=result.win_rate,
                    trades_per_day=result.trades_per_day,
                    max_drawdown_pct=result.max_drawdown_pct,
                    profit_factor=result.profit_factor,
                    total_trades=result.total_trades,
                    atr_spacing_avg=result.atr_spacing_avg,
                ))
            except Exception as e:
                logger.warning("Sweep backtest failed (spacing=%.1f, levels=%d): %s", spacing, levels, e)
            finally:
                await backtester.close()

    # Find best/worst by net_pnl
    if sweep_results:
        best = max(sweep_results, key=lambda r: r.net_pnl)
        worst = min(sweep_results, key=lambda r: r.net_pnl)
        best_config = {
            "grid_spacing_pct": best.grid_spacing_pct,
            "grid_levels": best.grid_levels,
            "net_pnl": best.net_pnl,
            "win_rate": best.win_rate,
            "trades_per_day": best.trades_per_day,
            "max_drawdown_pct": best.max_drawdown_pct,
            "profit_factor": best.profit_factor,
        }
        worst_config = {
            "grid_spacing_pct": worst.grid_spacing_pct,
            "grid_levels": worst.grid_levels,
            "net_pnl": worst.net_pnl,
            "win_rate": worst.win_rate,
        }
    else:
        best_config = {}
        worst_config = {}

    logger.info(
        "Sweep complete: %d/%d succeeded. Best: spacing=%.1f%% levels=%d PnL=%.2f",
        len(sweep_results), total,
        best_config.get("grid_spacing_pct", 0), best_config.get("grid_levels", 0),
        best_config.get("net_pnl", 0),
    )

    return ParameterSweepResult(
        symbol=symbol,
        days=days,
        interval=interval,
        volatility_mode=volatility_mode,
        results=sweep_results,
        best_config=best_config,
        worst_config=worst_config,
    )
