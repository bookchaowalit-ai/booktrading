"""Deterministic World Markets paper-research ranking."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from app.world.models import WorldMarket, WorldPaperSignal


@dataclass(frozen=True, slots=True)
class WorldScannerConfig:
    """Conservative filters for research candidates, not trading rules."""

    min_liquidity: float = 500.0
    min_volume: float = 1_000.0
    min_complement_gap: float = 0.03
    max_leg_spread: float = 0.08
    allow_unknown_metrics: bool = False
    require_resolution_text: bool = True
    require_resolution_details: bool = True

    def __post_init__(self) -> None:
        if self.min_liquidity < 0 or self.min_volume < 0:
            raise ValueError("minimum liquidity and volume cannot be negative")
        if not 0 < self.min_complement_gap < 1:
            raise ValueError("min_complement_gap must be between 0 and 1")
        if not 0 < self.max_leg_spread < 1:
            raise ValueError("max_leg_spread must be between 0 and 1")


class WorldPaperScanner:
    """Find gross complement gaps while clearly marking them as review-only.

    A displayed YES+NO gap is not an arbitrage guarantee.  Fees, slippage,
    stale quotes, partial fills, settlement rules, and oracle risk are outside
    the ranking calculation and must be validated in a separate paper ledger.
    """

    def __init__(self, config: WorldScannerConfig | None = None) -> None:
        self.config = config or WorldScannerConfig()

    def scan(self, markets: Iterable[WorldMarket], *, now: datetime | None = None) -> list[WorldPaperSignal]:
        _now = now or datetime.now(UTC)
        signals: list[WorldPaperSignal] = []
        for market in markets:
            if not self.is_eligible(market):
                continue
            data_confidence = self._data_confidence(market)

            buy_total = market.buy_both_total
            if buy_total is not None:
                buy_gap = 1.0 - buy_total
                if buy_gap >= self.config.min_complement_gap:
                    signals.append(
                        self._signal(
                            market,
                            signal_type="gross_complement_underpricing",
                            side="BUY_BOTH_REVIEW",
                            gap=buy_gap,
                            data_confidence=data_confidence,
                            reason=(
                                f"Displayed YES ask + NO ask = {buy_total:.4f}; gross gap={buy_gap:.4f}. "
                                "Review only after fees, fillability, and settlement checks."
                            ),
                            evaluated_at=_now,
                        )
                    )

            sell_total = market.sell_both_total
            if sell_total is not None:
                sell_gap = sell_total - 1.0
                if sell_gap >= self.config.min_complement_gap:
                    signals.append(
                        self._signal(
                            market,
                            signal_type="gross_complement_overpricing",
                            side="SELL_BOTH_REVIEW",
                            gap=sell_gap,
                            data_confidence=data_confidence,
                            reason=(
                                f"Displayed YES bid + NO bid = {sell_total:.4f}; gross gap={sell_gap:.4f}. "
                                "Review only; no shorting or order placement is implemented."
                            ),
                            evaluated_at=_now,
                        )
                    )

            if buy_total is None and sell_total is None:
                yes_mid = market.yes_mid
                no_mid = market.no_mid
                if yes_mid is not None and no_mid is not None:
                    midpoint_gap = abs(yes_mid + no_mid - 1.0)
                    if midpoint_gap >= self.config.min_complement_gap:
                        direction = "UNDERPRICED_MID_REVIEW" if yes_mid + no_mid < 1 else "OVERPRICED_MID_REVIEW"
                        signals.append(
                            self._signal(
                                market,
                                signal_type="midpoint_complement_gap",
                                side=direction,
                                gap=midpoint_gap,
                                data_confidence=data_confidence,
                                reason=(
                                    f"YES midpoint + NO midpoint = {yes_mid + no_mid:.4f}; "
                                    "no executable two-sided edge is established."
                                ),
                                evaluated_at=_now,
                            )
                        )
        return sorted(signals, key=lambda signal: (-signal.rank_score, signal.ticker, signal.signal_type))

    def is_eligible(self, market: WorldMarket) -> bool:
        if market.status not in {"", "active", "open", "live", "trading"}:
            return False
        if not market.ticker or (self.config.require_resolution_text and not (market.question or market.title)):
            return False
        if market.validation_errors:
            return False
        if self.config.require_resolution_details and market.resolution_errors:
            return False
        if not self.config.allow_unknown_metrics and (market.liquidity is None or market.volume is None):
            return False
        if market.liquidity is not None and market.liquidity < self.config.min_liquidity:
            return False
        if market.volume is not None and market.volume < self.config.min_volume:
            return False
        yes_spread = market.yes_spread
        no_spread = market.no_spread
        if yes_spread is not None and yes_spread > self.config.max_leg_spread:
            return False
        return not (no_spread is not None and no_spread > self.config.max_leg_spread)

    @staticmethod
    def _data_confidence(market: WorldMarket) -> float:
        checks = (
            market.yes_bid is not None and market.yes_ask is not None,
            market.no_bid is not None and market.no_ask is not None,
            market.liquidity is not None,
            market.volume is not None,
            bool(market.question or market.title),
            bool(market.strike_date or market.close_time or market.resolution_source),
        )
        return round(
            sum((0.22, 0.22, 0.18, 0.14, 0.14, 0.10)[index] for index, present in enumerate(checks) if present), 3
        )

    @staticmethod
    def _signal(
        market: WorldMarket,
        *,
        signal_type: str,
        side: str,
        gap: float,
        data_confidence: float,
        reason: str,
        evaluated_at: datetime,
    ) -> WorldPaperSignal:
        rank_score = round(min(1.0, 0.35 + gap * 4 + data_confidence * 0.35), 3)
        return WorldPaperSignal(
            ticker=market.ticker,
            signal_type=signal_type,
            side=side,
            rank_score=rank_score,
            data_confidence=data_confidence,
            reason=reason,
            metadata={
                "question": market.question or market.title,
                "category": market.category,
                "tags": list(market.tags),
                "gross_gap": round(gap, 6),
                "yes_bid": market.yes_bid,
                "yes_ask": market.yes_ask,
                "no_bid": market.no_bid,
                "no_ask": market.no_ask,
                "yes_ask_size": market.yes_ask_size,
                "no_ask_size": market.no_ask_size,
                "liquidity": market.liquidity,
                "volume": market.volume,
                "resolution_source": market.resolution_source,
                "resolution_complete": not market.resolution_errors,
                "updated_at": market.updated_at.astimezone(UTC).isoformat() if market.updated_at else None,
                "evaluated_at": evaluated_at.astimezone(UTC).isoformat(),
                "paper_only": True,
                "execution_enabled": False,
            },
        )
