"""
Macro market data source — Forex & Commodities.
Uses free APIs: exchangerate-api.com for forex, and metals.live / open exchange rates for commodities.
"""
import logging
from typing import List, Optional, Dict, Any
import httpx
from datetime import datetime
import uuid

from app.market_intel.sources.base import BaseSource
from app.market_intel.models import (
    MarketQuote, MarketOpportunity, MarketSummary, MarketType,
    OpportunityType, Severity,
)

logger = logging.getLogger(__name__)

# Free forex API (no key needed, 1500 req/month)
FOREX_API_URL = "https://api.exchangerate-api.com/v4/latest"
# Alternative forex (free, no key)
FOREX_FREE_URL = "https://open.er-api.com/v6/latest"

# Commodities — use free public endpoints
GOLD_API_URL = "https://api.metals.live/v1/spot/gold"
SILVER_API_URL = "https://api.metals.live/v1/spot/silver"
# Fallback: use Yahoo Finance for commodity ETFs
COMMODITY_SYMBOLS = {
    "GOLD": "GC=F",       # Gold futures
    "SILVER": "SI=F",     # Silver futures
    "OIL_WTI": "CL=F",    # WTI Crude Oil
    "OIL_BRENT": "BZ=F",  # Brent Crude
    "NATGAS": "NG=F",     # Natural Gas
    "COPPER": "HG=F",     # Copper
}


class MacroSource(BaseSource):
    """Forex & commodity market data."""

    def __init__(self):
        self._name = "macro"

    @property
    def source_name(self) -> str:
        return self._name

    @property
    def market_type(self) -> MarketType:
        # Macro covers both forex and commodity — return forex as primary
        return MarketType.FOREX

    async def fetch_quotes(self, symbols: Optional[List[str]] = None) -> List[MarketQuote]:
        """Fetch forex and commodity quotes.

        Default forex pairs: USD/THB, EUR/USD, GBP/USD, USD/JPY, USD/CNY
        Default commodities: Gold, Silver, Oil WTI
        """
        quotes = []
        quotes.extend(await self._fetch_forex(symbols))
        quotes.extend(await self._fetch_commodities(symbols))
        return quotes

    async def _fetch_forex(self, symbols: Optional[List[str]] = None) -> List[MarketQuote]:
        """Fetch forex rates from exchange rate API."""
        quotes = []
        forex_pairs = ["THB", "EUR", "GBP", "JPY", "CNY", "AUD", "SGD", "HKD"]

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{FOREX_FREE_URL}/USD")
                resp.raise_for_status()
                data = resp.json()

                rates = data.get("rates", {})
                base = data.get("base", "USD")
                last_update = data.get("time_last_update_utc", "")

                for pair in forex_pairs:
                    if pair not in rates:
                        continue
                    rate = rates[pair]
                    if rate <= 0:
                        continue

                    # Invert for convention (e.g., USD/THB = THB per 1 USD)
                    symbol = f"USD{pair}"
                    quotes.append(MarketQuote(
                        symbol=symbol,
                        market_type=MarketType.FOREX,
                        source=self.source_name,
                        price=rate,
                        metadata={
                            "base": base,
                            "last_update": last_update,
                            "all_rates_snapshot": {k: v for k, v in list(rates.items())[:10]},
                        },
                    ))

                # Add cross rates: EUR/JPY, GBP/JPY
                if "EUR" in rates and "JPY" in rates:
                    eur_jpy = rates["JPY"] / rates["EUR"] if rates["EUR"] else 0
                    if eur_jpy > 0:
                        quotes.append(MarketQuote(
                            symbol="EURJPY",
                            market_type=MarketType.FOREX,
                            source=self.source_name,
                            price=round(eur_jpy, 4),
                            metadata={"cross_rate": True},
                        ))

        except Exception as e:
            logger.error(f"Failed to fetch forex: {e}")

        return quotes

    async def _fetch_commodities(self, symbols: Optional[List[str]] = None) -> List[MarketQuote]:
        """Fetch commodity prices via metals.live + Yahoo Finance fallback."""
        quotes = []

        # 1) Try metals.live for gold/silver spot
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                for metal_name, api_url in [("GOLD", GOLD_API_URL), ("SILVER", SILVER_API_URL)]:
                    try:
                        resp = await client.get(api_url)
                        resp.raise_for_status()
                        data = resp.json()
                        if isinstance(data, list) and len(data) > 0:
                            price = float(data[0].get("price", 0))
                            if price > 0:
                                quotes.append(MarketQuote(
                                    symbol=metal_name,
                                    market_type=MarketType.COMMODITY,
                                    source=self.source_name,
                                    price=price,
                                    metadata={"source": "metals.live", "unit": "USD/oz"},
                                ))
                    except Exception as e:
                        logger.warning(f"metals.live {metal_name} failed: {e}")
        except Exception as e:
            logger.warning(f"metals.live bulk fetch failed: {e}")

        # 2) Fallback: Yahoo Finance commodity ETFs
        if len(quotes) < 3:
            try:
                yf_quotes = await self._fetch_commodity_yf()
                quotes.extend(yf_quotes)
            except Exception as e:
                logger.warning(f"Yahoo commodity fallback failed: {e}")

        return quotes

    async def _fetch_commodity_yf(self) -> List[MarketQuote]:
        """Fetch commodity prices via Yahoo Finance chart API."""
        quotes = []
        headers = {"User-Agent": "Mozilla/5.0"}

        async with httpx.AsyncClient(timeout=10.0) as client:
            for name, yf_symbol in COMMODITY_SYMBOLS.items():
                try:
                    resp = await client.get(
                        f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_symbol}",
                        params={"interval": "1d", "range": "2d"},
                        headers=headers,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    results = data.get("chart", {}).get("result", [])
                    if not results:
                        continue

                    meta = results[0].get("meta", {})
                    price = meta.get("regularMarketPrice", 0)
                    prev = meta.get("chartPreviousClose", 0) or meta.get("previousClose", 0)
                    change = price - prev if prev else 0
                    change_pct = (change / prev * 100) if prev else 0

                    if price > 0:
                        quotes.append(MarketQuote(
                            symbol=name,
                            market_type=MarketType.COMMODITY,
                            source=self.source_name,
                            price=price,
                            change_24h=round(change, 4),
                            change_pct_24h=round(change_pct, 2),
                            metadata={
                                "yf_symbol": yf_symbol,
                                "source": "yahoo_finance",
                                "exchange": meta.get("exchangeName", ""),
                                "currency": meta.get("currency", "USD"),
                            },
                        ))
                except Exception as e:
                    logger.warning(f"Yahoo commodity {name} failed: {e}")

        return quotes

    async def scan_opportunities(self, quotes: List[MarketQuote]) -> List[MarketOpportunity]:
        """Scan for macro opportunities: large forex moves, commodity shocks."""
        opportunities = []

        for q in quotes:
            change_pct = q.change_pct_24h or 0

            # Large commodity move (> 2% daily)
            if q.market_type == MarketType.COMMODITY and abs(change_pct) > 2.0:
                direction = "surging" if change_pct > 0 else "dropping"
                severity = Severity.HIGH if abs(change_pct) > 4 else Severity.MEDIUM
                opportunities.append(MarketOpportunity(
                    opportunity_id=str(uuid.uuid4()),
                    symbol=q.symbol,
                    market_type=q.market_type,
                    source=self.source_name,
                    opportunity_type=OpportunityType.MOMENTUM,
                    severity=severity,
                    title=f"Commodity {direction}: {q.symbol} ({change_pct:+.1f}%)",
                    description=f"{q.symbol} is {direction} at ${q.price:.2f}. "
                                f"Potential inflation signal or supply shock.",
                    current_price=q.price,
                    confidence=0.5,
                    metadata={"change_pct": change_pct},
                ))

            # Forex: flag large rate changes (rare but significant)
            if q.market_type == MarketType.FOREX and abs(change_pct) > 1.0:
                opportunities.append(MarketOpportunity(
                    opportunity_id=str(uuid.uuid4()),
                    symbol=q.symbol,
                    market_type=MarketType.FOREX,
                    source=self.source_name,
                    opportunity_type=OpportunityType.MOMENTUM,
                    severity=Severity.HIGH,
                    title=f"FX move: {q.symbol} ({change_pct:+.1f}%)",
                    description=f"{q.symbol} moved {change_pct:+.1f}%. Unusual for forex — check macro events.",
                    current_price=q.price,
                    confidence=0.55,
                    metadata={"change_pct": change_pct},
                ))

        return opportunities

    async def get_forex_summary(self) -> Dict[str, Any]:
        """Quick forex overview."""
        quotes = await self._fetch_forex()
        return {
            "base": "USD",
            "rates": {q.symbol: q.price for q in quotes},
            "count": len(quotes),
            "timestamp": datetime.utcnow().isoformat(),
        }
