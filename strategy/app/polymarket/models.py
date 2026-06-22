"""
Polymarket data models for prediction market analysis.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class PolymarketOutcome(BaseModel):
    """Binary outcome (Yes/No) for a prediction market."""
    name: str  # "Yes" or "No"
    price: float  # 0.0 to 1.0 (implied probability)
    winner: Optional[bool] = None  # None if unresolved


class PolymarketMarket(BaseModel):
    """Individual prediction market within an event."""
    condition_id: str
    question: str
    description: Optional[str] = None
    outcomes: List[PolymarketOutcome]
    volume: Optional[float] = None  # Total volume in USDC
    liquidity: Optional[float] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    resolved: bool = False
    enable_order_book: bool = True
    tags: List[str] = []
    
    @property
    def yes_price(self) -> float:
        """Get Yes outcome price."""
        for outcome in self.outcomes:
            if outcome.name.lower() == "yes":
                return outcome.price
        return 0.0
    
    @property
    def no_price(self) -> float:
        """Get No outcome price."""
        for outcome in self.outcomes:
            if outcome.name.lower() == "no":
                return outcome.price
        return 0.0


class PolymarketEvent(BaseModel):
    """Event containing multiple related markets."""
    event_id: str
    title: str
    description: Optional[str] = None
    slug: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    markets: List[PolymarketMarket] = []
    tags: List[str] = []
    series: Optional[str] = None
    closed: bool = False


class OrderbookLevel(BaseModel):
    """Single price level in orderbook."""
    price: float
    size: float


class Orderbook(BaseModel):
    """Orderbook for a Polymarket outcome."""
    market: str
    outcome: str
    bids: List[OrderbookLevel] = []
    asks: List[OrderbookLevel] = []
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    @property
    def best_bid(self) -> Optional[float]:
        return self.bids[0].price if self.bids else None
    
    @property
    def best_ask(self) -> Optional[float]:
        return self.asks[0].price if self.asks else None
    
    @property
    def spread(self) -> Optional[float]:
        if self.best_bid and self.best_ask:
            return self.best_ask - self.best_bid
        return None


class PriceHistory(BaseModel):
    """Historical price data for a market outcome."""
    market: str
    outcome: str
    prices: List[Dict[str, Any]] = []  # [{"t": timestamp, "p": price}, ...]


class MarketOpportunity(BaseModel):
    """Identified market inefficiency or opportunity."""
    market_id: str
    question: str
    opportunity_type: str  # "mispricing", "volume_spike", "liquidity_gap", "arbitrage"
    severity: str  # "low", "medium", "high"
    description: str
    current_price: float
    estimated_fair_value: Optional[float] = None
    confidence: float = Field(ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = {}
