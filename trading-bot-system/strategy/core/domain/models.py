"""
Domain models for the trading strategy service.
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class TradeSymbol(str, Enum):
    BTCUSDT = "BTCUSDT"
    ETHUSDT = "ETHUSDT"


@dataclass
class MarketData:
    """Represents real-time market data."""
    symbol: TradeSymbol
    price: float
    volume: float
    timestamp: datetime
    
    @classmethod
    def from_dict(cls, data: dict) -> "MarketData":
        return cls(
            symbol=TradeSymbol(data.get("symbol", "BTCUSDT")),
            price=float(data.get("price", 0)),
            volume=float(data.get("volume", 0)),
            timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now().isoformat()))
        )


@dataclass
class OrderSignal:
    """Represents a trading signal to be sent to the execution service."""
    symbol: TradeSymbol
    side: OrderSide
    strength: float  # 0.0 to 1.0
    reason: str
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol.value,
            "side": self.side.value,
            "strength": self.strength,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class StrategyConfig:
    """Configuration for the trading strategy."""
    rsi_period: int = 14
    ema_period: int = 14
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    min_signal_strength: float = 0.5
    symbols: list = None
    
    def __post_init__(self):
        if self.symbols is None:
            self.symbols = [TradeSymbol.BTCUSDT, TradeSymbol.ETHUSDT]


@dataclass
class TechnicalIndicators:
    """Calculated technical indicators."""
    symbol: TradeSymbol
    rsi: Optional[float] = None
    ema: Optional[float] = None
    sma: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
