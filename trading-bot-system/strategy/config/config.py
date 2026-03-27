"""
Configuration management for the strategy service.
"""
import os
from dataclasses import dataclass
from typing import List


@dataclass
class Config:
    """Application configuration."""
    
    # Redis configuration
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0
    
    # gRPC Backend configuration
    grpc_host: str = "localhost"
    grpc_port: int = 9000
    
    # API configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # Strategy configuration
    rsi_period: int = 14
    ema_period: int = 14
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    min_signal_strength: float = 0.5
    
    # Symbols to trade
    symbols: List[str] = None
    
    def __post_init__(self):
        if self.symbols is None:
            self.symbols = ["BTCUSDT", "ETHUSDT"]
    
    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        return cls(
            redis_host=os.getenv("REDIS_HOST", "localhost"),
            redis_port=int(os.getenv("REDIS_PORT", "6379")),
            redis_password=os.getenv("REDIS_PASSWORD", ""),
            redis_db=int(os.getenv("REDIS_DB", "0")),
            grpc_host=os.getenv("GRPC_HOST", "backend"),
            grpc_port=int(os.getenv("GRPC_PORT", "9000")),
            api_host=os.getenv("API_HOST", "0.0.0.0"),
            api_port=int(os.getenv("API_PORT", "8000")),
            rsi_period=int(os.getenv("RSI_PERIOD", "14")),
            ema_period=int(os.getenv("EMA_PERIOD", "14")),
            rsi_oversold=float(os.getenv("RSI_OVERSOLD", "30.0")),
            rsi_overbought=float(os.getenv("RSI_OVERBOUGHT", "70.0")),
            min_signal_strength=float(os.getenv("MIN_SIGNAL_STRENGTH", "0.5")),
            symbols=os.getenv("SYMBOLS", "BTCUSDT,ETHUSDT").split(","),
        )
    
    def to_dict(self) -> dict:
        """Convert configuration to dictionary."""
        return {
            "REDIS_HOST": self.redis_host,
            "REDIS_PORT": self.redis_port,
            "REDIS_PASSWORD": self.redis_password,
            "REDIS_DB": self.redis_db,
            "API_HOST": self.api_host,
            "API_PORT": self.api_port,
            "RSI_PERIOD": self.rsi_period,
            "EMA_PERIOD": self.ema_period,
            "RSI_OVERSOLD": self.rsi_oversold,
            "RSI_OVERBOUGHT": self.rsi_overbought,
            "MIN_SIGNAL_STRENGTH": self.min_signal_strength,
            "SYMBOLS": self.symbols,
        }
