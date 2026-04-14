"""
EMA Crossover Strategy
- BUY when fast EMA crosses above slow EMA (golden cross)
- SELL when fast EMA crosses below slow EMA (death cross)
"""
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Callable

from core.domain.models import (
    MarketData, OrderSide, OrderSignal, StrategyConfig, 
    TechnicalIndicators, TradeSymbol,
)
from core.service.indicators import TechnicalAnalysisService

logger = logging.getLogger(__name__)

class EMACrossStrategy:
    """
    EMA Crossover strategy implementation.
    Generates signals based on fast/slow EMA crossovers.
    """
    
    def __init__(self, symbol: TradeSymbol, fast_period: int = 12, slow_period: int = 26,
                 min_strength: float = 0.3):
        self.symbol = symbol
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.min_strength = min_strength
        self.ta_service = TechnicalAnalysisService()
        self.price_history: List[MarketData] = []
        self.max_history = max(fast_period, slow_period) + 10
        self.last_signal_side: Optional[str] = None  # Track last signal to avoid spam
    
    def process_market_data(self, data: MarketData) -> Optional[OrderSignal]:
        """Process market data and generate EMA cross signals."""
        if data.symbol != self.symbol:
            return None
        
        self.price_history.append(data)
        if len(self.price_history) > self.max_history:
            self.price_history = self.price_history[-self.max_history:]
        
        if len(self.price_history) < self.slow_period + 1:
            return None
        
        prices = [d.price for d in self.price_history]
        
        fast_ema = self.ta_service.calculate_ema(prices, self.fast_period)
        slow_ema = self.ta_service.calculate_ema(prices, self.slow_period)
        
        if fast_ema is None or slow_ema is None:
            return None
        
        # Check for crossover (need previous values too)
        if len(prices) < self.slow_period + 2:
            return None
        
        prev_fast = self.ta_service.calculate_ema(prices[:-1], self.fast_period)
        prev_slow = self.ta_service.calculate_ema(prices[:-1], self.slow_period)
        
        if prev_fast is None or prev_slow is None:
            return None
        
        signal = None
        
        # Golden cross: fast crosses above slow
        if prev_fast <= prev_slow and fast_ema > slow_ema:
            if self.last_signal_side != "BUY":
                strength = min(1.0, (fast_ema - slow_ema) / slow_ema * 100)
                if strength >= self.min_strength:
                    signal = OrderSignal(
                        symbol=self.symbol,
                        side=OrderSide.BUY,
                        strength=round(strength, 4),
                        reason=f"EMA golden cross (fast={fast_ema:.2f} > slow={slow_ema:.2f})",
                    )
                    self.last_signal_side = "BUY"
                    logger.info("EMA cross BUY signal: %s", self.symbol.value)
        
        # Death cross: fast crosses below slow
        elif prev_fast >= prev_slow and fast_ema < slow_ema:
            if self.last_signal_side != "SELL":
                strength = min(1.0, (slow_ema - fast_ema) / slow_ema * 100)
                if strength >= self.min_strength:
                    signal = OrderSignal(
                        symbol=self.symbol,
                        side=OrderSide.SELL,
                        strength=round(strength, 4),
                        reason=f"EMA death cross (fast={fast_ema:.2f} < slow={slow_ema:.2f})",
                    )
                    self.last_signal_side = "SELL"
                    logger.info("EMA cross SELL signal: %s", self.symbol.value)
        
        return signal
    
    def get_current_indicators(self, symbol: TradeSymbol) -> Optional[TechnicalIndicators]:
        """Get current EMA values."""
        if not self.price_history:
            return None
        
        prices = [d.price for d in self.price_history]
        fast_ema = self.ta_service.calculate_ema(prices, self.fast_period)
        slow_ema = self.ta_service.calculate_ema(prices, self.slow_period)
        
        return TechnicalIndicators(
            symbol=symbol,
            ema=fast_ema,  # Primary EMA is fast
            sma=None,
            rsi=None,
            macd=None,
            macd_signal=None,
        )
