"""
Market data sources — unified interface.
"""
from app.market_intel.sources.base import BaseSource
from app.market_intel.sources.crypto import CryptoSource
from app.market_intel.sources.prediction import PredictionSource
from app.market_intel.sources.stocks import StockSource
from app.market_intel.sources.macro import MacroSource

__all__ = [
    "BaseSource",
    "CryptoSource",
    "PredictionSource",
    "StockSource",
    "MacroSource",
]
