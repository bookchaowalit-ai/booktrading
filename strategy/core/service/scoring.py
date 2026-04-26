"""
Composite scoring engine for multi-indicator trading signals.
Combines trend, momentum, volatility, and RSI components into a single
weighted score (-1 to +1) to generate balanced BUY/SELL signals.
"""
import logging
from typing import Dict, List, Optional, Tuple

from core.domain.models import StrategyConfig, TechnicalIndicators

logger = logging.getLogger(__name__)


def _weighted_avg(scores: List[float]) -> float:
    """Average a list of scores, returning 0.0 if empty."""
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def _clamp(value: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


class CompositeScorer:
    """Multi-indicator composite scoring engine."""

    @staticmethod
    def score_trend(
        indicators: TechnicalIndicators,
        price: float,
        adx_min: float = 25.0,
    ) -> Tuple[float, str]:
        """Score trend component (-1 to +1). Returns (score, reason)."""
        parts: List[float] = []
        reasons: List[str] = []

        # EMA Cross direction
        if indicators.ema_cross == "golden":
            parts.append(1.0)
            reasons.append("EMA golden cross")
        elif indicators.ema_cross == "death":
            parts.append(-1.0)
            reasons.append("EMA death cross")
        elif indicators.ema_fast is not None and indicators.ema_slow is not None and indicators.ema_slow != 0:
            diff = (indicators.ema_fast - indicators.ema_slow) / indicators.ema_slow
            score = _clamp(diff * 100)
            parts.append(score)
            if abs(score) > 0.3:
                reasons.append(
                    f"EMA {'above' if score > 0 else 'below'} by {abs(score) * 100:.1f}%"
                )

        # ADX trend strength
        if indicators.adx is not None:
            if indicators.adx < adx_min:
                strength_factor = indicators.adx / adx_min if adx_min > 0 else 0.5
                parts.append(strength_factor)
                reasons.append(f"ADX={indicators.adx:.1f}(weak)")
            else:
                reasons.append(f"ADX={indicators.adx:.1f}(strong)")

        # ROC
        if indicators.roc is not None:
            roc_score = _clamp(indicators.roc / 5.0)
            parts.append(roc_score)

        return _weighted_avg(parts), "; ".join(reasons) if reasons else "no trend signal"

    @staticmethod
    def score_momentum(indicators: TechnicalIndicators) -> Tuple[float, str]:
        """Score momentum (-1 to +1)."""
        parts: List[float] = []
        reasons: List[str] = []

        # MACD histogram direction
        if indicators.macd_histogram is not None:
            hist_norm = _clamp(indicators.macd_histogram * 100)
            parts.append(hist_norm)
            reasons.append(f"MACD hist={indicators.macd_histogram:.4f}")

        # Stochastic RSI
        if indicators.stoch_k is not None:
            if indicators.stoch_k < 20:
                parts.append(1.0)
                reasons.append("StochRSI oversold")
            elif indicators.stoch_k > 80:
                parts.append(-1.0)
                reasons.append("StochRSI overbought")
            else:
                parts.append(0.0)

        return _weighted_avg(parts), "; ".join(reasons) if reasons else "no momentum signal"

    @staticmethod
    def score_volatility(
        indicators: TechnicalIndicators,
        price: float,
    ) -> Tuple[float, str]:
        """Score volatility / mean-reversion (-1 to +1)."""
        parts: List[float] = []
        reasons: List[str] = []

        if indicators.bb_upper is not None and indicators.bb_lower is not None:
            width = indicators.bb_upper - indicators.bb_lower
            if width != 0:
                bb_pct = (price - indicators.bb_lower) / width
                bb_pct = _clamp(bb_pct, 0.0, 1.0)
                bb_score = 1.0 - 2 * bb_pct
                parts.append(bb_score)
                reasons.append(f"BB%={bb_pct:.2f}")

            if indicators.bb_width is not None and indicators.bb_width < 0.04:
                reasons.append("BB squeeze pending")

        return _weighted_avg(parts), "; ".join(reasons) if reasons else "no vol signal"

    @staticmethod
    def score_rsi(indicators: TechnicalIndicators) -> Tuple[float, str]:
        """Score RSI component (-1 to +1)."""
        if indicators.rsi is None:
            return 0.0, "no RSI"
        if indicators.rsi < 30:
            return 1.0, f"RSI oversold ({indicators.rsi:.1f})"
        elif indicators.rsi > 70:
            return -1.0, f"RSI overbought ({indicators.rsi:.1f})"
        elif indicators.rsi < 50:
            return 0.3, f"RSI bearish ({indicators.rsi:.1f})"
        else:
            return -0.3, f"RSI bullish ({indicators.rsi:.1f})"

    @staticmethod
    def composite(
        indicators: TechnicalIndicators,
        price: float,
        weights: StrategyConfig,
    ) -> Tuple[float, Dict]:
        """
        Calculate composite score from all components.
        Returns (composite_score, breakdown_dict).
        Score range: -1.0 (strong sell) to +1.0 (strong buy), 0 = neutral.
        """
        trend_score, trend_reason = CompositeScorer.score_trend(
            indicators, price, weights.adx_min_trend
        )
        momentum_score, momentum_reason = CompositeScorer.score_momentum(indicators)
        volatility_score, volatility_reason = CompositeScorer.score_volatility(
            indicators, price
        )
        rsi_score, rsi_reason = CompositeScorer.score_rsi(indicators)

        weighted = (
            weights.weight_trend * trend_score
            + weights.weight_momentum * momentum_score
            + weights.weight_volatility * volatility_score
            + weights.weight_rsi * rsi_score
        )
        composite = _clamp(weighted)

        breakdown = {
            "trend": {
                "score": round(trend_score, 3),
                "weight": weights.weight_trend,
                "reason": trend_reason,
            },
            "momentum": {
                "score": round(momentum_score, 3),
                "weight": weights.weight_momentum,
                "reason": momentum_reason,
            },
            "volatility": {
                "score": round(volatility_score, 3),
                "weight": weights.weight_volatility,
                "reason": volatility_reason,
            },
            "rsi": {
                "score": round(rsi_score, 3),
                "weight": weights.weight_rsi,
                "reason": rsi_reason,
            },
            "composite": round(composite, 3),
        }
        return composite, breakdown
