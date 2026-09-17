"""World Markets source for the unified, read-only market scanner."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import TYPE_CHECKING

from app.market_intel.models import (
    MarketOpportunity,
    MarketQuote,
    MarketType,
    OpportunityType,
    Severity,
)
from app.market_intel.sources.base import BaseSource
from app.world.client import WorldApiError, WorldMarketsClient, WorldMarketsConfig, parse_world_market
from app.world.models import WorldMarket
from app.world.scanner import WorldPaperScanner, WorldScannerConfig

if TYPE_CHECKING:
    from app.world.landing import WorldLandingWriter


class WorldSource(BaseSource):
    """Fetch World events, optionally land raw responses, and rank paper signals."""

    def __init__(
        self,
        *,
        config: WorldMarketsConfig | None = None,
        client: WorldMarketsClient | None = None,
        landing_writer: WorldLandingWriter | None = None,
        scanner: WorldPaperScanner | None = None,
        page_limit: int = 200,
        max_pages: int = 5,
        category: str | None = None,
        tags: Sequence[str] | None = None,
        use_env_landing: bool = True,
        require_landing: bool = True,
    ) -> None:
        from app.world.landing import WorldLandingWriter

        self.config = config or (client.config if client is not None else WorldMarketsConfig.from_env())
        self.client = client or WorldMarketsClient(self.config)
        self.landing_writer = (
            landing_writer
            if landing_writer is not None
            else (WorldLandingWriter.from_env() if use_env_landing else None)
        )
        self.paper_scanner = scanner or WorldPaperScanner(WorldScannerConfig())
        self.page_limit = page_limit
        self.max_pages = max_pages
        self.category = category
        self.tags = tuple(tags or ())
        self.require_landing = require_landing
        self._markets: dict[str, WorldMarket] = {}

    @property
    def source_name(self) -> str:
        return "world_xyz"

    @property
    def market_type(self) -> MarketType:
        return MarketType.PREDICTION

    async def fetch_markets(self, symbols: list[str] | None = None) -> list[WorldMarket]:
        if self.require_landing and self.landing_writer is None:
            raise WorldApiError(
                "World Markets landing is not configured; set WORLD_MARKETS_LANDING_DIR or use explicit ephemeral mode"
            )
        wanted = {symbol.strip() for symbol in (symbols or []) if symbol and symbol.strip()}
        markets: list[WorldMarket] = []
        seen: set[str] = set()
        async for page in self.client.iter_event_pages(
            limit=self.page_limit,
            max_pages=self.max_pages,
            category=self.category,
            tags=self.tags,
        ):
            if self.landing_writer is not None:
                raw_bytes = page.raw_bytes or (
                    json.dumps(page.raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                ).encode("utf-8")
                self.landing_writer.write_snapshot(
                    raw_bytes,
                    endpoint=page.endpoint,
                    request_params=page.request_params,
                )
            for event in page.events:
                nested = event.get("markets")
                if isinstance(nested, dict):
                    nested = [nested]
                if not isinstance(nested, list):
                    nested = [event] if event.get("ticker") or event.get("market_ticker") else []
                for payload in nested:
                    if not isinstance(payload, dict):
                        continue
                    market = parse_world_market(payload, event=event)
                    if not market.ticker or market.ticker in seen or (wanted and market.ticker not in wanted):
                        continue
                    seen.add(market.ticker)
                    markets.append(market)
        self._markets = {market.ticker: market for market in markets}
        return markets

    async def fetch_quotes(self, symbols: list[str] | None = None) -> list[MarketQuote]:
        return [self._quote(market) for market in await self.fetch_markets(symbols)]

    async def scan_opportunities(self, quotes: list[MarketQuote]) -> list[MarketOpportunity]:
        allowed = {quote.symbol for quote in quotes}
        markets = [market for ticker, market in self._markets.items() if not allowed or ticker in allowed]
        signals = self.paper_scanner.scan(markets)
        opportunities: list[MarketOpportunity] = []
        for signal in signals:
            market = self._markets.get(signal.ticker)
            if market is None:
                continue
            gap = float(signal.metadata.get("gross_gap") or 0)
            severity = Severity.HIGH if gap >= 0.08 and signal.data_confidence >= 0.75 else Severity.MEDIUM
            opportunity_id = hashlib.sha256(f"{signal.ticker}:{signal.signal_type}".encode()).hexdigest()[:24]
            opportunities.append(
                MarketOpportunity(
                    opportunity_id=f"world-{opportunity_id}",
                    symbol=signal.ticker,
                    market_type=MarketType.PREDICTION,
                    source=self.source_name,
                    opportunity_type=OpportunityType.MISPRICING,
                    severity=severity,
                    title=f"World paper watch: {(market.question or market.title)[:70]}",
                    description=f"{signal.reason} No order is created.",
                    current_price=market.yes_mid if market.yes_mid is not None else 0.5,
                    confidence=signal.data_confidence,
                    metadata={
                        **signal.metadata,
                        "signal_type": signal.signal_type,
                        "side": signal.side,
                        "rank_score": signal.rank_score,
                        "confidence_kind": "data_quality_not_probability",
                        "validation_errors": list(market.validation_errors),
                        "resolution_errors": list(market.resolution_errors),
                    },
                )
            )
        return opportunities

    async def close(self) -> None:
        await self.client.close()

    @staticmethod
    def _quote(market: WorldMarket) -> MarketQuote:
        yes_mid = market.yes_mid
        return MarketQuote(
            symbol=market.ticker,
            market_type=MarketType.PREDICTION,
            source="world_xyz",
            price=yes_mid if yes_mid is not None else 0.5,
            bid=market.yes_bid,
            ask=market.yes_ask,
            volume_24h=market.volume,
            metadata={
                "provider": "world_xyz",
                "event_ticker": market.event_ticker,
                "series_ticker": market.series_ticker,
                "title": market.title,
                "question": market.question,
                "category": market.category,
                "tags": list(market.tags),
                "status": market.status,
                "yes_bid": market.yes_bid,
                "yes_ask": market.yes_ask,
                "no_bid": market.no_bid,
                "no_ask": market.no_ask,
                "yes_ask_size": market.yes_ask_size,
                "no_ask_size": market.no_ask_size,
                "no_price": market.no_price,
                "liquidity": market.liquidity,
                "close_time": market.close_time,
                "strike_date": market.strike_date,
                "resolution_source": market.resolution_source,
                "updated_at": market.updated_at.isoformat() if market.updated_at else None,
                "price_available": yes_mid is not None,
                "price_imputed": yes_mid is None,
                "validation_errors": list(market.validation_errors),
                "resolution_errors": list(market.resolution_errors),
                "paper_only": True,
                "execution_enabled": False,
            },
        )
