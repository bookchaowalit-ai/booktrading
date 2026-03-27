"""
Technical indicators calculation service using pandas.
"""
import numpy as np
import pandas as pd
from typing import List, Optional

from core.domain.models import MarketData, TechnicalIndicators, TradeSymbol


class TechnicalAnalysisService:
    """Service for calculating technical indicators."""
    
    def __init__(self, rsi_period: int = 14, ema_period: int = 14):
        self.rsi_period = rsi_period
        self.ema_period = ema_period
    
    def calculate_rsi(self, prices: List[float], period: Optional[int] = None) -> Optional[float]:
        """
        Calculate Relative Strength Index (RSI).
        
        RSI = 100 - (100 / (1 + RS))
        RS = Average Gain / Average Loss
        """
        if period is None:
            period = self.rsi_period
        
        if len(prices) < period + 1:
            return None
        
        # Calculate price changes
        deltas = np.diff(prices)
        
        # Separate gains and losses
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        # Calculate average gain and loss
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        # Calculate RS and RSI
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return round(rsi, 2)
    
    def calculate_ema(self, prices: List[float], period: Optional[int] = None) -> Optional[float]:
        """
        Calculate Exponential Moving Average (EMA).
        """
        if period is None:
            period = self.ema_period
        
        if len(prices) < period:
            return None
        
        # Use pandas for EMA calculation
        series = pd.Series(prices)
        ema = series.ewm(span=period, adjust=False).mean().iloc[-1]
        
        return round(ema, 2)
    
    def calculate_sma(self, prices: List[float], period: int = 14) -> Optional[float]:
        """
        Calculate Simple Moving Average (SMA).
        """
        if len(prices) < period:
            return None
        
        return round(sum(prices[-period:]) / period, 2)
    
    def calculate_macd(
        self, 
        prices: List[float], 
        fast_period: int = 12, 
        slow_period: int = 26, 
        signal_period: int = 9
    ) -> tuple:
        """
        Calculate MACD (Moving Average Convergence Divergence).
        
        Returns: (MACD line, Signal line)
        """
        if len(prices) < slow_period + signal_period:
            return None, None
        
        series = pd.Series(prices)
        
        # Calculate EMAs
        ema_fast = series.ewm(span=fast_period, adjust=False).mean()
        ema_slow = series.ewm(span=slow_period, adjust=False).mean()
        
        # MACD line
        macd_line = ema_fast - ema_slow
        
        # Signal line
        signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
        
        return (
            round(macd_line.iloc[-1], 2),
            round(signal_line.iloc[-1], 2)
        )
    
    def calculate_all_indicators(
        self, 
        symbol: TradeSymbol, 
        market_data: List[MarketData]
    ) -> TechnicalIndicators:
        """
        Calculate all technical indicators for a symbol.
        """
        if not market_data:
            return TechnicalIndicators(symbol=symbol)
        
        # Extract prices
        prices = [data.price for data in market_data]
        
        # Calculate indicators
        rsi = self.calculate_rsi(prices)
        ema = self.calculate_ema(prices)
        sma = self.calculate_sma(prices)
        macd, macd_signal = self.calculate_macd(prices)
        
        return TechnicalIndicators(
            symbol=symbol,
            rsi=rsi,
            ema=ema,
            sma=sma,
            macd=macd,
            macd_signal=macd_signal
        )


class SignalStrengthCalculator:
    """Calculate signal strength based on multiple factors."""
    
    @staticmethod
    def calculate_rsi_strength(rsi: float, oversold: float = 30, overbought: float = 70) -> float:
        """
        Calculate signal strength based on RSI.
        
        Returns: 0.0 to 1.0
        """
        if rsi < oversold:
            # Strong buy signal when RSI is very low
            return min(1.0, (oversold - rsi) / oversold + 0.5)
        elif rsi > overbought:
            # Strong sell signal when RSI is very high
            return min(1.0, (rsi - overbought) / (100 - overbought) + 0.5)
        else:
            # Weak signal in neutral zone
            return 0.0
    
    @staticmethod
    def calculate_combined_strength(
        rsi: Optional[float],
        ema: Optional[float],
        current_price: float,
        rsi_weight: float = 0.6,
        trend_weight: float = 0.4
    ) -> float:
        """
        Calculate combined signal strength from multiple indicators.
        """
        if rsi is None:
            return 0.0
        
        # RSI component
        rsi_strength = SignalStrengthCalculator.calculate_rsi_strength(rsi)
        
        # Trend component (price vs EMA)
        trend_strength = 0.0
        if ema is not None and ema > 0:
            price_deviation = abs(current_price - ema) / ema
            trend_strength = min(1.0, price_deviation * 10)  # Scale deviation
        
        # Combined strength
        combined = (rsi_strength * rsi_weight) + (trend_strength * trend_weight)
        
        return round(min(1.0, combined), 2)
