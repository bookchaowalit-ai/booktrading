"""
MACD (Moving Average Convergence Divergence) Strategy
- BUY when MACD line crosses above signal line (bullish)
- SELL when MACD line crosses below signal line (bearish)
"""
import logging
from typing import Optional, List

from core.domain.models import (
    MarketData, OrderSide, OrderSignal, StrategyConfig,
    TechnicalIndicators, TradeSymbol,
)
from core.service.indicators import TechnicalAnalysisService

logger = logging.getLogger(__name__)

class MACDStrategy:
    """
    MACD strategy implementation.
    Generates signals based on MACD line and signal line crossovers.
    """
    
    def __init__(self, symbol: TradeSymbol, fast_period: int = 12, slow_period: int = 26,
                 signal_period: int = 9, min_strength: float = 0.3):
        self.symbol = symbol
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        self.min_strength = min_strength
        self.ta_service = TechnicalAnalysisService()
        self.price_history: List[MarketData] = []
        self.max_history = slow_period + signal_period + 10
        self.last_signal_side: Optional[str] = None
    
    def process_market_data(self, data: MarketData) -> Optional[OrderSignal]:
        """Process market data and generate MACD signals."""
        if data.symbol != self.symbol:
            return None
        
        self.price_history.append(data)
        if len(self.price_history) > self.max_history:
            self.price_history = self.price_history[-self.max_history:]
        
        if len(self.price_history) < self.slow_period + self.signal_period:
            return None
        
        prices = [d.price for d in self.price_history]
        
        # Calculate MACD
        macd_line = self.ta_service.calculate_macd(prices, self.fast_period, self.slow_period)
        
        if macd_line is None:
            return None
        
        # Calculate signal line (EMA of MACD)
        # We need MACD history to calculate signal EMA
        macd_history = []
        for i in range(self.fast_period, len(prices) + 1):
            window = prices[max(0, i-self.slow_period):i]
            if len(window) >= self.slow_period:
                macd_val = self.ta_service.calculate_macd(window, self.fast_period, self.slow_period)
                if macd_val is not None:
                    macd_history.append(macd_val)
        
        if len(macd_history) < self.signal_period + 1:
            return None
        
        signal_line = self.ta_service.calculate_ema(macd_history, self.signal_period)
        prev_signal = self.ta_service.calculate_ema(macd_history[:-1], self.signal_period)
        
        if signal_line is None or prev_signal is None:
            return None
        
        prev_macd = macd_history[-2] if len(macd_history) >= 2 else macd_history[-1]
        current_macd = macd_history[-1]
        
        signal = None
        
        # Bullish crossover: MACD crosses above signal
        if prev_macd <= prev_signal and current_macd > signal_line:
            if self.last_signal_side != "BUY":
                strength = min(1.0, abs(current_macd - signal_line) / abs(signal_line) * 100) if signal_line != 0 else 0.5
                if strength >= self.min_strength:
                    signal = OrderSignal(
                        symbol=self.symbol,
                        side=OrderSide.BUY,
                        strength=round(strength, 4),
                        reason=f"MACD bullish cross (MACD={current_macd:.4f} > Signal={signal_line:.4f})",
                    )
                    self.last_signal_side = "BUY"
                    logger.info("MACD BUY signal: %s", self.symbol.value)
        
        # Bearish crossover: MACD crosses below signal
        elif prev_macd >= prev_signal and current_macd < signal_line:
            if self.last_signal_side != "SELL":
                strength = min(1.0, abs(current_macd - signal_line) / abs(signal_line) * 100) if signal_line != 0 else 0.5
                if strength >= self.min_strength:
                    signal = OrderSignal(
                        symbol=self.symbol,
                        side=OrderSide.SELL,
                        strength=round(strength, 4),
                        reason=f"MACD bearish cross (MACD={current_macd:.4f} < Signal={signal_line:.4f})",
                    )
                    self.last_signal_side = "SELL"
                    logger.info("MACD SELL signal: %s", self.symbol.value)
        
        return signal
    
    def get_current_indicators(self, symbol: TradeSymbol) -> Optional[TechnicalIndicators]:
        """Get current MACD values."""
        if not self.price_history:
            return None
        
        prices = [d.price for d in self.price_history]
        macd = self.ta_service.calculate_macd(prices, self.fast_period, self.slow_period)
        
        return TechnicalIndicators(
            symbol=symbol,
            rsi=None,
            ema=None,
            sma=None,
            macd=macd,
            macd_signal=None,
        )
