"""
Stock market data source — Yahoo Finance (free, no API key).
Covers US stocks and Thai stocks (SET).
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

# Yahoo Finance v8 chart API (public, no key needed)
YF_BASE = "https://query1.finance.yahoo.com"
# Alternative: v10 for quotes
YF_QUOTE_URL = "https://query1.finance.yahoo.com/v7/finance/quote"
# Fallback: use the download endpoint
YF_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"


class StockSource(BaseSource):
    """Stock market data from Yahoo Finance."""

    def __init__(self):
        self._name = "yahoo_finance"

    @property
    def source_name(self) -> str:
        return self._name

    @property
    def market_type(self) -> MarketType:
        return MarketType.STOCK

    async def fetch_quotes(self, symbols: Optional[List[str]] = None) -> List[MarketQuote]:
        """Fetch stock quotes from Yahoo Finance.

        Default symbols: major US indices + popular stocks + Thai blue chips.
        Thai stocks use .BK suffix (e.g., PTT.BK, AOT.BK).
        """
        if symbols is None:
            symbols = [
                # US indices ETFs
                "SPY", "QQQ", "DIA",
                # US tech giants
                "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META",
                # Thai blue chips (SET)
                "PTT.BK", "AOT.BK", "SCB.BK", "KBANK.BK", "CPALL.BK",
            ]

        quotes = []
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Use Yahoo Finance v7 quote API (batch)
                symbols_str = ",".join(symbols)
                headers = {"User-Agent": "Mozilla/5.0"}
                resp = await client.get(
                    YF_QUOTE_URL,
                    params={"symbols": symbols_str},
                    headers=headers,
                )

                if resp.status_code != 200:
                    # Fallback: fetch individually via chart endpoint
                    logger.warning(f"Yahoo v7 quote returned {resp.status_code}, falling back to chart API")
                    quotes = await self._fetch_individual(client, symbols, headers)
                else:
                    data = resp.json()
                    results = data.get("quoteResponse", {}).get("result", [])
                    for r in results:
                        symbol = r.get("symbol", "")
                        price = r.get("regularMarketPrice", 0) or 0
                        change = r.get("regularMarketChange", 0) or 0
                        change_pct = r.get("regularMarketChangePercent", 0) or 0
                        volume = r.get("regularMarketVolume", 0) or 0
                        prev_close = r.get("regularMarketPreviousClose", 0) or 0
                        day_high = r.get("regularMarketDayHigh", 0) or 0
                        day_low = r.get("regularMarketDayLow", 0) or 0
                        market_cap = r.get("marketCap", 0) or 0
                        market_state = r.get("marketState", "")

                        # Determine if Thai or US
                        sym_type = MarketType.STOCK

                        quotes.append(MarketQuote(
                            symbol=symbol,
                            market_type=sym_type,
                            source=self.source_name,
                            price=price,
                            change_24h=change,
                            change_pct_24h=change_pct,
                            volume_24h=volume,
                            metadata={
                                "previous_close": prev_close,
                                "day_high": day_high,
                                "day_low": day_low,
                                "market_cap": market_cap,
                                "market_state": market_state,
                                "exchange": r.get("fullExchangeName", ""),
                                "currency": r.get("currency", "USD"),
                                "52w_high": r.get("fiftyTwoWeekHigh", 0),
                                "52w_low": r.get("fiftyTwoWeekLow", 0),
                                "pe_ratio": r.get("trailingPE", 0),
                            },
                        ))
        except Exception as e:
            logger.error(f"Failed to fetch stock quotes: {e}")

        return quotes

    async def _fetch_individual(
        self, client: httpx.AsyncClient, symbols: List[str], headers: Dict
    ) -> List[MarketQuote]:
        """Fallback: fetch each symbol via chart endpoint."""
        quotes = []
        for symbol in symbols:
            try:
                resp = await client.get(
                    YF_CHART_URL.format(symbol=symbol),
                    params={"interval": "1d", "range": "2d"},
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
                result = data.get("chart", {}).get("result", [])
                if not result:
                    continue

                meta = result[0].get("meta", {})
                price = meta.get("regularMarketPrice", 0)
                prev = meta.get("chartPreviousClose", 0) or meta.get("previousClose", 0)
                change = price - prev if prev else 0
                change_pct = (change / prev * 100) if prev else 0

                quotes.append(MarketQuote(
                    symbol=symbol,
                    market_type=MarketType.STOCK,
                    source=self.source_name,
                    price=price,
                    change_24h=round(change, 4),
                    change_pct_24h=round(change_pct, 2),
                    metadata={
                        "exchange": meta.get("exchangeName", ""),
                        "currency": meta.get("currency", "USD"),
                    },
                ))
            except Exception as e:
                logger.warning(f"Failed to fetch {symbol}: {e}")

        return quotes

    async def scan_opportunities(self, quotes: List[MarketQuote]) -> List[MarketOpportunity]:
        """Scan for stock opportunities: momentum, mean reversion, volume spikes."""
        opportunities = []

        for q in quotes:
            change_pct = q.change_pct_24h or 0
            volume = q.volume_24h or 0
            high_52w = q.metadata.get("52w_high", 0)
            low_52w = q.metadata.get("52w_low", 0)
            pe = q.metadata.get("pe_ratio", 0) or 0

            # Large daily move (> 3%)
            if abs(change_pct) > 3.0:
                direction = "up" if change_pct > 0 else "down"
                severity = Severity.HIGH if abs(change_pct) > 5 else Severity.MEDIUM
                opportunities.append(MarketOpportunity(
                    opportunity_id=str(uuid.uuid4()),
                    symbol=q.symbol,
                    market_type=MarketType.STOCK,
                    source=self.source_name,
                    opportunity_type=OpportunityType.MOMENTUM,
                    severity=severity,
                    title=f"Stock {direction}: {q.symbol} ({change_pct:+.1f}%)",
                    description=f"{q.symbol} moved {change_pct:+.1f}% today. "
                                f"Exchange: {q.metadata.get('exchange', 'N/A')}.",
                    current_price=q.price,
                    confidence=0.5,
                    metadata={"change_pct": change_pct, "volume": volume},
                ))

            # Near 52-week low — potential mean reversion
            if low_52w and q.price > 0 and low_52w > 0:
                pct_from_low = (q.price - low_52w) / low_52w * 100
                if pct_from_low < 5:
                    opportunities.append(MarketOpportunity(
                        opportunity_id=str(uuid.uuid4()),
                        symbol=q.symbol,
                        market_type=MarketType.STOCK,
                        source=self.source_name,
                        opportunity_type=OpportunityType.MEAN_REVERSION,
                        severity=Severity.MEDIUM,
                        title=f"Near 52w low: {q.symbol}",
                        description=f"{q.symbol} at {q.price}, only {pct_from_low:.1f}% above 52w low ({low_52w}).",
                        current_price=q.price,
                        target_price=low_52w,
                        confidence=0.4,
                        metadata={"52w_low": low_52w, "52w_high": high_52w},
                    ))

            # Near 52-week high — potential breakout
            if high_52w and q.price > 0 and high_52w > 0:
                pct_from_high = (high_52w - q.price) / high_52w * 100
                if pct_from_high < 3:
                    opportunities.append(MarketOpportunity(
                        opportunity_id=str(uuid.uuid4()),
                        symbol=q.symbol,
                        market_type=MarketType.STOCK,
                        source=self.source_name,
                        opportunity_type=OpportunityType.BREAKOUT,
                        severity=Severity.MEDIUM,
                        title=f"Near 52w high: {q.symbol}",
                        description=f"{q.symbol} at {q.price}, only {pct_from_high:.1f}% below 52w high ({high_52w}).",
                        current_price=q.price,
                        target_price=high_52w,
                        confidence=0.45,
                        metadata={"52w_high": high_52w, "52w_low": low_52w},
                    ))

        return opportunities
