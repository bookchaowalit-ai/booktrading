"""
FastAPI application for the strategy service.
Provides REST API for strategy control and monitoring.
"""
import asyncio
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from core.domain.models import OrderSide, StrategyConfig, TradeSymbol, OrderSignal
from core.service.strategy import MultiSymbolStrategy, TradingStrategy, MultiSymbolStrategyWithGRPC
from infrastructure.redis.redis_adapter import RedisAdapter
from infrastructure.grpc.grpc_client import GRPCClientManager

# Request/Response models
class StrategyConfigRequest(BaseModel):
    rsi_period: int = 14
    ema_period: int = 14
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    min_signal_strength: float = 0.5


class IndicatorResponse(BaseModel):
    symbol: str
    rsi: Optional[float] = None
    ema: Optional[float] = None
    sma: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None


class SignalResponse(BaseModel):
    symbol: str
    side: str
    strength: float
    reason: str


class HealthResponse(BaseModel):
    status: str
    redis_connected: bool


# Global strategy instance
strategy: Optional[MultiSymbolStrategy] = None
redis_adapter: Optional[RedisAdapter] = None
grpc_client_manager: Optional[GRPCClientManager] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global strategy, redis_adapter, grpc_client_manager
    
    # Startup
    redis_host = app.state.config.get("REDIS_HOST", "localhost")
    redis_port = app.state.config.get("REDIS_PORT", 6379)
    grpc_host = app.state.config.get("GRPC_HOST", "backend")
    grpc_port = app.state.config.get("GRPC_PORT", 9000)
    
    # Initialize gRPC client
    grpc_client_manager = GRPCClientManager(host=grpc_host, port=grpc_port)
    grpc_client_manager.connect_with_retry()
    
    # Initialize Redis adapter
    redis_adapter = RedisAdapter(host=redis_host, port=redis_port)
    await redis_adapter.connect()
    
    # Create order executor callback using gRPC
    def execute_order_via_grpc(signal: OrderSignal) -> bool:
        if grpc_client_manager:
            response = grpc_client_manager.execute_order_with_retry(
                symbol=signal.symbol.value,
                side=signal.side.value,
                quantity=0.001,  # Default quantity, should be configurable
            )
            return response is not None and response.status != "REJECTED"
        return False
    
    # Initialize strategy with gRPC order executor
    strategy = MultiSymbolStrategyWithGRPC(execute_order_via_grpc)
    
    # Start market data consumer in background
    app.state.market_data_task = asyncio.create_task(
        consume_market_data()
    )
    
    yield
    
    # Shutdown
    if hasattr(app.state, "market_data_task"):
        app.state.market_data_task.cancel()
        try:
            await app.state.market_data_task
        except asyncio.CancelledError:
            pass
    
    if redis_adapter:
        await redis_adapter.disconnect()
    
    if grpc_client_manager:
        grpc_client_manager.client.disconnect()


async def consume_market_data():
    """Background task to consume market data and generate signals."""
    global strategy, redis_adapter
    
    async def on_market_data(market_data):
        if strategy:
            signal = strategy.process_market_data(market_data)
            if signal and redis_adapter:
                await redis_adapter.publish_order_signal(signal)
    
    if redis_adapter:
        await redis_adapter.subscribe_market_data(on_market_data)


def create_app(config: Optional[dict] = None) -> FastAPI:
    """Create and configure FastAPI application."""
    
    from fastapi.middleware.cors import CORSMiddleware
    
    app = FastAPI(
        title="Trading Strategy Service",
        description="Technical analysis and trading signal generation service",
        version="1.0.0",
        lifespan=lifespan,
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, specify exact origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    app.state.config = config or {}
    
    # Register routes
    register_routes(app)
    
    return app


def register_routes(app: FastAPI):
    """Register API routes."""
    
    @app.get("/api/health", response_model=HealthResponse)
    async def health_check():
        """Health check endpoint."""
        redis_connected = False
        if redis_adapter:
            redis_connected = await redis_adapter.health_check()
        
        return HealthResponse(
            status="healthy" if redis_connected else "degraded",
            redis_connected=redis_connected,
        )
    
    @app.get("/api/indicators", response_model=Dict[str, IndicatorResponse])
    async def get_indicators():
        """Get current technical indicators for all symbols."""
        if not strategy:
            raise HTTPException(status_code=503, detail="Strategy not initialized")
        
        indicators = strategy.get_all_indicators()
        
        return {
            symbol.value: IndicatorResponse(
                symbol=symbol.value,
                rsi=ind.rsi if ind else None,
                ema=ind.ema if ind else None,
                sma=ind.sma if ind else None,
                macd=ind.macd if ind else None,
                macd_signal=ind.macd_signal if ind else None,
            )
            for symbol, ind in indicators.items()
        }
    
    @app.get("/api/indicators/{symbol}", response_model=IndicatorResponse)
    async def get_indicator_for_symbol(symbol: str):
        """Get technical indicators for a specific symbol."""
        if not strategy:
            raise HTTPException(status_code=503, detail="Strategy not initialized")
        
        try:
            trade_symbol = TradeSymbol(symbol)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid symbol: {symbol}")
        
        indicators = strategy.strategies.get(trade_symbol)
        if not indicators:
            raise HTTPException(status_code=404, detail=f"Symbol not found: {symbol}")
        
        current = indicators.get_current_indicators(trade_symbol)
        
        return IndicatorResponse(
            symbol=symbol,
            rsi=current.rsi if current else None,
            ema=current.ema if current else None,
            sma=current.sma if current else None,
            macd=current.macd if current else None,
            macd_signal=current.macd_signal if current else None,
        )
    
    @app.get("/api/strategy/config", response_model=StrategyConfigRequest)
    async def get_strategy_config():
        """Get current strategy configuration."""
        if not strategy:
            raise HTTPException(status_code=503, detail="Strategy not initialized")
        
        config = strategy.config
        return StrategyConfigRequest(
            rsi_period=config.rsi_period,
            ema_period=config.ema_period,
            rsi_oversold=config.rsi_oversold,
            rsi_overbought=config.rsi_overbought,
            min_signal_strength=config.min_signal_strength,
        )
    
    @app.post("/api/strategy/config")
    async def update_strategy_config(new_config: StrategyConfigRequest):
        """Update strategy configuration."""
        global strategy
        
        config = StrategyConfig(
            rsi_period=new_config.rsi_period,
            ema_period=new_config.ema_period,
            rsi_oversold=new_config.rsi_oversold,
            rsi_overbought=new_config.rsi_overbought,
            min_signal_strength=new_config.min_signal_strength,
        )
        
        strategy = MultiSymbolStrategy(config)
        
        return {"status": "updated", "message": "Strategy configuration updated"}
    
    @app.post("/api/strategy/reset")
    async def reset_strategy():
        """Reset strategy state (clear price history)."""
        global strategy
        
        if not strategy:
            raise HTTPException(status_code=503, detail="Strategy not initialized")
        
        config = strategy.config
        strategy = MultiSymbolStrategy(config)
        
        return {"status": "reset", "message": "Strategy state reset"}


# Create default app instance
app = create_app()
