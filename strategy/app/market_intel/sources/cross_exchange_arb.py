"""
Cross-exchange arbitrage scanner — compares prices across exchanges.
Finds price discrepancies that can be exploited for profit.

Exchanges compared:
- Binance TH (api.binance.th)
- Binance Global (api.binance.com)
- Bitkub (Thai exchange)
- Gate.io
- KuCoin
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

# Exchange endpoints
EXCHANGES = {
    "binance_th": {
        "base": "https://api.binance.th",
        "api_version": "v1",
        "pairs": {
            "BTC": "BTCTHB",
            "ETH": "ETHTHB",
            "BNB": "BNBTHB",
            "SOL": "SOLTHB",
            "XRP": "XRPTHB",
        },
        "currency": "THB",
    },
    "binance_global": {
        "base": "https://api.binance.com",
        "api_version": "v3",
        "pairs": {
            "BTC": "BTCUSDT",
            "ETH": "ETHUSDT",
            "BNB": "BNBUSDT",
            "SOL": "SOLUSDT",
            "XRP": "XRPUSDT",
        },
        "currency": "USDT",
    },
    "gate": {
        "base": "https://api.gateio.ws/api/v4",
        "pairs": {
            "BTC": "BTC_USDT",
            "ETH": "ETH_USDT",
            "BNB": "BNB_USDT",
            "SOL": "SOL_USDT",
            "XRP": "XRP_USDT",
        },
        "currency": "USDT",
    },
    "kucoin": {
        "base": "https://api.kucoin.com",
        "pairs": {
            "BTC": "BTC-USDT",
            "ETH": "ETH-USDT",
            "BNB": "BNB-USDT",
            "SOL": "SOL-USDT",
            "XRP": "XRP-USDT",
        },
        "currency": "USDT",
    },
}

# Approximate THB/USDT rate (will be fetched dynamically)
DEFAULT_THB_USDT_RATE = 36.0  # ~36 THB per USDT

# Minimum spread to flag as opportunity
MIN_SPREAD_PCT = 0.5  # 0.5% minimum after fees


class CrossExchangeArbSource(BaseSource):
    """
    Scans for cross-exchange arbitrage opportunities.
    Compares prices across multiple exchanges for the same assets.
    """

    def __init__(self):
        self._name = "arb"
        self._thb_usdt_rate: float = DEFAULT_THB_USDT_RATE

    @property
    def source_name(self) -> str:
        return self._name

    @property
    def market_type(self) -> MarketType:
        return MarketType.CRYPTO

    async def fetch_quotes(self, symbols: Optional[List[str]] = None) -> List[MarketQuote]:
        """
        Fetch prices from all exchanges and normalize to USD for comparison.
        """
        quotes = []

        # 1. Get THB/USDT rate for normalization
        try:
            self._thb_usdt_rate = await self._fetch_thb_usdt_rate()
        except Exception as e:
            logger.warning(f"THB/USDT rate fetch failed, using default: {e}")

        # 2. Fetch prices from each exchange
        base_assets = ["BTC", "ETH", "BNB", "SOL", "XRP"]

        for exchange_name, config in EXCHANGES.items():
            try:
                exchange_quotes = await self._fetch_exchange_prices(exchange_name, config, base_assets)
                quotes.extend(exchange_quotes)
            except Exception as e:
                logger.warning(f"Failed to fetch from {exchange_name}: {e}")

        return quotes

    async def _fetch_thb_usdt_rate(self) -> float:
        """Fetch current THB/USDT exchange rate."""
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(
                    "https://api.binance.th/api/v1/ticker/price",
                    params={"symbol": "USDTTHB"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return float(data.get("price", DEFAULT_THB_USDT_RATE))
        except Exception:
            pass
        return DEFAULT_THB_USDT_RATE

    async def _fetch_exchange_prices(
        self,
        exchange_name: str,
        config: Dict,
        assets: List[str],
    ) -> List[MarketQuote]:
        """Fetch prices for assets on a specific exchange."""
        quotes = []
        base_url = config["base"]
        currency = config["currency"]

        async with httpx.AsyncClient(timeout=10.0) as client:
            for asset in assets:
                pair = config["pairs"].get(asset)
                if not pair:
                    continue

                try:
                    price = await self._fetch_single_price(client, exchange_name, base_url, pair, config)
                    if price <= 0:
                        continue

                    # Normalize to USD for comparison
                    if currency == "THB":
                        price_usd = price / self._thb_usdt_rate
                    else:
                        price_usd = price

                    quotes.append(MarketQuote(
                        symbol=f"ARB_{asset}",
                        market_type=MarketType.CRYPTO,
                        source=exchange_name,
                        price=price_usd,
                        metadata={
                            "asset": asset,
                            "exchange": exchange_name,
                            "local_price": price,
                            "local_pair": pair,
                            "local_currency": currency,
                            "thb_usdt_rate": self._thb_usdt_rate,
                        },
                    ))
                except Exception as e:
                    logger.debug(f"Price fetch failed for {asset} on {exchange_name}: {e}")

        return quotes

    async def _fetch_single_price(
        self,
        client: httpx.AsyncClient,
        exchange: str,
        base_url: str,
        pair: str,
        config: Dict,
    ) -> float:
        """Fetch single price from exchange."""
        if exchange == "binance_th":
            resp = await client.get(
                f"{base_url}/api/{config['api_version']}/ticker/price",
                params={"symbol": pair},
            )
            resp.raise_for_status()
            return float(resp.json().get("price", 0))

        elif exchange == "binance_global":
            resp = await client.get(
                f"{base_url}/api/{config['api_version']}/ticker/price",
                params={"symbol": pair},
            )
            resp.raise_for_status()
            return float(resp.json().get("price", 0))

        elif exchange == "gate":
            resp = await client.get(
                f"{base_url}/spot/tickers",
                params={"currency_pair": pair},
            )
            resp.raise_for_status()
            data = resp.json()
            if data and len(data) > 0:
                return float(data[0].get("last", 0))

        elif exchange == "kucoin":
            resp = await client.get(
                f"{base_url}/api/v1/market/orderbook/level1",
                params={"symbol": pair},
            )
            resp.raise_for_status()
            data = resp.json()
            return float(data.get("data", {}).get("price", 0))

        return 0.0

    async def scan_opportunities(self, quotes: List[MarketQuote]) -> List[MarketOpportunity]:
        """
        Find arbitrage opportunities by comparing prices across exchanges.
        """
        opportunities = []

        # Group quotes by asset
        by_asset: Dict[str, List[MarketQuote]] = {}
        for q in quotes:
            asset = q.metadata.get("asset", "")
            if asset:
                if asset not in by_asset:
                    by_asset[asset] = []
                by_asset[asset].append(q)

        # Compare prices within each asset
        for asset, asset_quotes in by_asset.items():
            if len(asset_quotes) < 2:
                continue

            # Find min and max prices
            min_q = min(asset_quotes, key=lambda q: q.price)
            max_q = max(asset_quotes, key=lambda q: q.price)

            if min_q.price <= 0:
                continue

            spread_pct = ((max_q.price - min_q.price) / min_q.price) * 100

            # Account for fees (~0.1% per trade x 2 = 0.2% total)
            net_spread_pct = spread_pct - 0.2

            if net_spread_pct >= MIN_SPREAD_PCT:
                # Determine severity based on spread
                if net_spread_pct > 2.0:
                    severity = Severity.HIGH
                    confidence = 0.7
                elif net_spread_pct > 1.0:
                    severity = Severity.MEDIUM
                    confidence = 0.6
                else:
                    severity = Severity.LOW
                    confidence = 0.5

                opportunities.append(MarketOpportunity(
                    opportunity_id=str(uuid.uuid4()),
                    symbol=f"ARB_{asset}",
                    market_type=MarketType.CRYPTO,
                    source=self.source_name,
                    opportunity_type=OpportunityType.CROSS_EXCHANGE_ARB,
                    severity=severity,
                    title=f"Arbitrage: {asset} ({net_spread_pct:.2f}% spread)",
                    description=(
                        f"Buy on {min_q.source}: ${min_q.price:.2f} "
                        f"({min_q.metadata.get('local_price', 0):.2f} {min_q.metadata.get('local_currency', '')})\n"
                        f"Sell on {max_q.source}: ${max_q.price:.2f} "
                        f"({max_q.metadata.get('local_price', 0):.2f} {max_q.metadata.get('local_currency', '')})\n"
                        f"Gross spread: {spread_pct:.2f}%\n"
                        f"Net after fees: {net_spread_pct:.2f}%\n"
                        f"THB/USDT rate: {self._thb_usdt_rate:.2f}"
                    ),
                    current_price=min_q.price,
                    target_price=max_q.price,
                    confidence=confidence,
                    metadata={
                        "asset": asset,
                        "buy_exchange": min_q.source,
                        "sell_exchange": max_q.source,
                        "buy_price_usd": min_q.price,
                        "sell_price_usd": max_q.price,
                        "gross_spread_pct": round(spread_pct, 3),
                        "net_spread_pct": round(net_spread_pct, 3),
                        "thb_usdt_rate": self._thb_usdt_rate,
                    },
                ))

        # Sort by net spread (highest first)
        opportunities.sort(key=lambda o: -o.metadata.get("net_spread_pct", 0))
        return opportunities

    async def get_summary(self, quotes: List[MarketQuote]) -> MarketSummary:
        """Summary of arbitrage opportunities."""
        exchanges = {}
        for q in quotes:
            ex = q.metadata.get("exchange", "unknown")
            exchanges[ex] = exchanges.get(ex, 0) + 1

        return MarketSummary(
            market_type=MarketType.CRYPTO,
            total_instruments=len(quotes),
            active_instruments=len(quotes),
            total_volume_usd=0,  # Arb doesn't track volume
            top_movers=[
                {"exchange": ex, "pairs": count}
                for ex, count in exchanges.items()
            ],
            last_updated=datetime.utcnow(),
        )
