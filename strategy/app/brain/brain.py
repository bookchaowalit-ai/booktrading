"""
Brain — Main Aggregator
========================
Combines signals from all 3 layers into a unified GridDirective per symbol.

Each layer produces its own signal with:
  - spacing_multiplier (how wide/tight the grid should be)
  - center_offset_pct (shift grid up/down)
  - pause_buys / pause_sells (halt orders)
  - confidence (0-1 how much to trust this layer)

The aggregator uses confidence-weighted averaging to produce the final directive.
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

from app.brain.signals.technical import TechnicalSignal, TechnicalSignalProvider
from app.brain.signals.funding_rate import FundingSignal, FundingRateProvider
from app.brain.signals.sentiment import SentimentSignal, SentimentProvider
from app.brain.signals.circuit_breaker import CircuitBreaker

logger = logging.getLogger("brain")


@dataclass
class GridDirective:
    """Final Brain output — consumed by the grid bot each tick."""
    symbol: str
    spacing_multiplier: float = 1.0      # Multiply base grid spacing by this
    center_offset_pct: float = 0.0       # Shift grid center by this %
    pause_buys: bool = False
    pause_sells: bool = False
    confidence: float = 0.0              # Overall confidence 0-1
    technical: Optional[dict] = None     # Layer 1 details
    funding: Optional[dict] = None       # Layer 2 details
    sentiment: Optional[dict] = None     # Layer 3 details
    updated_at: float = 0.0              # Unix timestamp


class Brain:
    """
    The Brain intelligence layer.

    Usage:
        brain = Brain()
        await brain.start()

        # Each grid tick:
        directive = await brain.get_directive("BTCUSDT")
        # Use directive.spacing_multiplier, directive.pause_buys, etc.

        await brain.stop()
    """

    def __init__(self):
        self.technical = TechnicalSignalProvider()
        self.funding = FundingRateProvider()
        # CryptoPanic auth token from env (optional — sentiment layer disabled if not set)
        cryptopanic_token = os.getenv("CRYPTOPANIC_AUTH_TOKEN")
        self.sentiment = SentimentProvider(auth_token=cryptopanic_token)

        # Layer 4: Flash Crash Circuit Breaker
        cb_threshold = float(os.getenv("CIRCUIT_BREAKER_THRESHOLD_PCT", "3.0"))
        cb_cooldown = float(os.getenv("CIRCUIT_BREAKER_COOLDOWN_SEC", "300"))
        self.circuit_breaker = CircuitBreaker(
            drop_threshold_pct=cb_threshold,
            cooldown_sec=cb_cooldown,
        )

        # Cache directives per symbol (refresh every BRAIN_REFRESH_SEC)
        self._directives: Dict[str, GridDirective] = {}
        self._last_refresh: Dict[str, float] = {}
        self._refresh_interval = 120  # Refresh signals every 2 minutes
        self._running = False

    async def start(self):
        """Initialize the Brain."""
        self._running = True
        logger.info(
            "Brain started (technical + funding + sentiment + circuit_breaker[%.1f%%/%.0fs])",
            self.circuit_breaker.drop_threshold_pct,
            self.circuit_breaker.cooldown_sec,
        )

    async def stop(self):
        """Shut down the Brain and close HTTP clients."""
        self._running = False
        await self.technical.close()
        await self.funding.close()
        await self.sentiment.close()
        logger.info("Brain stopped")

    async def get_directive(self, symbol: str, current_price: float = 0.0) -> GridDirective:
        """
        Get the current GridDirective for a symbol.
        Refreshes signals if cache is stale (> refresh_interval old).

        Args:
            symbol: Trading pair symbol
            current_price: Current market price (used for circuit breaker detection)
        """
        # Update circuit breaker with current price (Layer 4 — runs every tick)
        if current_price > 0:
            cb_triggered = self.circuit_breaker.update_price(symbol, current_price)
            if cb_triggered:
                # Circuit breaker triggered — return emergency directive
                return GridDirective(
                    symbol=symbol,
                    spacing_multiplier=2.0,  # Widen grid significantly
                    center_offset_pct=-1.0,  # Shift center down
                    pause_buys=True,         # Halt all buys
                    pause_sells=False,       # Allow sells (exit positions)
                    confidence=1.0,          # Maximum confidence
                    updated_at=time.time(),
                )

        now = time.time()
        last = self._last_refresh.get(symbol, 0)

        if now - last > self._refresh_interval:
            await self._refresh(symbol)
            self._last_refresh[symbol] = now

        return self._directives.get(symbol, GridDirective(symbol=symbol))

    async def _refresh(self, symbol: str):
        """Fetch fresh signals from all 3 layers and compute the directive."""
        try:
            # Run all 3 layers in parallel
            tech_signal, fund_signal, sent_signal = await asyncio.gather(
                self.technical.compute_signal(symbol),
                self.funding.compute_signal(symbol),
                self.sentiment.compute_signal(symbol),
                return_exceptions=True,
            )

            # Handle exceptions gracefully
            if isinstance(tech_signal, Exception):
                logger.warning("Technical signal failed for %s: %s", symbol, tech_signal)
                tech_signal = TechnicalSignal(symbol=symbol)
            if isinstance(fund_signal, Exception):
                logger.warning("Funding signal failed for %s: %s", symbol, fund_signal)
                fund_signal = FundingSignal(symbol=symbol)
            if isinstance(sent_signal, Exception):
                logger.warning("Sentiment signal failed for %s: %s", symbol, sent_signal)
                sent_signal = SentimentSignal(symbol=symbol)

            # ── Confidence-weighted aggregation ───────────────────────────
            directive = self._aggregate(symbol, tech_signal, fund_signal, sent_signal)
            self._directives[symbol] = directive

            logger.info(
                "[Brain %s] spacing=%.2fx offset=%.1f%% pause_b=%s pause_s=%s conf=%.2f",
                symbol,
                directive.spacing_multiplier,
                directive.center_offset_pct * 100,
                directive.pause_buys,
                directive.pause_sells,
                directive.confidence,
            )

        except Exception as e:
            logger.error("Brain refresh failed for %s: %s", symbol, e, exc_info=True)

    def _aggregate(
        self,
        symbol: str,
        tech: TechnicalSignal,
        fund: FundingSignal,
        sent: SentimentSignal,
    ) -> GridDirective:
        """
        Combine 3 layer signals using confidence-weighted averaging.

        Rules:
        - spacing_multiplier: weighted average by confidence
        - center_offset_pct: weighted average by confidence
        - pause_buys/pause_sells: ANY layer can trigger a pause (safety first)
        - overall confidence: max of individual confidences
        """
        directive = GridDirective(symbol=symbol, updated_at=time.time())

        # Collect layer outputs and their confidences
        layers = [
            (tech.spacing_multiplier, tech.center_offset_pct, tech.pause_buys, tech.pause_sells, tech.confidence),
            (fund.spacing_multiplier, fund.center_offset_pct, fund.pause_buys, fund.pause_sells, fund.confidence),
            (sent.spacing_multiplier, sent.center_offset_pct, sent.pause_buys, sent.pause_sells, sent.confidence),
        ]

        # Weighted average for spacing and offset
        total_weight = 0.0
        weighted_spacing = 0.0
        weighted_offset = 0.0
        max_confidence = 0.0

        for spacing, offset, pause_b, pause_s, conf in layers:
            # Minimum confidence threshold to include a layer
            if conf >= 0.1:
                weighted_spacing += spacing * conf
                weighted_offset += offset * conf
                total_weight += conf
                max_confidence = max(max_confidence, conf)

        if total_weight > 0:
            directive.spacing_multiplier = round(weighted_spacing / total_weight, 3)
            directive.center_offset_pct = round(weighted_offset / total_weight, 4)
        else:
            # No layers had confidence — use defaults
            directive.spacing_multiplier = 1.0
            directive.center_offset_pct = 0.0

        # Safety: ANY layer can trigger pause (conservative)
        directive.pause_buys = any(pause_b for _, _, pause_b, _, _ in layers)
        directive.pause_sells = any(pause_s for _, _, _, pause_s, _ in layers)

        # Overall confidence = max of individual (not average — one strong signal is enough)
        directive.confidence = round(max_confidence, 2)

        # Attach layer details for observability
        directive.technical = {
            "atr_pct": tech.atr_pct,
            "rsi": tech.rsi,
            "bb_position": tech.bb_position,
            "ema_trend": tech.ema_trend,
            "spacing_multiplier": tech.spacing_multiplier,
            "pause_buys": tech.pause_buys,
            "pause_sells": tech.pause_sells,
            "center_offset_pct": tech.center_offset_pct,
            "confidence": tech.confidence,
        }
        directive.funding = {
            "funding_rate": fund.funding_rate,
            "open_interest": fund.open_interest,
            "spacing_multiplier": fund.spacing_multiplier,
            "pause_buys": fund.pause_buys,
            "pause_sells": fund.pause_sells,
            "center_offset_pct": fund.center_offset_pct,
            "confidence": fund.confidence,
        }
        directive.sentiment = {
            "sentiment_score": sent.sentiment_score,
            "news_count": sent.news_count,
            "bullish_votes": sent.bullish_votes,
            "bearish_votes": sent.bearish_votes,
            "spacing_multiplier": sent.spacing_multiplier,
            "pause_buys": sent.pause_buys,
            "pause_sells": sent.pause_sells,
            "center_offset_pct": sent.center_offset_pct,
            "confidence": sent.confidence,
        }

        return directive

    def get_all_directives(self) -> Dict[str, dict]:
        """Get all cached directives (for API endpoint)."""
        return {
            symbol: {
                "spacing_multiplier": d.spacing_multiplier,
                "center_offset_pct": d.center_offset_pct,
                "pause_buys": d.pause_buys,
                "pause_sells": d.pause_sells,
                "confidence": d.confidence,
                "technical": d.technical,
                "funding": d.funding,
                "sentiment": d.sentiment,
                "updated_at": d.updated_at,
            }
            for symbol, d in self._directives.items()
        }


# ── Singleton ─────────────────────────────────────────────────────────────────

_brain: Optional[Brain] = None


def get_brain() -> Brain:
    global _brain
    if _brain is None:
        _brain = Brain()
    return _brain
