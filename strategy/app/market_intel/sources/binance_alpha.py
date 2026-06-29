"""
Binance Alpha scanner — finds early-stage tokens on Binance Alpha.
These are tokens highlighted by Binance BEFORE they potentially list on main exchange.

Uses Binance public endpoints (no auth needed for market data).
"""
import logging
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime

import httpx

from app.market_intel.sources.base import BaseSource
from app.market_intel.models import (
    MarketQuote, MarketOpportunity, MarketSummary, MarketType,
    OpportunityType, Severity,
)

logger = logging.getLogger(__name__)

# Binance Alpha endpoints (public)
BINANCE_ALPHA_URL = "https://www.binance.com/bapi/composite/v1/public/market/category"
BINANCE_WALLET_API = "https://wallet-api.binance.com"

# CoinGecko Binance Alpha category
COINGECKO_ALPHA_URL = "https://api.coingecko.com/api/v3/coins/categories"
COINGECKO_ALPHA_CATEGORY = "binance-alpha-spotlight"


class BinanceAlphaSource(BaseSource):
    """
    Scans Binance Alpha for early-stage tokens.
    These tokens are vetted by Binance but not yet on main exchange.
    """

    def __init__(self):
        self._name = "binance_alpha"

    @property
    def source_name(self) -> str:
        return self._name

    @property
    def market_type(self) -> MarketType:
        return MarketType.CRYPTO  # Still crypto, just early-stage

    async def fetch_quotes(self, symbols: Optional[List[str]] = None) -> List[MarketQuote]:
        """
        Fetch Binance Alpha tokens via CoinGecko category API.
        CoinGecko tracks Binance Alpha Spotlight tokens.
        """
        quotes = []

        # 1. Try CoinGecko category API
        try:
            cg_quotes = await self._fetch_coingecko_alpha()
            quotes.extend(cg_quotes)
        except Exception as e:
            logger.warning(f"CoinGecko Binance Alpha fetch failed: {e}")

        # 2. Try direct Binance wallet API
        try:
            binance_quotes = await self._fetch_binance_wallet_alpha()
            quotes.extend(binance_quotes)
        except Exception as e:
            logger.warning(f"Binance wallet Alpha fetch failed: {e}")

        return quotes

    async def _fetch_coingecko_alpha(self) -> List[MarketQuote]:
        """Fetch Binance Alpha tokens from CoinGecko."""
        quotes = []

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Get category data (includes top tokens in category)
                resp = await client.get(
                    f"{COINGECKO_ALPHA_URL}/{COINGECKO_ALPHA_CATEGORY}",
                    params={
                        "order": "market_cap_desc",
                        "per_page": 20,
                        "page": 1,
                        "sparkline": "false",
                    },
                )
                resp.raise_for_status()
                data = resp.json()

                if isinstance(data, list):
                    for token in data:
                        name = token.get("name", "Unknown")
                        symbol = token.get("symbol", "???").upper()
                        price = token.get("current_price", 0) or 0
                        change_24h = token.get("price_change_percentage_24h", 0) or 0
                        market_cap = token.get("market_cap", 0) or 0
                        volume_24h = token.get("total_volume", 0) or 0
                        ath = token.get("ath", 0) or 0
                        ath_change = token.get("ath_change_percentage", 0) or 0

                        quotes.append(MarketQuote(
                            symbol=f"ALPHA_{symbol}",
                            market_type=MarketType.CRYPTO,
                            source="coingecko_alpha",
                            price=price,
                            change_24h=price * (change_24h / 100) if change_24h else 0,
                            change_pct_24h=change_24h,
                            volume_24h=volume_24h,
                            metadata={
                                "name": name,
                                "market_cap": market_cap,
                                "ath": ath,
                                "ath_change_pct": ath_change,
                                "category": "binance_alpha",
                                "coingecko_id": token.get("id", ""),
                            },
                        ))
        except Exception as e:
            logger.error(f"CoinGecko Alpha fetch error: {e}")

        return quotes

    async def _fetch_binance_wallet_alpha(self) -> List[MarketQuote]:
        """Fetch from Binance Wallet API directly."""
        quotes = []

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Binance Alpha listing endpoint
                resp = await client.get(
                    "https://www.binance.com/bapi/composite/v1/public/market/category/symbols",
                    params={"category": "alpha"},
                    headers={"User-Agent": "Mozilla/5.0"},
                )

                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("data", {}).get("symbols", [])

                    for item in items[:15]:
                        name = item.get("name", "Unknown")
                        symbol = item.get("symbol", "???")
                        price = float(item.get("price", 0) or 0)
                        change_pct = float(item.get("priceChange24h", 0) or 0)

                        if price > 0:
                            quotes.append(MarketQuote(
                                symbol=f"ALPHA_{symbol}",
                                market_type=MarketType.CRYPTO,
                                source="binance_wallet",
                                price=price,
                                change_pct_24h=change_pct,
                                metadata={
                                    "name": name,
                                    "category": "binance_alpha",
                                    "source_url": f"https://www.binance.com/en/price/{symbol.lower()}",
                                },
                            ))
        except Exception as e:
            logger.debug(f"Binance wallet API error: {e}")

        return quotes

    async def scan_opportunities(self, quotes: List[MarketQuote]) -> List[MarketOpportunity]:
        """
        Scan for Binance Alpha opportunities:
        - Tokens far from ATH (potential upside if listed on main exchange)
        - High volume tokens gaining traction
        - New additions to Alpha list
        """
        opportunities = []

        for q in quotes:
            meta = q.metadata
            ath_change = meta.get("ath_change_pct", 0)
            volume = q.volume_24h or 0
            change_pct = q.change_pct_24h or 0

            # 1. Token far from ATH (>50% down) — potential recovery if listed
            if ath_change < -50 and q.price > 0:
                opportunities.append(MarketOpportunity(
                    opportunity_id=str(uuid.uuid4()),
                    symbol=q.symbol,
                    market_type=MarketType.CRYPTO,
                    source=self.source_name,
                    opportunity_type=OpportunityType.EARLY_ALPHA,
                    severity=Severity.MEDIUM,
                    title=f"Alpha opportunity: {meta.get('name', q.symbol)} ({ath_change:.0f}% from ATH)",
                    description=(
                        f"Binance Alpha token\n"
                        f"Current: ${q.price:.6f}\n"
                        f"ATH: ${meta.get('ath', 0):.6f}\n"
                        f"Down {ath_change:.0f}% from peak\n"
                        f"Potential upside if listed on Binance main"
                    ),
                    current_price=q.price,
                    target_price=meta.get("ath", q.price * 2),
                    confidence=0.45,
                    metadata=meta,
                ))

            # 2. High volume + positive momentum
            if volume > 100000 and change_pct > 5:
                opportunities.append(MarketOpportunity(
                    opportunity_id=str(uuid.uuid4()),
                    symbol=q.symbol,
                    market_type=MarketType.CRYPTO,
                    source=self.source_name,
                    opportunity_type=OpportunityType.MOMENTUM,
                    severity=Severity.HIGH if change_pct > 15 else Severity.MEDIUM,
                    title=f"Alpha momentum: {meta.get('name', q.symbol)} ({change_pct:+.1f}%)",
                    description=(
                        f"High volume Binance Alpha token\n"
                        f"24h Volume: ${volume:,.0f}\n"
                        f"Price: ${q.price:.6f}"
                    ),
                    current_price=q.price,
                    confidence=0.5,
                    metadata=meta,
                ))

        return opportunities[:15]

    async def get_summary(self, quotes: List[MarketQuote]) -> MarketSummary:
        """Summary of Binance Alpha tokens."""
        total_mcap = sum(q.metadata.get("market_cap", 0) for q in quotes)

        return MarketSummary(
            market_type=MarketType.CRYPTO,
            total_instruments=len(quotes),
            active_instruments=len([q for q in quotes if (q.volume_24h or 0) > 0]),
            total_volume_usd=sum(q.volume_24h or 0 for q in quotes),
            top_movers=[
                {
                    "name": q.metadata.get("name", q.symbol),
                    "price": q.price,
                    "change_24h_pct": q.change_pct_24h,
                    "from_ath_pct": q.metadata.get("ath_change_pct", 0),
                }
                for q in sorted(quotes, key=lambda x: abs(x.change_pct_24h or 0), reverse=True)[:5]
            ],
            last_updated=datetime.utcnow(),
        )
