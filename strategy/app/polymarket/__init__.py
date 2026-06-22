"""
Polymarket prediction market research module.
Provides data fetching, analysis, and opportunity detection for Polymarket.
"""
from app.polymarket.client import PolymarketClient, get_polymarket_client
from app.polymarket.analyzer import PolymarketAnalyzer, get_analyzer
from app.polymarket.paper_bot import PolymarketPaperBot, get_poly_paper_bot
from app.polymarket.models import (
    PolymarketEvent,
    PolymarketMarket,
    PolymarketOutcome,
    Orderbook,
    OrderbookLevel,
    PriceHistory,
    MarketOpportunity,
)

__all__ = [
    "PolymarketClient",
    "get_polymarket_client",
    "PolymarketAnalyzer",
    "get_analyzer",
    "PolymarketPaperBot",
    "get_poly_paper_bot",
    "PolymarketEvent",
    "PolymarketMarket",
    "PolymarketOutcome",
    "Orderbook",
    "OrderbookLevel",
    "PriceHistory",
    "MarketOpportunity",
]
