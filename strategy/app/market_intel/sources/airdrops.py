"""
Airdrop scanner — finds free crypto airdrops from public aggregators.
Zero capital required. Just time + wallet interactions.

Sources:
- Airdrops.io (public listing page)
- CoinMarketCap airdrops
- DeFi Llama airdrops (potential tokens without airdrop yet)
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

# Public airdrop aggregators
AIRDROPS_IO_URL = "https://airdrops.io"
COINMARKETCAP_AIRDROPS = "https://coinmarketcap.com/airdrop/"
DEFILLAMA_AIRDROPS = "https://airdrops.llama.fi/"

# Known high-potential airdrop tasks (manually curated + auto-refreshed)
# These are protocols that haven't launched tokens yet but are likely to
KNOWN_UPCOMING_AIRDROPS = [
    {
        "name": "LayerZero",
        "chain": "Multi-chain",
        "task": "Bridge assets via Stargate, use dApps on new chains",
        "estimated_value": "$500-5000",
        "difficulty": "Medium",
        "cost": "Gas fees only (~$5-20)",
        "url": "https://layerzero.network/",
    },
    {
        "name": "Base (Coinbase L2)",
        "chain": "Base",
        "task": "Use dApps on Base ecosystem (Aerodrome, Friend.tech)",
        "estimated_value": "$200-2000",
        "difficulty": "Easy",
        "cost": "Gas fees only (~$1-5)",
        "url": "https://base.org/",
    },
    {
        "name": "Scroll",
        "chain": "Scroll (ETH L2)",
        "task": "Bridge ETH, use DeFi on Scroll",
        "estimated_value": "$300-3000",
        "difficulty": "Medium",
        "cost": "Gas fees only (~$2-10)",
        "url": "https://scroll.io/",
    },
    {
        "name": "zkSync Era",
        "chain": "zkSync",
        "task": "Bridge + use ecosystem dApps",
        "estimated_value": "$200-1500",
        "difficulty": "Medium",
        "cost": "Gas fees only (~$3-15)",
        "url": "https://zksync.io/",
    },
    {
        "name": "Berachain",
        "chain": "Berachain",
        "task": "Testnet interactions, provide liquidity",
        "estimated_value": "$100-1000",
        "difficulty": "Easy",
        "cost": "Free (testnet)",
        "url": "https://www.berachain.com/",
    },
]


class AirdropSource(BaseSource):
    """
    Scans for free airdrop opportunities.
    Returns airdrops as 'quotes' and actionable opportunities.
    """

    def __init__(self):
        self._name = "airdrops"
        self._cached_opportunities: List[Dict[str, Any]] = []
        self._last_fetch: Optional[datetime] = None

    @property
    def source_name(self) -> str:
        return self._name

    @property
    def market_type(self) -> MarketType:
        return MarketType.AIRDROP

    async def fetch_quotes(self, symbols: Optional[List[str]] = None) -> List[MarketQuote]:
        """
        Fetch airdrop listings as quotes.
        Each airdrop becomes a 'quote' with estimated value as price.
        """
        quotes = []

        # 1. Fetch from DeFi Llama airdrops API (free, no key)
        try:
            quotes.extend(await self._fetch_defillama())
        except Exception as e:
            logger.warning(f"DeFi Llama airdrops failed: {e}")

        # 2. Add curated known airdrops
        quotes.extend(self._curated_airdrops_as_quotes())

        self._last_fetch = datetime.utcnow()
        return quotes

    async def _fetch_defillama(self) -> List[MarketQuote]:
        """Fetch potential airdrops from DeFi Llama."""
        quotes = []
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(DEFILLAMA_AIRDROPS)
                resp.raise_for_status()
                data = resp.json()

                # DeFi Llama returns list of protocols without tokens
                if isinstance(data, list):
                    for item in data[:20]:  # Top 20
                        name = item.get("name", "Unknown")
                        chain = item.get("chain", "Unknown") if isinstance(item, dict) else "Unknown"
                        tvl = item.get("tvl", 0) if isinstance(item, dict) else 0
                        logo = item.get("logo", "") if isinstance(item, dict) else ""

                        # Higher TVL = higher potential airdrop value
                        estimated_value = min(tvl * 0.001, 10000) if tvl else 100

                        quotes.append(MarketQuote(
                            symbol=f"AIRDROP_{name.upper().replace(' ', '_')[:10]}",
                            market_type=MarketType.AIRDROP,
                            source="defillama",
                            price=estimated_value,  # Estimated value
                            metadata={
                                "name": name,
                                "chain": chain,
                                "tvl": tvl,
                                "logo": logo,
                                "type": "potential_airdrop",
                                "url": f"https://defillama.com/protocol/{name.lower().replace(' ', '-')}",
                            },
                        ))
        except Exception as e:
            logger.error(f"DeFi Llama fetch error: {e}")

        return quotes

    def _curated_airdrops_as_quotes(self) -> List[MarketQuote]:
        """Convert curated airdrop list to quotes."""
        quotes = []
        for airdrop in KNOWN_UPCOMING_AIRDROPS:
            # Parse estimated value range
            est_range = airdrop.get("estimated_value", "$100")
            est_low = int(est_range.replace("$", "").replace(",", "").split("-")[0])

            quotes.append(MarketQuote(
                symbol=f"AIRDROP_{airdrop['name'].upper().replace(' ', '_')[:15]}",
                market_type=MarketType.AIRDROP,
                source="curated",
                price=est_low,
                metadata={
                    "name": airdrop["name"],
                    "chain": airdrop["chain"],
                    "task": airdrop["task"],
                    "estimated_value": airdrop["estimated_value"],
                    "difficulty": airdrop["difficulty"],
                    "cost": airdrop["cost"],
                    "url": airdrop["url"],
                    "type": "curated_airdrop",
                },
            ))
        return quotes

    async def scan_opportunities(self, quotes: List[MarketQuote]) -> List[MarketOpportunity]:
        """
        Convert airdrop quotes into actionable opportunities.
        All airdrops are HIGH severity because they're FREE money.
        """
        opportunities = []

        for q in quotes:
            if q.price <= 0:
                continue

            meta = q.metadata
            opp_type = meta.get("type", "potential_airdrop")

            # Determine severity based on estimated value and cost
            cost_str = meta.get("cost", "Unknown")
            is_free = "free" in cost_str.lower() or "testnet" in cost_str.lower()
            est_value = q.price

            if is_free or est_value > 1000:
                severity = Severity.HIGH
                confidence = 0.8
            elif est_value > 300:
                severity = Severity.MEDIUM
                confidence = 0.6
            else:
                severity = Severity.LOW
                confidence = 0.4

            # Build description
            if opp_type == "curated_airdrop":
                description = (
                    f"Task: {meta.get('task', 'N/A')}\n"
                    f"Cost: {meta.get('cost', 'N/A')}\n"
                    f"Estimated: {meta.get('estimated_value', 'N/A')}\n"
                    f"URL: {meta.get('url', 'N/A')}"
                )
            else:
                description = (
                    f"Protocol: {meta.get('name', 'Unknown')}\n"
                    f"Chain: {meta.get('chain', 'Unknown')}\n"
                    f"TVL: ${meta.get('tvl', 0):,.0f}\n"
                    f"Higher TVL = higher potential airdrop value"
                )

            opportunities.append(MarketOpportunity(
                opportunity_id=str(uuid.uuid4()),
                symbol=q.symbol,
                market_type=MarketType.AIRDROP,
                source=q.source,
                opportunity_type=OpportunityType.AIRDROP_FREE,
                severity=severity,
                title=f"Airdrop: {meta.get('name', q.symbol)} (Est. {meta.get('estimated_value', '$100+')})",
                description=description,
                current_price=est_value,
                target_price=est_value * 3,  # Upside potential
                confidence=confidence,
                metadata=meta,
            ))

        # Sort by estimated value (highest first)
        opportunities.sort(key=lambda o: -o.current_price)
        return opportunities[:15]  # Top 15

    async def get_summary(self, quotes: List[MarketQuote]) -> MarketSummary:
        """Summary of airdrop opportunities."""
        free_count = len([q for q in quotes if "free" in q.metadata.get("cost", "").lower() or "testnet" in q.metadata.get("cost", "").lower()])
        total_est = sum(q.price for q in quotes)

        return MarketSummary(
            market_type=MarketType.AIRDROP,
            total_instruments=len(quotes),
            active_instruments=len(quotes),
            total_volume_usd=total_est,
            top_movers=[
                {
                    "name": q.metadata.get("name", q.symbol),
                    "estimated_value": q.metadata.get("estimated_value", "N/A"),
                    "cost": q.metadata.get("cost", "N/A"),
                    "difficulty": q.metadata.get("difficulty", "N/A"),
                }
                for q in sorted(quotes, key=lambda x: -x.price)[:5]
            ],
            last_updated=datetime.utcnow(),
        )
