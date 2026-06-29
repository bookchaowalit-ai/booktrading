"""
Degen/Meme coin scanner — finds trending early-stage tokens via DexScreener API.
Focuses on Solana and BSC chains (low gas, high activity).

DexScreener API is FREE and requires no API key.
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

# DexScreener API (free, no key)
DEXSCREENER_BASE = "https://api.dexscreener.com"

# Chains to scan (low gas, high meme activity)
TARGET_CHAINS = ["solana", "bsc", "ethereum", "base", "arbitrum"]

# Filters for quality
MIN_LIQUIDITY_USD = 5000       # At least $5k liquidity
MIN_VOLUME_24H_USD = 10000     # At least $10k 24h volume
MIN_TXNS_24H = 50              # At least 50 transactions


class DegenSource(BaseSource):
    """
    Scans DexScreener for trending meme/degen tokens.
    Returns early-stage tokens with momentum signals.
    """

    def __init__(self):
        self._name = "degen"

    @property
    def source_name(self) -> str:
        return self._name

    @property
    def market_type(self) -> MarketType:
        return MarketType.DEGEN

    async def fetch_quotes(self, symbols: Optional[List[str]] = None) -> List[MarketQuote]:
        """
        Fetch trending tokens from DexScreener.
        Uses multiple endpoints to find early movers.
        """
        quotes = []

        # 1. Search for boosted/trending tokens
        try:
            boosted = await self._fetch_boosted_tokens()
            quotes.extend(boosted)
        except Exception as e:
            logger.warning(f"DexScreener boosted tokens failed: {e}")

        # 2. Search specific chains for new pairs
        for chain in TARGET_CHAINS[:2]:  # Limit to solana + bsc for speed
            try:
                chain_quotes = await self._fetch_chain_trending(chain)
                quotes.extend(chain_quotes)
            except Exception as e:
                logger.warning(f"DexScreener {chain} failed: {e}")

        # 3. Search for specific meme keywords
        try:
            meme_quotes = await self._search_meme_keywords()
            quotes.extend(meme_quotes)
        except Exception as e:
            logger.warning(f"Meme keyword search failed: {e}")

        return quotes

    async def _fetch_boosted_tokens(self) -> List[MarketQuote]:
        """Fetch tokens with DexScreener boosts (paid promotion = serious projects)."""
        quotes = []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{DEXSCREENER_BASE}/token-boosts/latest/v1")
                resp.raise_for_status()
                data = resp.json()

                if isinstance(data, list):
                    for item in data[:15]:
                        url = item.get("url", "")
                        chain = item.get("chainId", "unknown")
                        token_address = item.get("tokenAddress", "")
                        description = item.get("description", "")[:100]

                        # Fetch pair data for this token
                        if token_address:
                            pair_data = await self._fetch_pair_by_address(chain, token_address)
                            if pair_data:
                                quotes.append(self._pair_to_quote(pair_data))
        except Exception as e:
            logger.error(f"Boosted tokens fetch error: {e}")

        return quotes

    async def _fetch_pair_by_address(self, chain: str, address: str) -> Optional[Dict]:
        """Fetch pair data for a specific token address."""
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(f"{DEXSCREENER_BASE}/latest/dex/tokens/{address}")
                resp.raise_for_status()
                data = resp.json()
                pairs = data.get("pairs", [])
                if pairs:
                    # Return the pair with highest liquidity
                    return max(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))
        except Exception as e:
            logger.debug(f"Pair fetch failed for {address}: {e}")
        return None

    async def _fetch_chain_trending(self, chain: str) -> List[MarketQuote]:
        """Fetch new/trending pairs on a specific chain."""
        quotes = []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Search for high-volume pairs on this chain
                resp = await client.get(
                    f"{DEXSCREENER_BASE}/latest/dex/search",
                    params={"q": "trending"},
                )
                resp.raise_for_status()
                data = resp.json()

                pairs = data.get("pairs", [])
                for pair in pairs[:10]:
                    if pair.get("chainId") != chain:
                        continue

                    liquidity = float(pair.get("liquidity", {}).get("usd", 0) or 0)
                    volume_24h = float(pair.get("volume", {}).get("h24", 0) or 0)

                    # Filter for quality
                    if liquidity < MIN_LIQUIDITY_USD or volume_24h < MIN_VOLUME_24H_USD:
                        continue

                    quotes.append(self._pair_to_quote(pair))
        except Exception as e:
            logger.error(f"Chain trending fetch error ({chain}): {e}")

        return quotes

    async def _search_meme_keywords(self) -> List[MarketQuote]:
        """Search DexScreener for meme-related tokens."""
        quotes = []
        keywords = ["pepe", "doge", "shib", "cat", "moon", "elon"]

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                for keyword in keywords[:3]:  # Limit requests
                    try:
                        resp = await client.get(
                            f"{DEXSCREENER_BASE}/latest/dex/search",
                            params={"q": keyword},
                        )
                        resp.raise_for_status()
                        data = resp.json()

                        pairs = data.get("pairs", [])
                        for pair in pairs[:5]:
                            liquidity = float(pair.get("liquidity", {}).get("usd", 0) or 0)
                            volume_24h = float(pair.get("volume", {}).get("h24", 0) or 0)

                            if liquidity < MIN_LIQUIDITY_USD:
                                continue

                            quote = self._pair_to_quote(pair)
                            # Avoid duplicates
                            if not any(q.symbol == quote.symbol for q in quotes):
                                quotes.append(quote)
                    except Exception as e:
                        logger.debug(f"Keyword search failed for {keyword}: {e}")
        except Exception as e:
            logger.error(f"Meme keyword search error: {e}")

        return quotes

    def _pair_to_quote(self, pair: Dict) -> MarketQuote:
        """Convert DexScreener pair data to MarketQuote."""
        base_token = pair.get("baseToken", {})
        price_usd = float(pair.get("priceUsd", 0) or 0)
        change_24h = float(pair.get("priceChange", {}).get("h24", 0) or 0)
        volume_24h = float(pair.get("volume", {}).get("h24", 0) or 0)
        liquidity = float(pair.get("liquidity", {}).get("usd", 0) or 0)
        txns_24h = pair.get("txns", {}).get("h24", {})
        buys = txns_24h.get("buys", 0)
        sells = txns_24h.get("sells", 0)
        fdv = float(pair.get("fdv", 0) or 0)
        pair_created = pair.get("pairCreatedAt", 0)

        symbol = base_token.get("symbol", "UNKNOWN")
        chain = pair.get("chainId", "unknown")

        return MarketQuote(
            symbol=f"DEGEN_{symbol}",
            market_type=MarketType.DEGEN,
            source="dexscreener",
            price=price_usd,
            change_24h=price_usd * (change_24h / 100) if change_24h else 0,
            change_pct_24h=change_24h,
            volume_24h=volume_24h,
            metadata={
                "name": base_token.get("name", ""),
                "chain": chain,
                "pair_address": pair.get("pairAddress", ""),
                "dex": pair.get("dexId", ""),
                "liquidity_usd": liquidity,
                "fdv": fdv,
                "buys_24h": buys,
                "sells_24h": sells,
                "pair_age_ms": pair_created,
                "pair_url": pair.get("url", ""),
            },
        )

    async def scan_opportunities(self, quotes: List[MarketQuote]) -> List[MarketOpportunity]:
        """
        Scan for degen opportunities:
        - High momentum tokens (>20% in 24h)
        - New pairs with high volume (potential early entry)
        - Tokens with buy pressure (buys >> sells)
        """
        opportunities = []

        for q in quotes:
            meta = q.metadata
            change_pct = q.change_pct_24h or 0
            liquidity = meta.get("liquidity_usd", 0)
            volume = q.volume_24h or 0
            buys = meta.get("buys_24h", 0)
            sells = meta.get("sells_24h", 0)

            # 1. High momentum (>20% move)
            if abs(change_pct) > 20:
                direction = "pumping" if change_pct > 0 else "dumping"
                severity = Severity.HIGH if change_pct > 50 else Severity.MEDIUM
                opportunities.append(MarketOpportunity(
                    opportunity_id=str(uuid.uuid4()),
                    symbol=q.symbol,
                    market_type=MarketType.DEGEN,
                    source="dexscreener",
                    opportunity_type=OpportunityType.TRENDING_DEGEN,
                    severity=severity,
                    title=f"Degen {direction}: {meta.get('name', q.symbol)} ({change_pct:+.0f}%)",
                    description=(
                        f"Chain: {meta.get('chain', 'unknown')}\n"
                        f"Price: ${q.price:.8f}\n"
                        f"Liquidity: ${liquidity:,.0f}\n"
                        f"24h Volume: ${volume:,.0f}\n"
                        f"DEX: {meta.get('dex', 'unknown')}\n"
                        f"URL: {meta.get('pair_url', 'N/A')}"
                    ),
                    current_price=q.price,
                    confidence=0.4,  # Lower confidence for degen plays
                    metadata=meta,
                ))

            # 2. Buy pressure (buys > 2x sells)
            if sells > 0 and buys > sells * 2 and liquidity > 10000:
                ratio = buys / sells
                opportunities.append(MarketOpportunity(
                    opportunity_id=str(uuid.uuid4()),
                    symbol=q.symbol,
                    market_type=MarketType.DEGEN,
                    source="dexscreener",
                    opportunity_type=OpportunityType.VOLUME_SPIKE,
                    severity=Severity.MEDIUM,
                    title=f"Buy pressure: {meta.get('name', q.symbol)} ({ratio:.1f}x buys)",
                    description=(
                        f"Buys: {buys} | Sells: {sells}\n"
                        f"Chain: {meta.get('chain')}\n"
                        f"Liquidity: ${liquidity:,.0f}"
                    ),
                    current_price=q.price,
                    confidence=0.5,
                    metadata={**meta, "buy_sell_ratio": ratio},
                ))

        # Sort by severity then volume
        severity_order = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2}
        opportunities.sort(key=lambda o: (severity_order.get(o.severity, 3), -(o.metadata.get("liquidity_usd", 0))))
        return opportunities[:20]

    async def get_summary(self, quotes: List[MarketQuote]) -> MarketSummary:
        """Summary of degen market."""
        total_liq = sum(q.metadata.get("liquidity_usd", 0) for q in quotes)
        chains = {}
        for q in quotes:
            chain = q.metadata.get("chain", "unknown")
            chains[chain] = chains.get(chain, 0) + 1

        return MarketSummary(
            market_type=MarketType.DEGEN,
            total_instruments=len(quotes),
            active_instruments=len([q for q in quotes if (q.volume_24h or 0) > 0]),
            total_volume_usd=sum(q.volume_24h or 0 for q in quotes),
            top_movers=[
                {
                    "name": q.metadata.get("name", q.symbol),
                    "chain": q.metadata.get("chain"),
                    "price_usd": q.price,
                    "change_24h_pct": q.change_pct_24h,
                    "liquidity": q.metadata.get("liquidity_usd", 0),
                }
                for q in sorted(quotes, key=lambda x: abs(x.change_pct_24h or 0), reverse=True)[:5]
            ],
            last_updated=datetime.utcnow(),
        )
