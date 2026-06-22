"""
Polymarket API client for fetching market data.
Supports Gamma API (events/markets), CLOB API (orderbooks/prices), and Data API (positions/trades).
All market data endpoints are public (no auth required).
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import httpx

from app.polymarket.models import (
    PolymarketEvent,
    PolymarketMarket,
    PolymarketOutcome,
    Orderbook,
    OrderbookLevel,
    PriceHistory,
)

logger = logging.getLogger(__name__)

# Default API endpoints
GAMMA_API_BASE = "https://gamma-api.polymarket.com"
CLOB_API_BASE = "https://clob.polymarket.com"
DATA_API_BASE = "https://data-api.polymarket.com"


class PolymarketClient:
    """
    Async client for Polymarket APIs.
    - Gamma API: Events, markets, tags, search (public)
    - CLOB API: Orderbook, prices, spreads, price history (public reads)
    - Data API: Positions, trades, activity, open interest (public)
    """

    def __init__(
        self,
        gamma_base: str = GAMMA_API_BASE,
        clob_base: str = CLOB_API_BASE,
        data_base: str = DATA_API_BASE,
        timeout: float = 15.0,
    ):
        self.gamma_base = gamma_base
        self.clob_base = clob_base
        self.data_base = data_base
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ── Gamma API (Events & Markets) ──────────────────────────────────────────

    async def get_events(
        self,
        limit: int = 20,
        offset: int = 0,
        active: bool = True,
        closed: bool = False,
        tag: Optional[str] = None,
    ) -> List[PolymarketEvent]:
        """Fetch events from Gamma API."""
        client = await self._get_client()
        params = {"limit": limit, "offset": offset, "active": str(active).lower(), "closed": str(closed).lower()}
        if tag:
            params["tag"] = tag

        try:
            resp = await client.get(f"{self.gamma_base}/events", params=params)
            resp.raise_for_status()
            data = resp.json()
            return [self._parse_event(e) for e in data]
        except Exception as e:
            logger.error(f"Failed to fetch events: {e}")
            return []

    async def get_event(self, event_id: str) -> Optional[PolymarketEvent]:
        """Fetch single event by ID."""
        client = await self._get_client()
        try:
            resp = await client.get(f"{self.gamma_base}/events/{event_id}")
            resp.raise_for_status()
            return self._parse_event(resp.json())
        except Exception as e:
            logger.error(f"Failed to fetch event {event_id}: {e}")
            return None

    async def get_markets(
        self,
        limit: int = 50,
        offset: int = 0,
        active: bool = True,
        closed: bool = False,
    ) -> List[PolymarketMarket]:
        """Fetch markets from Gamma API."""
        client = await self._get_client()
        params = {"limit": limit, "offset": offset, "active": str(active).lower(), "closed": str(closed).lower()}

        try:
            resp = await client.get(f"{self.gamma_base}/markets", params=params)
            resp.raise_for_status()
            data = resp.json()
            return [self._parse_market(m) for m in data]
        except Exception as e:
            logger.error(f"Failed to fetch markets: {e}")
            return []

    async def search_markets(self, query: str, limit: int = 20) -> List[PolymarketMarket]:
        """Search markets by keyword via Gamma public search."""
        client = await self._get_client()
        try:
            resp = await client.get(
                f"{self.gamma_base}/public-search",
                params={"query": query, "limit": limit},
            )
            resp.raise_for_status()
            data = resp.json()
            return [self._parse_market(m) for m in data]
        except Exception as e:
            logger.error(f"Failed to search markets: {e}")
            return []

    async def get_tags(self) -> List[Dict[str, Any]]:
        """Fetch available market tags/categories."""
        client = await self._get_client()
        try:
            resp = await client.get(f"{self.gamma_base}/tags")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Failed to fetch tags: {e}")
            return []

    # ── CLOB API (Orderbook & Prices) ─────────────────────────────────────────

    async def get_orderbook(self, token_id: str) -> Optional[Orderbook]:
        """Fetch orderbook for a specific outcome token."""
        client = await self._get_client()
        try:
            resp = await client.get(f"{self.clob_base}/book", params={"token_id": token_id})
            resp.raise_for_status()
            data = resp.json()
            return self._parse_orderbook(token_id, data)
        except Exception as e:
            logger.error(f"Failed to fetch orderbook for {token_id}: {e}")
            return None

    async def get_price(self, token_id: str) -> Optional[float]:
        """Get current price for a token."""
        client = await self._get_client()
        try:
            resp = await client.get(f"{self.clob_base}/price", params={"token_id": token_id})
            resp.raise_for_status()
            data = resp.json()
            return float(data.get("price", 0))
        except Exception as e:
            logger.error(f"Failed to fetch price for {token_id}: {e}")
            return None

    async def get_prices(self, token_ids: List[str]) -> Dict[str, float]:
        """Get current prices for multiple tokens."""
        client = await self._get_client()
        try:
            resp = await client.get(
                f"{self.clob_base}/prices",
                params={"token_ids": ",".join(token_ids)},
            )
            resp.raise_for_status()
            data = resp.json()
            return {k: float(v) for k, v in data.items()}
        except Exception as e:
            logger.error(f"Failed to fetch prices: {e}")
            return {}

    async def get_midpoint(self, token_id: str) -> Optional[float]:
        """Get midpoint price (avg of best bid and ask)."""
        client = await self._get_client()
        try:
            resp = await client.get(f"{self.clob_base}/midpoint", params={"token_id": token_id})
            resp.raise_for_status()
            data = resp.json()
            return float(data.get("mid", 0))
        except Exception as e:
            logger.error(f"Failed to fetch midpoint for {token_id}: {e}")
            return None

    async def get_spread(self, token_id: str) -> Optional[Dict[str, float]]:
        """Get current spread for a token."""
        client = await self._get_client()
        try:
            resp = await client.get(f"{self.clob_base}/spread", params={"token_id": token_id})
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Failed to fetch spread for {token_id}: {e}")
            return None

    async def get_price_history(
        self,
        token_id: str,
        interval: str = "1h",
        fidelity: int = 60,
    ) -> Optional[PriceHistory]:
        """Fetch price history for a token."""
        client = await self._get_client()
        try:
            resp = await client.get(
                f"{self.clob_base}/prices-history",
                params={"market": token_id, "interval": interval, "fidelity": fidelity},
            )
            resp.raise_for_status()
            data = resp.json()
            return PriceHistory(
                market=token_id,
                outcome="unknown",
                prices=data.get("history", []),
            )
        except Exception as e:
            logger.error(f"Failed to fetch price history for {token_id}: {e}")
            return None

    # ── Data API (Positions & Activity) ───────────────────────────────────────

    async def get_open_interest(self, market: str) -> Optional[float]:
        """Get open interest for a market."""
        client = await self._get_client()
        try:
            resp = await client.get(f"{self.data_base}/oi", params={"market": market})
            resp.raise_for_status()
            data = resp.json()
            return float(data.get("openInterest", 0))
        except Exception as e:
            logger.error(f"Failed to fetch OI for {market}: {e}")
            return None

    async def get_trades(self, market: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent trades for a market."""
        client = await self._get_client()
        try:
            resp = await client.get(
                f"{self.data_base}/trades",
                params={"market": market, "limit": limit},
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Failed to fetch trades for {market}: {e}")
            return []

    async def get_holders(self, market: str) -> List[Dict[str, Any]]:
        """Get top holders for a market."""
        client = await self._get_client()
        try:
            resp = await client.get(f"{self.data_base}/holders", params={"market": market})
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Failed to fetch holders for {market}: {e}")
            return []

    # ── Parsing Helpers ───────────────────────────────────────────────────────

    def _parse_event(self, data: Dict[str, Any]) -> PolymarketEvent:
        """Parse raw event JSON into PolymarketEvent."""
        markets = []
        for m in data.get("markets", []):
            markets.append(self._parse_market(m))

        return PolymarketEvent(
            event_id=str(data.get("id", "")),
            title=data.get("title", ""),
            description=data.get("description"),
            slug=data.get("slug", ""),
            start_date=self._parse_date(data.get("startDate")),
            end_date=self._parse_date(data.get("endDate")),
            markets=markets,
            tags=[t.get("label", "") for t in data.get("tags", [])],
            series=data.get("series"),
            closed=data.get("closed", False),
        )

    def _parse_market(self, data: Dict[str, Any]) -> PolymarketMarket:
        """Parse raw market JSON into PolymarketMarket."""
        outcomes = []
        outcome_prices = data.get("outcomePrices", "")
        outcome_names = data.get("outcomes", "")

        # outcomePrices can be a JSON string like "[\"0.65\", \"0.35\"]"
        if isinstance(outcome_prices, str):
            import json
            try:
                outcome_prices = json.loads(outcome_prices)
            except Exception:
                outcome_prices = []

        if isinstance(outcome_names, str):
            import json
            try:
                outcome_names = json.loads(outcome_names)
            except Exception:
                outcome_names = []

        if outcome_names and outcome_prices:
            for name, price in zip(outcome_names, outcome_prices):
                outcomes.append(PolymarketOutcome(name=name, price=float(price)))
        else:
            # Default Yes/No
            outcomes = [
                PolymarketOutcome(name="Yes", price=0.5),
                PolymarketOutcome(name="No", price=0.5),
            ]

        return PolymarketMarket(
            condition_id=data.get("conditionId", data.get("condition_id", "")),
            question=data.get("question", ""),
            description=data.get("description"),
            outcomes=outcomes,
            volume=float(data.get("volume", 0) or 0),
            liquidity=float(data.get("liquidity", 0) or 0),
            start_date=self._parse_date(data.get("startDate")),
            end_date=self._parse_date(data.get("endDate")),
            resolved=data.get("resolved", False),
            enable_order_book=data.get("enableOrderBook", True),
            tags=[t.get("label", "") if isinstance(t, dict) else str(t) for t in data.get("tags", [])],
        )

    def _parse_orderbook(self, token_id: str, data: Dict[str, Any]) -> Orderbook:
        """Parse raw orderbook JSON."""
        bids = [OrderbookLevel(price=float(b.get("price", 0)), size=float(b.get("size", 0))) for b in data.get("bids", [])]
        asks = [OrderbookLevel(price=float(a.get("price", 0)), size=float(a.get("size", 0))) for a in data.get("asks", [])]
        return Orderbook(
            market=token_id,
            outcome="unknown",
            bids=sorted(bids, key=lambda x: x.price, reverse=True),
            asks=sorted(asks, key=lambda x: x.price),
        )

    def _parse_date(self, val) -> Optional[datetime]:
        """Parse date string to datetime."""
        if not val:
            return None
        try:
            if isinstance(val, (int, float)):
                return datetime.fromtimestamp(val)
            return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
        except Exception:
            return None


# Singleton client instance
_client_instance: Optional[PolymarketClient] = None


def get_polymarket_client() -> PolymarketClient:
    global _client_instance
    if _client_instance is None:
        _client_instance = PolymarketClient()
    return _client_instance
