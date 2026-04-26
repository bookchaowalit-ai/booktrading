"""
Technical indicators calculation service using pandas.
"""
import numpy as np
import pandas as pd
from typing import List, Optional, Tuple

from core.domain.models import MarketData, TechnicalIndicators, TradeSymbol


class TechnicalAnalysisService:
    """Service for calculating technical indicators."""

    def __init__(
        self,
        rsi_period: int = 14,
        ema_period: int = 14,
        ema_fast_period: int = 9,
        ema_slow_period: int = 21,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        bollinger_period: int = 20,
        bollinger_std: float = 2.0,
        atr_period: int = 14,
        adx_period: int = 14,
        roc_period: int = 10,
        stoch_rsi_period: int = 14,
    ):
        self.rsi_period = rsi_period
        self.ema_period = ema_period
        self.ema_fast_period = ema_fast_period
        self.ema_slow_period = ema_slow_period
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.bollinger_period = bollinger_period
        self.bollinger_std = bollinger_std
        self.atr_period = atr_period
        self.adx_period = adx_period
        self.roc_period = roc_period
        self.stoch_rsi_period = stoch_rsi_period
    
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
    
    def calculate_macd_full(
        self,
        prices: List[float],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """
        Calculate MACD with signal line and histogram.
        Returns: (macd_line, signal_line, histogram)
        """
        if len(prices) < slow_period + signal_period:
            return None, None, None

        series = pd.Series(prices)
        ema_fast = series.ewm(span=fast_period, adjust=False).mean()
        ema_slow = series.ewm(span=slow_period, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
        histogram = macd_line - signal_line

        return (
            round(macd_line.iloc[-1], 4),
            round(signal_line.iloc[-1], 4),
            round(histogram.iloc[-1], 4),
        )

    def calculate_bollinger_bands(
        self,
        prices: List[float],
        period: int = 20,
        std_dev: float = 2.0,
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """
        Calculate Bollinger Bands.
        Returns: (upper_band, middle_band, lower_band)
        """
        if len(prices) < period:
            return None, None, None

        series = pd.Series(prices)
        sma = series.rolling(window=period).mean()
        std = series.rolling(window=period).std()

        upper = sma + std_dev * std
        lower = sma - std_dev * std

        return (
            round(upper.iloc[-1], 2),
            round(sma.iloc[-1], 2),
            round(lower.iloc[-1], 2),
        )

    def calculate_atr(
        self,
        prices: List[float],
        period: int = 14,
    ) -> Optional[float]:
        """
        Calculate Average True Range as percentage of price.
        Uses price deltas as proxy for true range (no OHLC data).
        Returns: ATR value as % of current price (0.01 = 1%)
        """
        if len(prices) < period + 1:
            return None

        # Use absolute price changes as proxy for true range
        changes = np.abs(np.diff(prices))
        atr = np.mean(changes[-period:])

        # Normalize as percentage of current price
        current_price = prices[-1]
        if current_price == 0:
            return None

        return round(atr / current_price, 6)

    def calculate_stoch_rsi(
        self,
        prices: List[float],
        rsi_period: int = 14,
        stoch_period: int = 14,
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Calculate Stochastic RSI.
        Returns: (k_line, d_line)
        """
        if len(prices) < rsi_period + stoch_period + 1:
            return None, None

        # Calculate RSI values for the lookback window
        rsi_values = []
        for i in range(rsi_period + 1, len(prices) + 1):
            window = prices[:i]
            rsi = self.calculate_rsi(window, rsi_period)
            if rsi is not None:
                rsi_values.append(rsi)

        if len(rsi_values) < stoch_period:
            return None, None

        rsi_series = pd.Series(rsi_values)

        # Stoch %K = (RSI - min_RSI) / (max_RSI - min_RSI) * 100
        min_rsi = rsi_series.rolling(window=stoch_period).min()
        max_rsi = rsi_series.rolling(window=stoch_period).max()

        range_rsi = max_rsi - min_rsi
        k_line = ((rsi_series - min_rsi) / range_rsi * 100) if range_rsi.iloc[-1] != 0 else pd.Series([50.0])
        d_line = k_line.ewm(span=3, adjust=False).mean()

        k_val = k_line.iloc[-1]
        d_val = d_line.iloc[-1]

        if pd.isna(k_val) or pd.isna(d_val):
            return None, None

        return round(k_val, 2), round(d_val, 2)

    def calculate_ema_cross(
        self,
        prices: List[float],
        fast_period: int = 9,
        slow_period: int = 21,
    ) -> Tuple[Optional[float], Optional[float], Optional[str]]:
        """
        Calculate fast/slow EMA and detect crossover.
        Returns: (fast_ema, slow_ema, cross_direction)
        cross_direction: "golden" | "death" | None
        """
        if len(prices) < slow_period + 1:
            return None, None, None

        fast_ema = self.calculate_ema(prices, fast_period)
        slow_ema = self.calculate_ema(prices, slow_period)

        if fast_ema is None or slow_ema is None:
            return None, None, None

        # Previous EMAs
        prev_fast = self.calculate_ema(prices[:-1], fast_period)
        prev_slow = self.calculate_ema(prices[:-1], slow_period)

        cross_direction = None
        if prev_fast is not None and prev_slow is not None:
            if prev_fast <= prev_slow and fast_ema > slow_ema:
                cross_direction = "golden"
            elif prev_fast >= prev_slow and fast_ema < slow_ema:
                cross_direction = "death"

        return round(fast_ema, 2), round(slow_ema, 2), cross_direction

    def calculate_adx(
        self,
        prices: List[float],
        period: int = 14,
    ) -> Optional[float]:
        """
        Calculate Average Directional Index (simplified).
        ADX measures trend strength (0-100). >25 = trending.
        Uses price changes as proxy for directional movement.
        """
        if len(prices) < period * 2 + 1:
            return None

        changes = np.diff(prices)
        if len(changes) < period * 2:
            return None

        # Simplified ADX using autocorrelation of directional movement
        # +DI and -DI proxy: use consecutive up/down movements
        ups = np.where(changes > 0, changes, 0)
        downs = np.where(changes < 0, -changes, 0)

        # Smoothed averages
        avg_up = np.mean(ups[-period:])
        avg_down = np.mean(downs[-period:])

        total_movement = avg_up + avg_down
        if total_movement == 0:
            return 0.0

        # DX (Directional Index)
        dx = abs(avg_up - avg_down) / total_movement * 100

        # Simple smoothed ADX approximation
        # Use multiple windows for smoothing
        dx_values = []
        for i in range(period, len(changes) - period + 1, max(1, period // 2)):
            chunk_ups = np.where(changes[i - period:i] > 0, changes[i - period:i], 0)
            chunk_downs = np.where(changes[i - period:i] < 0, -changes[i - period:i], 0)
            cu = np.mean(chunk_ups)
            cd = np.mean(chunk_downs)
            ct = cu + cd
            if ct > 0:
                dx_values.append(abs(cu - cd) / ct * 100)

        if not dx_values:
            return round(dx, 2)

        adx = np.mean(dx_values[-3:])  # Average last 3 DX values
        return round(adx, 2)

    def calculate_roc(
        self,
        prices: List[float],
        period: int = 10,
    ) -> Optional[float]:
        """
        Calculate Rate of Change (ROC) as percentage.
        Positive = bullish momentum, negative = bearish.
        """
        if len(prices) < period + 1:
            return None

        current = prices[-1]
        past = prices[-(period + 1)]

        if past == 0:
            return None

        return round((current - past) / past * 100, 4)

    def calculate_obv_trend(
        self,
        prices: List[float],
        period: int = 14,
    ) -> Optional[float]:
        """
        Calculate OBV trend as a normalized value (-1 to 1).
        Uses price direction × volume proxy (absolute price change).
        Positive = buying pressure, negative = selling pressure.
        """
        if len(prices) < period + 1:
            return None

        changes = np.diff(prices[-(period + 1):])
        # Use absolute price change as volume proxy
        volume_proxy = np.abs(changes)

        # OBV = cumulative sum of direction × volume
        directions = np.sign(changes)
        obv = directions * volume_proxy
        obv_sum = np.sum(obv)
        obv_total = np.sum(np.abs(obv))

        if obv_total == 0:
            return 0.0

        return round(obv_sum / obv_total, 4)

    def calculate_all_indicators(
        self,
        symbol: TradeSymbol,
        market_data: List[MarketData],
    ) -> TechnicalIndicators:
        """
        Calculate all technical indicators for a symbol.
        """
        if not market_data:
            return TechnicalIndicators(symbol=symbol)

        prices = [data.price for data in market_data]

        # Basic indicators
        rsi = self.calculate_rsi(prices)
        ema = self.calculate_ema(prices)
        sma = self.calculate_sma(prices)

        # MACD
        macd, macd_signal = self.calculate_macd(
            prices, self.macd_fast, self.macd_slow, self.macd_signal
        )
        macd_full, macd_signal_full, macd_hist = self.calculate_macd_full(
            prices, self.macd_fast, self.macd_slow, self.macd_signal
        )

        # Bollinger Bands
        bb_upper, bb_mid, bb_lower = self.calculate_bollinger_bands(
            prices, self.bollinger_period, self.bollinger_std
        )
        bb_width = None
        if bb_upper and bb_lower:
            bb_width = round((bb_upper - bb_lower) / bb_mid, 6) if bb_mid else None

        # EMA Cross
        ema_fast, ema_slow, ema_cross = self.calculate_ema_cross(
            prices, self.ema_fast_period, self.ema_slow_period
        )

        # ATR
        atr = self.calculate_atr(prices, self.atr_period)

        # Stochastic RSI
        stoch_k, stoch_d = self.calculate_stoch_rsi(
            prices, self.rsi_period, self.stoch_rsi_period
        )

        # ADX
        adx = self.calculate_adx(prices, self.adx_period)

        # ROC
        roc = self.calculate_roc(prices, self.roc_period)

        # OBV Trend
        obv_trend = self.calculate_obv_trend(prices, period=14)

        return TechnicalIndicators(
            symbol=symbol,
            # Existing
            rsi=rsi,
            ema=ema,
            sma=sma,
            macd=macd,
            macd_signal=macd_signal,
            # New
            bb_upper=bb_upper,
            bb_lower=bb_lower,
            bb_width=bb_width,
            atr=atr,
            stoch_k=stoch_k,
            stoch_d=stoch_d,
            macd_histogram=macd_hist,
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            ema_cross=ema_cross,
            adx=adx,
            roc=roc,
            obv_trend=obv_trend,
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
