"""
Strategy Service Configuration
Centralized configuration management with validation
"""

import os
import logging
from typing import List, Optional
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)


class ServiceConfig(BaseModel):
    """Main service configuration with validation"""

    # Redis Configuration
    redis_host: str = Field(default="localhost", env="REDIS_HOST")
    redis_port: int = Field(default=6379, env="REDIS_PORT", gt=0, le=65535)
    redis_password: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    redis_db: int = Field(default=0, env="REDIS_DB", ge=0, le=15)

    # gRPC Configuration
    grpc_host: str = Field(default="backend", env="GRPC_HOST")
    grpc_port: int = Field(default=9000, env="GRPC_PORT", gt=0, le=65535)

    # API Configuration
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    api_port: int = Field(default=8000, env="API_PORT", gt=0, le=65535)
    auth_token: Optional[str] = Field(default=None, env="AUTH_TOKEN")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    allowed_origins: str = Field(default="http://localhost:3000", env="ALLOWED_ORIGINS")

    # Strategy Configuration
    rsi_period: int = Field(default=14, env="RSI_PERIOD", gt=0)
    ema_period: int = Field(default=14, env="EMA_PERIOD", gt=0)
    rsi_oversold: float = Field(default=30.0, env="RSI_OVERSOLD", gt=0, lt=100)
    rsi_overbought: float = Field(default=70.0, env="RSI_OVERBOUGHT", gt=0, lt=100)
    min_signal_strength: float = Field(default=0.5, env="MIN_SIGNAL_STRENGTH", gt=0, le=1.0)
    symbols: str = Field(default="BTCUSDT,ETHUSDT,BTCTHB,ETHTHB", env="SYMBOLS")

    # Composite scoring weights
    weight_trend: float = Field(default=0.25, env="WEIGHT_TREND", gt=0, le=1.0)
    weight_momentum: float = Field(default=0.30, env="WEIGHT_MOMENTUM", gt=0, le=1.0)
    weight_volatility: float = Field(default=0.20, env="WEIGHT_VOLATILITY", gt=0, le=1.0)
    weight_rsi: float = Field(default=0.15, env="WEIGHT_RSI", gt=0, le=1.0)

    # Indicator parameters
    ema_fast_period: int = Field(default=9, env="EMA_FAST_PERIOD", gt=0)
    ema_slow_period: int = Field(default=21, env="EMA_SLOW_PERIOD", gt=0)
    macd_fast: int = Field(default=12, env="MACD_FAST", gt=0)
    macd_slow: int = Field(default=26, env="MACD_SLOW", gt=0)
    macd_signal_period: int = Field(default=9, env="MACD_SIGNAL", gt=0)
    bollinger_period: int = Field(default=20, env="BB_PERIOD", gt=0)
    bollinger_std: float = Field(default=2.0, env="BB_STD", gt=0)
    atr_period: int = Field(default=14, env="ATR_PERIOD", gt=0)
    adx_period: int = Field(default=14, env="ADX_PERIOD", gt=0)
    roc_period: int = Field(default=10, env="ROC_PERIOD", gt=0)
    stoch_rsi_period: int = Field(default=14, env="STOCH_RSI_PERIOD", gt=0)

    # Market regime filter
    adx_min_trend: float = Field(default=25.0, env="ADX_MIN_TREND", gt=0, le=100)

    # Signal gate
    min_composite_score: float = Field(default=0.5, env="MIN_COMPOSITE_SCORE", gt=0, le=1.0)

    # Polymarket Configuration
    polymarket_gamma_api: str = Field(default="https://gamma-api.polymarket.com", env="POLYMARKET_GAMMA_API")
    polymarket_clob_api: str = Field(default="https://clob.polymarket.com", env="POLYMARKET_CLOB_API")
    polymarket_data_api: str = Field(default="https://data-api.polymarket.com", env="POLYMARKET_DATA_API")
    polymarket_enabled: bool = Field(default=True, env="POLYMARKET_ENABLED")

    # Market Intelligence Configuration
    market_intel_enabled: bool = Field(default=True, env="MARKET_INTEL_ENABLED")
    market_intel_sources: str = Field(default="crypto,prediction,stocks,macro", env="MARKET_INTEL_SOURCES")
    market_intel_crypto_symbols: str = Field(default="BTCTHB,ETHTHB,BTCUSDT,ETHUSDT", env="MARKET_INTEL_CRYPTO_SYMBOLS")
    market_intel_stock_symbols: str = Field(
        default="SPY,QQQ,AAPL,MSFT,GOOGL,AMZN,NVDA,TSLA,META,PTT.BK,AOT.BK,SCB.BK",
        env="MARKET_INTEL_STOCK_SYMBOLS",
    )

    @validator("rsi_oversold")
    def validate_rsi_oversold(cls, v, values):
        if "rsi_overbought" in values and v >= values["rsi_overbought"]:
            raise ValueError("rsi_oversold must be less than rsi_overbought")
        return v

    @validator("symbols")
    def validate_symbols(cls, v):
        symbols = [s.strip() for s in v.split(",") if s.strip()]
        if not symbols:
            raise ValueError("At least one symbol must be provided")
        return v

    @validator("log_level")
    def validate_log_level(cls, v):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v_upper

    @property
    def symbol_list(self) -> List[str]:
        """Get symbols as a list"""
        return [s.strip() for s in self.symbols.split(",") if s.strip()]

    @property
    def allowed_origins_list(self) -> List[str]:
        """Get allowed origins as a list"""
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    def to_dict(self) -> dict:
        """Convert to dictionary for app configuration"""
        return self.dict(exclude={"auth_token"})

    @classmethod
    def from_env(cls) -> "ServiceConfig":
        """Create configuration from environment variables"""
        return cls(
            redis_host=os.getenv("REDIS_HOST", "localhost"),
            redis_port=int(os.getenv("REDIS_PORT", "6379")),
            redis_password=os.getenv("REDIS_PASSWORD"),
            redis_db=int(os.getenv("REDIS_DB", "0")),
            grpc_host=os.getenv("GRPC_HOST", "backend"),
            grpc_port=int(os.getenv("GRPC_PORT", "9000")),
            api_host=os.getenv("API_HOST", "0.0.0.0"),
            api_port=int(os.getenv("API_PORT", "8000")),
            auth_token=os.getenv("AUTH_TOKEN"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            allowed_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:3000"),
            rsi_period=int(os.getenv("RSI_PERIOD", "14")),
            ema_period=int(os.getenv("EMA_PERIOD", "14")),
            rsi_oversold=float(os.getenv("RSI_OVERSOLD", "30.0")),
            rsi_overbought=float(os.getenv("RSI_OVERBOUGHT", "70.0")),
            min_signal_strength=float(os.getenv("MIN_SIGNAL_STRENGTH", "0.5")),
            symbols=os.getenv("SYMBOLS", "BTCUSDT,ETHUSDT"),
            weight_trend=float(os.getenv("WEIGHT_TREND", "0.25")),
            weight_momentum=float(os.getenv("WEIGHT_MOMENTUM", "0.30")),
            weight_volatility=float(os.getenv("WEIGHT_VOLATILITY", "0.20")),
            weight_rsi=float(os.getenv("WEIGHT_RSI", "0.15")),
            ema_fast_period=int(os.getenv("EMA_FAST_PERIOD", "9")),
            ema_slow_period=int(os.getenv("EMA_SLOW_PERIOD", "21")),
            macd_fast=int(os.getenv("MACD_FAST", "12")),
            macd_slow=int(os.getenv("MACD_SLOW", "26")),
            macd_signal_period=int(os.getenv("MACD_SIGNAL", "9")),
            bollinger_period=int(os.getenv("BB_PERIOD", "20")),
            bollinger_std=float(os.getenv("BB_STD", "2.0")),
            atr_period=int(os.getenv("ATR_PERIOD", "14")),
            adx_period=int(os.getenv("ADX_PERIOD", "14")),
            roc_period=int(os.getenv("ROC_PERIOD", "10")),
            stoch_rsi_period=int(os.getenv("STOCH_RSI_PERIOD", "14")),
            adx_min_trend=float(os.getenv("ADX_MIN_TREND", "25.0")),
            min_composite_score=float(os.getenv("MIN_COMPOSITE_SCORE", "0.5")),
        )

    def validate_all(self) -> None:
        """Run all validations and log configuration"""
        logger.info("Configuration validated successfully")
        logger.info(f"Redis: {self.redis_host}:{self.redis_port}")
        logger.info(f"API: {self.api_host}:{self.api_port}")
        logger.info(f"gRPC: {self.grpc_host}:{self.grpc_port}")
        logger.info(f"Symbols: {self.symbols}")
        logger.info(
            f"Strategy: RSI({self.rsi_period}), EMA Cross {self.ema_fast_period}/{self.ema_slow_period}, "
            f"MACD({self.macd_fast}/{self.macd_slow}/{self.macd_signal_period}), "
            f"BB({self.bollinger_period},{self.bollinger_std})"
        )
        logger.info(
            f"Weights: trend={self.weight_trend}, momentum={self.weight_momentum}, "
            f"volatility={self.weight_volatility}, rsi={self.weight_rsi}"
        )
        logger.info(f"Min composite score: {self.min_composite_score}")
        logger.info(f"ADX min trend: {self.adx_min_trend}")

        if self.auth_token:
            logger.info("Authentication: ENABLED")
        else:
            logger.warning("Authentication: DISABLED (set AUTH_TOKEN to enable)")


# Backwards compatibility alias
Config = ServiceConfig

# Global configuration instance
config = ServiceConfig.from_env()
