"""
Crypto market data source — Binance TH / Binance Global.
Fetches prices and detects crypto-specific opportunities.
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

BINANCE_TH_BASE = "https://api.binance.th"
BINANCE_GLOBAL_BASE = "https://api.binance.com"
# Binance TH uses v1 API, Binance Global uses v3
BINANCE_TH_API_VERSION = "v1"
BINANCE_GLOBAL_API_VERSION = "v3"


class CryptoSource(BaseSource):
    """Crypto market data from Binance TH."""

    def __init__(self, use_testnet: bool = False, exchange: str = "binance_th"):
        self.exchange = exchange
        if exchange == "binance_th":
            self.base_url = BINANCE_TH_BASE
            self.api_version = BINANCE_TH_API_VERSION
        else:
            self.base_url = BINANCE_GLOBAL_BASE
            self.api_version = BINANCE_GLOBAL_API_VERSION

    @property
    def source_name(self) -> str:
        return self.exchange

    @property
    def market_type(self) -> MarketType:
        return MarketType.CRYPTO

    async def fetch_quotes(self, symbols: Optional[List[str]] = None) -> List[MarketQuote]:
        """Fetch crypto prices from Binance."""
        if symbols is None:
            symbols = ["BTCTHB", "ETHTHB", "BTCUSDT", "ETHUSDT"]

        quotes = []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Fetch individual symbol tickers (Binance TH doesn't support bulk endpoint)
                for symbol in symbols:
                    try:
                        resp = await client.get(
                            f"{self.base_url}/api/{self.api_version}/ticker/24hr",
                            params={"symbol": symbol},
                        )
                        resp.raise_for_status()
                        ticker = resp.json()

                        price = float(ticker.get("lastPrice", 0))
                        change = float(ticker.get("priceChange", 0))
                        change_pct = float(ticker.get("priceChangePercent", 0))
                        volume = float(ticker.get("quoteVolume", 0))
                        high = float(ticker.get("highPrice", 0))
                        low = float(ticker.get("lowPrice", 0))

                        quotes.append(MarketQuote(
                            symbol=symbol,
                            market_type=MarketType.CRYPTO,
                            source=self.source_name,
                            price=price,
                            change_24h=change,
                            change_pct_24h=change_pct,
                            volume_24h=volume,
                            metadata={
                                "high_24h": high,
                                "low_24h": low,
                                "weighted_avg_price": float(ticker.get("weightedAvgPrice", 0)),
                                "trade_count": int(ticker.get("count", 0)),
                            },
                        ))
                    except Exception as sym_err:
                        logger.warning(f"Failed to fetch {symbol}: {sym_err}")
        except Exception as e:
            logger.error(f"Failed to fetch crypto quotes: {e}")

        return quotes

    async def scan_opportunities(self, quotes: List[MarketQuote]) -> List[MarketOpportunity]:
        """Scan for crypto opportunities: volume spikes, large moves."""
        opportunities = []

        for q in quotes:
            # Volume spike: > $10M daily volume
            if q.volume_24h and q.volume_24h > 10_000_000:
                opportunities.append(MarketOpportunity(
                    opportunity_id=str(uuid.uuid4()),
                    symbol=q.symbol,
                    market_type=MarketType.CRYPTO,
                    source=self.source_name,
                    opportunity_type=OpportunityType.VOLUME_SPIKE,
                    severity=Severity.MEDIUM,
                    title=f"High volume: {q.symbol}",
                    description=f"${q.volume_24h:,.0f} 24h volume. Active market with good liquidity.",
                    current_price=q.price,
                    confidence=0.6,
                    metadata={"volume_24h": q.volume_24h},
                ))

            # Large price move: > 5% in 24h
            if q.change_pct_24h and abs(q.change_pct_24h) > 5.0:
                direction = "up" if q.change_pct_24h > 0 else "down"
                severity = Severity.HIGH if abs(q.change_pct_24h) > 10 else Severity.MEDIUM
                opportunities.append(MarketOpportunity(
                    opportunity_id=str(uuid.uuid4()),
                    symbol=q.symbol,
                    market_type=MarketType.CRYPTO,
                    source=self.source_name,
                    opportunity_type=OpportunityType.MOMENTUM,
                    severity=severity,
                    title=f"Large move {direction}: {q.symbol} ({q.change_pct_24h:+.1f}%)",
                    description=f"{q.symbol} moved {q.change_pct_24h:+.1f}% in 24h. Potential trend or reversal.",
                    current_price=q.price,
                    confidence=0.5,
                    metadata={
                        "change_pct": q.change_pct_24h,
                        "high_24h": q.metadata.get("high_24h"),
                        "low_24h": q.metadata.get("low_24h"),
                    },
                ))

        return opportunities
