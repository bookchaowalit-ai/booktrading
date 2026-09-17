"""Stable, provider-neutral models for World Markets research."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class WorldMarket:
    """A normalized binary market observed from World Markets.

    The model deliberately keeps the provider payload in ``raw``.  Normalized
    fields are used for filtering and ranking only; no field implies a fill or
    a profitable trade.
    """

    ticker: str
    event_ticker: str = ""
    series_ticker: str = ""
    title: str = ""
    question: str = ""
    category: str = ""
    tags: tuple[str, ...] = ()
    status: str = "unknown"
    yes_bid: float | None = None
    yes_ask: float | None = None
    no_bid: float | None = None
    no_ask: float | None = None
    yes_ask_size: float | None = None
    no_ask_size: float | None = None
    yes_price: float | None = None
    no_price: float | None = None
    last_price: float | None = None
    volume: float | None = None
    liquidity: float | None = None
    open_time: str | None = None
    close_time: str | None = None
    strike_date: str | None = None
    resolution_source: str | None = None
    updated_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def yes_mid(self) -> float | None:
        """Return the YES midpoint when a two-sided quote is available."""

        if self.yes_bid is not None and self.yes_ask is not None:
            return (self.yes_bid + self.yes_ask) / 2
        if self.yes_price is not None:
            return self.yes_price
        return self.last_price

    @property
    def no_mid(self) -> float | None:
        """Return the NO midpoint when a two-sided quote is available."""

        if self.no_bid is not None and self.no_ask is not None:
            return (self.no_bid + self.no_ask) / 2
        return self.no_price

    @property
    def yes_spread(self) -> float | None:
        if self.yes_bid is None or self.yes_ask is None:
            return None
        return max(0.0, self.yes_ask - self.yes_bid)

    @property
    def no_spread(self) -> float | None:
        if self.no_bid is None or self.no_ask is None:
            return None
        return max(0.0, self.no_ask - self.no_bid)

    @property
    def buy_both_total(self) -> float | None:
        """Gross cost of buying YES and NO at the displayed asks."""

        if self.yes_ask is None or self.no_ask is None:
            return None
        return self.yes_ask + self.no_ask

    @property
    def sell_both_total(self) -> float | None:
        """Gross proceeds from selling YES and NO at the displayed bids."""

        if self.yes_bid is None or self.no_bid is None:
            return None
        return self.yes_bid + self.no_bid

    @property
    def validation_errors(self) -> tuple[str, ...]:
        """Return deterministic quote and metric quality errors."""

        errors: list[str] = []
        for name in ("yes_bid", "yes_ask", "no_bid", "no_ask", "yes_price", "no_price", "last_price"):
            value = getattr(self, name)
            if value is not None and (not math.isfinite(value) or not 0.0 <= value <= 1.0):
                errors.append(f"{name}_outside_binary_price_range")
        for side in ("yes", "no"):
            bid = getattr(self, f"{side}_bid")
            ask = getattr(self, f"{side}_ask")
            if bid is not None and ask is not None and bid > ask:
                errors.append(f"{side}_bid_above_ask")
        for name in ("volume", "liquidity", "yes_ask_size", "no_ask_size"):
            value = getattr(self, name)
            if value is not None and (not math.isfinite(value) or value < 0.0):
                errors.append(f"{name}_negative_or_non_finite")
        return tuple(errors)

    @property
    def resolution_errors(self) -> tuple[str, ...]:
        """Return the minimum context needed for a safe research candidate."""

        errors: list[str] = []
        if not (self.question or self.title):
            errors.append("missing_question_or_title")
        if not self.resolution_source:
            errors.append("missing_resolution_source")
        if not (self.strike_date or self.close_time):
            errors.append("missing_strike_or_close_time")
        return tuple(errors)


@dataclass(frozen=True, slots=True)
class WorldEventPage:
    """One paginated response from the World events endpoint."""

    events: tuple[dict[str, Any], ...]
    cursor: str | None
    raw: Any
    raw_bytes: bytes
    endpoint: str
    request_params: dict[str, str]


@dataclass(frozen=True, slots=True)
class WorldPriceTick:
    """A normalized read-only price update from the World WebSocket."""

    ticker: str
    yes_bid: float | None = None
    yes_ask: float | None = None
    no_bid: float | None = None
    no_ask: float | None = None
    last_price: float | None = None
    timestamp: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def yes_mid(self) -> float | None:
        if self.yes_bid is not None and self.yes_ask is not None:
            return (self.yes_bid + self.yes_ask) / 2
        return self.last_price

    @property
    def no_mid(self) -> float | None:
        if self.no_bid is not None and self.no_ask is not None:
            return (self.no_bid + self.no_ask) / 2
        return None


@dataclass(frozen=True, slots=True)
class WorldPaperSignal:
    """A ranked research signal; it is never an order instruction."""

    ticker: str
    signal_type: str
    side: str
    rank_score: float
    data_confidence: float
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)
