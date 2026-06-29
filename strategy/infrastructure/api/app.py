"""
FastAPI application for the strategy service.
Provides REST API for strategy control and monitoring.
"""
import asyncio
import logging
import math
import os
import random
import time
import httpx
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

# ── Configuration ──────────────────────────────────────────────────────────────
API_TOKEN: Optional[str] = None  # Set via AUTH_TOKEN env var
DISABLE_PAPER_BOT = os.getenv("DISABLE_PAPER_BOT", "false").lower() in ("true", "1", "yes")


def require_auth(request: Request):
    """Validate the Authorization header against the configured API token."""
    if not API_TOKEN:  # None or empty string = dev mode, allow all
        return True
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

    # Initialize Redis adapter (non-fatal: grid bot uses paper engine HTTP, not Redis)
    redis_adapter = RedisAdapter(host=redis_host, port=redis_port, password=redis_password)
    try:
        await redis_adapter.connect()
    except Exception as e:
        logger.warning("Redis unavailable at startup, continuing without it: %s", e)
        redis_adapter = None

    # Start Brain intelligence layer (before grid bot, since grid bot queries it)
    from app.brain.brain import get_brain
    brain = get_brain()
    await brain.start()
    logger.info("Brain intelligence layer started (technical + funding + sentiment)")

    # Start grid trading bot as background task (PAPER trading)
    if DISABLE_PAPER_BOT:
        logger.info("Paper trading bot DISABLED via DISABLE_PAPER_BOT env var")
        app.state.grid_bot_task = None
    else:
        from app.grid_bot import get_grid_bot
        grid_bot = get_grid_bot()
        app.state.grid_bot_task = asyncio.create_task(grid_bot.start())
        logger.info("Grid trading bot started (BTC + ETH paper trading)")

    # Start REAL grid trading bot as background task
    from app.real_grid_bot import get_real_grid_bot
    real_grid_bot = get_real_grid_bot()
    # Inject Redis client for state persistence
    if redis_adapter and redis_adapter.redis:
        real_grid_bot.set_redis(redis_adapter.redis)
    app.state.real_grid_bot_task = asyncio.create_task(real_grid_bot.start())
    logger.info("Real grid trading bot started (BTCTHB — real orders)")

    # Start Polymarket Paper Trading Bot
    from app.polymarket.paper_bot import get_poly_paper_bot
    poly_paper_bot = get_poly_paper_bot()
    if redis_adapter and redis_adapter.redis:
        poly_paper_bot.set_redis(redis_adapter.redis)
    await poly_paper_bot.start()
    logger.info("Polymarket paper trading bot started (prediction market simulation)")

    # Start Arbitrage Paper Trading Bot
    from app.arbitrage_paper_bot import get_arb_paper_bot
    arb_paper_bot = get_arb_paper_bot()
    if redis_adapter and redis_adapter.redis:
        arb_paper_bot._redis = redis_adapter.redis
    await arb_paper_bot.start()
    logger.info("Arbitrage paper trading bot started (cross-exchange simulation)")

    # Start webhook notifier for Telegram/Discord alerts
    from app.webhook_notifier import get_webhook_notifier
    webhook_notifier = get_webhook_notifier()
    await webhook_notifier.start()
    logger.info("Webhook notifier started (Telegram/Discord alerts)")

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

    # Start background market intelligence scanner
    if app.state.config.get("market_intel_enabled", True):
        app.state.market_intel_task = asyncio.create_task(
            _background_market_scan(app)
        )
        logger.info("Background market intelligence scanner started (5min interval)")
    else:
        app.state.market_intel_task = None

    yield

    # Shutdown
    # Stop Brain intelligence layer
    from app.brain.brain import get_brain
    brain = get_brain()
    await brain.stop()

    # Stop webhook notifier
    from app.webhook_notifier import get_webhook_notifier
    webhook_notifier = get_webhook_notifier()
    await webhook_notifier.stop()

    # Stop Polymarket paper bot
    from app.polymarket.paper_bot import get_poly_paper_bot
    poly_paper_bot = get_poly_paper_bot()
    await poly_paper_bot.stop()

    if hasattr(app.state, "real_grid_bot_task"):
        app.state.real_grid_bot_task.cancel()
        try:
            await app.state.real_grid_bot_task
        except asyncio.CancelledError:
            pass

    if hasattr(app.state, "market_intel_task") and app.state.market_intel_task:
        app.state.market_intel_task.cancel()
        try:
            await app.state.market_intel_task
        except asyncio.CancelledError:
            pass

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


# ── Background Market Intelligence Scanner ─────────────────────────────────────
# In-memory alert storage (capped at 100 entries)
_market_alerts: list = []
_MAX_ALERTS = 100
_last_scan_result: dict = {}


async def _background_market_scan(app_instance):
    """
    Periodically scan markets for opportunities and store high-severity alerts.
    Runs every 5 minutes.
    """
    global _market_alerts, _last_scan_result
    await asyncio.sleep(30)  # Wait for startup to complete

    while True:
        try:
            cfg = app_instance.state.config
            if not cfg.get("market_intel_enabled", True):
                await asyncio.sleep(300)
                continue

            from app.market_intel import get_scanner
            crypto_syms = [s.strip() for s in cfg.get("market_intel_crypto_symbols", "BTCTHB,ETHTHB,BTCUSDT,ETHUSDT").split(",") if s.strip()]
            stock_syms = [s.strip() for s in cfg.get("market_intel_stock_symbols", "SPY,QQQ,AAPL,MSFT,GOOGL").split(",") if s.strip()]
            sources = [s.strip() for s in cfg.get("market_intel_sources", "crypto,prediction,stocks,macro,airdrops,degen,binance_alpha,arb").split(",") if s.strip()]

            scanner = get_scanner(
                crypto_symbols=crypto_syms,
                stock_symbols=stock_syms,
                polymarket_gamma_api=cfg.get("polymarket_gamma_api", "https://gamma-api.polymarket.com"),
                polymarket_clob_api=cfg.get("polymarket_clob_api", "https://clob.polymarket.com"),
                enabled_sources=sources,
            )

            result = await scanner.scan_all(min_confidence=0.4)
            _last_scan_result = result.model_dump()

            # Log signals to performance tracker
            try:
                from app.market_intel.signal_logger import get_signal_logger
                signal_logger = get_signal_logger(redis_adapter.redis if redis_adapter and redis_adapter.redis else None)
                for opp in result.opportunities:
                    await signal_logger.log_signal(
                        symbol=opp.symbol,
                        market_type=opp.market_type.value,
                        source=opp.source,
                        signal_type=opp.opportunity_type.value,
                        severity=opp.severity.value,
                        title=opp.title,
                        price_at_signal=opp.current_price,
                        confidence=opp.confidence,
                        metadata=opp.metadata if hasattr(opp, 'metadata') else {},
                    )
            except Exception as e:
                logger.warning(f"Failed to log signals: {e}")

            # Extract high/critical severity alerts
            from app.market_intel.models import Severity
            new_alerts = [
                {
                    "id": opp.opportunity_id,
                    "symbol": opp.symbol,
                    "market": opp.market_type.value,
                    "source": opp.source,
                    "type": opp.opportunity_type.value,
                    "severity": opp.severity.value,
                    "title": opp.title,
                    "description": opp.description,
                    "price": opp.current_price,
                    "confidence": opp.confidence,
                    "timestamp": opp.timestamp.isoformat() if opp.timestamp else None,
                }
                for opp in result.opportunities
                if opp.severity in (Severity.HIGH, Severity.CRITICAL)
            ]

            if new_alerts:
                _market_alerts.extend(new_alerts)
                # Cap the list
                if len(_market_alerts) > _MAX_ALERTS:
                    _market_alerts = _market_alerts[-_MAX_ALERTS:]
                logger.info(f"Market scan: {result.total_opportunities} opps, {len(new_alerts)} high-severity alerts")

                # Send Telegram notifications for new high-severity alerts
                try:
                    from app.webhook_notifier import get_webhook_notifier
                    notifier = get_webhook_notifier()
                    for alert in new_alerts[:5]:  # Limit to top 5 to avoid spam
                        await notifier.send_market_opportunity(
                            symbol=alert["symbol"],
                            market=alert["market"],
                            severity=alert["severity"],
                            title=alert["title"],
                            description=alert["description"],
                            confidence=alert["confidence"],
                            price=alert.get("price", 0),
                            opp_type=alert.get("type", ""),
                        )
                    # Send summary if significant opportunities found
                    if result.total_opportunities > 0:
                        top_3 = [
                            {
                                "symbol": opp.symbol,
                                "title": opp.title,
                                "confidence": opp.confidence,
                            }
                            for opp in result.opportunities[:3]
                        ]
                        await notifier.send_market_scan_summary(
                            total_opps=result.total_opportunities,
                            by_severity=result.by_severity,
                            by_market=result.by_market,
                            top_opps=top_3,
                        )
                except Exception as notif_err:
                    logger.debug(f"Notification send skipped: {notif_err}")
            else:
                logger.debug(f"Market scan: {result.total_opportunities} opps, no high-severity alerts")

        except Exception as e:
            logger.error(f"Background market scan failed: {e}")

        await asyncio.sleep(300)  # 5 minutes


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

    # ── Paper Grid Bot Endpoints ──

    @app.get("/api/grid/status")
    async def paper_grid_status():
        """Get paper grid bot status (geometric + DGT + confluence)."""
        from app.grid_bot import get_grid_bot
        bot = get_grid_bot()
        return bot.get_status()

    # ── Real Grid Bot Endpoints ──

    @app.get("/api/real-grid/status")
    async def real_grid_status():
        """Get real grid bot status."""
        from app.real_grid_bot import get_real_grid_bot
        bot = get_real_grid_bot()
        return bot.get_status()

    @app.post("/api/real-grid/kill")
    @auth_required
    async def real_grid_kill(request: Request):
        """Kill switch — halt all real trading."""
        from app.real_grid_bot import get_real_grid_bot
        bot = get_real_grid_bot()
        bot.disable()
        return {"status": "killed", "message": "All real trading halted"}

    @app.post("/api/real-grid/enable")
    @auth_required
    async def real_grid_enable(request: Request):
        """Re-enable real grid bot after kill switch."""
        from app.real_grid_bot import get_real_grid_bot
        bot = get_real_grid_bot()
        bot.enable()
        return {"status": "enabled", "message": "Real trading resumed"}

    @app.get("/api/real-grid/notifications")
    async def real_grid_notifications(limit: int = 20):
        """Get recent fill notifications from the real grid bot."""
        from app.real_grid_bot import get_real_grid_bot
        bot = get_real_grid_bot()
        return bot.get_notifications(limit=limit)

    @app.get("/api/real-grid/health")
    async def real_grid_health():
        """Get health status with stuck detection."""
        from app.real_grid_bot import get_real_grid_bot
        bot = get_real_grid_bot()
        return bot.get_health()

    @app.post("/api/real-grid/restart")
    @auth_required
    async def real_grid_restart(request: Request):
        """Force restart the bot (re-sync open orders, clear stuck state)."""
        from app.real_grid_bot import get_real_grid_bot
        bot = get_real_grid_bot()
        success = await bot.force_restart()
        if success:
            return {"status": "restarted", "message": "Bot re-synced successfully"}
        raise HTTPException(status_code=500, detail="Restart failed")

    @app.get("/api/real-grid/config/{symbol}")
    async def real_grid_config_get(symbol: str):
        """Get current grid config for a symbol."""
        from app.real_grid_bot import get_real_grid_bot
        bot = get_real_grid_bot()
        config = bot.get_config(symbol.upper())
        if config:
            return config
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")

    @app.put("/api/real-grid/config/{symbol}")
    @auth_required
    async def real_grid_config_update(symbol: str, request: dict):
        """Update grid config for a symbol.
        
        Body: {"grid_spacing_pct": 2.0, "grid_levels": 3, "order_size": 0.00005, ...}
        """
        from app.real_grid_bot import get_real_grid_bot
        bot = get_real_grid_bot()
        success = bot.update_config(symbol.upper(), **request)
        if success:
            return {"status": "updated", "symbol": symbol.upper(), "config": request}
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")

    # ── Performance Metrics Endpoint ──

    @app.get("/api/real-grid/performance")
    async def real_grid_performance():
        """Get performance metrics for all symbols: fill rates, ATR spacing, profit velocity, compound recommendations."""
        from app.real_grid_bot import get_real_grid_bot
        bot = get_real_grid_bot()
        return bot.get_performance()

    # ── Risk Manager Endpoints ──

    @app.get("/api/risk/status")
    async def risk_status():
        """Get risk manager status and metrics."""
        from app.risk_manager import get_risk_manager
        rm = get_risk_manager()
        return rm.get_status()

    @app.post("/api/risk/reset")
    @auth_required
    async def risk_reset(request: Request):
        """Reset risk manager kill switch."""
        from app.risk_manager import get_risk_manager
        rm = get_risk_manager()
        rm.reset_kill_switch()
        return {"status": "reset", "message": "Risk manager kill switch reset"}

    # ── Brain Intelligence Layer Endpoints ──

    @app.get("/api/brain/status")
    async def brain_status():
        """Get Brain intelligence layer status — all directives and layer signals."""
        from app.brain.brain import get_brain
        brain = get_brain()
        return {
            "running": brain._running,
            "directives": brain.get_all_directives(),
            "refresh_interval": brain._refresh_interval,
            "circuit_breaker": brain.circuit_breaker.get_status(),
        }

    @app.get("/api/brain/directive/{symbol}")
    async def brain_directive(symbol: str, current_price: float = 0.0):
        """Get current Brain directive for a specific symbol."""
        from app.brain.brain import get_brain
        brain = get_brain()
        directive = await brain.get_directive(symbol.upper(), current_price=current_price)
        return {
            "symbol": directive.symbol,
            "spacing_multiplier": directive.spacing_multiplier,
            "center_offset_pct": directive.center_offset_pct,
            "pause_buys": directive.pause_buys,
            "pause_sells": directive.pause_sells,
            "confidence": directive.confidence,
            "technical": directive.technical,
            "funding": directive.funding,
            "sentiment": directive.sentiment,
            "updated_at": directive.updated_at,
        }

    @app.post("/api/brain/refresh")
    @auth_required
    async def brain_refresh(request: Request):
        """Force refresh all Brain signals (bypass cache)."""
        from app.brain.brain import get_brain
        brain = get_brain()
        # Clear cache to force refresh on next get_directive
        brain._last_refresh.clear()
        return {"status": "refreshed", "message": "Brain signals will refresh on next grid tick"}

    @app.post("/api/brain/reset-cb")
    async def brain_reset_cb(symbol: str = None):
        """Manually reset circuit breaker for a symbol (or all if symbol not specified)."""
        from app.brain.brain import get_brain
        brain = get_brain()
        brain.circuit_breaker.reset(symbol.upper() if symbol else None)
        return {"status": "reset", "symbol": symbol or "all"}

    # ── Trade Journal Endpoints (from strategy side) ──

    @app.get("/api/journal/entries")
    async def journal_entries(limit: int = 50, status: str = None):
        """Get trade journal entries (in-memory cache + backend DB)."""
        from app.trade_journal import get_trade_journal
        from app.real_grid_bot import BACKEND_API_BASE
        import httpx as _httpx

        journal = get_trade_journal()
        in_memory = journal.get_recent_entries(limit)
        in_stats = journal.get_stats()

        # Fetch DB-persisted entries from backend
        db_entries = []
        db_stats = {}
        try:
            async with _httpx.AsyncClient(timeout=10.0) as client:
                # List entries
                params = {"limit": str(limit)}
                if status:
                    params["status"] = status
                resp = await client.get(
                    f"{BACKEND_API_BASE}/api/journal/list", params=params
                )
                if resp.status_code == 200:
                    db_entries = resp.json()

                # Stats
                resp2 = await client.get(f"{BACKEND_API_BASE}/api/journal/stats")
                if resp2.status_code == 200:
                    db_stats = resp2.json()
        except Exception as e:
            logger.warning("Failed to fetch journal from backend: %s", e)

        return {
            "in_memory": in_memory,
            "db_entries": db_entries,
            "in_memory_stats": in_stats,
            "db_stats": db_stats,
        }

    @app.get("/api/journal/stats")
    async def journal_stats():
        """Get trade journal stats from DB."""
        from app.real_grid_bot import BACKEND_API_BASE
        import httpx as _httpx
        try:
            async with _httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{BACKEND_API_BASE}/api/journal/stats")
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass
        from app.trade_journal import get_trade_journal
        return get_trade_journal().get_stats()

    # ── Daily Report ──

    @app.get("/api/report/daily")
    async def daily_report(symbol: str = "BTCTHB"):
        """Export daily report: open orders, filled trades, PnL, fees, risk events."""
        from app.real_grid_bot import get_real_grid_bot, BACKEND_API_BASE
        from app.risk_manager import get_risk_manager
        from app.trade_journal import get_trade_journal
        import httpx as _httpx

        bot = get_real_grid_bot()
        risk = get_risk_manager()
        journal = get_trade_journal()

        # Fetch open orders from backend
        open_orders = []
        try:
            async with _httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{BACKEND_API_BASE}/api/trade/open-orders",
                    params={"symbol": symbol},
                )
                if resp.status_code == 200:
                    open_orders = resp.json().get("orders", [])
        except Exception:
            pass

        # Fetch filled trades from backend
        filled_trades = []
        try:
            async with _httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{BACKEND_API_BASE}/api/trade/history",
                    params={"limit": "100"},
                )
                if resp.status_code == 200:
                    all_trades = resp.json()
                    filled_trades = [t for t in all_trades if t.get("symbol") == symbol and t.get("status") == "FILLED"]
        except Exception:
            pass

        # Symbol state
        sym_state = bot.states.get(symbol)
        symbol_info = {}
        if sym_state:
            symbol_info = {
                "last_price": sym_state.last_price,
                "active_buys": len(sym_state.active_buys),
                "active_sells": len(sym_state.active_sells),
                "daily_pnl": round(sym_state.daily_pnl, 2),
                "daily_trades": sym_state.daily_trades,
                "halted": sym_state.halted,
            }

        return {
            "symbol": symbol,
            "bot_enabled": bot._enabled,
            "bot_running": bot._running,
            "symbol_state": symbol_info,
            "open_orders": open_orders,
            "filled_trades": filled_trades,
            "risk": {
                "halted": risk.state.halted,
                "halt_reason": risk.state.halt_reason,
                "daily_pnl": round(risk.state.daily_pnl, 2),
                "daily_trades": risk.state.daily_trades,
                "daily_wins": risk.state.daily_wins,
                "daily_losses": risk.state.daily_losses,
                "consecutive_losses": risk.state.consecutive_losses,
                "current_drawdown_pct": round(risk.state.current_drawdown_pct, 2),
            },
            "journal_stats": journal.get_stats(),
            "risk_events": risk.state.risk_events[-20:],  # last 20 events
        }

    # ── Backtester Endpoints ──

    @app.post("/api/backtest/run")
    async def run_backtest(request: dict):
        """
        Run grid trading backtest with given parameters.
        
        Body:
            symbol: str = "BTCTHB"
            days: int = 30
            interval: str = "1h"  # 1m, 5m, 15m, 1h, 4h, 1d
            grid_spacing_pct: float = 1.5
            grid_levels: int = 2
            order_size: float = 0.00005
            max_position: float = 0.001
            max_open_orders: int = 10
            initial_capital_thb: float = 10000.0
            volatility_mode: str = "fixed"  # "fixed" or "atr"
            atr_period: int = 14
            atr_multiplier: float = 1.5
            min_spacing_pct: float = 0.5
            max_spacing_pct: float = 5.0
            # ── Advanced strategy options ──
            grid_mode: str = "arithmetic"  # "arithmetic" | "geometric"
            dgt_enabled: bool = False      # DGT dynamic grid reset + profit reinvest
            dgt_reinvest_pct: float = 0.5  # % of profits to reinvest
            enable_entry_confluence: bool = False  # RSI+MACD+Volume gate
            rsi_buy_threshold: float = 45.0
            volume_multiplier: float = 1.5
        """
        from app.backtester import GridBacktester, BacktestConfig

        config = BacktestConfig(
            symbol=request.get("symbol", "BTCTHB"),
            grid_spacing_pct=request.get("grid_spacing_pct", 1.5),
            grid_levels=request.get("grid_levels", 2),
            order_size=request.get("order_size", 0.00005),
            max_position=request.get("max_position", 0.001),
            max_open_orders=request.get("max_open_orders", 10),
            initial_capital_thb=request.get("initial_capital_thb", 10000.0),
            volatility_mode=request.get("volatility_mode", "fixed"),
            atr_period=request.get("atr_period", 14),
            atr_multiplier=request.get("atr_multiplier", 1.5),
            min_spacing_pct=request.get("min_spacing_pct", 0.5),
            max_spacing_pct=request.get("max_spacing_pct", 5.0),
            grid_mode=request.get("grid_mode", "arithmetic"),
            dgt_enabled=request.get("dgt_enabled", False),
            dgt_reinvest_pct=request.get("dgt_reinvest_pct", 0.5),
            enable_entry_confluence=request.get("enable_entry_confluence", False),
            rsi_buy_threshold=request.get("rsi_buy_threshold", 45.0),
            volume_multiplier=request.get("volume_multiplier", 1.5),
        )
        days = request.get("days", 30)
        interval = request.get("interval", "1h")

        backtester = GridBacktester(config)
        try:
            result = await backtester.run(days=days, interval=interval)
            return {
                "symbol": result.symbol,
                "start_time": result.start_time,
                "end_time": result.end_time,
                "duration_days": round(result.duration_days, 1),
                "total_trades": result.total_trades,
                "winning_trades": result.winning_trades,
                "losing_trades": result.losing_trades,
                "win_rate": result.win_rate,
                "total_pnl": result.total_pnl,
                "total_fees": result.total_fees,
                "net_pnl": result.net_pnl,
                "max_drawdown": result.max_drawdown,
                "max_drawdown_pct": result.max_drawdown_pct,
                "avg_win": result.avg_win,
                "avg_loss": result.avg_loss,
                "profit_factor": result.profit_factor,
                "avg_grid_spacing_pct": result.avg_grid_spacing_pct,
                "trades_per_day": result.trades_per_day,
                "config": result.config,
                "volatility_mode": result.volatility_mode,
                "atr_spacing_avg": result.atr_spacing_avg,
                "atr_spacing_min": result.atr_spacing_min,
                "atr_spacing_max": result.atr_spacing_max,
                "grid_mode": result.grid_mode,
                "dgt_resets": result.dgt_resets,
                "dgt_reinvested_thb": result.dgt_reinvested_thb,
                "confluence_buys_blocked": result.confluence_buys_blocked,
                "final_order_size": result.final_order_size,
                "trades": [
                    {
                        "timestamp": t.timestamp,
                        "side": t.side,
                        "price": t.price,
                        "quantity": t.quantity,
                        "pnl": t.pnl,
                        "fee": t.fee,
                    }
                    for t in result.trades
                ],
            }
        finally:
            await backtester.close()

    @app.post("/api/backtest/sweep")
    async def run_parameter_sweep_endpoint(request: dict):
        """
        Run parameter sweep: test multiple grid_spacing_pct x grid_levels combos.
        
        Body:
            symbol: str = "BTCTHB"
            days: int = 30
            interval: str = "1h"
            volatility_mode: str = "fixed"  # "fixed" or "atr"
            spacing_range: [0.5, 1.0, 1.5, 2.0, 3.0]  # optional
            levels_range: [1, 2, 3, 4]  # optional
            atr_period: int = 14
            atr_multiplier: float = 1.5
            order_size: float = 0.00005
            initial_capital_thb: float = 10000.0
        """
        from app.backtester import run_parameter_sweep

        result = await run_parameter_sweep(
            symbol=request.get("symbol", "BTCTHB"),
            days=request.get("days", 30),
            interval=request.get("interval", "1h"),
            volatility_mode=request.get("volatility_mode", "fixed"),
            spacing_range=request.get("spacing_range"),
            levels_range=request.get("levels_range"),
            atr_period=request.get("atr_period", 14),
            atr_multiplier=request.get("atr_multiplier", 1.5),
            min_spacing_pct=request.get("min_spacing_pct", 0.5),
            max_spacing_pct=request.get("max_spacing_pct", 5.0),
            order_size=request.get("order_size", 0.00005),
            initial_capital_thb=request.get("initial_capital_thb", 10000.0),
        )
        return {
            "symbol": result.symbol,
            "days": result.days,
            "interval": result.interval,
            "volatility_mode": result.volatility_mode,
            "total_combinations": len(result.results),
            "best_config": result.best_config,
            "worst_config": result.worst_config,
            "results": [
                {
                    "grid_spacing_pct": r.grid_spacing_pct,
                    "grid_levels": r.grid_levels,
                    "net_pnl": r.net_pnl,
                    "win_rate": r.win_rate,
                    "trades_per_day": r.trades_per_day,
                    "max_drawdown_pct": r.max_drawdown_pct,
                    "profit_factor": r.profit_factor,
                    "total_trades": r.total_trades,
                    "atr_spacing_avg": r.atr_spacing_avg,
                }
                for r in sorted(result.results, key=lambda x: x.net_pnl, reverse=True)
            ],
        }

    # ── Polymarket Endpoints ──

    @app.post("/api/backtest/compare")
    async def compare_strategies(request: dict):
        """
        Run 11 strategy variants side-by-side for comparison:
          1. baseline: arithmetic grid (legacy)
          2. geometric: geometric grid only
          3. dgt: arithmetic + DGT reset + profit reinvest
          4. full: geometric + DGT + confluence entry timing
          5. full+ob1: full + order book imbalance override
          6. full+ob1+trend: full + ob1 + EMA trend filter
          7. full+ob1+desperation: full + ob1 + anti-over-filtering
          8. full+ob1+desperation+adaptive: + ATR-based dynamic grid spacing
          9. full+ob1+desp+mtf: + multi-timeframe confirmation (4h trend)
         10. full+ob1+desp+ses: + statistical entry scoring
         11. full+ob1+desp+mtf+ses: all improvements combined
        """
        from app.backtester import GridBacktester, BacktestConfig

        symbol = request.get("symbol", "BTCTHB")
        days = request.get("days", 30)
        interval = request.get("interval", "1h")
        spacing = request.get("grid_spacing_pct", 1.5)
        levels = request.get("grid_levels", 2)
        order_size = request.get("order_size", 0.00005)
        capital = request.get("initial_capital_thb", 10000.0)

        configs = {
            "baseline": BacktestConfig(
                symbol=symbol, grid_spacing_pct=spacing, grid_levels=levels,
                order_size=order_size, initial_capital_thb=capital,
            ),
            "geometric": BacktestConfig(
                symbol=symbol, grid_spacing_pct=spacing, grid_levels=levels,
                order_size=order_size, initial_capital_thb=capital,
                grid_mode="geometric",
            ),
            "dgt": BacktestConfig(
                symbol=symbol, grid_spacing_pct=spacing, grid_levels=levels,
                order_size=order_size, initial_capital_thb=capital,
                dgt_enabled=True, dgt_reinvest_pct=0.5,
            ),
            "full": BacktestConfig(
                symbol=symbol, grid_spacing_pct=spacing, grid_levels=levels,
                order_size=order_size, initial_capital_thb=capital,
                grid_mode="geometric", dgt_enabled=True, dgt_reinvest_pct=0.5,
                enable_entry_confluence=True, rsi_buy_threshold=45.0,
                volume_multiplier=1.5,
            ),
            "full+ob1": BacktestConfig(
                symbol=symbol, grid_spacing_pct=spacing, grid_levels=levels,
                order_size=order_size, initial_capital_thb=capital,
                grid_mode="geometric", dgt_enabled=True, dgt_reinvest_pct=0.5,
                enable_entry_confluence=True, rsi_buy_threshold=45.0,
                volume_multiplier=1.5,
                enable_orderbook_imbalance=True, imbalance_threshold=0.65,
                imbalance_rsi_relax=10.0,
            ),
            "full+ob1+trend": BacktestConfig(
                symbol=symbol, grid_spacing_pct=spacing, grid_levels=levels,
                order_size=order_size, initial_capital_thb=capital,
                grid_mode="geometric", dgt_enabled=True, dgt_reinvest_pct=0.5,
                enable_entry_confluence=True, rsi_buy_threshold=45.0,
                volume_multiplier=1.5,
                enable_orderbook_imbalance=True, imbalance_threshold=0.65,
                imbalance_rsi_relax=10.0,
                enable_ema_trend_filter=True, ema_trend_period=50,
            ),
            "full+ob1+desperation": BacktestConfig(
                symbol=symbol, grid_spacing_pct=spacing, grid_levels=levels,
                order_size=order_size, initial_capital_thb=capital,
                grid_mode="geometric", dgt_enabled=True, dgt_reinvest_pct=0.5,
                enable_entry_confluence=True, rsi_buy_threshold=45.0,
                volume_multiplier=1.5,
                enable_orderbook_imbalance=True, imbalance_threshold=0.65,
                imbalance_rsi_relax=10.0,
                enable_desperation_buy=True, desperation_buy_threshold=20,
                desperation_buy_size_pct=0.5,
            ),
            "full+ob1+desp+adaptive": BacktestConfig(
                symbol=symbol, grid_spacing_pct=spacing, grid_levels=levels,
                order_size=order_size, initial_capital_thb=capital,
                grid_mode="geometric", dgt_enabled=True, dgt_reinvest_pct=0.5,
                enable_entry_confluence=True, rsi_buy_threshold=45.0,
                volume_multiplier=1.5,
                enable_orderbook_imbalance=True, imbalance_threshold=0.65,
                imbalance_rsi_relax=10.0,
                enable_desperation_buy=True, desperation_buy_threshold=20,
                desperation_buy_size_pct=0.5,
                volatility_mode="atr", atr_period=14, atr_multiplier=1.5,
                min_spacing_pct=0.5, max_spacing_pct=5.0,
            ),
            "full+ob1+desp+mtf": BacktestConfig(
                symbol=symbol, grid_spacing_pct=spacing, grid_levels=levels,
                order_size=order_size, initial_capital_thb=capital,
                grid_mode="geometric", dgt_enabled=True, dgt_reinvest_pct=0.5,
                enable_entry_confluence=True, rsi_buy_threshold=45.0,
                volume_multiplier=1.5,
                enable_orderbook_imbalance=True, imbalance_threshold=0.65,
                imbalance_rsi_relax=10.0,
                enable_desperation_buy=True, desperation_buy_threshold=20,
                desperation_buy_size_pct=0.5,
                enable_mtf_confirmation=True, mtf_interval="4h",
                mtf_ema_fast=20, mtf_ema_slow=50,
            ),
            "full+ob1+desp+ses": BacktestConfig(
                symbol=symbol, grid_spacing_pct=spacing, grid_levels=levels,
                order_size=order_size, initial_capital_thb=capital,
                grid_mode="geometric", dgt_enabled=True, dgt_reinvest_pct=0.5,
                enable_entry_confluence=True, rsi_buy_threshold=45.0,
                volume_multiplier=1.5,
                enable_orderbook_imbalance=True, imbalance_threshold=0.65,
                imbalance_rsi_relax=10.0,
                enable_desperation_buy=True, desperation_buy_threshold=20,
                desperation_buy_size_pct=0.5,
                enable_statistical_scoring=True, ses_warmup_trades=10,
                ses_min_score=0.55,
            ),
            "full+ob1+desp+mtf+ses": BacktestConfig(
                symbol=symbol, grid_spacing_pct=spacing, grid_levels=levels,
                order_size=order_size, initial_capital_thb=capital,
                grid_mode="geometric", dgt_enabled=True, dgt_reinvest_pct=0.5,
                enable_entry_confluence=True, rsi_buy_threshold=45.0,
                volume_multiplier=1.5,
                enable_orderbook_imbalance=True, imbalance_threshold=0.65,
                imbalance_rsi_relax=10.0,
                enable_desperation_buy=True, desperation_buy_threshold=20,
                desperation_buy_size_pct=0.5,
                enable_mtf_confirmation=True, mtf_interval="4h",
                mtf_ema_fast=20, mtf_ema_slow=50,
                enable_statistical_scoring=True, ses_warmup_trades=10,
                ses_min_score=0.55,
            ),
            # ── Bear Market Micro-Scalper (0.3% spacing, 5 levels) ─────────
            "micro-scalper(0.3%/5lv)": BacktestConfig(
                symbol=symbol, grid_spacing_pct=0.3, grid_levels=5,
                order_size=0.00002, initial_capital_thb=capital,
                grid_mode="geometric", dgt_enabled=True, dgt_reinvest_pct=0.5,
                enable_entry_confluence=True, rsi_buy_threshold=45.0,
                volume_multiplier=1.2,
                enable_orderbook_imbalance=True, imbalance_threshold=0.60,
                imbalance_rsi_relax=10.0,
                enable_desperation_buy=True, desperation_buy_threshold=8,
                desperation_buy_size_pct=0.5,
            ),
        }

        results = {}
        for name, cfg in configs.items():
            bt = GridBacktester(cfg)
            try:
                r = await bt.run(days=days, interval=interval)
                results[name] = {
                    "net_pnl": r.net_pnl,
                    "win_rate": r.win_rate,
                    "total_trades": r.total_trades,
                    "trades_per_day": r.trades_per_day,
                    "max_drawdown_pct": r.max_drawdown_pct,
                    "profit_factor": r.profit_factor,
                    "grid_mode": r.grid_mode,
                    "dgt_resets": r.dgt_resets,
                    "dgt_reinvested_thb": r.dgt_reinvested_thb,
                    "confluence_buys_blocked": r.confluence_buys_blocked,
                    "final_order_size": r.final_order_size,
                    "imbalance_overrides": r.imbalance_overrides,
                    "avg_imbalance": r.avg_imbalance,
                    "ema_trend_blocked": r.ema_trend_blocked,
                    "desperation_buys_triggered": r.desperation_buys_triggered,
                    "atr_spacing_avg": r.atr_spacing_avg,
                    "atr_spacing_min": r.atr_spacing_min,
                    "atr_spacing_max": r.atr_spacing_max,
                    "mtf_blocked": r.mtf_blocked,
                    "ses_score_avg": r.ses_score_avg,
                    "ses_trades_allowed": r.ses_trades_allowed,
                    "ses_trades_blocked": r.ses_trades_blocked,
                }
            except Exception as e:
                results[name] = {"error": str(e)}
            finally:
                await bt.close()

        # Determine winner by net_pnl (ignoring errors)
        valid = {k: v for k, v in results.items() if "error" not in v}
        winner = max(valid, key=lambda k: valid[k]["net_pnl"]) if valid else None

        return {
            "symbol": symbol,
            "days": days,
            "interval": interval,
            "strategies": results,
            "winner": winner,
        }

    @app.post("/api/backtest/walk-forward")
    async def walk_forward_tuning(request: dict):
        """
        Walk-forward parameter optimization.
        Tunes desperation_buy_threshold, imbalance_threshold, rsi_buy_threshold
        across multiple data folds to find stable optimal values.
        """
        from app.backtester import run_walk_forward_tuning

        symbol = request.get("symbol", "BTCTHB")
        days = request.get("days", 30)
        interval = request.get("interval", "1h")
        n_folds = request.get("n_folds", 3)

        result = await run_walk_forward_tuning(
            symbol=symbol, days=days, interval=interval, n_folds=n_folds,
        )
        return result

    @app.get("/api/polymarket/events")
    async def polymarket_events(limit: int = 20, active: bool = True, tag: str = None):
        """Fetch active Polymarket events with markets."""
        from app.polymarket import get_polymarket_client
        client = get_polymarket_client()
        events = await client.get_events(limit=limit, active=active, tag=tag)
        return {
            "events": [
                {
                    "id": e.event_id,
                    "title": e.title,
                    "slug": e.slug,
                    "markets_count": len(e.markets),
                    "tags": e.tags,
                    "closed": e.closed,
                }
                for e in events
            ],
            "total": len(events),
        }

    @app.get("/api/polymarket/markets")
    async def polymarket_markets(limit: int = 50, active: bool = True):
        """Fetch active Polymarket markets with current prices."""
        from app.polymarket import get_polymarket_client
        client = get_polymarket_client()
        markets = await client.get_markets(limit=limit, active=active)
        return {
            "markets": [
                {
                    "condition_id": m.condition_id,
                    "question": m.question,
                    "yes_price": m.yes_price,
                    "no_price": m.no_price,
                    "volume": m.volume,
                    "liquidity": m.liquidity,
                    "resolved": m.resolved,
                }
                for m in markets
            ],
            "total": len(markets),
        }

    @app.get("/api/polymarket/search")
    async def polymarket_search(q: str, limit: int = 20):
        """Search Polymarket markets by keyword."""
        from app.polymarket import get_analyzer
        analyzer = get_analyzer()
        result = await analyzer.search_and_analyze(q)
        return result

    @app.get("/api/polymarket/opportunities")
    async def polymarket_opportunities(min_confidence: float = 0.3, limit: int = 30):
        """Scan all markets for trading opportunities and inefficiencies."""
        from app.polymarket import get_analyzer
        analyzer = get_analyzer()
        events = await analyzer.refresh_markets(limit=limit)
        opportunities = await analyzer.scan_opportunities(events, min_confidence=min_confidence)
        summary = await analyzer.get_market_summary(events)
        return {
            "opportunities": [opp.model_dump() for opp in opportunities],
            "summary": summary,
        }

    # ── Polymarket Paper Trading Bot Endpoints ──

    @app.get("/api/poly-paper/status")
    async def poly_paper_status():
        """Get Polymarket paper trading bot status."""
        from app.polymarket.paper_bot import get_poly_paper_bot
        bot = get_poly_paper_bot()
        return bot.get_status()

    @app.get("/api/poly-paper/positions")
    async def poly_paper_positions(active_only: bool = False):
        """Get paper trading positions."""
        from app.polymarket.paper_bot import get_poly_paper_bot
        bot = get_poly_paper_bot()
        return bot.get_positions(active_only=active_only)

    @app.get("/api/poly-paper/trades")
    async def poly_paper_trades(limit: int = 50):
        """Get recent paper trades."""
        from app.polymarket.paper_bot import get_poly_paper_bot
        bot = get_poly_paper_bot()
        return bot.get_trades(limit=limit)

    @app.get("/api/poly-paper/performance")
    async def poly_paper_performance():
        """Get detailed paper trading performance metrics."""
        from app.polymarket.paper_bot import get_poly_paper_bot
        bot = get_poly_paper_bot()
        return bot.get_performance()

    @app.get("/api/poly-paper/notifications")
    async def poly_paper_notifications(limit: int = 20):
        """Get recent paper trading notifications."""
        from app.polymarket.paper_bot import get_poly_paper_bot
        bot = get_poly_paper_bot()
        return bot.get_notifications(limit=limit)

    @app.get("/api/poly-paper/signals")
    async def poly_paper_signals(limit: int = 30):
        """Get recent alpha signals from multi-signal engine."""
        from app.polymarket.paper_bot import get_poly_paper_bot
        bot = get_poly_paper_bot()
        return bot.get_signals(limit=limit)

    @app.post("/api/poly-paper/reset-kill-switch")
    async def poly_paper_reset_kill_switch():
        """Reset the Polymarket paper bot kill switch after manual review."""
        from app.polymarket.paper_bot import get_poly_paper_bot
        bot = get_poly_paper_bot()
        bot.reset_kill_switch()
        return {"status": "reset", "message": "Polymarket paper bot kill switch reset"}

    # ── Arbitrage Paper Trading Bot Endpoints ──

    @app.get("/api/arb-paper/status")
    async def arb_paper_status():
        """Get arbitrage paper trading bot status."""
        from app.arbitrage_paper_bot import get_arb_paper_bot
        bot = get_arb_paper_bot()
        return bot.get_status()

    @app.post("/api/arb-paper/reset")
    async def arb_paper_reset():
        """Reset arbitrage paper bot state."""
        from app.arbitrage_paper_bot import get_arb_paper_bot
        bot = get_arb_paper_bot()
        bot.reset()
        return {"status": "reset", "message": "Arbitrage paper bot state reset"}

    @app.get("/api/polymarket/summary")
    async def polymarket_summary(limit: int = 50):
        """Get summary statistics across all Polymarket markets."""
        from app.polymarket import get_analyzer
        analyzer = get_analyzer()
        events = await analyzer.refresh_markets(limit=limit)
        summary = await analyzer.get_market_summary(events)
        return summary

    @app.get("/api/polymarket/tags")
    async def polymarket_tags():
        """Get available Polymarket market tags/categories."""
        from app.polymarket import get_polymarket_client
        client = get_polymarket_client()
        tags = await client.get_tags()
        return {"tags": tags}

    @app.get("/api/polymarket/orderbook/{token_id}")
    async def polymarket_orderbook(token_id: str):
        """Get orderbook for a specific Polymarket outcome token."""
        from app.polymarket import get_polymarket_client
        client = get_polymarket_client()
        orderbook = await client.get_orderbook(token_id)
        if not orderbook:
            raise HTTPException(status_code=404, detail="Orderbook not found")
        return orderbook.model_dump()

    @app.get("/api/polymarket/price-history/{token_id}")
    async def polymarket_price_history(token_id: str, interval: str = "1h"):
        """Get price history for a Polymarket token."""
        from app.polymarket import get_polymarket_client
        client = get_polymarket_client()
        history = await client.get_price_history(token_id, interval=interval)
        if not history:
            raise HTTPException(status_code=404, detail="Price history not found")
        return history.model_dump()


    # ── Market Intelligence Endpoints ──

    def _get_market_scanner():
        """Get or create the market scanner singleton."""
        from app.market_intel import get_scanner
        cfg = app.state.config
        crypto_syms = [s.strip() for s in cfg.get("market_intel_crypto_symbols", "BTCTHB,ETHTHB,BTCUSDT,ETHUSDT").split(",") if s.strip()]
        stock_syms = [s.strip() for s in cfg.get("market_intel_stock_symbols", "SPY,QQQ,AAPL,MSFT,GOOGL").split(",") if s.strip()]
        sources = [s.strip() for s in cfg.get("market_intel_sources", "crypto,prediction,stocks,macro,airdrops,degen,binance_alpha,arb").split(",") if s.strip()]
        return get_scanner(
            crypto_symbols=crypto_syms,
            stock_symbols=stock_syms,
            polymarket_gamma_api=cfg.get("polymarket_gamma_api", "https://gamma-api.polymarket.com"),
            polymarket_clob_api=cfg.get("polymarket_clob_api", "https://clob.polymarket.com"),
            enabled_sources=sources,
        )

    @app.get("/api/market-intel/scan")
    async def market_intel_scan(min_confidence: float = 0.3, markets: str = None):
        """Cross-market opportunity scan across all enabled sources."""
        scanner = _get_market_scanner()
        market_filter = None
        if markets:
            from app.market_intel.models import MarketType
            market_filter = [MarketType(m.strip()) for m in markets.split(",") if m.strip()]
        result = await scanner.scan_all(min_confidence=min_confidence, markets=market_filter)

        # Log signals to performance tracker
        try:
            sig_logger = _get_signal_logger()
            for opp in result.opportunities:
                await sig_logger.log_signal(
                    symbol=opp.symbol,
                    market_type=opp.market_type.value,
                    source=opp.source,
                    signal_type=opp.opportunity_type.value,
                    severity=opp.severity.value,
                    title=opp.title,
                    price_at_signal=opp.current_price,
                    confidence=opp.confidence,
                    metadata=opp.metadata if hasattr(opp, 'metadata') else {},
                )
        except Exception as e:
            logger.warning(f"Failed to log signals from manual scan: {e}")

        return result.model_dump()

    @app.get("/api/market-intel/quotes")
    async def market_intel_quotes(markets: str = None):
        """Fetch live quotes from all enabled market sources."""
        scanner = _get_market_scanner()
        market_filter = None
        if markets:
            from app.market_intel.models import MarketType
            market_filter = [MarketType(m.strip()) for m in markets.split(",") if m.strip()]
        quotes = await scanner.get_all_quotes(markets=market_filter)
        return {
            "quotes": [q.model_dump() for q in quotes],
            "total": len(quotes),
        }

    @app.get("/api/market-intel/overview")
    async def market_intel_overview():
        """High-level overview of all markets with top opportunities."""
        scanner = _get_market_scanner()
        overview = await scanner.get_market_overview()
        return overview

    @app.get("/api/market-intel/sources")
    async def market_intel_sources():
        """List available market data sources and their status."""
        scanner = _get_market_scanner()
        return {
            "sources": [
                {
                    "name": src.source_name,
                    "market_type": src.market_type.value,
                    "enabled": True,
                }
                for src in scanner.sources.values()
            ],
            "total": len(scanner.sources),
        }

    @app.get("/api/market-intel/alerts")
    async def market_intel_alerts(limit: int = 50, severity: str = None):
        """
        Get high-severity market alerts from background scanning.
        Returns alerts sorted by most recent first.
        """
        alerts = list(reversed(_market_alerts))  # Most recent first
        if severity:
            alerts = [a for a in alerts if a.get("severity") == severity.lower()]
        return {
            "alerts": alerts[:limit],
            "total": len(alerts),
            "max_stored": _MAX_ALERTS,
        }

    @app.get("/api/market-intel/last-scan")
    async def market_intel_last_scan():
        """Get the most recent background scan result."""
        if not _last_scan_result:
            return {"status": "no_scan_yet", "message": "Background scan has not completed yet"}
        return _last_scan_result

    @app.get("/api/market-intel/portfolio")
    async def market_intel_portfolio():
        """
        Portfolio integration: cross-reference Binance TH holdings with market intel signals.
        Returns holdings with THB values and matched signals.
        """
        BINANCE_TH_PAIRS = {
            "BTC": "BTCTHB", "ETH": "ETHTHB", "BNB": "BNBTHB",
            "SOL": "SOLTHB", "XRP": "XRPTHB", "ASTER": "ASTERTHB",
            "ATH": "ATHTHB", "PLUME": "PLUMETHB", "VELO": "VELOTHB",
            "ZENT": "ZENTTHB", "USDT": "USDTTHB",
        }

        # 1. Fetch balances from Go backend
        balances_raw = []
        try:
            from app.real_grid_bot import BACKEND_API_BASE
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{BACKEND_API_BASE}/api/trade/balances")
                if resp.status_code == 200:
                    balances_raw = resp.json().get("balances", [])
        except Exception as e:
            logger.warning(f"Portfolio: failed to fetch balances: {e}")

        # 2. Get prices for all THB pairs
        prices = {}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                for symbol in BINANCE_TH_PAIRS.values():
                    try:
                        resp = await client.get(
                            f"https://api.binance.th/api/v1/ticker/price",
                            params={"symbol": symbol},
                        )
                        if resp.status_code == 200:
                            prices[symbol] = float(resp.json().get("price", 0))
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"Portfolio: failed to fetch prices: {e}")

        # 3. Build holdings list
        holdings = []
        total_thb = 0.0
        for b in balances_raw:
            currency = b.get("currency", "")
            free = float(b.get("free", 0))
            locked = float(b.get("locked", 0))
            total_amt = free + locked

            if total_amt <= 0:
                continue

            # THB itself
            if currency == "THB":
                holdings.append({
                    "currency": "THB",
                    "symbol": "—",
                    "amount": total_amt,
                    "free": free,
                    "locked": locked,
                    "price_thb": 1.0,
                    "value_thb": total_amt,
                    "signals": [],
                })
                total_thb += total_amt
                continue

            symbol = BINANCE_TH_PAIRS.get(currency)
            if not symbol:
                continue

            price = prices.get(symbol, 0)
            value_thb = total_amt * price
            total_thb += value_thb

            # 4. Match signals from last scan
            signals = []
            if _last_scan_result and "opportunities" in _last_scan_result:
                for opp in _last_scan_result["opportunities"]:
                    if opp.get("symbol") == symbol:
                        signals.append({
                            "title": opp.get("title", ""),
                            "severity": opp.get("severity", "low"),
                            "confidence": opp.get("confidence", 0),
                            "type": opp.get("type", ""),
                        })

            holdings.append({
                "currency": currency,
                "symbol": symbol,
                "amount": total_amt,
                "free": free,
                "locked": locked,
                "price_thb": price,
                "value_thb": round(value_thb, 2),
                "signals": signals,
            })

        # Sort by value descending
        holdings.sort(key=lambda h: h["value_thb"], reverse=True)
        signal_count = sum(len(h["signals"]) for h in holdings)

        return {
            "holdings": holdings,
            "total_value_thb": round(total_thb, 2),
            "signal_count": signal_count,
            "pairs_tracked": len(BINANCE_TH_PAIRS),
        }

    # ── Airdrop Task Tracker Endpoints ──

    def _get_airdrop_tracker():
        """Get airdrop tracker with Redis client."""
        from app.market_intel.airdrop_tracker import get_airdrop_tracker
        redis_client = redis_adapter.redis if redis_adapter and redis_adapter.redis else None
        return get_airdrop_tracker(redis_client=redis_client)

    @app.get("/api/airdrop-tracker/tasks")
    async def airdrop_tracker_list():
        """List all tracked airdrop tasks."""
        tracker = _get_airdrop_tracker()
        tasks = await tracker.list_tasks()
        stats = await tracker.get_stats()
        return {"tasks": tasks, "stats": stats}

    @app.post("/api/airdrop-tracker/tasks")
    async def airdrop_tracker_add(request: Request):
        """Add a new airdrop task to track."""
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON body")

        name = body.get("name")
        if not name:
            raise HTTPException(status_code=400, detail="'name' is required")

        tracker = _get_airdrop_tracker()
        task = await tracker.add_task(
            name=name,
            chain=body.get("chain", ""),
            task_description=body.get("task_description", ""),
            estimated_value=body.get("estimated_value", ""),
            difficulty=body.get("difficulty", ""),
            cost=body.get("cost", ""),
            url=body.get("url", ""),
            deadline=body.get("deadline", ""),
        )
        return {"task": task}

    @app.patch("/api/airdrop-tracker/tasks/{task_id}")
    async def airdrop_tracker_update(task_id: str, request: Request):
        """Update an existing airdrop task."""
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON body")

        tracker = _get_airdrop_tracker()
        task = await tracker.update_task(task_id, body)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return {"task": task}

    @app.patch("/api/airdrop-tracker/tasks/{task_id}/subtasks/{subtask_idx}")
    async def airdrop_tracker_update_subtask(task_id: str, subtask_idx: int, request: Request):
        """Toggle a subtask completion status."""
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON body")

        completed = body.get("completed", True)
        tracker = _get_airdrop_tracker()
        task = await tracker.update_subtask(task_id, subtask_idx, completed)
        if not task:
            raise HTTPException(status_code=404, detail="Task or subtask not found")
        return {"task": task}

    @app.delete("/api/airdrop-tracker/tasks/{task_id}")
    async def airdrop_tracker_delete(task_id: str):
        """Remove a tracked airdrop task."""
        tracker = _get_airdrop_tracker()
        success = await tracker.delete_task(task_id)
        if not success:
            raise HTTPException(status_code=404, detail="Task not found")
        return {"deleted": True, "task_id": task_id}

    @app.get("/api/airdrop-tracker/stats")
    async def airdrop_tracker_stats():
        """Get tracker statistics."""
        tracker = _get_airdrop_tracker()
        return await tracker.get_stats()

    # ── Signal Performance Tracker Endpoints ──

    def _get_signal_logger():
        """Get signal logger with Redis client."""
        from app.market_intel.signal_logger import get_signal_logger
        redis_client = redis_adapter.redis if redis_adapter and redis_adapter.redis else None
        return get_signal_logger(redis_client=redis_client)

    @app.get("/api/signal-tracker/signals")
    async def signal_tracker_list(
        limit: int = 100,
        source: Optional[str] = None,
        market_type: Optional[str] = None,
        evaluated_only: bool = False,
    ):
        """Get logged signals with optional filters."""
        logger = _get_signal_logger()
        signals = await logger.get_signals(
            limit=limit,
            source=source,
            market_type=market_type,
            evaluated_only=evaluated_only,
        )
        return {"signals": signals, "total": len(signals)}

    @app.get("/api/signal-tracker/stats")
    async def signal_tracker_stats():
        """Get performance statistics."""
        logger = _get_signal_logger()
        return await logger.get_performance_stats()

    @app.post("/api/signal-tracker/evaluate")
    async def signal_tracker_evaluate():
        """
        Manually trigger signal evaluation against current prices.
        Normally runs automatically, but can be triggered on-demand.
        """
        import httpx
        logger = _get_signal_logger()
        
        # Fetch current prices for all tracked symbols
        BINANCE_TH_PAIRS = {
            "BTC": "BTCTHB", "ETH": "ETHTHB", "BNB": "BNBTHB",
            "SOL": "SOLTHB", "XRP": "XRPTHB", "ASTER": "ASTERTHB",
            "ATH": "ATHTHB", "PLUME": "PLUMETHB", "VELO": "VELOTHB",
            "ZENT": "ZENTTHB", "USDT": "USDTTHB",
        }
        
        current_prices = {}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                for currency, symbol in BINANCE_TH_PAIRS.items():
                    try:
                        resp = await client.get(f"https://api.binance.th/v3/ticker/price?symbol={symbol}")
                        if resp.status_code == 200:
                            data = resp.json()
                            current_prices[currency] = float(data.get("price", 0))
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"Failed to fetch prices for evaluation: {e}")
        
        result = await logger.evaluate_signals(current_prices)
        return result

    # ── Evidence Endpoint ──

    @app.get("/api/evidence")
    async def evidence_status():
        """
        Read evidence files and return structured JSON.
        - docs/EVIDENCE_LOG.md → parsed timeline entries
        - docs/READINESS_CHECKLIST.md → gate statuses
        - data/paper_grid_1day.json → latest trial results (if exists)
        All reads are read-only. Missing files return safe defaults.
        """
        import json as _json
        import re
        from pathlib import Path

        base_dir = Path(__file__).resolve().parent.parent.parent  # /app inside container
        docs_dir = base_dir / "docs"
        data_dir = base_dir / "data"

        # ── 1. Parse EVIDENCE_LOG.md ──
        evidence_entries = []
        evidence_file = docs_dir / "EVIDENCE_LOG.md"
        if evidence_file.exists():
            try:
                content = evidence_file.read_text(encoding="utf-8")
                # Split by ### headers (each entry starts with ### YYYY-MM-DD)
                sections = re.split(r'\n### ', content)
                for section in sections[1:]:  # skip preamble before first ###
                    lines = section.strip().split('\n')
                    header = lines[0].strip()
                    # Extract date
                    date_match = re.match(r'(\d{4}-\d{2}-\d{2})', header)
                    date_str = date_match.group(1) if date_match else header[:10]
                    # Extract key fields
                    title = header
                    status = 'info'
                    details_lines = []
                    for line in lines[1:]:
                        line = line.strip()
                        if not line or line.startswith('---'):
                            continue
                        if line.startswith('**') and line.endswith('**'):
                            continue  # skip bold section headers
                        if line.startswith('- '):
                            details_lines.append(line[2:])
                        elif line.startswith('**Verdict:**'):
                            verdict_text = line.replace('**Verdict:**', '').strip()
                            if 'PASS' in verdict_text.upper():
                                status = 'pass'
                            elif 'FAIL' in verdict_text.upper():
                                status = 'fail'
                            else:
                                status = 'info'
                            details_lines.append(f"Verdict: {verdict_text}")
                        else:
                            details_lines.append(line)
                    # Determine entry type from THIS section (not whole file)
                    section_text = (header + ' ' + ' '.join(details_lines)).lower()
                    entry_type = 'log'
                    if 'trial' in section_text or 'paper grid' in section_text:
                        entry_type = 'trial'
                    elif 'kill switch' in section_text and 'active' in section_text:
                        entry_type = 'kill_switch'
                    elif 'research' in section_text or 'watchlist' in section_text or 'scanner' in section_text:
                        entry_type = 'research'
                    elif 'monitor' in section_text or 'daily' in section_text or 'check' in section_text:
                        entry_type = 'monitor'
                    elif 'gate' in section_text or 'readiness' in section_text:
                        entry_type = 'gate'
                    evidence_entries.append({
                        'date': date_str,
                        'title': title,
                        'status': status,
                        'type': entry_type,
                        'details': ' | '.join(details_lines[:5]),  # cap at 5 lines
                    })
                # Reverse to newest-first
                evidence_entries.reverse()
            except Exception as e:
                logger.warning(f"Failed to parse EVIDENCE_LOG.md: {e}")

        # ── 2. Parse READINESS_CHECKLIST.md gates ──
        gates = []
        checklist_file = docs_dir / "READINESS_CHECKLIST.md"
        if checklist_file.exists():
            try:
                content = checklist_file.read_text(encoding="utf-8")
                # Find the Current Status table
                table_match = re.search(
                    r'\| Gate \| Status \| Blocked By \|\n\|[-|]+\|\n((?:\|.*\|\n)*)',
                    content
                )
                if table_match:
                    rows = table_match.group(1).strip().split('\n')
                    for row in rows:
                        cells = [c.strip() for c in row.split('|') if c.strip()]
                        if len(cells) >= 3:
                            gate_name = cells[0].lstrip('0123456789. ')
                            status_text = cells[1]
                            blocked_by = cells[2]
                            is_ready = '🟢' in status_text or ('ready' in status_text.lower() and 'not ready' not in status_text.lower())
                            gates.append({
                                'name': gate_name,
                                'status': 'ready' if is_ready else 'not_ready',
                                'status_text': status_text.replace('🔴', '').replace('🟢', '').strip(),
                                'blocked_by': blocked_by,
                            })
            except Exception as e:
                logger.warning(f"Failed to parse READINESS_CHECKLIST.md: {e}")

        # ── 3. Paper grid trial results (if exists) ──
        paper_trial = None
        trial_file = data_dir / "paper_grid_1day.json"
        if trial_file.exists():
            try:
                paper_trial = _json.loads(trial_file.read_text(encoding="utf-8"))
                if isinstance(paper_trial, dict):
                    _snapshots = paper_trial.get('snapshots') or []
                    _final_price = float(paper_trial.get('final_price') or 0)
                    if _final_price <= 0 and _snapshots:
                        _fallback_price = float((_snapshots[-1] or {}).get('price') or 0)
                        if _fallback_price > 0:
                            paper_trial['final_price'] = _fallback_price
                            paper_trial['final_price_source'] = 'last_snapshot'
                            _baseline = float(paper_trial.get('baseline_price') or 0)
                            if _baseline > 0:
                                paper_trial['price_change_pct'] = round((_fallback_price - _baseline) / _baseline * 100, 3)
                    if not paper_trial.get('status'):
                        _duration = float(paper_trial.get('duration_hours') or 0)
                        paper_trial['status'] = 'completed' if _duration >= 23.5 else 'partial'
            except Exception as e:
                logger.warning(f"Failed to read paper_grid_1day.json: {e}")

        # ── 4. Build latest_change summary ──
        latest_change = None
        if evidence_entries:
            first = evidence_entries[0]  # already newest-first
            latest_change = {
                'date': first['date'],
                'title': first['title'],
                'type': first['type'],
                'status': first['status'],
            }

        return {
            'evidence_entries': evidence_entries,
            'gates': gates,
            'paper_trial': paper_trial,
            'latest_change': latest_change,
            'files_found': {
                'evidence_log': evidence_file.exists(),
                'readiness_checklist': checklist_file.exists(),
                'paper_grid_json': trial_file.exists(),
            },
        }

    # ── /api/research — crypto watchlist + polymarket scanner ────────────────
    @app.get("/api/research")
    async def research_watchlists():
        import re
        from pathlib import Path

        base_dir = Path(__file__).resolve().parent.parent.parent  # /app
        docs_dir = base_dir / "docs"

        # ── 1. Parse CRYPTO_WATCHLIST.md ──
        crypto = {'pairs': [], 'meta': {}, 'files_found': False}
        crypto_file = docs_dir / "CRYPTO_WATCHLIST.md"
        if crypto_file.exists():
            crypto['files_found'] = True
            try:
                content = crypto_file.read_text(encoding="utf-8")
                # Meta: Last scan, pairs scanned, min volume
                scan_match = re.search(r'\*\*Last scan:\*\*\s*(.+)', content)
                pairs_match = re.search(r'\*\*Pairs scanned:\*\*\s*(\d+)', content)
                vol_match = re.search(r'\*\*Min volume filter:\*\*\s*(.+)', content)
                crypto['meta'] = {
                    'last_scan': scan_match.group(1).strip() if scan_match else None,
                    'pairs_scanned': int(pairs_match.group(1)) if pairs_match else 0,
                    'min_volume': vol_match.group(1).strip() if vol_match else None,
                }
                # Ranked pairs table
                table_match = re.search(
                    r'\| # \| Score \| Exchange \| Symbol \| Price \| Vol.*\n'
                    r'\|[-|]+\n'
                    r'((?:\|.*\n)*)',
                    content
                )
                if table_match:
                    rows = table_match.group(1).strip().split('\n')
                    for row in rows:
                        cells = [c.strip() for c in row.split('|') if c.strip()]
                        if len(cells) >= 9:
                            crypto['pairs'].append({
                                'rank': int(cells[0]) if cells[0].isdigit() else 0,
                                'score': float(cells[1]) if cells[1].replace('.', '').isdigit() else 0,
                                'exchange': cells[2],
                                'symbol': cells[3],
                                'price': cells[4],
                                'volume': cells[5],
                                'vol_pct': cells[6],
                                'spread': cells[7],
                                'depth': cells[8],
                            })
            except Exception as e:
                logger.warning(f"Failed to parse CRYPTO_WATCHLIST.md: {e}")

        # ── 2. Parse MARKET_WATCHLIST.md (Polymarket) ──
        poly = {'candidates': [], 'reviewed': [], 'meta': {}, 'files_found': False}
        poly_file = docs_dir / "MARKET_WATCHLIST.md"
        if poly_file.exists():
            poly['files_found'] = True
            try:
                content = poly_file.read_text(encoding="utf-8")
                # Meta
                scan_match = re.search(r'\*\*Last scan:\*\*\s*(.+)', content)
                cand_match = re.search(r'\*\*Candidates:\*\*\s*(.+)', content)
                poly['meta'] = {
                    'last_scan': scan_match.group(1).strip() if scan_match else None,
                    'candidates_summary': cand_match.group(1).strip() if cand_match else None,
                }
                # Filters
                filters = []
                for fm in re.finditer(r'- (Min liquidity|Min volume|Max spread|Price range|Blocked categories):\s*(.+)', content):
                    filters.append({'key': fm.group(1), 'value': fm.group(2).strip()})
                poly['meta']['filters'] = filters
                # Manual review table
                review_match = re.search(
                    r'\| # \| Market \| Resolution \| Category Leak\?.*\n'
                    r'\|[-|]+\n'
                    r'((?:\|.*\n)*)',
                    content
                )
                if review_match:
                    rows = review_match.group(1).strip().split('\n')
                    for row in rows:
                        cells = [c.strip() for c in row.split('|') if c.strip()]
                        if len(cells) >= 6:
                            poly['reviewed'].append({
                                'rank': int(cells[0]) if cells[0].isdigit() else 0,
                                'market': cells[1],
                                'resolution': cells[2],
                                'category_leak': cells[3],
                                'data_source': cells[4],
                                'signal': cells[5],
                                'decision': cells[6] if len(cells) > 6 else '',
                            })
            except Exception as e:
                logger.warning(f"Failed to parse MARKET_WATCHLIST.md: {e}")

        # ── 3. Build summary object ──
        # Count trade candidates (non-REJECT items from Polymarket)
        trade_candidates = sum(1 for r in poly.get('reviewed', []) if r.get('decision', '').upper() != 'REJECT')
        crypto_count = len(crypto.get('pairs', []))
        poly_blocked = all(r.get('decision', '').upper() == 'REJECT' for r in poly.get('reviewed', []))
        
        # Extract filter values
        filter_map = {f['key']: f['value'] for f in poly.get('meta', {}).get('filters', [])}
        
        summary = {
            'trade_candidates': trade_candidates,
            'crypto_watch_count': crypto_count,
            'polymarket_status': 'blocked' if poly_blocked else 'active',
            'blocklist_active': len(filter_map.get('Blocked categories', '')) > 0,
            'min_volume': filter_map.get('Min volume', crypto.get('meta', {}).get('min_volume', 'N/A')),
            'min_liquidity': filter_map.get('Min liquidity', 'N/A'),
        }

        return {
            'crypto': crypto,
            'polymarket': poly,
            'summary': summary,
        }

    # ── /api/command-center — single source of truth for dashboard ─────────────
    @app.get("/api/command-center")
    async def command_center():
        import re as _re
        from pathlib import Path as _Path
        from datetime import datetime as _dt

        base_dir = _Path(__file__).resolve().parent.parent.parent  # /app
        docs_dir = base_dir / "docs"
        data_dir = base_dir / "data"

        # ── 1. System health ──
        redis_connected = False
        if redis_adapter:
            redis_connected = await redis_adapter.health_check()
        system_health = {
            'strategy_api': 'healthy',
            'redis_connected': redis_connected,
        }

        # ── 2. Risk manager (kill switch, drawdown) ──
        try:
            from app.risk_manager import get_risk_manager
            rm = get_risk_manager()
            risk = rm.get_status()
            kill_switch_active = risk.get('halted', False)
            drawdown_pct = risk.get('current_drawdown_pct', 0)
            max_drawdown = risk.get('max_drawdown_pct', 5.0)
        except Exception:
            kill_switch_active = True
            drawdown_pct = 15.8
            max_drawdown = 5.0
            risk = {}

        # ── 3. Polymarket paper positions ──
        poly_kill_switch = False
        poly_kill_reason = ''
        try:
            from app.polymarket.paper_bot import get_poly_paper_bot
            bot = get_poly_paper_bot()
            poly_status = bot.get_status()
            active_positions = poly_status.get('positions', {}).get('active', 0)
            resolved_positions = poly_status.get('positions', {}).get('resolved', 0)
            # Paper bot's own kill switch (separate from grid risk_manager)
            poly_kill_switch = getattr(bot, '_kill_switch_active', False)
            poly_kill_reason = getattr(bot, '_kill_reason', '')
        except Exception:
            active_positions = 0
            resolved_positions = 0
            poly_status = {}

        # ── 4. Real grid status ──
        try:
            from app.real_grid_bot import get_real_grid_bot
            _rgbot = get_real_grid_bot()
            grid_status = _rgbot.get_status()
            grid_running = grid_status.get('running', False)
            grid_symbols = grid_status.get('symbols', {})
            total_fills = sum(s.get('daily_trades', 0) for s in grid_symbols.values())
            total_pnl = sum(s.get('daily_pnl', 0) for s in grid_symbols.values())
        except Exception:
            grid_running = False
            grid_symbols = {}
            total_fills = 0
            total_pnl = 0
            grid_status = {}

        # ── 5. Evidence (latest entry + gates) ──
        latest_evidence = None
        gates_ready = 0
        gates_total = 0
        evidence_file = docs_dir / "EVIDENCE_LOG.md"
        if evidence_file.exists():
            try:
                content = evidence_file.read_text(encoding="utf-8")
                sections = _re.split(r'\n### ', content)
                if len(sections) > 1:
                    last_section = sections[-1].strip()
                    lines = last_section.split('\n')
                    header = lines[0].strip()
                    date_match = _re.match(r'(\d{4}-\d{2}-\d{2})', header)
                    latest_evidence = {
                        'date': date_match.group(1) if date_match else header[:10],
                        'title': header,
                    }
            except Exception:
                pass

        checklist_file = docs_dir / "READINESS_CHECKLIST.md"
        if checklist_file.exists():
            try:
                content = checklist_file.read_text(encoding="utf-8")
                table_match = _re.search(
                    r'\| Gate \| Status \| Blocked By \|\n\|[-|]+\n((?:\|.*\n)*)',
                    content
                )
                if table_match:
                    rows = table_match.group(1).strip().split('\n')
                    for row in rows:
                        cells = [c.strip() for c in row.split('|') if c.strip()]
                        if len(cells) >= 2:
                            gates_total += 1
                            status_text = cells[1]
                            if '🟢' in status_text or ('ready' in status_text.lower() and 'not ready' not in status_text.lower()):
                                gates_ready += 1
            except Exception:
                pass

        # ── 6. Research counts ──
        crypto_pairs = 0
        crypto_file = docs_dir / "CRYPTO_WATCHLIST.md"
        if crypto_file.exists():
            try:
                content = crypto_file.read_text(encoding="utf-8")
                table_match = _re.search(
                    r'\| # \| Score \| Exchange \| Symbol.*\n\|[-|]+\n((?:\|.*\n)*)',
                    content
                )
                if table_match:
                    crypto_pairs = len([r for r in table_match.group(1).strip().split('\n') if r.strip()])
            except Exception:
                pass

        # ── 7. Paper grid trial (if exists) ──
        paper_trial = None
        trial_file = data_dir / "paper_grid_1day.json"
        if trial_file.exists():
            try:
                import json as _json
                paper_trial = _json.loads(trial_file.read_text(encoding="utf-8"))
                if isinstance(paper_trial, dict):
                    _snapshots = paper_trial.get('snapshots') or []
                    _final_price = float(paper_trial.get('final_price') or 0)
                    if _final_price <= 0 and _snapshots:
                        _fallback_price = float((_snapshots[-1] or {}).get('price') or 0)
                        if _fallback_price > 0:
                            paper_trial['final_price'] = _fallback_price
                            paper_trial['final_price_source'] = 'last_snapshot'
                            _baseline = float(paper_trial.get('baseline_price') or 0)
                            if _baseline > 0:
                                paper_trial['price_change_pct'] = round((_fallback_price - _baseline) / _baseline * 100, 3)
                    if not paper_trial.get('status'):
                        _duration = float(paper_trial.get('duration_hours') or 0)
                        paper_trial['status'] = 'completed' if _duration >= 23.5 else 'partial'
            except Exception:
                pass

        # ── 8+9 moved after dynamic gates (section 12) for correct flow ──

        # ── 10. Capital snapshot ──
        paper_bankroll = 0.0
        peak_bankroll = 0.0
        poly_max_positions = 0
        poly_position_size = 0.0
        try:
            paper_bankroll = poly_status.get('alpha', {}).get('bankroll', {}).get('current', 0.0)
            peak_bankroll = poly_status.get('alpha', {}).get('bankroll', {}).get('peak', 0.0)
            poly_max_positions = poly_status.get('config', {}).get('max_positions', 0)
            poly_position_size = poly_status.get('config', {}).get('position_size_usdc', 0.0)
        except Exception:
            pass

        max_allowed_exposure = poly_max_positions * poly_position_size if poly_max_positions else 0.0
        estimated_exposure = active_positions * poly_position_size if active_positions else 0.0
        bankroll_pnl = paper_bankroll - 100.0  # initial bankroll is $100

        # Paper bot drawdown (the meaningful one for capital display)
        paper_drawdown_pct = 0.0
        if peak_bankroll > 0:
            paper_drawdown_pct = ((peak_bankroll - paper_bankroll) / peak_bankroll) * 100
            paper_drawdown_pct = round(max(0, paper_drawdown_pct), 2)

        capital = {
            'paper_bankroll': round(paper_bankroll, 2),
            'peak_bankroll': round(peak_bankroll, 2),
            'bankroll_pnl': round(bankroll_pnl, 2),
            'active_positions': active_positions,
            'max_positions': poly_max_positions,
            'estimated_exposure': round(estimated_exposure, 2),
            'max_allowed_exposure': round(max_allowed_exposure, 2),
            'drawdown_pct': paper_drawdown_pct,
            'max_drawdown_pct': round(max_drawdown, 2),
            'kill_switch_active': poly_kill_switch,
            'risk_source': 'paper_bot',
            'grid_running': grid_running,
            'grid_daily_pnl': round(total_pnl, 2),
        }

        # ── 11. Risk sources — explicit about which bot reports what ──
        risk_sources = {
            'paper_bot': {
                'drawdown_pct': paper_drawdown_pct,
                'bankroll': round(paper_bankroll, 2),
                'peak_bankroll': round(peak_bankroll, 2),
                'kill_switch_active': poly_kill_switch,
                'kill_reason': poly_kill_reason,
                'active_positions': active_positions,
            },
            'grid_bot': {
                'drawdown_pct': round(drawdown_pct, 2),
                'halted': kill_switch_active,
                'running': grid_running,
                'daily_pnl': round(total_pnl, 2),
            },
        }

        # Add arbitrage paper bot to risk sources
        try:
            from app.arbitrage_paper_bot import get_arb_paper_bot
            _arb_bot = get_arb_paper_bot()
            _arb_status = _arb_bot.get_status()
            risk_sources['arb_paper_bot'] = {
                'running': _arb_status.get('running', False),
                'capital_thb': _arb_status.get('capital_thb', 0),
                'pnl_thb': _arb_status.get('pnl_thb', 0),
                'total_trades': _arb_status.get('total_trades', 0),
                'win_rate': _arb_status.get('win_rate', 0),
                'opportunities_found': _arb_status.get('opportunities_found', 0),
            }
        except Exception as e:
            logger.debug("Could not get arb_paper_bot status: %s", e)

        # ── 12. Dynamic gates — compute blocked_by from live state ──
        dynamic_gates = []
        _gate_defs = [
            ('Enable Dry-Run', []),
            ('Reset Kill Switch', ['Need dry-run evidence first']),
            ('Micro-Live', ['Need kill switch reset first']),
            ('Production Deploy', ['Need domain/secrets/prod env']),
        ]
        for _gi, (_gname, _gdefault_block) in enumerate(_gate_defs):
            _blockers = []
            if _gi == 0:
                # Gate 1: check live conditions
                if poly_kill_switch:
                    _blockers.append(f'Kill switch active ({poly_kill_reason})' if poly_kill_reason else 'Kill switch active')
                if active_positions > poly_max_positions:
                    _blockers.append(f'{active_positions} active positions (target \u2264 {poly_max_positions})')
                if paper_drawdown_pct > max_drawdown:
                    _blockers.append(f'Drawdown {paper_drawdown_pct:.1f}% exceeds limit {max_drawdown:.1f}%')
            else:
                # Subsequent gates: blocked if previous gate not satisfied
                _prev_blockers = dynamic_gates[_gi - 1]['blocked_by'] if dynamic_gates else ['Previous gate not ready']
                if _prev_blockers:
                    _blockers = _gdefault_block
            _is_ready = len(_blockers) == 0
            dynamic_gates.append({
                'name': _gname,
                'status': 'ready' if _is_ready else 'not_ready',
                'status_text': 'Ready' if _is_ready else 'Not ready',
                'blocked_by': '; '.join(_blockers) if _blockers else '',
            })
        # Recompute gates_ready from dynamic gates
        gates_ready = sum(1 for g in dynamic_gates if g['status'] == 'ready')

        # ── 8. Compute decision + next trigger (uses live dynamic state) ──
        # Use paper bot kill switch — the dominant risk source for BookFinance
        effective_kill = poly_kill_switch
        if effective_kill:
            current_decision = 'WAIT'
            next_trigger = poly_kill_reason or 'Reset kill switch after evidence collection'
        elif gates_ready < gates_total:
            current_decision = 'REVIEW_SIGNALS'
            next_trigger = f'Complete {gates_total - gates_ready} remaining gate(s)'
        elif not grid_running:
            current_decision = 'ENABLE_DRY_RUN'
            next_trigger = 'Enable dry-run mode with validated parameters'
        else:
            current_decision = 'MONITOR'
            next_trigger = 'Continue monitoring live operations'

        # ── 9. Build structured Today brief (uses live dynamic state) ──
        _headline_map = {
            'WAIT': 'Capital protection active — all trading paused',
            'REVIEW_SIGNALS': f'Reviewing signals — {gates_ready}/{gates_total} gates ready',
            'ENABLE_DRY_RUN': 'Evidence gates satisfied — ready to enable dry-run',
            'MONITOR': 'Grid live — monitoring operations',
        }
        headline = _headline_map.get(current_decision, 'Unknown state')

        _parts = []
        if current_decision == 'WAIT':
            _parts.append('Capital protection is active — all trading is paused.')
        elif current_decision == 'REVIEW_SIGNALS':
            _parts.append(f'Reviewing signals: {gates_ready}/{gates_total} evidence gates ready.')
        elif current_decision == 'ENABLE_DRY_RUN':
            _parts.append('Evidence gates are satisfied. Grid is idle — ready to enable dry-run.')
        else:
            _parts.append('Grid is live and monitoring.')

        if active_positions or resolved_positions:
            _parts.append(f'{active_positions} active position(s), {resolved_positions} resolved.')
        else:
            _parts.append('No open exposure.')

        if grid_running:
            _pnl_str = f'{total_pnl:+,.2f}' if total_pnl else '0.00'
            _parts.append(f'Today: {total_fills} fill(s), PnL {_pnl_str} THB.')
        elif paper_trial:
            _trial_status = paper_trial.get('status', 'completed') if isinstance(paper_trial, dict) else 'completed'
            _trial_hours = paper_trial.get('duration_hours') if isinstance(paper_trial, dict) else None
            _trial_fills = paper_trial.get('orders_filled') if isinstance(paper_trial, dict) else None
            if _trial_status == 'running':
                _parts.append('Paper grid observation is running.')
            else:
                _hours_text = f'{_trial_hours:.1f}h' if isinstance(_trial_hours, (int, float)) else 'recorded'
                _fills_text = f', {_trial_fills} fill(s)' if isinstance(_trial_fills, int) else ''
                _parts.append(f'Paper grid observation {_trial_status}: {_hours_text}{_fills_text}.')
        else:
            _parts.append('No grid activity.')

        _sh = system_health if isinstance(system_health, dict) else {}
        _sh_api = _sh.get('strategy_api', 'unknown')
        _sh_redis = _sh.get('redis_connected', False)
        if _sh_api == 'healthy' and _sh_redis:
            _parts.append('All systems healthy.')
        elif _sh_api == 'healthy':
            _parts.append('Strategy API is healthy. Redis connection issue.')
        else:
            _parts.append(f'System health: {_sh_api}.')

        _parts.append(f'Next: {next_trigger}.')
        ai_summary = ' '.join(_parts)

        _action_map = {
            'WAIT': 'Wait for kill switch reset after evidence review.',
            'REVIEW_SIGNALS': 'Review per-signal PnL as more positions resolve.',
            'ENABLE_DRY_RUN': 'Enable dry-run mode with validated parameters.',
            'MONITOR': 'No action needed — continue monitoring.',
        }
        human_action = _action_map.get(current_decision, 'Review system state.')

        blocked_by = []
        if effective_kill:
            blocked_by.append('Kill switch is active')
        if gates_ready < gates_total:
            blocked_by.append(f'{gates_total - gates_ready} readiness gate(s) incomplete')
        if active_positions > poly_max_positions:
            blocked_by.append(f'{active_positions} active positions (target \u2264 {poly_max_positions})')
        if gates_ready >= gates_total and not grid_running and not effective_kill:
            blocked_by.append('Grid not yet running')

        today_brief = {
            'headline': headline,
            'summary': ai_summary,
            'human_action': human_action,
            'blocked_by': blocked_by,
        }

        return {
            'ai_summary': ai_summary,
            'today': today_brief,
            'timestamp': _dt.utcnow().isoformat() + 'Z',
            'current_decision': current_decision,
            'next_trigger': next_trigger,
            'kill_switch': {
                'active': poly_kill_switch,
                'reason': poly_kill_reason,
                'drawdown_pct': paper_drawdown_pct,
                'max_drawdown_pct': max_drawdown,
                'source': 'paper_bot',
            },
            'positions': {
                'active': active_positions,
                'resolved': resolved_positions,
            },
            'grid': {
                'running': grid_running,
                'daily_fills': total_fills,
                'daily_pnl': total_pnl,
            },
            'evidence': {
                'latest': latest_evidence,
                'gates_ready': gates_ready,
                'gates_total': gates_total,
                'gates': dynamic_gates,
            },
            'research': {
                'crypto_pairs': crypto_pairs,
            },
            'paper_trial': paper_trial,
            'system_health': system_health,
            'capital': capital,
            'risk_sources': risk_sources,
        }


# Create default app instance
app = create_app()
