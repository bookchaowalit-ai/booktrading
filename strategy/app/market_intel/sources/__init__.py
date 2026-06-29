"""
Market data sources — unified interface.
"""
from app.market_intel.sources.base import BaseSource
from app.market_intel.sources.crypto import CryptoSource
from app.market_intel.sources.prediction import PredictionSource
from app.market_intel.sources.stocks import StockSource
from app.market_intel.sources.macro import MacroSource
from app.market_intel.sources.airdrops import AirdropSource
from app.market_intel.sources.degen import DegenSource
from app.market_intel.sources.binance_alpha import BinanceAlphaSource
from app.market_intel.sources.cross_exchange_arb import CrossExchangeArbSource

__all__ = [
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
