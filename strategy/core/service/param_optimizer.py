"""
Auto Parameter Optimizer
Uses walk-forward analysis to find optimal strategy parameters.
Tests parameter combinations on historical data and selects the best.
"""
import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
import math

logger = logging.getLogger(__name__)


@dataclass
class ParameterSet:
    params: Dict[str, float]
    score: float  # Higher is better (Sharpe-like metric)
    total_trades: int
    win_rate: float
    profit_factor: float
    max_drawdown: float
    total_return: float


class ParamOptimizer:
    """Finds optimal strategy parameters using walk-forward analysis."""
    
    def optimize_rsi(self, prices: List[float], periods: List[int] = None,
                     oversold_range: List[float] = None,
                     overbought_range: List[float] = None) -> ParameterSet:
        """
        Find optimal RSI parameters by backtesting combinations.
        """
        if periods is None:
            periods = [7, 10, 14, 18, 21]
        if oversold_range is None:
            oversold_range = [20, 25, 30, 35]
        if overbought_range is None:
            overbought_range = [65, 70, 75, 80]
        
        best_result = None
        best_params = None
        
        for period in periods:
            for os_level in oversold_range:
                for ob_level in overbought_range:
                    if os_level >= ob_level:
                        continue
                    
                    result = self._backtest_rsi(prices, period, os_level, ob_level)
                    if best_result is None or result.score > best_result.score:
                        best_result = result
                        best_params = {"rsi_period": period, "rsi_oversold": os_level, "rsi_overbought": ob_level}
        
        if best_result is None:
            return ParameterSet(
                params={"rsi_period": 14, "rsi_oversold": 30, "rsi_overbought": 70},
                score=0, total_trades=0, win_rate=0, profit_factor=0,
                max_drawdown=0, total_return=0,
            )
        
        return ParameterSet(
            params=best_params,
            score=best_result.score,
            total_trades=best_result.total_trades,
            win_rate=best_result.win_rate,
            profit_factor=best_result.profit_factor,
            max_drawdown=best_result.max_drawdown,
            total_return=best_result.total_return,
        )
    
    def optimize_ema_cross(self, prices: List[float],
                           fast_range: List[int] = None,
                           slow_range: List[int] = None) -> ParameterSet:
        """Find optimal EMA cross parameters."""
        if fast_range is None:
            fast_range = [5, 8, 9, 12]
        if slow_range is None:
            slow_range = [21, 26, 34, 50]
        
        best_result = None
        best_params = None
        
        for fast in fast_range:
            for slow in slow_range:
                if fast >= slow:
                    continue
                
                result = self._backtest_ema_cross(prices, fast, slow)
                if best_result is None or result.score > best_result.score:
                    best_result = result
                    best_params = {"ema_fast": fast, "ema_slow": slow}
        
        if best_result is None:
            return ParameterSet(
                params={"ema_fast": 12, "ema_slow": 26},
                score=0, total_trades=0, win_rate=0, profit_factor=0,
                max_drawdown=0, total_return=0,
            )
        
        return ParameterSet(
            params=best_params,
            score=best_result.score,
            total_trades=best_result.total_trades,
            win_rate=best_result.win_rate,
            profit_factor=best_result.profit_factor,
            max_drawdown=best_result.max_drawdown,
            total_return=best_result.total_return,
        )
    
    def _backtest_rsi(self, prices: List[float], period: int,
                      oversold: float, overbought: float) -> ParameterSet:
        """Simple RSI backtest for parameter scoring."""
        if len(prices) < period + 50:
            return ParameterSet({}, 0, 0, 0, 0, 0, 0)
        
        capital = 10000.0
        position = 0.0
        entry_price = 0.0
        trades = []
        peak = capital
        
        for i in range(period + 1, len(prices)):
            rsi = self._compute_rsi(prices[:i+1], period)
            if rsi is None:
                continue
            
            price = prices[i]
            
            if position == 0 and rsi < oversold:
                # BUY
                position = capital / price
                entry_price = price
                capital = 0
            elif position > 0 and rsi > overbought:
                # SELL
                capital = position * price
                pnl = capital - entry_price * position
                trades.append(pnl)
                
                # Reset
                peak = max(peak, capital)
                position = 0
                entry_price = 0.0
        
        # Close position at last price
        if position > 0:
            capital = position * prices[-1]
            trades.append(capital - entry_price * position)
        
        return self._score_trades(trades, prices)
    
    def _backtest_ema_cross(self, prices: List[float], fast: int, slow: int) -> ParameterSet:
        """Simple EMA cross backtest."""
        if len(prices) < slow + 10:
            return ParameterSet({}, 0, 0, 0, 0, 0, 0)
        
        capital = 10000.0
        position = 0.0
        entry_price = 0.0
        trades = []
        peak = capital
        prev_fast_ema = None
        prev_slow_ema = None
        
        for i in range(slow, len(prices)):
            fast_ema = self._compute_ema(prices[:i+1], fast)
            slow_ema = self._compute_ema(prices[:i+1], slow)
            
            if prev_fast_ema is not None and prev_slow_ema is not None:
                price = prices[i]
                
                # Golden cross
                if prev_fast_ema <= prev_slow_ema and fast_ema > slow_ema and position == 0:
                    position = capital / price
                    entry_price = price
                    capital = 0
                
                # Death cross
                elif prev_fast_ema >= prev_slow_ema and fast_ema < slow_ema and position > 0:
                    capital = position * price
                    trades.append(capital - entry_price * position)
                    peak = max(peak, capital)
                    position = 0
                    entry_price = 0.0
            
            prev_fast_ema = fast_ema
            prev_slow_ema = slow_ema
        
        if position > 0:
            capital = position * prices[-1]
            trades.append(capital - entry_price * position)
        
        return self._score_trades(trades, prices)
    
    def _score_trades(self, trades: List[float], prices: List[float]) -> ParameterSet:
        """Score a set of trades and return ParameterSet."""
        if not trades:
            return ParameterSet({}, 0, 0, 0, 0, 100, 0)
        
        wins = [t for t in trades if t > 0]
        losses = [t for t in trades if t <= 0]
        
        win_rate = len(wins) / len(trades) * 100 if trades else 0
        total_return = sum(trades)
        gross_profit = sum(wins) if wins else 0
        gross_loss = abs(sum(losses)) if losses else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else gross_profit
        
        # Max drawdown
        equity = 10000.0
        peak_eq = equity
        max_dd = 0.0
        for t in trades:
            equity += t
            peak_eq = max(peak_eq, equity)
            dd = (peak_eq - equity) / peak_eq * 100
            max_dd = max(max_dd, dd)
        
        # Score: Sharpe-like metric (return / drawdown)
        score = (total_return / 10000.0) * 100 - max_dd * 0.5 + win_rate * 0.3
        if profit_factor > 1:
            score += profit_factor * 10
        
        return ParameterSet(
            params={},
            score=round(score, 2),
            total_trades=len(trades),
            win_rate=round(win_rate, 1),
            profit_factor=round(profit_factor, 2),
            max_drawdown=round(max_dd, 2),
            total_return=round(total_return, 2),
        )
    
    @staticmethod
    def _compute_rsi(prices: List[float], period: int) -> Optional[float]:
        if len(prices) < period + 1:
            return None
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        recent = deltas[-period:]
        gains = sum(d for d in recent if d > 0) / period
        losses = sum(-d for d in recent if d < 0) / period
        if losses == 0:
            return 100.0
        rs = gains / losses
        return 100.0 - (100.0 / (1.0 + rs))
    
    @staticmethod
    def _compute_ema(prices: List[float], period: int) -> float:
        if len(prices) < period:
            return sum(prices) / len(prices)
        mult = 2.0 / (period + 1)
        ema = sum(prices[:period]) / period
        for p in prices[period:]:
            ema = (p - ema) * mult + ema
        return ema
