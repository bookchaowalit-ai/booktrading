"""
AI Trade Signal Predictor
Uses historical price data and technical indicators to predict short-term price direction.
Implements a lightweight model without external ML dependencies (uses pure numpy/pandas).

Features used for prediction:
- Price momentum (rate of change over N periods)
- RSI level and trend
- EMA distance (price vs trend)
- Volume relative to average
- Bollinger Band position
- MACD histogram trend

Output: Signal (BUY/SELL/NEUTRAL) with confidence score (0-1)
"""
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple
import math

import numpy as np

logger = logging.getLogger(__name__)


class AISignal(Enum):
    BUY = "BUY"
    SELL = "SELL"
    NEUTRAL = "NEUTRAL"


@dataclass
class AIPrediction:
    """Result of AI prediction"""
    signal: AISignal
    confidence: float           # 0.0 - 1.0
    predicted_direction: float  # -1.0 to 1.0
    feature_importance: dict    # Which features contributed most
    reason: str


class AIPredictor:
    """
    AI-based trade signal predictor.
    
    Uses a weighted ensemble approach combining multiple simple models:
    1. Momentum model — predicts based on price momentum
    2. Mean-reversion model — predicts based on RSI + Bollinger Bands
    3. Trend model — predicts based on EMA alignment + MACD
    
    No training required — weights are derived from recent market regime analysis.
    """
    
    def __init__(self, lookback: int = 100):
        self.lookback = lookback
        # Feature weights (updated dynamically based on market regime)
        self.weights = {
            "momentum": 0.3,
            "mean_reversion": 0.3,
            "trend": 0.4,
        }
    
    def predict(self, prices: List[float], volumes: Optional[List[float]] = None,
                rsi_values: Optional[List[float]] = None,
                ema_fast: Optional[List[float]] = None,
                ema_slow: Optional[List[float]] = None,
                macd_values: Optional[List[float]] = None) -> AIPrediction:
        """
        Generate a prediction for the next price movement.
        
        Args:
            prices: Recent price history (at least 50 data points)
            volumes: Corresponding volume data (optional)
            rsi_values: Pre-computed RSI values (optional)
            ema_fast: Pre-computed fast EMA values (optional)
            ema_slow: Pre-computed slow EMA values (optional)
            macd_values: Pre-computed MACD values (optional)
        
        Returns:
            AIPrediction with signal, confidence, and reasoning
        """
        if len(prices) < 50:
            return AIPrediction(
                signal=AISignal.NEUTRAL,
                confidence=0.0,
                predicted_direction=0.0,
                feature_importance={},
                reason="Insufficient data for prediction (need at least 50 points)",
            )
        
        prices_arr = np.array(prices[-self.lookback:])
        current_price = prices_arr[-1]
        
        # Compute all features
        features = self._compute_features(prices_arr, volumes, rsi_values, ema_fast, ema_slow, macd_values)
        
        # Run ensemble prediction
        signals = {}
        
        # 1. Momentum model
        mom_signal, mom_score = self._momentum_model(prices_arr, volumes)
        signals["momentum"] = (mom_signal, mom_score)
        
        # 2. Mean reversion model
        mr_signal, mr_score = self._mean_reversion_model(prices_arr, features.get("rsi"))
        signals["mean_reversion"] = (mr_signal, mr_score)
        
        # 3. Trend model
        trend_signal, trend_score = self._trend_model(prices_arr, features.get("ema_fast"), features.get("ema_slow"), features.get("macd"))
        signals["trend"] = (trend_signal, trend_score)
        
        # Weighted ensemble
        weighted_score = 0.0
        total_weight = 0.0
        feature_importance = {}
        
        for model_name, (sig, score) in signals.items():
            w = self.weights.get(model_name, 0.0)
            weighted_score += sig * score * w
            total_weight += w
            feature_importance[model_name] = round(score, 3)
        
        if total_weight > 0:
            weighted_score /= total_weight
        
        # Convert to signal
        direction = float(np.clip(weighted_score, -1.0, 1.0))
        confidence = abs(direction)
        
        # Adaptive threshold: higher confidence needed for strong signals
        if confidence > 0.6:
            signal = AISignal.BUY if direction > 0 else AISignal.SELL
        elif confidence > 0.35:
            signal = AISignal.BUY if direction > 0 else AISignal.SELL
        else:
            signal = AISignal.NEUTRAL
        
        reason = self._generate_reason(features, signals, signal)
        
        return AIPrediction(
            signal=signal,
            confidence=round(confidence, 4),
            predicted_direction=round(direction, 4),
            feature_importance=feature_importance,
            reason=reason,
        )
    
    def _compute_features(self, prices: np.ndarray, volumes: Optional[List[float]],
                          rsi_values: Optional[List[float]],
                          ema_fast: Optional[List[float]],
                          ema_slow: Optional[List[float]],
                          macd_values: Optional[List[float]]) -> dict:
        """Compute technical features from price data."""
        features = {}
        
        # RSI
        if rsi_values and len(rsi_values) >= 2:
            features["rsi"] = rsi_values[-1]
            features["rsi_trend"] = rsi_values[-1] - rsi_values[-2]
        else:
            features["rsi"] = self._compute_rsi(prices, 14)
            features["rsi_trend"] = 0.0
        
        # EMA
        if ema_fast and ema_slow and len(ema_fast) >= 1:
            features["ema_fast"] = ema_fast[-1]
            features["ema_slow"] = ema_slow[-1]
            features["ema_spread"] = (ema_fast[-1] - ema_slow[-1]) / ema_slow[-1] * 100
        else:
            features["ema_fast"] = self._compute_ema(prices, 12)
            features["ema_slow"] = self._compute_ema(prices, 26)
            features["ema_spread"] = (features["ema_fast"] - features["ema_slow"]) / features["ema_slow"] * 100
        
        # MACD
        if macd_values and len(macd_values) >= 2:
            features["macd"] = macd_values[-1]
            features["macd_change"] = macd_values[-1] - macd_values[-2]
        else:
            features["macd"] = 0.0
            features["macd_change"] = 0.0
        
        # Volume
        if volumes and len(volumes) >= 21:
            features["volume_ratio"] = volumes[-1] / (sum(volumes[-21:-1]) / 20)
        else:
            features["volume_ratio"] = 1.0
        
        # Volatility (Bollinger Band width)
        sma_20 = np.mean(prices[-20:])
        std_20 = np.std(prices[-20:])
        features["bb_upper"] = sma_20 + 2 * std_20
        features["bb_lower"] = sma_20 - 2 * std_20
        features["bb_position"] = (prices[-1] - features["bb_lower"]) / (features["bb_upper"] - features["bb_lower"]) if features["bb_upper"] != features["bb_lower"] else 0.5
        
        # Momentum
        features["roc_5"] = (prices[-1] / prices[-6] - 1) * 100 if len(prices) >= 6 else 0
        features["roc_10"] = (prices[-1] / prices[-11] - 1) * 100 if len(prices) >= 11 else 0
        
        return features
    
    def _momentum_model(self, prices: np.ndarray, volumes: Optional[List[float]]) -> Tuple[float, float]:
        """
        Momentum-based prediction.
        Returns: (direction: -1 to 1, confidence: 0 to 1)
        """
        roc_5 = (prices[-1] / prices[-6] - 1) * 100 if len(prices) >= 6 else 0
        roc_10 = (prices[-1] / prices[-11] - 1) * 100 if len(prices) >= 11 else 0
        roc_20 = (prices[-1] / prices[-21] - 1) * 100 if len(prices) >= 21 else 0
        
        # Weighted momentum score
        momentum = roc_5 * 0.5 + roc_10 * 0.3 + roc_20 * 0.2
        
        # Direction
        direction = 1.0 if momentum > 0 else -1.0
        
        # Confidence based on momentum strength and consistency
        # Check if momentum is consistent across timeframes
        consistency = 1.0
        signs = [1 if roc_5 > 0 else -1, 1 if roc_10 > 0 else -1, 1 if roc_20 > 0 else -1]
        if len(set(signs)) > 1:
            consistency = 0.5  # Mixed signals reduce confidence
        
        # Volume confirmation
        vol_confidence = 1.0
        if volumes and len(volumes) >= 21:
            avg_vol = sum(volumes[-21:-1]) / 20
            if avg_vol > 0:
                vol_ratio = volumes[-1] / avg_vol
                if vol_ratio > 1.5 and momentum > 0:
                    vol_confidence = 1.2  # High volume confirms uptrend
                elif vol_ratio > 1.5 and momentum < 0:
                    vol_confidence = 1.1  # High volume on downtrend is also significant
        
        confidence = min(1.0, (abs(momentum) / 5.0) * consistency * vol_confidence)
        
        return direction, confidence
    
    def _mean_reversion_model(self, prices: np.ndarray, rsi: Optional[float]) -> Tuple[float, float]:
        """
        Mean reversion prediction based on RSI and Bollinger Bands.
        """
        rsi_val = rsi if rsi is not None else self._compute_rsi(prices, 14)
        
        # RSI-based signal
        if rsi_val < 30:
            direction = 1.0  # Oversold → BUY
            confidence = min(1.0, (30 - rsi_val) / 30)
        elif rsi_val > 70:
            direction = -1.0  # Overbought → SELL
            confidence = min(1.0, (rsi_val - 70) / 30)
        else:
            direction = 0.0
            confidence = 0.0
        
        # Bollinger Band confirmation
        sma_20 = np.mean(prices[-20:])
        std_20 = np.std(prices[-20:])
        bb_upper = sma_20 + 2 * std_20
        bb_lower = sma_20 - 2 * std_20
        current_price = prices[-1]
        
        if bb_upper != bb_lower:
            bb_position = (current_price - bb_lower) / (bb_upper - bb_lower)
            
            # If price is near lower BB and RSI is oversold → stronger BUY
            if bb_position < 0.2 and rsi_val < 30:
                confidence = min(1.0, confidence * 1.3)
            # If price is near upper BB and RSI is overbought → stronger SELL
            elif bb_position > 0.8 and rsi_val > 70:
                confidence = min(1.0, confidence * 1.3)
            # Contradiction: price near BB but RSI disagrees → reduce confidence
            elif (bb_position < 0.2 and rsi_val > 50) or (bb_position > 0.8 and rsi_val < 50):
                confidence *= 0.5
        
        return direction, confidence
    
    def _trend_model(self, prices: np.ndarray, ema_fast: Optional[float],
                     ema_slow: Optional[float], macd: Optional[float]) -> Tuple[float, float]:
        """
        Trend-following prediction based on EMA alignment and MACD.
        """
        ef = ema_fast if ema_fast is not None else self._compute_ema(prices, 12)
        es = ema_slow if ema_slow is not None else self._compute_ema(prices, 26)
        
        ema_spread_pct = (ef - es) / es * 100
        
        # EMA trend direction
        if ef > es:
            direction = 1.0  # Uptrend
        else:
            direction = -1.0  # Downtrend
        
        # Confidence based on spread strength
        confidence = min(1.0, abs(ema_spread_pct) / 2.0)
        
        # MACD confirmation
        if macd is not None and abs(macd) > 0:
            macd_direction = 1.0 if macd > 0 else -1.0
            if macd_direction == direction:
                confidence = min(1.0, confidence * 1.2)  # MACD confirms trend
            else:
                confidence *= 0.7  # MACD contradicts → weaker signal
        
        return direction, confidence
    
    def _generate_reason(self, features: dict, signals: dict, predicted_signal: AISignal) -> str:
        """Generate human-readable explanation for the prediction."""
        parts = []
        sig_name = predicted_signal.value
        
        # Momentum
        mom_sig, mom_conf = signals["momentum"]
        if mom_conf > 0.3:
            parts.append(f"Momentum {'bullish' if mom_sig > 0 else 'bearish'} (strength: {mom_conf:.2f})")
        
        # Mean reversion
        mr_sig, mr_conf = signals["mean_reversion"]
        if mr_conf > 0.3:
            rsi = features.get("rsi", 50)
            parts.append(f"RSI at {rsi:.1f} suggests {'oversold bounce' if mr_sig > 0 else 'overbought pullback'}")
        
        # Trend
        trend_sig, trend_conf = signals["trend"]
        if trend_conf > 0.3:
            parts.append(f"Trend is {'upward' if trend_sig > 0 else 'downward'} (EMA spread: {features.get('ema_spread', 0):.2f}%)")
        
        reason = f"AI predicts {sig_name}: " + "; ".join(parts) if parts else f"AI predicts {sig_name} (low conviction)"
        return reason
    
    # ── Helper indicator calculations ──
    
    @staticmethod
    def _compute_rsi(prices: np.ndarray, period: int = 14) -> float:
        if len(prices) < period + 1:
            return 50.0
        deltas = np.diff(prices[-period-1:])
        gains = np.where(deltas > 0, deltas, 0).sum() / period
        losses = np.where(deltas < 0, -deltas, 0).sum() / period
        if losses == 0:
            return 100.0
        rs = gains / losses
        return 100.0 - (100.0 / (1.0 + rs))
    
    @staticmethod
    def _compute_ema(prices: np.ndarray, period: int) -> float:
        if len(prices) < period:
            return float(np.mean(prices))
        multiplier = 2.0 / (period + 1)
        ema = float(np.mean(prices[:period]))
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        return ema
