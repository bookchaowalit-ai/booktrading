"""
Base source interface for market data providers.
All sources implement this interface for unified access.
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from app.market_intel.models import MarketQuote, MarketOpportunity, MarketSummary, MarketType
from datetime import datetime


class BaseSource(ABC):
    """Abstract base class for all market data sources."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Unique identifier for this source."""
        pass

    @property
    @abstractmethod
    def market_type(self) -> MarketType:
        """Market type this source provides."""
        pass

    @abstractmethod
    async def fetch_quotes(self, symbols: Optional[List[str]] = None) -> List[MarketQuote]:
        """Fetch current quotes for instruments."""
        pass

    @abstractmethod
    async def scan_opportunities(self, quotes: List[MarketQuote]) -> List[MarketOpportunity]:
        """Scan for opportunities based on current data."""
        pass

    async def get_summary(self, quotes: List[MarketQuote]) -> MarketSummary:
        """Get market summary. Default implementation."""
        total_volume = sum(q.volume_24h or 0 for q in quotes)
        return MarketSummary(
            market_type=self.market_type,
            total_instruments=len(quotes),
            active_instruments=len([q for q in quotes if q.volume_24h and q.volume_24h > 0]),
            total_volume_usd=total_volume,
            last_updated=datetime.utcnow(),
        )
