"""
Unified market intelligence models.
Works across all market types: crypto, stocks, prediction markets, forex, commodities.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class MarketType(str, Enum):
    CRYPTO = "crypto"
    STOCK = "stock"
    PREDICTION = "prediction"
    FOREX = "forex"
    COMMODITY = "commodity"


class OpportunityType(str, Enum):
    MISPRICING = "mispricing"
    ARBITRAGE = "arbitrage"
    MOMENTUM = "momentum"
    VOLUME_SPIKE = "volume_spike"
    LIQUIDITY_GAP = "liquidity_gap"
    MEAN_REVERSION = "mean_reversion"
    BREAKOUT = "breakout"
    STALE_PRICE = "stale_price"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MarketQuote(BaseModel):
    """Unified quote across all markets."""
    symbol: str
    market_type: MarketType
    source: str  # "binance_th", "polymarket", "yahoo", "forex_api"
    price: float
    change_24h: Optional[float] = None
    change_pct_24h: Optional[float] = None
    volume_24h: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = {}


class MarketOpportunity(BaseModel):
    """Unified opportunity signal across all markets."""
    opportunity_id: str
    symbol: str
    market_type: MarketType
    source: str
    opportunity_type: OpportunityType
    severity: Severity
    title: str
    description: str
    current_price: float
    target_price: Optional[float] = None
    confidence: float = Field(ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = {}


class MarketSummary(BaseModel):
    """Summary of a market or market segment."""
    market_type: MarketType
    total_instruments: int
    active_instruments: int
    total_volume_usd: float = 0.0
    top_movers: List[Dict[str, Any]] = []
    opportunities_count: int = 0
    last_updated: Optional[datetime] = None


class ScannerResult(BaseModel):
    """Result from cross-market scanner."""
    scan_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    markets_scanned: List[MarketType]
    total_opportunities: int
    by_severity: Dict[str, int] = {}
    by_market: Dict[str, int] = {}
    opportunities: List[MarketOpportunity] = []
    summary: Dict[str, Any] = {}
