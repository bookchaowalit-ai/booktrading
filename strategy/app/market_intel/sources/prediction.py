"""
Prediction market data source — Polymarket.
Fetches events/markets and detects mispricings and arbitrage.
"""
import logging
from typing import List, Optional, Dict, Any
import httpx
from datetime import datetime
import uuid
import json

from app.market_intel.sources.base import BaseSource
from app.market_intel.models import (
    MarketQuote, MarketOpportunity, MarketSummary, MarketType,
    OpportunityType, Severity,
)

logger = logging.getLogger(__name__)

GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"


class PredictionSource(BaseSource):
    """Prediction market data from Polymarket."""

    def __init__(self, gamma_api: str = GAMMA_API, clob_api: str = CLOB_API):
        self.gamma_api = gamma_api
        self.clob_api = clob_api

    @property
    def source_name(self) -> str:
        return "polymarket"

    @property
    def market_type(self) -> MarketType:
        return MarketType.PREDICTION

    async def fetch_quotes(self, symbols: Optional[List[str]] = None) -> List[MarketQuote]:
        """Fetch prediction market prices from Polymarket."""
        quotes = []
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Fetch active events
                params = {"limit": 50, "active": "true", "closed": "false"}
                resp = await client.get(f"{self.gamma_api}/events", params=params)
                resp.raise_for_status()
                events = resp.json()

                for event in events:
                    for market in event.get("markets", []):
                        condition_id = market.get("conditionId", "")
                        question = market.get("question", "")
                        volume = float(market.get("volume", 0) or 0)
                        liquidity = float(market.get("liquidity", 0) or 0)

                        # Parse outcome prices
                        outcome_prices = market.get("outcomePrices", "[]")
                        if isinstance(outcome_prices, str):
                            try:
                                outcome_prices = json.loads(outcome_prices)
                            except Exception:
                                outcome_prices = []

                        yes_price = float(outcome_prices[0]) if len(outcome_prices) > 0 else 0.5
                        no_price = float(outcome_prices[1]) if len(outcome_prices) > 1 else 0.5

                        quotes.append(MarketQuote(
                            symbol=condition_id or question[:20],
                            market_type=MarketType.PREDICTION,
                            source=self.source_name,
                            price=yes_price,
                            volume_24h=volume,
                            metadata={
                                "question": question,
                                "event_title": event.get("title", ""),
                                "no_price": no_price,
                                "liquidity": liquidity,
                                "resolved": market.get("resolved", False),
                                "total_price": round(yes_price + no_price, 4),
                            },
                        ))
        except Exception as e:
            logger.error(f"Failed to fetch prediction quotes: {e}")

        return quotes

    async def scan_opportunities(self, quotes: List[MarketQuote]) -> List[MarketOpportunity]:
        """Scan for prediction market opportunities: mispricings, low liquidity."""
        opportunities = []

        for q in quotes:
            yes_price = q.price
            no_price = q.metadata.get("no_price", 0)
            total = yes_price + no_price
            liquidity = q.metadata.get("liquidity", 0)
            volume = q.volume_24h or 0

            # Mispricing: Yes + No should equal 1.0
            if total > 0 and abs(total - 1.0) > 0.02:
                deviation = abs(total - 1.0)
                if total > 1.0:
                    opp_type = OpportunityType.ARBITRAGE
                    desc = f"Yes({yes_price:.3f}) + No({no_price:.3f}) = {total:.3f}. Sell both for {deviation:.3f} profit."
                else:
                    opp_type = OpportunityType.MISPRICING
                    desc = f"Yes({yes_price:.3f}) + No({no_price:.3f}) = {total:.3f}. Buy both for {deviation:.3f} profit."

                severity = Severity.HIGH if deviation > 0.05 else Severity.MEDIUM
                opportunities.append(MarketOpportunity(
                    opportunity_id=str(uuid.uuid4()),
                    symbol=q.symbol,
                    market_type=MarketType.PREDICTION,
                    source=self.source_name,
                    opportunity_type=opp_type,
                    severity=severity,
                    title=f"Mispricing: {q.metadata.get('question', '')[:50]}",
                    description=desc,
                    current_price=yes_price,
                    target_price=0.5,
                    confidence=min(deviation * 10, 1.0),
                    metadata={
                        "yes_price": yes_price,
                        "no_price": no_price,
                        "total": total,
                        "deviation": deviation,
                        "question": q.metadata.get("question", ""),
                    },
                ))

            # Low liquidity
            if volume < 1000 and liquidity < 500:
                opportunities.append(MarketOpportunity(
                    opportunity_id=str(uuid.uuid4()),
                    symbol=q.symbol,
                    market_type=MarketType.PREDICTION,
                    source=self.source_name,
                    opportunity_type=OpportunityType.LIQUIDITY_GAP,
                    severity=Severity.MEDIUM if volume < 100 else Severity.LOW,
                    title=f"Low liquidity: {q.metadata.get('question', '')[:40]}",
                    description=f"Volume=${volume:.0f}, Liquidity=${liquidity:.0f}. Large orders will move price.",
                    current_price=yes_price,
                    confidence=0.5,
                    metadata={"volume": volume, "liquidity": liquidity},
                ))

        return opportunities

    async def search_markets(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search Polymarket by keyword."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.gamma_api}/public-search",
                    params={"query": query, "limit": limit},
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"Failed to search markets: {e}")
            return []
