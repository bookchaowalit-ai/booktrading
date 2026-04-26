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
    BTCTHB = "BTCTHB"
    ETHTHB = "ETHTHB"


@dataclass
class MarketData:
    """Represents real-time market data."""
    symbol: TradeSymbol
    price: float
    volume: float
    timestamp: datetime
    
    @classmethod
    def from_dict(cls, data: dict) -> "MarketData":
        symbol_str = data.get("symbol", "BTCUSDT")
        try:
            symbol = TradeSymbol(symbol_str)
        except ValueError:
            # Dynamically register new trading pair
            symbol = TradeSymbol.__new__(TradeSymbol, symbol_str)  # type: ignore
            symbol._name_ = symbol_str
            symbol._value_ = symbol_str
            symbol._sorted_ = False
            TradeSymbol._member_map_[symbol_str] = symbol
            TradeSymbol._value2member_map_[symbol_str] = symbol
            TradeSymbol._member_names_.append(symbol_str)
        return cls(
            symbol=symbol,
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
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class StrategyConfig:
    """Configuration for the trading strategy."""
    # Base parameters (backwards compatible)
    rsi_period: int = 14
    ema_period: int = 14
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    min_signal_strength: float = 0.5
    symbols: list = None
    # Composite scoring weights
    weight_trend: float = 0.25       # EMA cross + ADX
    weight_momentum: float = 0.30    # MACD + StochRSI
    weight_volatility: float = 0.20  # Bollinger Bands
    weight_rsi: float = 0.15         # RSI as minor component
    # Indicator parameters
    ema_fast_period: int = 9
    ema_slow_period: int = 21
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    bollinger_period: int = 20
    bollinger_std: float = 2.0
    atr_period: int = 14
    adx_period: int = 14
    roc_period: int = 10
    stoch_rsi_period: int = 14
    # Market regime filter
    adx_min_trend: float = 25.0      # Min ADX for trend filter
    # Signal gate
    min_composite_score: float = 0.5  # Composite score threshold

    def __post_init__(self):
        if self.symbols is None:
            self.symbols = [TradeSymbol.BTCUSDT, TradeSymbol.ETHUSDT]


@dataclass
class TechnicalIndicators:
    """Calculated technical indicators."""
    symbol: TradeSymbol
    # Existing
    rsi: Optional[float] = None
    ema: Optional[float] = None
    sma: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    # New
    bb_upper: Optional[float] = None
    bb_lower: Optional[float] = None
    bb_width: Optional[float] = None
    atr: Optional[float] = None
    stoch_k: Optional[float] = None
    stoch_d: Optional[float] = None
    macd_histogram: Optional[float] = None
    ema_fast: Optional[float] = None
    ema_slow: Optional[float] = None
    ema_cross: Optional[str] = None  # "golden", "death", None
    adx: Optional[float] = None
    roc: Optional[float] = None
    obv_trend: Optional[float] = None  # -1 to 1
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
