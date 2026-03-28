"""
FastAPI application for the strategy service.
Provides REST API for strategy control and monitoring.
"""
import asyncio
import math
import random
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from core.domain.models import OrderSide, StrategyConfig, TradeSymbol, OrderSignal
from core.service.strategy import MultiSymbolStrategy, TradingStrategy, MultiSymbolStrategyWithGRPC
from core.service.indicators import TechnicalAnalysisService
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


class BacktestRequest(BaseModel):
    symbol: str = "BTCUSDT"
    start_date: str = "2024-01-01"
    end_date: str = "2024-12-31"
    initial_capital: float = 10000.0
    leverage: float = 1.0
    strategy: str = "moderate"
    commission: float = 0.001
    slippage: float = 0.0005


class BacktestResponse(BaseModel):
    total_return: float
    total_return_percent: float
    total_trades: int
    win_rate: float
    profit_factor: float
    max_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    avg_win: float
    avg_loss: float
    best_trade: float
    worst_trade: float


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
    redis_password = app.state.config.get("REDIS_PASSWORD", "") or None
    grpc_host = app.state.config.get("GRPC_HOST", "backend")
    grpc_port = app.state.config.get("GRPC_PORT", 9000)
    
    # Initialize gRPC client
    grpc_client_manager = GRPCClientManager(host=grpc_host, port=grpc_port)
    grpc_client_manager.connect_with_retry()
    
    # Initialize Redis adapter
    redis_adapter = RedisAdapter(host=redis_host, port=redis_port, password=redis_password)
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

    @app.get("/api/signals")
    async def get_signals():
        """
        Get current trading signals for all symbols.
        Derives signals from current indicators using the same RSI logic as the live strategy.
        """
        if not strategy:
            raise HTTPException(status_code=503, detail="Strategy not initialized")

        signals: List[SignalResponse] = []
        config = strategy.config

        for symbol, sym_strategy in strategy.strategies.items():
            indicators = sym_strategy.get_current_indicators(symbol)
            if indicators is None or indicators.rsi is None:
                continue

            rsi = indicators.rsi
            side: Optional[str] = None
            reason = ""

            if rsi < config.rsi_oversold:
                side = OrderSide.BUY.value
                reason = f"RSI oversold ({rsi:.2f} < {config.rsi_oversold})"
            elif rsi > config.rsi_overbought:
                side = OrderSide.SELL.value
                reason = f"RSI overbought ({rsi:.2f} > {config.rsi_overbought})"

            if side is None:
                continue

            # Simple strength calculation based on RSI distance from threshold
            if side == OrderSide.BUY.value:
                strength = min(1.0, (config.rsi_oversold - rsi) / config.rsi_oversold)
            else:
                strength = min(1.0, (rsi - config.rsi_overbought) / (100 - config.rsi_overbought))

            signals.append(SignalResponse(
                symbol=symbol.value,
                side=side,
                strength=round(strength, 4),
                reason=reason,
            ))

        market_sentiment = round(sum(s.strength for s in signals) / len(signals), 4) if signals else 0.0

        return {
            "signals": [s.dict() for s in signals],
            "market_sentiment": market_sentiment,
        }

    @app.post("/api/backtest", response_model=BacktestResponse)
    async def run_backtest(req: BacktestRequest):
        """
        Run a backtest simulation using RSI+EMA strategy on synthetic price data.
        Generates realistic OHLCV data using geometric Brownian motion, then
        applies the configured strategy to produce performance metrics.
        """
        try:
            start = datetime.strptime(req.start_date, "%Y-%m-%d")
            end = datetime.strptime(req.end_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

        days = (end - start).days
        if days < 2:
            raise HTTPException(status_code=400, detail="Date range must be at least 2 days.")
        if days > 1825:
            raise HTTPException(status_code=400, detail="Date range must be at most 5 years.")

        # ── Simulate daily prices via geometric Brownian motion ──
        rng = random.Random(hash(req.symbol + req.start_date))
        mu = 0.0003        # daily drift
        sigma = 0.025      # daily volatility
        seed_price = {"BTCUSDT": 40000, "ETHUSDT": 2200}.get(req.symbol.upper(), 100)
        prices: List[float] = [seed_price]
        for _ in range(days):
            ret = mu + sigma * rng.gauss(0, 1)
            prices.append(prices[-1] * math.exp(ret))

        # ── Apply RSI+EMA strategy ──
        rsi_period = 14
        ema_period = 14
        ta = TechnicalAnalysisService(rsi_period=rsi_period, ema_period=ema_period)

        capital = req.initial_capital
        position: Optional[float] = None   # entry price when in position
        position_size: float = 0.0
        trades: List[float] = []           # PnL per trade
        peak_capital = capital
        max_drawdown_pct = 0.0

        for i in range(rsi_period + 1, len(prices)):
            window = prices[:i]
            rsi = ta.calculate_rsi(window)
            ema = ta.calculate_ema(window)
            price = prices[i]

            if rsi is None or ema is None:
                continue

            commission_cost = req.commission
            slippage_cost = req.slippage

            # ── Entry: RSI oversold + price above EMA → BUY ──
            if position is None and rsi < 30 and price > ema:
                position = price * (1 + slippage_cost)
                position_size = (capital * req.leverage) / position
                capital -= position * position_size * commission_cost

            # ── Exit: RSI overbought → SELL ──
            elif position is not None and rsi > 70:
                exit_price = price * (1 - slippage_cost)
                pnl = (exit_price - position) * position_size
                pnl -= exit_price * position_size * commission_cost
                capital += pnl
                trades.append(pnl)
                position = None
                position_size = 0.0

            # Track drawdown
            if capital > peak_capital:
                peak_capital = capital
            drawdown = (peak_capital - capital) / peak_capital * 100
            if drawdown > max_drawdown_pct:
                max_drawdown_pct = drawdown

        # Close open position at last price
        if position is not None:
            exit_price = prices[-1] * (1 - req.slippage)
            pnl = (exit_price - position) * position_size
            pnl -= exit_price * position_size * req.commission
            capital += pnl
            trades.append(pnl)

        total_return = capital - req.initial_capital
        total_return_pct = (total_return / req.initial_capital) * 100

        wins = [t for t in trades if t > 0]
        losses = [t for t in trades if t <= 0]
        win_rate = (len(wins) / len(trades) * 100) if trades else 0.0
        avg_win = sum(wins) / len(wins) if wins else 0.0
        avg_loss = abs(sum(losses) / len(losses)) if losses else 0.0
        profit_factor = (sum(wins) / abs(sum(losses))) if losses and sum(losses) != 0 else (sum(wins) if wins else 0.0)

        # Sharpe ratio (annualised, simplified)
        daily_returns = []
        for t in trades:
            daily_returns.append(t / req.initial_capital)
        if len(daily_returns) > 1:
            import statistics
            mean_r = statistics.mean(daily_returns)
            std_r = statistics.stdev(daily_returns)
            sharpe = (mean_r / std_r * math.sqrt(252)) if std_r > 0 else 0.0
            neg_returns = [r for r in daily_returns if r < 0]
            std_neg = statistics.stdev(neg_returns) if len(neg_returns) > 1 else std_r
            sortino = (mean_r / std_neg * math.sqrt(252)) if std_neg > 0 else 0.0
        else:
            sharpe = sortino = 0.0

        return BacktestResponse(
            total_return=round(total_return, 2),
            total_return_percent=round(total_return_pct, 2),
            total_trades=len(trades),
            win_rate=round(win_rate, 1),
            profit_factor=round(profit_factor, 2),
            max_drawdown=round(max_drawdown_pct, 2),
            sharpe_ratio=round(sharpe, 2),
            sortino_ratio=round(sortino, 2),
            avg_win=round(avg_win, 2),
            avg_loss=round(avg_loss, 2),
            best_trade=round(max(trades), 2) if trades else 0.0,
            worst_trade=round(min(trades), 2) if trades else 0.0,
        )


# Create default app instance
app = create_app()
