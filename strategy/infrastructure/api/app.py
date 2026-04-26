"""
FastAPI application for the strategy service.
Provides REST API for strategy control and monitoring.
"""
import asyncio
import logging
import math
import random
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from functools import wraps
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from core.domain.models import OrderSide, StrategyConfig, TradeSymbol, OrderSignal
from core.service.strategy import MultiSymbolStrategy, TradingStrategy, MultiSymbolStrategyWithGRPC
from core.service.indicators import TechnicalAnalysisService
from core.service.scoring import CompositeScorer
from core.service.ai_predictor import AIPredictor, AISignal
from core.service.strategy_recommender import StrategyRecommender, MarketRegime
from core.service.anomaly_detector import AnomalyDetector
from core.service.param_optimizer import ParamOptimizer
from infrastructure.redis.redis_adapter import RedisAdapter
from infrastructure.grpc.grpc_client import GRPCClientManager

logger = logging.getLogger(__name__)

# ── Authentication ──────────────────────────────────────────────────────────────
API_TOKEN: Optional[str] = None  # Set via AUTH_TOKEN env var


def require_auth(request: Request):
    """Validate the Authorization header against the configured API token."""
    if API_TOKEN is None:
        return True  # No token configured — allow all (dev mode)
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return False
    return auth[7:] == API_TOKEN


# ── Rate Limiting ───────────────────────────────────────────────────────────────
class RateLimiter:
    """Simple sliding window rate limiter."""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.clients: dict[str, list[float]] = defaultdict(list)

    def allow(self, client_ip: str) -> bool:
        now = time.time()
        cutoff = now - self.window_seconds
        # Remove old entries
        self.clients[client_ip] = [t for t in self.clients[client_ip] if t > cutoff]
        if len(self.clients[client_ip]) >= self.max_requests:
            return False
        self.clients[client_ip].append(now)
        return True


rate_limiter = RateLimiter(max_requests=60, window_seconds=60)


async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    if not rate_limiter.allow(client_ip):
        return JSONResponse(
            status_code=429,
            content={"error": "Rate limit exceeded. Try again later."},
            headers={"Retry-After": "60"},
        )
    response = await call_next(request)
    return response


# ── Request / Response Models ───────────────────────────────────────────────────
class StrategyConfigRequest(BaseModel):
    rsi_period: int = Field(default=14, gt=0, le=200)
    ema_period: int = Field(default=14, gt=0, le=200)
    rsi_oversold: float = Field(default=30.0, gt=0, lt=100)
    rsi_overbought: float = Field(default=70.0, gt=0, lt=100)
    min_signal_strength: float = Field(default=0.5, gt=0, le=1.0)

    def model_post_init(self, __context):
        if self.rsi_oversold >= self.rsi_overbought:
            raise ValueError("rsi_oversold must be less than rsi_overbought")


class IndicatorResponse(BaseModel):
    symbol: str
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
    ema_cross: Optional[str] = None
    adx: Optional[float] = None
    roc: Optional[float] = None
    obv_trend: Optional[float] = None


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
    initial_capital: float = Field(default=10000.0, gt=0)
    leverage: float = Field(default=1.0, gt=0, le=100)
    strategy: str = "moderate"
    commission: float = Field(default=0.001, ge=0, lt=0.1)
    slippage: float = Field(default=0.0005, ge=0, lt=0.1)


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


# ── Auth Middleware for Protected Endpoints ─────────────────────────────────────
HEALTH_ENDPOINTS = {"/api/health"}


def auth_required(func):
    """Decorator that enforces authentication on an endpoint."""

    @wraps(func)
    async def wrapper(*args, request: Request = None, **kwargs):
        if not require_auth(request):
            raise HTTPException(status_code=401, detail="Invalid or missing API token")
        return await func(*args, request=request, **kwargs)

    return wrapper


# ── Global Strategy Instance ────────────────────────────────────────────────────
strategy: Optional[MultiSymbolStrategy] = None
redis_adapter: Optional[RedisAdapter] = None
grpc_client_manager: Optional[GRPCClientManager] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global strategy, redis_adapter, grpc_client_manager

    # Startup
    redis_host = app.state.config.get("redis_host", "localhost")
    redis_port = app.state.config.get("redis_port", 6379)
    redis_password = app.state.config.get("redis_password") or None
    grpc_host = app.state.config.get("grpc_host", "backend")
    grpc_port = app.state.config.get("grpc_port", 9000)

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

    # Build StrategyConfig from app config (which contains env vars)
    symbols_str = app.state.config.get("symbols", "BTCUSDT,ETHUSDT")
    symbol_list = [s.strip() for s in symbols_str.split(",") if s.strip()]
    trade_symbols = []
    for sym_str in symbol_list:
        try:
            trade_symbols.append(TradeSymbol(sym_str))
        except ValueError:
            sym = TradeSymbol.__new__(TradeSymbol, sym_str)
            sym._name_ = sym_str
            sym._value_ = sym_str
            sym._sorted_ = False
            TradeSymbol._member_map_[sym_str] = sym
            TradeSymbol._value2member_map_[sym_str] = sym
            TradeSymbol._member_names_.append(sym_str)
            trade_symbols.append(sym)

    strategy_config = StrategyConfig(
        rsi_period=int(app.state.config.get("rsi_period", 14)),
        ema_period=int(app.state.config.get("ema_period", 14)),
        rsi_oversold=float(app.state.config.get("rsi_oversold", 30.0)),
        rsi_overbought=float(app.state.config.get("rsi_overbought", 70.0)),
        min_signal_strength=float(app.state.config.get("min_signal_strength", 0.5)),
        weight_trend=float(app.state.config.get("weight_trend", 0.25)),
        weight_momentum=float(app.state.config.get("weight_momentum", 0.30)),
        weight_volatility=float(app.state.config.get("weight_volatility", 0.20)),
        weight_rsi=float(app.state.config.get("weight_rsi", 0.15)),
        ema_fast_period=int(app.state.config.get("ema_fast_period", 9)),
        ema_slow_period=int(app.state.config.get("ema_slow_period", 21)),
        macd_fast=int(app.state.config.get("macd_fast", 12)),
        macd_slow=int(app.state.config.get("macd_slow", 26)),
        macd_signal=int(app.state.config.get("macd_signal_period", 9)),
        bollinger_period=int(app.state.config.get("bollinger_period", 20)),
        bollinger_std=float(app.state.config.get("bollinger_std", 2.0)),
        atr_period=int(app.state.config.get("atr_period", 14)),
        adx_period=int(app.state.config.get("adx_period", 14)),
        roc_period=int(app.state.config.get("roc_period", 10)),
        stoch_rsi_period=int(app.state.config.get("stoch_rsi_period", 14)),
        adx_min_trend=float(app.state.config.get("adx_min_trend", 25.0)),
        min_composite_score=float(app.state.config.get("min_composite_score", 0.5)),
        symbols=trade_symbols,
    )

    # Initialize strategy with gRPC order executor
    strategy = MultiSymbolStrategyWithGRPC(execute_order_via_grpc, config=strategy_config)

    # Start market data consumer in background with error handling
    app.state.market_data_task = asyncio.create_task(
        consume_market_data_safe()
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


async def consume_market_data_safe():
    """Background task to consume market data with proper error handling."""
    global strategy, redis_adapter

    async def on_market_data(market_data):
        try:
            if strategy:
                signal = strategy.process_market_data(market_data)
                if signal and redis_adapter:
                    await redis_adapter.publish_order_signal(signal)
        except Exception:
            logger.exception("Error processing market data for %s", market_data.symbol if market_data else "unknown")

    if redis_adapter:
        try:
            await redis_adapter.subscribe_market_data(on_market_data)
        except Exception:
            logger.exception("Market data subscription failed")
            # Reconnect loop
            while True:
                try:
                    logger.info("Attempting to reconnect to market data...")
                    await asyncio.sleep(5)
                    await redis_adapter.subscribe_market_data(on_market_data)
                    logger.info("Reconnected to market data successfully")
                    break
                except Exception:
                    logger.exception("Failed to reconnect to market data, retrying in 5s")
                    await asyncio.sleep(5)


def create_app(config: Optional[dict] = None) -> FastAPI:
    """Create and configure FastAPI application."""

    from fastapi.middleware.cors import CORSMiddleware
    import os

    app = FastAPI(
        title="Trading Strategy Service",
        description="Technical analysis and trading signal generation service",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS: restrict to configured origins
    allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in allowed_origins],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate limiting middleware
    app.middleware("http")(rate_limit_middleware)

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"},
        )

    app.state.config = config or {}

    # Set auth token from env
    global API_TOKEN
    API_TOKEN = os.getenv("AUTH_TOKEN", None)

    # Register routes
    register_routes(app)

    return app


def register_routes(app: FastAPI):
    """Register API routes."""

    @app.get("/api/health", response_model=HealthResponse)
    async def health_check():
        """Health check endpoint (no auth required)."""
        redis_connected = False
        if redis_adapter:
            redis_connected = await redis_adapter.health_check()

        return HealthResponse(
            status="healthy" if redis_connected else "degraded",
            redis_connected=redis_connected,
        )

    @app.get("/api/indicators", response_model=Dict[str, IndicatorResponse])
    async def get_indicators(request: Request):
        """Get current technical indicators for all symbols (public - no auth required)."""
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
                bb_upper=ind.bb_upper if ind else None,
                bb_lower=ind.bb_lower if ind else None,
                bb_width=ind.bb_width if ind else None,
                atr=ind.atr if ind else None,
                stoch_k=ind.stoch_k if ind else None,
                stoch_d=ind.stoch_d if ind else None,
                macd_histogram=ind.macd_histogram if ind else None,
                ema_fast=ind.ema_fast if ind else None,
                ema_slow=ind.ema_slow if ind else None,
                ema_cross=ind.ema_cross if ind else None,
                adx=ind.adx if ind else None,
                roc=ind.roc if ind else None,
                obv_trend=ind.obv_trend if ind else None,
            )
            for symbol, ind in indicators.items()
        }

    @app.get("/api/indicators/{symbol}", response_model=IndicatorResponse)
    async def get_indicator_for_symbol(symbol: str, request: Request):
        """Get technical indicators for a specific symbol (public - no auth required)."""
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
            bb_upper=current.bb_upper if current else None,
            bb_lower=current.bb_lower if current else None,
            bb_width=current.bb_width if current else None,
            atr=current.atr if current else None,
            stoch_k=current.stoch_k if current else None,
            stoch_d=current.stoch_d if current else None,
            macd_histogram=current.macd_histogram if current else None,
            ema_fast=current.ema_fast if current else None,
            ema_slow=current.ema_slow if current else None,
            ema_cross=current.ema_cross if current else None,
            adx=current.adx if current else None,
            roc=current.roc if current else None,
            obv_trend=current.obv_trend if current else None,
        )

    @app.get("/api/strategy/config", response_model=StrategyConfigRequest)
    @auth_required
    async def get_strategy_config(request: Request):
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
    @auth_required
    async def update_strategy_config(new_config: StrategyConfigRequest, request: Request):
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
    @auth_required
    async def reset_strategy(request: Request):
        """Reset strategy state (clear price history)."""
        global strategy

        if not strategy:
            raise HTTPException(status_code=503, detail="Strategy not initialized")

        config = strategy.config
        strategy = MultiSymbolStrategy(config)

        return {"status": "reset", "message": "Strategy state reset"}

    @app.get("/api/signals")
    @auth_required
    async def get_signals(request: Request):
        """
        Get current trading signals for all symbols.
        Uses composite scoring from all indicators.
        """
        if not strategy:
            raise HTTPException(status_code=503, detail="Strategy not initialized")

        signals: List[SignalResponse] = []
        config = strategy.config

        for symbol, sym_strategy in strategy.strategies.items():
            indicators = sym_strategy.get_current_indicators(symbol)
            if indicators is None:
                continue

            # Get current price from history
            history = sym_strategy.get_price_history(symbol)
            if not history:
                continue
            price = history[-1].price

            # Calculate composite score
            composite_score, breakdown = CompositeScorer.composite(
                indicators, price, config
            )

            threshold = config.min_composite_score
            side: Optional[str] = None

            if composite_score > threshold:
                side = OrderSide.BUY.value
            elif composite_score < -threshold:
                side = OrderSide.SELL.value

            if side is None:
                continue

            # Build reason from breakdown
            reasons = []
            for comp in ("trend", "momentum", "volatility", "rsi"):
                if comp in breakdown:
                    reasons.append(breakdown[comp].get("reason", ""))

            strength = round(abs(composite_score), 4)

            signals.append(SignalResponse(
                symbol=symbol.value,
                side=side,
                strength=strength,
                reason=f"Score={composite_score:.3f}: " + "; ".join(r for r in reasons if r),
            ))

        market_sentiment = round(sum(s.strength for s in signals) / len(signals), 4) if signals else 0.0

        return {
            "signals": [s.model_dump() for s in signals],
            "market_sentiment": market_sentiment,
        }

    @app.get("/api/strategies")
    @auth_required
    async def get_available_strategies(request: Request):
        """List all available strategies."""
        return {
            "strategies": [
                {"name": "rsi", "description": "RSI Oversold/Overbought", "params": ["rsi_period", "rsi_oversold", "rsi_overbought"]},
                {"name": "ema_cross", "description": "EMA Crossover", "params": ["ema_fast_period", "ema_slow_period"]},
                {"name": "macd", "description": "MACD Signal Crossover", "params": ["macd_fast", "macd_slow", "macd_signal"]},
            ]
        }

    @app.post("/api/backtest", response_model=BacktestResponse)
    @auth_required
    async def run_backtest(req: BacktestRequest, request: Request):
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

    # ── AI Endpoints ──

    @app.post("/api/ai/predict")
    @auth_required
    async def ai_predict(request: Request):
        """AI-powered trade signal prediction."""
        body = await request.json()
        prices = body.get("prices", [])
        volumes = body.get("volumes")

        if len(prices) < 50:
            raise HTTPException(status_code=400, detail="Need at least 50 price points for AI prediction")

        predictor = AIPredictor()
        prediction = predictor.predict(prices, volumes)

        return {
            "signal": prediction.signal.value,
            "confidence": prediction.confidence,
            "predicted_direction": prediction.predicted_direction,
            "feature_importance": prediction.feature_importance,
            "reason": prediction.reason,
        }

    @app.get("/api/ai/recommend")
    @auth_required
    async def ai_recommend(request: Request):
        """Get AI strategy recommendation based on current market data."""
        prices_str = request.query_params.get("prices")
        if not prices_str:
            raise HTTPException(status_code=400, detail="prices query param required (comma-separated)")

        prices = [float(p) for p in prices_str.split(",")]
        if len(prices) < 50:
            raise HTTPException(status_code=400, detail="Need at least 50 price points")

        recommender = StrategyRecommender()
        rec = recommender.recommend(prices)

        return {
            "regime": rec.regime.value,
            "recommended_strategy": rec.recommended_strategy.value,
            "confidence": rec.confidence,
            "suggested_params": rec.suggested_params,
            "reasoning": rec.reasoning,
            "regime_scores": rec.regime_scores,
        }

    @app.post("/api/ai/anomalies")
    @auth_required
    async def detect_anomalies(request: Request):
        """Detect anomalies in trading data."""
        body = await request.json()
        prices = body.get("prices", [])
        volumes = body.get("volumes")

        if len(prices) < 30:
            raise HTTPException(status_code=400, detail="Need at least 30 price points")

        detector = AnomalyDetector()
        report = detector.detect(prices, volumes)

        return {
            "anomalies": [
                {
                    "type": a.type.value,
                    "severity": a.severity,
                    "timestamp": a.timestamp,
                    "description": a.description,
                    "recommendation": a.recommendation,
                    "data": a.data_point,
                }
                for a in report.anomalies
            ],
            "overall_risk": report.overall_risk,
            "healthy_score": report.healthy_score,
            "summary": report.summary,
        }

    @app.post("/api/ai/optimize")
    @auth_required
    async def optimize_params(request: Request):
        """Auto-optimize strategy parameters."""
        body = await request.json()
        prices = body.get("prices", [])
        strategy_type = body.get("strategy", "rsi")

        if len(prices) < 100:
            raise HTTPException(status_code=400, detail="Need at least 100 price points for optimization")

        optimizer = ParamOptimizer()

        if strategy_type == "rsi":
            result = optimizer.optimize_rsi(prices)
        elif strategy_type == "ema_cross":
            result = optimizer.optimize_ema_cross(prices)
        else:
            raise HTTPException(status_code=400, detail="Supported strategies: rsi, ema_cross")

        return {
            "optimal_params": result.params,
            "score": result.score,
            "total_trades": result.total_trades,
            "win_rate": result.win_rate,
            "profit_factor": result.profit_factor,
            "max_drawdown": result.max_drawdown,
            "total_return": result.total_return,
        }

    @app.get("/api/ai/dashboard")
    @auth_required
    async def ai_dashboard(request: Request):
        """Get comprehensive AI analysis in one call."""
        prices_str = request.query_params.get("prices")
        volumes_str = request.query_params.get("volumes")

        if not prices_str:
            raise HTTPException(status_code=400, detail="prices query param required")

        prices = [float(p) for p in prices_str.split(",")]
        volumes = [float(v) for v in volumes_str.split(",")] if volumes_str else None

        if len(prices) < 50:
            raise HTTPException(status_code=400, detail="Need at least 50 price points")

        # Run all AI analyses
        predictor = AIPredictor()
        recommender = StrategyRecommender()
        detector = AnomalyDetector()

        prediction = predictor.predict(prices, volumes)
        recommendation = recommender.recommend(prices, volumes)
        anomaly_report = detector.detect(prices, volumes)

        return {
            "prediction": {
                "signal": prediction.signal.value,
                "confidence": prediction.confidence,
                "direction": prediction.predicted_direction,
                "reason": prediction.reason,
                "feature_importance": prediction.feature_importance,
            },
            "recommendation": {
                "regime": recommendation.regime.value,
                "strategy": recommendation.recommended_strategy.value,
                "confidence": recommendation.confidence,
                "params": recommendation.suggested_params,
                "reasoning": recommendation.reasoning,
            },
            "anomalies": {
                "count": len(anomaly_report.anomalies),
                "overall_risk": anomaly_report.overall_risk,
                "health_score": anomaly_report.healthy_score,
                "latest": [
                    {"type": a.type.value, "severity": a.severity, "desc": a.description}
                    for a in anomaly_report.anomalies[:5]
                ],
            },
        }


# Create default app instance
app = create_app()
