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
    symbols: str = Field(default="BTCUSDT,ETHUSDT", env="SYMBOLS")

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
        return cls()

    def validate_all(self) -> None:
        """Run all validations and log configuration"""
        logger.info("Configuration validated successfully")
        logger.info(f"Redis: {self.redis_host}:{self.redis_port}")
        logger.info(f"API: {self.api_host}:{self.api_port}")
        logger.info(f"gRPC: {self.grpc_host}:{self.grpc_port}")
        logger.info(f"Symbols: {self.symbols}")
        logger.info(f"Strategy: RSI({self.rsi_period}), EMA({self.ema_period})")

        if self.auth_token:
            logger.info("Authentication: ENABLED")
        else:
            logger.warning("Authentication: DISABLED (set AUTH_TOKEN to enable)")


# Global configuration instance
config = ServiceConfig.from_env()
