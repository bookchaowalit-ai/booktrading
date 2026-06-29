"""
Market Intelligence — unified multi-market analysis.

Covers: Crypto, Stocks (US + Thai), Prediction Markets (Polymarket), Forex, Commodities,
        Airdrops, Degen/Meme coins, Binance Alpha, Cross-exchange Arbitrage.
"""
from app.market_intel.models import (
    MarketType,
    OpportunityType,
    Severity,
    MarketQuote,
    MarketOpportunity,
    MarketSummary,
    ScannerResult,
)
from app.market_intel.scanner import MarketScanner, get_scanner
from app.market_intel.sources import (
    BaseSource,
    CryptoSource,
    PredictionSource,
    StockSource,
    MacroSource,
    AirdropSource,
    DegenSource,
    BinanceAlphaSource,
    CrossExchangeArbSource,
)

__all__ = [
    # Models
    "MarketType",
    "OpportunityType",
    "Severity",
    "MarketQuote",
    "MarketOpportunity",
    "MarketSummary",
    "ScannerResult",
    # Scanner
    "MarketScanner",
    "get_scanner",
    # Sources
    "BaseSource",
    "CryptoSource",
    "PredictionSource",
    "StockSource",
    "MacroSource",
    "AirdropSource",
    "DegenSource",
    "BinanceAlphaSource",
    "CrossExchangeArbSource",
]
