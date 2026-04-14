"""
Smart Strategy Recommender
Analyzes market regime (trending, ranging, volatile, quiet) and recommends
the best trading strategy with optimal parameters.

Market Regimes:
1. Strong Trend — EMA Cross strategy works best
2. Ranging/Sideways — RSI mean-reversion works best
3. High Volatility Breakout — MACD momentum works best
4. Low Volatility/Quiet — No trading recommended

The recommender uses:
- ADX (Average Directional Index) to measure trend strength
- ATR (Average True Range) to measure volatility
- Bollinger Band width to measure squeeze/expansion
- RSI level to measure momentum exhaustion
- Volume trend to confirm moves
"""
import logging
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict, Any
import math

import numpy as np

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    STRONG_TREND = "strong_trend"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"


class RecommendedStrategy(Enum):
    EMA_CROSS = "ema_cross"
    RSI = "rsi"
    MACD = "macd"
    WAIT = "wait"  # Market conditions not favorable


@dataclass
class StrategyRecommendation:
    regime: MarketRegime
    recommended_strategy: RecommendedStrategy
    confidence: float  # 0-1
    suggested_params: Dict[str, Any]
    reasoning: str
    regime_scores: Dict[str, float]  # Score for each regime (0-1)


class StrategyRecommender:
    """Analyzes market conditions and recommends the optimal strategy."""
    
    def __init__(self):
        pass
    
    def recommend(self, prices: List[float], volumes: Optional[List[float]] = None,
                  rsi_value: Optional[float] = None) -> StrategyRecommendation:
        """
        Analyze market regime and recommend best strategy.
        
        Args:
            prices: Price history (at least 50 periods)
            volumes: Volume data (optional)
            rsi_value: Current RSI (optional, computed if not provided)
        
        Returns:
            StrategyRecommendation with regime analysis and parameters
        """
        if len(prices) < 50:
            return StrategyRecommendation(
                regime=MarketRegime.LOW_VOLATILITY,
                recommended_strategy=RecommendedStrategy.WAIT,
                confidence=0.0,
                suggested_params={},
                reasoning="Insufficient data for analysis",
                regime_scores={},
            )
        
        prices_arr = np.array(prices)
        
        # Compute market regime scores
        regime_scores = {}
        regime_scores["strong_trend"] = self._score_trend(prices_arr)
        regime_scores["ranging"] = self._score_ranging(prices_arr)
        regime_scores["high_volatility"] = self._score_volatility(prices_arr, volumes)
        regime_scores["low_volatility"] = self._score_low_volatility(prices_arr)
        
        # Determine dominant regime
        dominant_regime = max(regime_scores, key=regime_scores.get)
        regime_score = regime_scores[dominant_regime]
        
        # Map regime to recommended strategy
        strategy_map = {
            "strong_trend": RecommendedStrategy.EMA_CROSS,
            "ranging": RecommendedStrategy.RSI,
            "high_volatility": RecommendedStrategy.MACD,
            "low_volatility": RecommendedStrategy.WAIT,
        }
        
        recommended = strategy_map[dominant_regime]
        
        # Get optimal parameters for the recommended strategy
        params = self._get_optimal_params(recommended, prices_arr, regime_scores)
        
        # Generate reasoning
        reasoning = self._generate_reasoning(dominant_regime, recommended, regime_scores, params)
        
        return StrategyRecommendation(
            regime=MarketRegime(dominant_regime),
            recommended_strategy=recommended,
            confidence=round(regime_score, 4),
            suggested_params=params,
            reasoning=reasoning,
            regime_scores={k: round(v, 4) for k, v in regime_scores.items()},
        )
    
    def _score_trend(self, prices: np.ndarray) -> float:
        """
        Score how strongly the market is trending (0-1).
        Uses ADX-like approach: measures directional movement strength.
        """
        # Simple ADX approximation using EMA alignment
        ema_12 = self._ema(prices, 12)
        ema_26 = self._ema(prices, 26)
        ema_50 = self._ema(prices, 50)
        
        # Check if EMAs are properly aligned (trend confirmation)
        if ema_12 > ema_26 > ema_50:
            alignment_score = 1.0
        elif ema_12 < ema_26 < ema_50:
            alignment_score = 1.0
        else:
            alignment_score = 0.3
        
        # Price momentum consistency
        changes = np.diff(prices[-20:])
        same_direction = sum(1 for c in changes if c > 0) if changes[0] > 0 else sum(1 for c in changes if c < 0)
        consistency = same_direction / len(changes) if len(changes) > 0 else 0.5
        
        # EMA spread (wider spread = stronger trend)
        spread_pct = abs(ema_12 - ema_26) / ema_26 * 100
        spread_score = min(1.0, spread_pct / 3.0)  # 3% spread = max score
        
        score = alignment_score * 0.4 + consistency * 0.3 + spread_score * 0.3
        return min(1.0, score)
    
    def _score_ranging(self, prices: np.ndarray) -> float:
        """
        Score how much the market is ranging/sideways (0-1).
        Ranging = price oscillates around a mean with no clear direction.
        """
        sma_20 = np.mean(prices[-20:])
        sma_50 = np.mean(prices[-50:])
        
        # Price should be close to both SMAs (no clear trend)
        price = prices[-1]
        dist_20 = abs(price - sma_20) / sma_20 * 100
        dist_50 = abs(price - sma_50) / sma_50 * 100
        
        sma_score = max(0, 1.0 - (dist_20 + dist_50) / 4.0)  # Low distance = high score
        
        # Price should be mean-reverting (many crossovers of SMA)
        recent = prices[-50:]
        crossovers = 0
        for i in range(1, len(recent)):
            if (recent[i-1] < sma_20 and recent[i] > sma_20) or \
               (recent[i-1] > sma_20 and recent[i] < sma_20):
                crossovers += 1
        
        crossover_score = min(1.0, crossovers / 5.0)  # 5+ crossovers = max score
        
        # Low directional momentum
        changes = np.diff(prices[-20:])
        positive = sum(1 for c in changes if c > 0)
        balance = 1.0 - abs(positive / len(changes) - 0.5) * 2  # 50/50 = max score
        
        score = sma_score * 0.3 + crossover_score * 0.4 + balance * 0.3
        return min(1.0, score)
    
    def _score_volatility(self, prices: np.ndarray, volumes: Optional[List[float]]) -> float:
        """
        Score market volatility (0-1).
        High volatility = large price swings + high volume.
        """
        # ATR-like measure using price ranges
        daily_changes = np.abs(np.diff(prices[-20:]))
        avg_change_pct = np.mean(daily_changes / prices[-21:-1]) * 100
        
        # Volatility score based on average daily change
        vol_score = min(1.0, avg_change_pct / 3.0)  # 3% avg daily change = max
        
        # Volume confirmation
        vol_volume = 0.5
        if volumes and len(volumes) >= 21:
            avg_vol = np.mean(volumes[-21:-1])
            if avg_vol > 0:
                vol_ratio = volumes[-1] / avg_vol
                vol_volume = min(1.0, vol_ratio / 2.0)
        
        # Recent price range
        recent_range = (np.max(prices[-20:]) - np.min(prices[-20:])) / np.mean(prices[-20:]) * 100
        range_score = min(1.0, recent_range / 10.0)  # 10% range = max
        
        score = vol_score * 0.4 + vol_volume * 0.2 + range_score * 0.4
        return min(1.0, score)
    
    def _score_low_volatility(self, prices: np.ndarray) -> float:
        """
        Score how quiet the market is (0-1).
        Low volatility = small moves, low volume, tight Bollinger Bands.
        """
        daily_changes = np.abs(np.diff(prices[-20:]))
        avg_change_pct = np.mean(daily_changes / prices[-21:-1]) * 100
        
        # Inverse of volatility score
        low_vol_score = max(0, 1.0 - avg_change_pct / 2.0)  # <1% avg change = high score
        
        # Bollinger Band squeeze
        sma_20 = np.mean(prices[-20:])
        std_20 = np.std(prices[-20:])
        if sma_20 > 0:
            bb_width = (2 * std_20) / sma_20 * 100
            squeeze_score = max(0, 1.0 - bb_width / 5.0)  # <5% BB width = high score
        else:
            squeeze_score = 0.0
        
        score = (low_vol_score + squeeze_score) / 2
        return min(1.0, score)
    
    def _get_optimal_params(self, strategy: RecommendedStrategy, prices: np.ndarray,
                           regime_scores: Dict[str, float]) -> Dict[str, Any]:
        """Get strategy-specific optimal parameters based on current conditions."""
        base_params = {}
        
        if strategy == RecommendedStrategy.EMA_CROSS:
            # Adjust EMA periods based on trend strength
            trend_strength = regime_scores.get("strong_trend", 0.5)
            if trend_strength > 0.7:
                base_params = {
                    "ema_fast_period": 9,
                    "ema_slow_period": 21,
                    "description": "Fast EMAs for strong trend capture",
                }
            else:
                base_params = {
                    "ema_fast_period": 12,
                    "ema_slow_period": 26,
                    "description": "Standard EMAs for moderate trends",
                }
        
        elif strategy == RecommendedStrategy.RSI:
            # Adjust RSI thresholds based on ranging score
            ranging_strength = regime_scores.get("ranging", 0.5)
            if ranging_strength > 0.7:
                base_params = {
                    "rsi_period": 10,
                    "rsi_oversold": 25,
                    "rsi_overbought": 75,
                    "min_signal_strength": 0.4,
                    "description": "Wider RSI bands for clear ranging market",
                }
            else:
                base_params = {
                    "rsi_period": 14,
                    "rsi_oversold": 30,
                    "rsi_overbought": 70,
                    "min_signal_strength": 0.5,
                    "description": "Standard RSI for moderate ranging",
                }
        
        elif strategy == RecommendedStrategy.MACD:
            vol_strength = regime_scores.get("high_volatility", 0.5)
            base_params = {
                "macd_fast": 8 if vol_strength > 0.7 else 12,
                "macd_slow": 21 if vol_strength > 0.7 else 26,
                "macd_signal": 7,
                "min_signal_strength": 0.4,
                "description": "Fast MACD for volatile breakout market" if vol_strength > 0.7 else "Standard MACD settings",
            }
        
        elif strategy == RecommendedStrategy.WAIT:
            base_params = {
                "description": "Market conditions are not favorable. Consider waiting.",
                "reason": "Low volatility and no clear trend detected",
            }
        
        return base_params
    
    def _generate_reasoning(self, regime: str, strategy: RecommendedStrategy,
                          regime_scores: Dict[str, float], params: Dict[str, Any]) -> str:
        """Generate human-readable explanation for the recommendation."""
        regime_names = {
            "strong_trend": "Strong Trending",
            "ranging": "Ranging/Sideways",
            "high_volatility": "High Volatility",
            "low_volatility": "Low Volatility/Quiet",
        }
        
        strategy_names = {
            RecommendedStrategy.EMA_CROSS: "EMA Crossover",
            RecommendedStrategy.RSI: "RSI Mean-Reversion",
            RecommendedStrategy.MACD: "MACD Momentum",
            RecommendedStrategy.WAIT: "No Trading (Wait)",
        }
        
        top_regime = max(regime_scores, key=regime_scores.get)
        top_score = regime_scores[top_regime]
        
        reason = (
            f"Market regime: {regime_names.get(regime, regime)} "
            f"(confidence: {top_score:.0%}). "
            f"Recommended: {strategy_names[strategy]}. "
            f"{params.get('description', '')}"
        )
        
        return reason
    
    @staticmethod
    def _ema(prices: np.ndarray, period: int) -> float:
        if len(prices) < period:
            return float(np.mean(prices))
        multiplier = 2.0 / (period + 1)
        ema = float(np.mean(prices[:period]))
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        return ema
