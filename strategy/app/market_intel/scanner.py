"""
Cross-market opportunity scanner.
Scans all market sources simultaneously and aggregates results.
"""
import logging
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.market_intel.models import (
    MarketQuote, MarketOpportunity, MarketSummary, ScannerResult,
    MarketType, Severity,
)
from app.market_intel.sources.base import BaseSource
from app.market_intel.sources.crypto import CryptoSource
from app.market_intel.sources.prediction import PredictionSource
from app.market_intel.sources.stocks import StockSource
from app.market_intel.sources.macro import MacroSource

logger = logging.getLogger(__name__)


class MarketScanner:
    """
    Cross-market scanner that queries all sources and aggregates opportunities.
    """

    def __init__(
        self,
        crypto_symbols: Optional[List[str]] = None,
        stock_symbols: Optional[List[str]] = None,
        polymarket_gamma_api: str = "https://gamma-api.polymarket.com",
        polymarket_clob_api: str = "https://clob.polymarket.com",
        enabled_sources: Optional[List[str]] = None,
    ):
        self.crypto_symbols = crypto_symbols or ["BTCTHB", "ETHTHB", "BTCUSDT", "ETHUSDT"]
        self.stock_symbols = stock_symbols
        self.enabled = set(enabled_sources or ["crypto", "prediction", "stocks", "macro"])

        # Initialize sources
        self.sources: Dict[str, BaseSource] = {}
        if "crypto" in self.enabled:
            self.sources["crypto"] = CryptoSource()
        if "prediction" in self.enabled:
            self.sources["prediction"] = PredictionSource(
                gamma_api=polymarket_gamma_api,
                clob_api=polymarket_clob_api,
            )
        if "stocks" in self.enabled:
            self.sources["stocks"] = StockSource()
        if "macro" in self.enabled:
            self.sources["macro"] = MacroSource()

    async def scan_all(
        self,
        min_confidence: float = 0.3,
        markets: Optional[List[MarketType]] = None,
    ) -> ScannerResult:
        """
        Scan all enabled sources for opportunities.
        Returns aggregated ScannerResult.
        """
        all_opportunities: List[MarketOpportunity] = []
        all_quotes: List[MarketQuote] = []
        summaries: Dict[str, Any] = {}
        markets_scanned: List[MarketType] = []

        for name, source in self.sources.items():
            # Skip if filtering by market type and this source doesn't match
            if markets and source.market_type not in markets:
                continue

            markets_scanned.append(source.market_type)

            try:
                # Fetch quotes
                if name == "crypto":
                    quotes = await source.fetch_quotes(symbols=self.crypto_symbols)
                elif name == "stocks":
                    quotes = await source.fetch_quotes(symbols=self.stock_symbols)
                else:
                    quotes = await source.fetch_quotes()

                all_quotes.extend(quotes)

                # Scan for opportunities
                opps = await source.scan_opportunities(quotes)
                # Filter by confidence
                opps = [o for o in opps if o.confidence >= min_confidence]
                all_opportunities.extend(opps)

                # Summary
                summary = await source.get_summary(quotes)
                summary.opportunities_count = len(opps)
                summaries[name] = summary.model_dump()

            except Exception as e:
                logger.error(f"Scanner error on {name}: {e}")
                summaries[name] = {"error": str(e)}

        # Sort opportunities: critical > high > medium > low
        severity_order = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3}
        all_opportunities.sort(key=lambda o: (severity_order.get(o.severity, 4), -o.confidence))

        # Count by severity and market
        by_severity = {}
        by_market = {}
        for opp in all_opportunities:
            by_severity[opp.severity.value] = by_severity.get(opp.severity.value, 0) + 1
            by_market[opp.market_type.value] = by_market.get(opp.market_type.value, 0) + 1

        return ScannerResult(
            scan_id=str(uuid.uuid4()),
            markets_scanned=markets_scanned,
            total_opportunities=len(all_opportunities),
            by_severity=by_severity,
            by_market=by_market,
            opportunities=all_opportunities,
            summary=summaries,
        )

    async def get_all_quotes(self, markets: Optional[List[MarketType]] = None) -> List[MarketQuote]:
        """Fetch quotes from all sources without scanning."""
        all_quotes = []
        for name, source in self.sources.items():
            if markets and source.market_type not in markets:
                continue
            try:
                if name == "crypto":
                    quotes = await source.fetch_quotes(symbols=self.crypto_symbols)
                elif name == "stocks":
                    quotes = await source.fetch_quotes(symbols=self.stock_symbols)
                else:
                    quotes = await source.fetch_quotes()
                all_quotes.extend(quotes)
            except Exception as e:
                logger.error(f"Quote fetch error on {name}: {e}")
        return all_quotes

    async def get_market_overview(self) -> Dict[str, Any]:
        """High-level overview of all markets."""
        overview = {}
        for name, source in self.sources.items():
            try:
                if name == "crypto":
                    quotes = await source.fetch_quotes(symbols=self.crypto_symbols[:4])
                elif name == "stocks":
                    quotes = await source.fetch_quotes(symbols=self.stock_symbols[:5] if self.stock_symbols else None)
                else:
                    quotes = await source.fetch_quotes()

                opps = await source.scan_opportunities(quotes)

                overview[name] = {
                    "market_type": source.market_type.value,
                    "instruments": len(quotes),
                    "opportunities": len(opps),
                    "top_opps": [
                        {
                            "title": o.title,
                            "severity": o.severity.value,
                            "confidence": o.confidence,
                        }
                        for o in sorted(opps, key=lambda x: -x.confidence)[:3]
                    ],
                    "sample_quotes": [
                        {
                            "symbol": q.symbol,
                            "price": q.price,
                            "change_pct": q.change_pct_24h,
                        }
                        for q in quotes[:5]
                    ],
                }
            except Exception as e:
                overview[name] = {"error": str(e)}

        return overview

    def reload_sources(
        self,
        crypto_symbols: Optional[List[str]] = None,
        stock_symbols: Optional[List[str]] = None,
    ):
        """Hot-reload source configurations."""
        if crypto_symbols:
            self.crypto_symbols = crypto_symbols
        if stock_symbols:
            self.stock_symbols = stock_symbols


# Singleton
_scanner: Optional[MarketScanner] = None


def get_scanner(**kwargs) -> MarketScanner:
    global _scanner
    if _scanner is None:
        _scanner = MarketScanner(**kwargs)
    return _scanner
