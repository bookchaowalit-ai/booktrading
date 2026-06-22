"""
Polymarket market analyzer — detects opportunities and inefficiencies.
Analyzes prices, volumes, spreads, and orderbook depth to find mispricings.
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import statistics

from app.polymarket.models import (
    PolymarketMarket,
    PolymarketEvent,
    Orderbook,
    MarketOpportunity,
)
from app.polymarket.client import PolymarketClient

logger = logging.getLogger(__name__)


class PolymarketAnalyzer:
    """
    Analyzes Polymarket data to identify trading opportunities.
    
    Detection strategies:
    1. Mispricing — Yes+No prices don't sum to ~1.0 (arbitrage)
    2. Wide spread — Large bid-ask spread = liquidity opportunity
    3. Volume spike — Unusual volume relative to market average
    4. Stale price — Price hasn't moved despite new information
    5. Low liquidity — Thin orderbook = potential for price impact
    """

    def __init__(self, client: PolymarketClient):
        self.client = client
        self._cached_events: List[PolymarketEvent] = []
        self._last_fetch: Optional[datetime] = None

    async def refresh_markets(self, limit: int = 50) -> List[PolymarketEvent]:
        """Fetch fresh market data from Polymarket."""
        events = await self.client.get_events(limit=limit, active=True, closed=False)
        self._cached_events = events
        self._last_fetch = datetime.utcnow()
        logger.info(f"Refreshed {len(events)} Polymarket events")
        return events

    async def scan_opportunities(
        self,
        events: Optional[List[PolymarketEvent]] = None,
        min_confidence: float = 0.3,
    ) -> List[MarketOpportunity]:
        """
        Scan all markets for opportunities.
        Returns sorted by severity (high > medium > low) then confidence.
        """
        if events is None:
            events = self._cached_events
            if not events:
                events = await self.refresh_markets()

        opportunities: List[MarketOpportunity] = []

        for event in events:
            for market in event.markets:
                # Check 1: Mispricing (Yes + No != 1.0)
                opp = self._check_mispricing(market, event.title)
                if opp and opp.confidence >= min_confidence:
                    opportunities.append(opp)

                # Check 2: Wide spread (needs orderbook fetch)
                if market.enable_order_book:
                    opp = await self._check_spread(market, event.title)
                    if opp and opp.confidence >= min_confidence:
                        opportunities.append(opp)

                # Check 3: Low liquidity
                opp = self._check_liquidity(market, event.title)
                if opp and opp.confidence >= min_confidence:
                    opportunities.append(opp)

        # Sort: high severity first, then by confidence
        severity_order = {"high": 0, "medium": 1, "low": 2}
        opportunities.sort(key=lambda x: (severity_order.get(x.severity, 3), -x.confidence))

        return opportunities

    def _check_mispricing(self, market: PolymarketMarket, event_title: str) -> Optional[MarketOpportunity]:
        """
        Detect mispricing: Yes + No should sum to ~1.0.
        If sum > 1.0 + threshold, both are overpriced (sell both).
        If sum < 1.0 - threshold, both are underpriced (buy both).
        """
        if len(market.outcomes) < 2:
            return None

        yes_price = market.yes_price
        no_price = market.no_price
        total = yes_price + no_price

        if total == 0:
            return None

        deviation = abs(total - 1.0)

        # Threshold: >2% deviation is noteworthy
        if deviation < 0.02:
            return None

        if total > 1.0:
            # Overpriced — sell both for guaranteed profit
            severity = "high" if deviation > 0.05 else "medium"
            return MarketOpportunity(
                market_id=market.condition_id,
                question=market.question,
                opportunity_type="arbitrage",
                severity=severity,
                description=f"Yes({yes_price:.3f}) + No({no_price:.3f}) = {total:.3f}. Sell both for {deviation:.3f} profit per share.",
                current_price=yes_price,
                estimated_fair_value=0.5,
                confidence=min(deviation * 10, 1.0),  # Higher deviation = higher confidence
                metadata={
                    "yes_price": yes_price,
                    "no_price": no_price,
                    "total": total,
                    "deviation": deviation,
                    "event_title": event_title,
                },
            )
        else:
            # Underpriced — buy both
            severity = "high" if deviation > 0.05 else "medium"
            return MarketOpportunity(
                market_id=market.condition_id,
                question=market.question,
                opportunity_type="mispricing",
                severity=severity,
                description=f"Yes({yes_price:.3f}) + No({no_price:.3f}) = {total:.3f}. Buy both for {deviation:.3f} guaranteed profit.",
                current_price=yes_price,
                estimated_fair_value=0.5,
                confidence=min(deviation * 10, 1.0),
                metadata={
                    "yes_price": yes_price,
                    "no_price": no_price,
                    "total": total,
                    "deviation": deviation,
                    "event_title": event_title,
                },
            )

    async def _check_spread(self, market: PolymarketMarket, event_title: str) -> Optional[MarketOpportunity]:
        """
        Detect wide bid-ask spread — indicates illiquidity or stale market.
        Spread > 5% is noteworthy.
        """
        # We'd need token_id to fetch orderbook, which requires more data
        # For now, use the price difference as a proxy
        if len(market.outcomes) < 2:
            return None

        yes_price = market.yes_price
        no_price = market.no_price

        # If prices are very close to 0.50/0.50, market is uncertain — wide spreads likely
        if 0.45 <= yes_price <= 0.55:
            # Uncertain market — likely has wide spreads
            return MarketOpportunity(
                market_id=market.condition_id,
                question=market.question,
                opportunity_type="liquidity_gap",
                severity="low",
                description=f"Market is near 50/50 ({yes_price:.2f}/{no_price:.2f}), likely has wide spreads. Good for limit orders.",
                current_price=yes_price,
                confidence=0.3,
                metadata={
                    "yes_price": yes_price,
                    "no_price": no_price,
                    "event_title": event_title,
                },
            )

        return None

    def _check_liquidity(self, market: PolymarketMarket, event_title: str) -> Optional[MarketOpportunity]:
        """
        Detect low liquidity markets — potential for price impact.
        Volume < $1000 or liquidity < $500 is considered low.
        """
        volume = market.volume or 0
        liquidity = market.liquidity or 0

        if volume < 1000 and liquidity < 500:
            return MarketOpportunity(
                market_id=market.condition_id,
                question=market.question,
                opportunity_type="liquidity_gap",
                severity="medium" if volume < 100 else "low",
                description=f"Low liquidity: volume=${volume:.0f}, liquidity=${liquidity:.0f}. Large orders will move price.",
                current_price=market.yes_price,
                confidence=0.5,
                metadata={
                    "volume": volume,
                    "liquidity": liquidity,
                    "event_title": event_title,
                },
            )

        return None

    async def get_market_summary(self, events: Optional[List[PolymarketEvent]] = None) -> Dict[str, Any]:
        """Get summary statistics across all markets."""
        if events is None:
            events = self._cached_events

        total_markets = sum(len(e.markets) for e in events)
        total_volume = sum(m.volume or 0 for e in events for m in e.markets)
        total_liquidity = sum(m.liquidity or 0 for e in events for m in e.markets)

        # Count resolved vs active
        active_markets = [m for e in events for m in e.markets if not m.resolved]
        resolved_markets = [m for e in events for m in e.markets if m.resolved]

        # Price distribution
        yes_prices = [m.yes_price for e in events for m in e.markets if not m.resolved]
        if yes_prices:
            avg_yes = statistics.mean(yes_prices)
            high_confidence = sum(1 for p in yes_prices if p > 0.8 or p < 0.2)
            uncertain = sum(1 for p in yes_prices if 0.4 <= p <= 0.6)
        else:
            avg_yes = 0
            high_confidence = 0
            uncertain = 0

        return {
            "total_events": len(events),
            "total_markets": total_markets,
            "active_markets": len(active_markets),
            "resolved_markets": len(resolved_markets),
            "total_volume_usdc": round(total_volume, 2),
            "total_liquidity_usdc": round(total_liquidity, 2),
            "avg_yes_price": round(avg_yes, 3),
            "high_confidence_markets": high_confidence,
            "uncertain_markets": uncertain,
            "last_updated": self._last_fetch.isoformat() if self._last_fetch else None,
        }

    async def search_and_analyze(self, query: str) -> Dict[str, Any]:
        """Search markets by keyword and analyze results."""
        markets = await self.client.search_markets(query)
        if not markets:
            return {"query": query, "markets_found": 0, "opportunities": []}

        # Create pseudo-events for analysis
        pseudo_events = [
            PolymarketEvent(
                event_id=f"search_{i}",
                title=m.question,
                slug=query.lower().replace(" ", "-"),
                markets=[m],
            )
            for i, m in enumerate(markets)
        ]

        opportunities = await self.scan_opportunities(pseudo_events)

        return {
            "query": query,
            "markets_found": len(markets),
            "markets": [
                {
                    "question": m.question,
                    "yes_price": m.yes_price,
                    "no_price": m.no_price,
                    "volume": m.volume,
                    "liquidity": m.liquidity,
                }
                for m in markets
            ],
            "opportunities": [opp.model_dump() for opp in opportunities],
        }


# Singleton
_analyzer_instance: Optional[PolymarketAnalyzer] = None


def get_analyzer() -> PolymarketAnalyzer:
    global _analyzer_instance
    if _analyzer_instance is None:
        from app.polymarket.client import get_polymarket_client
        _analyzer_instance = PolymarketAnalyzer(get_polymarket_client())
    return _analyzer_instance
