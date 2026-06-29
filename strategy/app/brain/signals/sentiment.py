"""
Layer 3: Sentiment Signals
============================
Uses the Fear & Greed Index (alternative.me) for market-wide sentiment.
Free, no API key required. Updates daily.

Fear & Greed Index → Grid Modulation:
- Extreme Fear (0-20)  → widen grid, pause buys (crash protection)
- Fear (21-40)         → slightly widen grid, bearish offset
- Neutral (41-60)      → no modulation
- Greed (61-80)        → tighten buys, bullish offset
- Extreme Greed (81-100) → tighten grid, pause sells (euphoria protection)
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger("brain.sentiment")

FEAR_GREED_URL = "https://api.alternative.me/fng/?limit=1"

# Cache: F&G updates daily, so cache for 6 hours
_CACHE_TTL = 6 * 3600  # 6 hours in seconds


@dataclass
class SentimentSignal:
    """Output from the sentiment layer."""
    symbol: str
    bullish_votes: int = 0
    bearish_votes: int = 0
    neutral_votes: int = 0
    sentiment_score: Optional[float] = None   # -1.0 (bearish) to +1.0 (bullish)
    news_count: int = 0

    # Grid modulation outputs
    spacing_multiplier: float = 1.0
    pause_buys: bool = False
    pause_sells: bool = False
    center_offset_pct: float = 0.0
    confidence: float = 0.0


class SentimentProvider:
    """
    Fetches Fear & Greed Index and produces market-wide grid signals.

    The Fear & Greed Index is a composite of:
    - Volatility (25%)
    - Market momentum (25%)
    - Social media (15%)
    - Surveys (15%)
    - Bitcoin dominance (10%)
    - Google Trends (10%)

    Value ranges:
    - 0-24: Extreme Fear
    - 25-49: Fear
    - 50: Neutral
    - 51-74: Greed
    - 75-100: Extreme Greed
    """

    def __init__(self, auth_token: Optional[str] = None):
        self._http: Optional[httpx.AsyncClient] = None
        self._auth_token = auth_token  # kept for backward compat, unused
        # Cache for market-wide F&G value
        self._cached_value: Optional[int] = None
        self._cached_classification: str = ""
        self._cached_at: float = 0.0

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=10.0)
        return self._http

    async def _fetch_fear_greed(self) -> tuple[Optional[int], str]:
        """Fetch Fear & Greed Index value. Returns (value, classification)."""
        # Check cache first
        now = time.time()
        if self._cached_value is not None and (now - self._cached_at) < _CACHE_TTL:
            return self._cached_value, self._cached_classification

        client = await self._get_client()
        try:
            resp = await client.get(FEAR_GREED_URL)
            if resp.status_code != 200:
                logger.warning("Fear & Greed fetch failed: HTTP %d", resp.status_code)
                return self._cached_value, self._cached_classification

            data = resp.json()
            items = data.get("data", [])
            if not items:
                logger.warning("Fear & Greed: empty data")
                return self._cached_value, self._cached_classification

            value = int(items[0]["value"])
            classification = items[0].get("value_classification", "Neutral")

            # Update cache
            self._cached_value = value
            self._cached_classification = classification
            self._cached_at = now

            return value, classification

        except Exception as e:
            logger.warning("Fear & Greed fetch error: %s", e)
            return self._cached_value, self._cached_classification

    async def compute_signal(self, symbol: str) -> SentimentSignal:
        """Compute sentiment signal for a symbol using market-wide F&G."""
        signal = SentimentSignal(symbol=symbol)

        try:
            fng_value, classification = await self._fetch_fear_greed()

            if fng_value is None:
                logger.debug("No F&G data available for %s", symbol)
                return signal

            # Convert F&G (0-100) to sentiment score (-1.0 to +1.0)
            # 0 → -1.0 (extreme fear), 50 → 0.0 (neutral), 100 → +1.0 (extreme greed)
            score = (fng_value - 50) / 50.0
            signal.sentiment_score = round(score, 3)
            signal.news_count = 1  # F&G counts as 1 data point

            # ── Fear & Greed → Grid Modulation ──────────────────────────
            # High confidence since F&G is a reliable composite indicator
            base_confidence = 0.6

            if fng_value <= 20:
                # ── EXTREME FEAR: Crash protection ──
                # Widen grid significantly (more volatile market)
                signal.spacing_multiplier = 1.5
                # Pause buys — don't catch falling knives
                signal.pause_buys = True
                # Shift grid down slightly (expect lower prices)
                signal.center_offset_pct = -0.003
                signal.confidence = 0.85
                logger.info(
                    "[Sentiment %s] F&G=%d (%s) → EXTREME FEAR: widen 1.5x, pause buys, offset -0.3%%",
                    symbol, fng_value, classification
                )

            elif fng_value <= 40:
                # ── FEAR: Cautious ──
                # Slightly widen grid
                signal.spacing_multiplier = 1.2
                # Bearish offset
                signal.center_offset_pct = -0.001
                signal.confidence = base_confidence
                logger.info(
                    "[Sentiment %s] F&G=%d (%s) → FEAR: widen 1.2x, offset -0.1%%",
                    symbol, fng_value, classification
                )

            elif fng_value <= 60:
                # ── NEUTRAL: No modulation ──
                signal.spacing_multiplier = 1.0
                signal.center_offset_pct = 0.0
                signal.confidence = 0.3  # Low confidence = don't override technical
                logger.info(
                    "[Sentiment %s] F&G=%d (%s) → NEUTRAL: no modulation",
                    symbol, fng_value, classification
                )

            elif fng_value <= 80:
                # ── GREED: Bullish momentum ──
                # Tighten buys to catch more upside
                signal.spacing_multiplier = 0.9
                # Bullish offset
                signal.center_offset_pct = 0.001
                signal.confidence = base_confidence
                logger.info(
                    "[Sentiment %s] F&G=%d (%s) → GREED: tighten 0.9x, offset +0.1%%",
                    symbol, fng_value, classification
                )

            else:
                # ── EXTREME GREED: Euphoria protection ──
                # Tighten grid (more fills in bullish momentum)
                signal.spacing_multiplier = 0.85
                # Pause sells — don't short a euphoric market
                signal.pause_sells = True
                # Shift grid up
                signal.center_offset_pct = 0.003
                signal.confidence = 0.85
                logger.info(
                    "[Sentiment %s] F&G=%d (%s) → EXTREME GREED: tighten 0.85x, pause sells, offset +0.3%%",
                    symbol, fng_value, classification
                )

        except Exception as e:
            logger.warning("Sentiment error for %s: %s", symbol, e)

        return signal

    async def close(self):
        if self._http and not self._http.is_closed:
            await self._http.aclose()
