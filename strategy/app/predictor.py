"""
AI Price Prediction Service
Uses simple ML (moving average crossover + RSI) to predict price direction
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class PricePredictor:
    """
    Simple price prediction using technical indicators:
    - Moving Average Crossover (SMA/EMA)
    - RSI (Relative Strength Index)
    - MACD (Moving Average Convergence Divergence)
    - Bollinger Bands
    
    Returns prediction: BULLISH, BEARISH, or NEUTRAL
    """
    
    def __init__(self):
        self.models = {}
        
    def predict(self, prices: List[float], volume: Optional[List[float]] = None) -> Dict:
        """
        Predict price direction based on technical analysis
        
        Args:
            prices: List of recent prices (oldest to newest)
            volume: Optional list of trading volumes
            
        Returns:
            Dict with prediction, confidence, and indicators
        """
        if len(prices) < 20:
            return {
                "prediction": "NEUTRAL",
                "confidence": 0.0,
                "message": "Insufficient data (need at least 20 prices)",
                "indicators": {}
            }
        
        prices_array = np.array(prices)
        
        # Calculate indicators
        indicators = self._calculate_indicators(prices_array, volume)
        
        # Generate signals from each indicator
        signals = self._generate_signals(indicators)
        
        # Combine signals with weighted voting
        prediction, confidence = self._combine_signals(signals)
        
        return {
            "prediction": prediction,
            "confidence": round(confidence, 3),
            "current_price": prices[-1],
            "indicators": indicators,
            "signals": signals,
            "message": f"Prediction: {prediction} ({confidence:.1%} confidence)"
        }
    
    def _calculate_indicators(self, prices: np.ndarray, volume: Optional[np.ndarray]) -> Dict:
        """Calculate all technical indicators"""
        indicators = {}
        
        # Simple Moving Averages
        indicators['sma_7'] = self._sma(prices, 7)
        indicators['sma_20'] = self._sma(prices, 20)
        indicators['sma_50'] = self._sma(prices, min(50, len(prices)))
        
        # Exponential Moving Averages
        indicators['ema_12'] = self._ema(prices, 12)
        indicators['ema_26'] = self._ema(prices, 26)
        
        # RSI
        indicators['rsi_14'] = self._rsi(prices, 14)
        
        # MACD
        macd, macd_signal, macd_histogram = self._macd(prices)
        indicators['macd'] = macd
        indicators['macd_signal'] = macd_signal
        indicators['macd_histogram'] = macd_histogram
        
        # Bollinger Bands
        bb_upper, bb_middle, bb_lower = self._bollinger_bands(prices, 20, 2)
        indicators['bb_upper'] = bb_upper
        indicators['bb_middle'] = bb_middle
        indicators['bb_lower'] = bb_lower
        
        # Volume indicators (if available)
        if volume is not None and len(volume) >= 20:
            indicators['volume_sma'] = np.mean(volume[-20:])
            indicators['current_volume'] = volume[-1]
            indicators['volume_ratio'] = volume[-1] / indicators['volume_sma']
        
        return indicators
    
    def _generate_signals(self, indicators: Dict) -> Dict:
        """Generate trading signals from indicators"""
        signals = {}
        current_price = indicators.get('current_price', 0)
        
        # 1. Moving Average Crossover (weight: 0.25)
        if 'sma_7' in indicators and 'sma_20' in indicators:
            if indicators['sma_7'] > indicators['sma_20']:
                signals['ma_crossover'] = {'signal': 'BUY', 'weight': 0.25, 'strength': 1.0}
            else:
                signals['ma_crossover'] = {'signal': 'SELL', 'weight': 0.25, 'strength': 1.0}
        
        # 2. RSI (weight: 0.25)
        if 'rsi_14' in indicators:
            rsi = indicators['rsi_14']
            if rsi < 30:
                signals['rsi'] = {'signal': 'BUY', 'weight': 0.25, 'strength': min(1.0, (30 - rsi) / 30)}
            elif rsi > 70:
                signals['rsi'] = {'signal': 'SELL', 'weight': 0.25, 'strength': min(1.0, (rsi - 70) / 30)}
            else:
                signals['rsi'] = {'signal': 'NEUTRAL', 'weight': 0.25, 'strength': 0.0}
        
        # 3. MACD (weight: 0.25)
        if 'macd_histogram' in indicators:
            if indicators['macd_histogram'] > 0:
                signals['macd'] = {'signal': 'BUY', 'weight': 0.25, 'strength': min(1.0, abs(indicators['macd_histogram']) / 100)}
            else:
                signals['macd'] = {'signal': 'SELL', 'weight': 0.25, 'strength': min(1.0, abs(indicators['macd_histogram']) / 100)}
        
        # 4. Bollinger Bands (weight: 0.15)
        if 'bb_upper' in indicators and 'bb_lower' in indicators:
            bb_position = (current_price - indicators['bb_lower']) / (indicators['bb_upper'] - indicators['bb_lower'])
            if bb_position < 0.2:
                signals['bollinger'] = {'signal': 'BUY', 'weight': 0.15, 'strength': 1.0 - bb_position / 0.2}
            elif bb_position > 0.8:
                signals['bollinger'] = {'signal': 'SELL', 'weight': 0.15, 'strength': (bb_position - 0.8) / 0.2}
            else:
                signals['bollinger'] = {'signal': 'NEUTRAL', 'weight': 0.15, 'strength': 0.0}
        
        # 5. Volume (weight: 0.10)
        if 'volume_ratio' in indicators:
            if indicators['volume_ratio'] > 1.5:
                signals['volume'] = {'signal': 'BUY', 'weight': 0.10, 'strength': min(1.0, (indicators['volume_ratio'] - 1.5) / 2)}
            else:
                signals['volume'] = {'signal': 'NEUTRAL', 'weight': 0.10, 'strength': 0.0}
        
        return signals
    
    def _combine_signals(self, signals: Dict) -> tuple:
        """Combine all signals into final prediction"""
        if not signals:
            return "NEUTRAL", 0.0
        
        buy_score = 0.0
        sell_score = 0.0
        total_weight = 0.0
        
        for name, signal in signals.items():
            weight = signal['weight']
            strength = signal['strength']
            total_weight += weight
            
            if signal['signal'] == 'BUY':
                buy_score += weight * strength
            elif signal['signal'] == 'SELL':
                sell_score += weight * strength
        
        # Normalize
        if total_weight > 0:
            buy_score /= total_weight
            sell_score /= total_weight
        
        # Determine prediction
        if buy_score > sell_score:
            prediction = "BULLISH"
            confidence = buy_score
        elif sell_score > buy_score:
            prediction = "BEARISH"
            confidence = sell_score
        else:
            prediction = "NEUTRAL"
            confidence = 0.5
        
        return prediction, min(confidence, 1.0)
    
    # ── Technical Indicator Calculations ─────────────────────────────────────
    
    @staticmethod
    def _sma(prices: np.ndarray, period: int) -> float:
        """Simple Moving Average"""
        return float(np.mean(prices[-period:]))
    
    @staticmethod
    def _ema(prices: np.ndarray, period: int) -> float:
        """Exponential Moving Average"""
        if len(prices) < period:
            return float(np.mean(prices))
        
        multiplier = 2 / (period + 1)
        ema = np.mean(prices[:period])
        
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        
        return float(ema)
    
    @staticmethod
    def _rsi(prices: np.ndarray, period: int = 14) -> float:
        """Relative Strength Index"""
        if len(prices) < period + 1:
            return 50.0
        
        deltas = np.diff(prices[-period-1:])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        return float(100 - (100 / (1 + rs)))
    
    @staticmethod
    def _macd(prices: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple:
        """MACD (Moving Average Convergence Divergence)"""
        ema_fast = PricePredictor._ema(prices, fast)
        ema_slow = PricePredictor._ema(prices, slow)
        
        macd_line = ema_fast - ema_slow
        
        # Simplified - in production use proper MACD calculation
        macd_signal = macd_line * 0.9  # Simplified signal line
        histogram = macd_line - macd_signal
        
        return macd_line, macd_signal, histogram
    
    @staticmethod
    def _bollinger_bands(prices: np.ndarray, period: int = 20, std_dev: int = 2) -> tuple:
        """Bollinger Bands"""
        if len(prices) < period:
            period = len(prices)
        
        sma = np.mean(prices[-period:])
        std = np.std(prices[-period:])
        
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        
        return float(upper), float(sma), float(lower)


# Singleton instance
predictor = PricePredictor()
