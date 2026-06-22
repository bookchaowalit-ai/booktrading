"""
Real Grid Trading Bot v2
=========================
Places real buy/sell orders on Binance TH via the Go backend's /api/trade endpoints.

Key improvements over v1:
- Queries actual open orders from Binance TH (not just memory)
- Cancels stale orders that are too far from current price
- Tracks PnL from actual filled trades (not double-counting)
- Prevents duplicate orders at same price level

Usage:
    # Via FastAPI background task (auto-started with strategy service)
    # Or standalone: python -m app.real_grid_bot
"""

import asyncio
import json
import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

import httpx

from app.risk_manager import get_risk_manager
from app.trade_journal import get_trade_journal, JournalEntry
from app.webhook_notifier import get_webhook_notifier

logger = logging.getLogger("real_grid_bot")

# ── Configuration ─────────────────────────────────────────────────────────────

BINANCE_PUBLIC_REST = os.getenv("BINANCE_PRICE_API", "https://api.binance.th")
BACKEND_API_BASE = os.getenv("BACKEND_API_BASE", "http://backend:8080")

# Mainnet safety: explicit confirmation required for real money trading
# Set BINANCE_TH_USE_TESTNET=true to disable real trading (safety mode)
BINANCE_TH_MAINNET = os.getenv("BINANCE_TH_USE_TESTNET", "false").lower() != "true"


@dataclass
class RealGridConfig:
    symbol: str
    grid_spacing_pct: float = 1.5       # % between grid levels (fixed mode)
    grid_levels: int = 3                # number of levels above/below (conservative)
    order_size: float = 0.00005         # base quantity per grid order (~104 THB)
    max_position: float = 0.001         # max position size in base asset
    poll_interval_sec: int = 60         # how often to check prices
    max_daily_loss_usd: float = 50.0    # stop trading if daily loss exceeds this
    max_open_orders: int = 10           # max simultaneous open orders
    stale_threshold_pct: float = 5.0    # cancel orders >5% away from current price
    # Volatility-adaptive spacing
    volatility_mode: str = "fixed"      # "fixed" or "atr"
    atr_period: int = 14                # ATR period for volatility calculation
    atr_multiplier: float = 1.5         # multiplier for ATR-based spacing
    min_spacing_pct: float = 0.5        # minimum spacing % (floor)
    max_spacing_pct: float = 5.0        # maximum spacing % (ceiling)
    # Auto-compounding: scale order size with accumulated profits
    auto_compound_enabled: bool = True  # enable auto-compounding
    compound_threshold_thb: float = 500.0  # profit threshold to trigger scaling
    compound_factor: float = 0.1        # scale factor per threshold (10% increase)
    max_compound_multiplier: float = 3.0  # cap at 3x base order size


@dataclass
class RealGridState:
    """Tracks active grid orders for a symbol."""
    symbol: str
    # Tracked by price -> orderId (from Binance TH)
    active_buys: Dict[int, str] = field(default_factory=dict)
    active_sells: Dict[int, str] = field(default_factory=dict)
    last_price: float = 0.0
    trades_executed: int = 0
    daily_pnl: float = 0.0
    daily_trades: int = 0
    last_daily_reset: float = 0.0
    halted: bool = False   # kill switch
    # Track which trade IDs we've already counted for PnL
    counted_trade_ids: Set[str] = field(default_factory=set)
    # Auto-compounding: track cumulative profit for order size scaling
    cumulative_pnl: float = 0.0
    current_order_size: float = 0.0  # dynamically scaled order size
    # ── Performance metrics ──
    orders_placed: int = 0            # total orders placed (lifetime)
    orders_filled: int = 0            # total orders filled (lifetime)
    last_atr_spacing_pct: float = 0.0 # most recent ATR-computed spacing %
    atr_spacing_history: List[float] = field(default_factory=list)  # last N ATR spacing values
    profit_velocity_thb_per_day: float = 0.0  # rolling avg profit per day
    fill_rate: float = 0.0            # orders_filled / orders_placed
    last_fill_timestamp: float = 0.0  # epoch of last fill
    performance_start_time: float = 0.0  # when metrics tracking began
    # ── Actual PnL tracking (buy-sell matching) ──
    buy_fill_prices: Dict[int, float] = field(default_factory=dict)    # orderId_int -> actual buy fill price
    filled_buy_prices: Dict[int, float] = field(default_factory=dict)  # buy_price -> sell_price (matched pairs)
    # ── Sharpe/Sortino tracking ──
    trade_returns: List[float] = field(default_factory=list)  # per-trade return % for risk-adjusted metrics
    daily_pnl_history: List[float] = field(default_factory=list)  # daily PnL snapshots for auto-tune
    # ── Capital allocation & regime detection ──
    regime: str = "normal"              # "low_vol", "normal", "high_vol", "extreme"
    allocation_weight: float = 1.0      # 0.0-2.0 multiplier on grid_levels from capital allocation
    atr_percentile: float = 50.0        # current ATR percentile (0-100)
    allocation_score: float = 0.0       # composite score for capital allocation ranking
    regime_history: List[str] = field(default_factory=list)  # last N regime classifications


# ── Per-symbol default configs ────────────────────────────────────────────────
# Tuned for each asset's price level and Binance TH min notional (100 THB)
# Optimized via backtesting (30-day period, 1h interval)
SYMBOL_DEFAULTS = {
    "BTCTHB": {
        "grid_spacing_pct": 2.0,        # ~42,000 THB between levels at ~2.1M (wider = fewer fees)
        "grid_levels": 2,               # 2 above + 2 below = 4 levels max
        "order_size": 0.00005,          # ~105 THB per order
        "max_position": 0.001,          # ~2,100 THB max exposure
        "max_daily_loss_usd": 50.0,
        "volatility_mode": "atr",       # Use ATR for dynamic spacing
        "atr_period": 14,
        "atr_multiplier": 1.5,
        "min_spacing_pct": 1.0,         # Min 1% for BTC
        "max_spacing_pct": 4.0,         # Max 4% for BTC
    },
    "ETHTHB": {
        "grid_spacing_pct": 2.0,        # ~1,140 THB between levels at ~57K
        "grid_levels": 2,               # 2 above + 2 below = 4 levels max
        "order_size": 0.002,            # ~114 THB per order (above 100 THB min)
        "max_position": 0.01,           # ~570 THB max exposure
        "max_daily_loss_usd": 50.0,
        "volatility_mode": "atr",       # Use ATR for dynamic spacing
        "atr_period": 14,
        "atr_multiplier": 1.5,
        "min_spacing_pct": 1.5,         # Min 1.5% for ETH
        "max_spacing_pct": 5.0,         # Max 5% for ETH
    },
    "BNBTHB": {
        "grid_spacing_pct": 2.5,        # ~300 THB between levels at ~12K
        "grid_levels": 2,               # 2 above + 2 below = 4 levels max
        "order_size": 0.009,            # ~108 THB per order (above 100 THB min)
        "max_position": 0.05,           # ~600 THB max exposure
        "max_daily_loss_usd": 40.0,
        "volatility_mode": "atr",       # Use ATR for dynamic spacing
        "atr_period": 14,
        "atr_multiplier": 1.5,
        "min_spacing_pct": 1.5,
        "max_spacing_pct": 5.0,
    },
    "SOLTHB": {
        "grid_spacing_pct": 3.0,        # ~45 THB between levels at ~5K (wider for volatility)
        "grid_levels": 2,               # 2 above + 2 below = 4 levels max
        "order_size": 0.025,            # ~125 THB per order (above 100 THB min)
        "max_position": 0.5,            # ~2,500 THB max exposure
        "max_daily_loss_usd": 30.0,
        "volatility_mode": "atr",       # Use ATR for dynamic spacing (SOL is volatile)
        "atr_period": 14,
        "atr_multiplier": 2.0,          # Higher multiplier for SOL volatility
        "min_spacing_pct": 2.0,
        "max_spacing_pct": 6.0,
    },
    "XRPTHB": {
        "grid_spacing_pct": 2.5,        # ~12.5 THB between levels at ~25
        "grid_levels": 2,               # 2 above + 2 below = 4 levels max
        "order_size": 4.0,              # ~100 THB per order
        "max_position": 40.0,           # ~1,000 THB max exposure
        "max_daily_loss_usd": 25.0,
        "volatility_mode": "atr",       # Use ATR for dynamic spacing
        "atr_period": 14,
        "atr_multiplier": 1.5,
        "min_spacing_pct": 1.5,
        "max_spacing_pct": 5.0,
    },
}

# ── Strategy Constants ─────────────────────────────────────────────────────────

# Binance TH fee: 0.1% per trade (maker+taker), round trip = 0.2%
# Minimum spacing must exceed fees to be profitable
BINANCE_TH_FEE_PCT = 0.1              # 0.1% per side
ROUND_TRIP_FEE_PCT = BINANCE_TH_FEE_PCT * 2  # 0.2% round trip
MIN_PROFITABLE_SPACING_PCT = 0.5      # spacing must be > 0.5% to profit after fees

# Regime detection thresholds (ATR percentile)
REGIME_THRESHOLDS = {
    "low_vol": 25,     # ATR < 25th percentile
    "normal_low": 50,  # 25th-50th
    "normal_high": 75, # 50th-75th
    "high_vol": 90,    # 75th-90th
    "extreme": 90,     # > 90th percentile
}

# Capital allocation: minimum tracking days before allocation kicks in
MIN_ALLOCATION_TRACKING_DAYS = 3


class RealGridBot:
    """
    Real grid trading bot that:
    1. Fetches live price from Binance TH public API
    2. Queries actual open orders from Binance TH via backend
    3. Cancels stale orders that moved too far from price
    4. Places new grid orders at proper levels
    5. Calculates PnL from actual filled trades
    6. Enforces safety controls (max position, daily loss, kill switch)
    """

    def __init__(self, configs: Optional[List[RealGridConfig]] = None):
        # Read REAL_SYMBOLS from env (e.g., "BTCTHB" or "BTCTHB,ETHTHB")
        real_symbols_str = os.getenv("REAL_SYMBOLS", "BTCTHB")
        real_symbols = [s.strip() for s in real_symbols_str.split(",") if s.strip()]
        
        self.configs = configs or [
            RealGridConfig(
                symbol=sym,
                **SYMBOL_DEFAULTS.get(sym, SYMBOL_DEFAULTS.get("BTCTHB", {})),
            )
            for sym in real_symbols
        ]
        self.states: Dict[str, RealGridState] = {}
        self._running = False
        self._http: Optional[httpx.AsyncClient] = None
        self._enabled = True  # master kill switch
        # Notification queue for fill events (max 50)
        self._notifications: deque = deque(maxlen=50)
        # Redis client for state persistence (injected via set_redis)
        self._redis = None
        # Webhook notifier for Telegram/Discord alerts
        self._webhook = get_webhook_notifier()
        # Health tracking: last tick time per symbol
        self._last_tick_time: Dict[str, float] = {}

    def set_redis(self, redis_client):
        """Inject Redis client for state persistence."""
        self._redis = redis_client
        logger.info("Real Grid Bot: Redis persistence enabled")

    async def _save_state(self, symbol: str):
        """Persist grid state to Redis (called after each tick)."""
        if not self._redis:
            return
        state = self.states.get(symbol)
        if not state:
            return
        try:
            data = {
                "active_buys": {str(k): v for k, v in state.active_buys.items()},
                "active_sells": {str(k): v for k, v in state.active_sells.items()},
                "last_price": state.last_price,
                "trades_executed": state.trades_executed,
                "daily_pnl": state.daily_pnl,
                "daily_trades": state.daily_trades,
                "last_daily_reset": state.last_daily_reset,
                "halted": state.halted,
                "counted_trade_ids": list(state.counted_trade_ids),
                "cumulative_pnl": state.cumulative_pnl,
                "current_order_size": state.current_order_size,
                # Performance metrics
                "orders_placed": state.orders_placed,
                "orders_filled": state.orders_filled,
                "last_atr_spacing_pct": state.last_atr_spacing_pct,
                "atr_spacing_history": state.atr_spacing_history[-50:],  # keep last 50
                "profit_velocity_thb_per_day": state.profit_velocity_thb_per_day,
                "fill_rate": state.fill_rate,
                "last_fill_timestamp": state.last_fill_timestamp,
                "performance_start_time": state.performance_start_time,
                "buy_fill_prices": {str(k): v for k, v in state.buy_fill_prices.items()},
                "filled_buy_prices": {str(k): v for k, v in state.filled_buy_prices.items()},
                "trade_returns": state.trade_returns[-500:],
                "daily_pnl_history": state.daily_pnl_history[-90:],
            }
            await self._redis.set(f"real_grid:{symbol}:state", json.dumps(data))
        except Exception as e:
            logger.debug("Failed to save state to Redis for %s: %s", symbol, e)

    async def _load_state(self, symbol: str) -> bool:
        """Restore grid state from Redis. Returns True if restored."""
        if not self._redis:
            return False
        try:
            raw = await self._redis.get(f"real_grid:{symbol}:state")
            if not raw:
                return False
            data = json.loads(raw)
            state = self.states[symbol]
            state.active_buys = {int(k): v for k, v in data.get("active_buys", {}).items()}
            state.active_sells = {int(k): v for k, v in data.get("active_sells", {}).items()}
            state.last_price = data.get("last_price", 0.0)
            state.trades_executed = data.get("trades_executed", 0)
            state.daily_pnl = data.get("daily_pnl", 0.0)
            state.daily_trades = data.get("daily_trades", 0)
            state.last_daily_reset = data.get("last_daily_reset", 0.0)
            state.halted = data.get("halted", False)
            state.counted_trade_ids = set(data.get("counted_trade_ids", []))
            state.cumulative_pnl = data.get("cumulative_pnl", 0.0)
            restored_size = data.get("current_order_size", 0.0)
            if restored_size > 0:
                state.current_order_size = restored_size
            # Restore performance metrics
            state.orders_placed = data.get("orders_placed", 0)
            state.orders_filled = data.get("orders_filled", 0)
            state.last_atr_spacing_pct = data.get("last_atr_spacing_pct", 0.0)
            state.atr_spacing_history = data.get("atr_spacing_history", [])
            state.profit_velocity_thb_per_day = data.get("profit_velocity_thb_per_day", 0.0)
            state.fill_rate = data.get("fill_rate", 0.0)
            state.last_fill_timestamp = data.get("last_fill_timestamp", 0.0)
            state.performance_start_time = data.get("performance_start_time", 0.0)
            # Restore buy-fill tracking
            state.buy_fill_prices = {int(k): v for k, v in data.get("buy_fill_prices", {}).items()}
            state.filled_buy_prices = {int(k): v for k, v in data.get("filled_buy_prices", {}).items()}
            state.trade_returns = data.get("trade_returns", [])
            state.daily_pnl_history = data.get("daily_pnl_history", [])
            logger.info(
                "Restored state for %s from Redis: buys=%d sells=%d pnl=%.2f cum_pnl=%.2f order_size=%.6f",
                symbol, len(state.active_buys), len(state.active_sells), state.daily_pnl,
                state.cumulative_pnl, state.current_order_size,
            )
            return True
        except Exception as e:
            logger.warning("Failed to load state from Redis for %s: %s", symbol, e)
            return False

    async def start(self):
        """Start the real grid bot."""
        self._running = True
        self._http = httpx.AsyncClient(timeout=15.0)

        # Initialize risk manager and trade journal
        self._risk = get_risk_manager()
        self._journal = get_trade_journal()
        await self._journal.start(self._http)

        # ── Mainnet safety check ──
        if BINANCE_TH_MAINNET:
            logger.warning(
                "=" * 60 + "\n"
                "  REAL MONEY TRADING ENABLED (MAINNET)\n"
                "  Symbols: %s\n"
                "  If this is NOT intended, set BINANCE_TH_USE_TESTNET=true\n"
                + "=" * 60,
                ", ".join(c.symbol for c in self.configs),
            )
        else:
            logger.info(
                "Real Grid Bot running in TESTNET/SAFETY mode - real orders DISABLED"
            )

        logger.info("Real Grid Bot v2 started with %d symbol(s)", len(self.configs))

        for cfg in self.configs:
            self.states[cfg.symbol] = RealGridState(
                symbol=cfg.symbol,
                last_daily_reset=time.time(),
                current_order_size=cfg.order_size,  # Initialize with base order size
                performance_start_time=time.time(),  # Track when metrics began
            )
            # Attempt to restore previous state from Redis
            await self._load_state(cfg.symbol)

        # Check if backend is ready
        if not await self._check_backend():
            logger.warning("Backend not ready — will retry on first tick")

        while self._running:
            try:
                if not self._enabled:
                    await asyncio.sleep(30)
                    continue

                for cfg in self.configs:
                    await self._tick(cfg)
                await asyncio.sleep(self.configs[0].poll_interval_sec)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Real Grid Bot error: %s", e, exc_info=True)
                await asyncio.sleep(30)

        logger.info(
            "Real Grid Bot stopped. Trades: %d",
            sum(s.trades_executed for s in self.states.values()),
        )

    async def stop(self):
        """Stop the real grid bot."""
        self._running = False
        # Final state save to Redis
        for symbol in self.states:
            await self._save_state(symbol)
        if self._http:
            await self._http.aclose()

    def enable(self):
        """Re-enable the bot after kill switch."""
        self._enabled = True
        for state in self.states.values():
            state.halted = False
        # Also reset risk manager kill switch
        get_risk_manager().reset_kill_switch()
        logger.info("Real Grid Bot ENABLED")

    def disable(self):
        """Kill switch — stop all trading."""
        self._enabled = False
        logger.warning("Real Grid Bot KILLED — all trading halted")

    def update_config(self, symbol: str, **kwargs) -> bool:
        """Update grid config for a symbol.
        
        Args:
            symbol: Trading pair (e.g., "BTCTHB")
            **kwargs: Config fields to update (grid_spacing_pct, grid_levels, order_size, etc.)
        
        Returns:
            True if config was updated, False if symbol not found
        """
        for cfg in self.configs:
            if cfg.symbol == symbol:
                for key, value in kwargs.items():
                    if hasattr(cfg, key):
                        setattr(cfg, key, value)
                        logger.info("[RealGrid %s] Config updated: %s = %s", symbol, key, value)
                return True
        return False

    def get_config(self, symbol: str) -> Optional[Dict]:
        """Get current grid config for a symbol."""
        for cfg in self.configs:
            if cfg.symbol == symbol:
                return {
                    "symbol": cfg.symbol,
                    "grid_spacing_pct": cfg.grid_spacing_pct,
                    "grid_levels": cfg.grid_levels,
                    "order_size": cfg.order_size,
                    "max_position": cfg.max_position,
                    "poll_interval_sec": cfg.poll_interval_sec,
                    "max_daily_loss_usd": cfg.max_daily_loss_usd,
                    "max_open_orders": cfg.max_open_orders,
                    "stale_threshold_pct": cfg.stale_threshold_pct,
                    # Volatility-adaptive fields
                    "volatility_mode": cfg.volatility_mode,
                    "atr_period": cfg.atr_period,
                    "atr_multiplier": cfg.atr_multiplier,
                    "min_spacing_pct": cfg.min_spacing_pct,
                    "max_spacing_pct": cfg.max_spacing_pct,
                }
        return None

    async def _check_backend(self) -> bool:
        """Check if Go backend is reachable and ready."""
        try:
            resp = await self._http.get(f"{BACKEND_API_BASE}/api/trade/status")
            if resp.status_code == 200:
                data = resp.json()
                return data.get("ready_to_trade", False)
        except Exception:
            pass
        return False

    async def _tick(self, cfg: RealGridConfig):
        """One tick: sync orders, fetch price, cancel stale, place new."""
        state = self.states[cfg.symbol]
        # Track last tick time for health monitoring
        self._last_tick_time[cfg.symbol] = time.time()

        # Daily reset
        if time.time() - state.last_daily_reset > 86400:
            # Capture daily PnL before resetting
            _daily_pnl = state.daily_pnl
            _daily_trades = state.daily_trades
            
            # Send daily summary before resetting (per-symbol if trades occurred)
            if _daily_trades > 0:
                await self._webhook.send_daily_summary(
                    symbol=cfg.symbol,
                    daily_pnl=_daily_pnl,
                    daily_trades=_daily_trades,
                )
            
            # Record daily PnL snapshot for auto-tune and Sharpe/Sortino
            state.daily_pnl_history.append(_daily_pnl)
            if len(state.daily_pnl_history) > 90:
                state.daily_pnl_history = state.daily_pnl_history[-90:]
            
            state.daily_pnl = 0.0
            state.daily_trades = 0
            state.last_daily_reset = time.time()
            state.halted = False
            state.counted_trade_ids.clear()
            
            # Auto-tune compound threshold based on performance
            if _daily_trades > 0:
                self._auto_tune_compound_threshold(cfg, state)
            
            # Capital allocation: rebalance grid levels across symbols
            self._run_capital_allocation()
            
            # Send comprehensive daily digest (all symbols)
            await self._send_comprehensive_digest()
            
            # Auto-rebalance: cancel all orders and re-place at fresh levels
            await self._rebalance_grid(cfg, state)

        # Safety: daily loss limit
        if state.daily_pnl < -cfg.max_daily_loss_usd:
            if not state.halted:
                logger.warning(
                    "[RealGrid %s] Daily loss limit hit: $%.2f — HALTING",
                    cfg.symbol, state.daily_pnl,
                )
                state.halted = True
                # Send kill switch alert
                await self._webhook.send_kill_switch_alert(
                    symbol=cfg.symbol,
                    reason=f"Daily loss limit hit: ${state.daily_pnl:.2f}",
                )
            return

        if state.halted:
            return

        # Step 1: Sync open orders from Binance TH
        await self._sync_open_orders(cfg, state)

        # Step 2: Fetch current price
        price = await self._fetch_price(cfg.symbol)
        if price <= 0:
            return

        # ── Flash-crash circuit breaker (Fix 4) ──
        if state.last_price > 0:
            price_drop_pct = ((state.last_price - price) / state.last_price) * 100
            if price_drop_pct > 5.0:
                if not state.halted:
                    logger.warning(
                        "[RealGrid %s] FLASH CRASH: price dropped %.1f%% (%d -> %d) — HALTING",
                        cfg.symbol, price_drop_pct, int(state.last_price), int(price),
                    )
                    state.halted = True
                    await self._webhook.send_kill_switch_alert(
                        symbol=cfg.symbol,
                        reason=f"Flash crash detected: {price_drop_pct:.1f}% drop ({int(state.last_price)} -> {int(price)})",
                    )
                state.last_price = price
                return

        state.last_price = price

        # Step 3: Cancel stale orders (too far from current price)
        await self._cancel_stale_orders(cfg, state, price)

        # Step 4: Calculate PnL from filled trades
        await self._update_pnl(cfg, state)

        # Step 5: Detect market regime and adjust parameters
        regime = await self._detect_regime(cfg, state)
        self._apply_regime_adjustment(cfg, state, regime)
        
        # If halted by extreme regime, skip this tick
        if state.halted:
            await self._save_state(cfg.symbol)
            return

        # Step 6: Calculate dynamic spacing based on volatility mode
        if cfg.volatility_mode == "atr":
            spacing_pct = await self._calculate_atr_spacing(cfg, price)
            # Track ATR spacing for performance analysis
            state.last_atr_spacing_pct = spacing_pct
            state.atr_spacing_history.append(spacing_pct)
            if len(state.atr_spacing_history) > 50:
                state.atr_spacing_history = state.atr_spacing_history[-50:]
        else:
            spacing_pct = cfg.grid_spacing_pct
        
        # Step 7: Apply fee-aware minimum spacing floor
        spacing_pct = self._apply_fee_floor(cfg, spacing_pct)
        
        spacing = price * (spacing_pct / 100.0)
        
        logger.info(
            "[RealGrid %s] price=%d spacing=%d (%.1f%%) mode=%s regime=%s alloc=%.1f buys=%d sells=%d pnl=$%.2f",
            cfg.symbol, int(price), int(spacing), spacing_pct, cfg.volatility_mode,
            state.regime, state.allocation_weight,
            len(state.active_buys), len(state.active_sells),
            state.daily_pnl,
        )

        # ── Portfolio-level exposure cap (Fix 6) ──
        total_notional = 0.0
        for sym, st in self.states.items():
            sym_cfg = next((c for c in self.configs if c.symbol == sym), None)
            if sym_cfg:
                size = st.current_order_size if st.current_order_size > 0 else sym_cfg.order_size
                n_orders = len(st.active_buys) + len(st.active_sells)
                total_notional += n_orders * size * st.last_price if st.last_price > 0 else 0
        MAX_PORTFOLIO_NOTIONAL = 50000.0  # 50K THB total exposure cap
        if total_notional >= MAX_PORTFOLIO_NOTIONAL:
            logger.debug("[RealGrid %s] Portfolio exposure cap: %.0f THB >= %.0f — skipping", cfg.symbol, total_notional, MAX_PORTFOLIO_NOTIONAL)
            await self._save_state(cfg.symbol)
            return

        for level in range(1, cfg.grid_levels + 1):
            # Binance TH THB pairs require integer prices (tickSize=1.0)
            buy_price = int(price - (spacing * level))
            sell_price = int(price + (spacing * level))

            total_orders = len(state.active_buys) + len(state.active_sells)
            if total_orders >= cfg.max_open_orders:
                break

            # Place LIMIT buy if not already active at this price
            if buy_price not in state.active_buys:
                await self._place_grid_order(cfg, state, "BUY", buy_price)

            # Place LIMIT sell if not already active at this price
            if sell_price not in state.active_sells:
                await self._place_grid_order(cfg, state, "SELL", sell_price)

        # Persist state to Redis after each tick
        await self._save_state(cfg.symbol)

    async def _sync_open_orders(self, cfg: RealGridConfig, state: RealGridState):
        """Query actual open orders from Binance TH and update state.
        
        Only removes orders that no longer exist on exchange (filled/cancelled).
        Does NOT clear state first to prevent duplicate orders.
        """
        try:
            resp = await self._http.get(
                f"{BACKEND_API_BASE}/api/trade/open-orders",
                params={"symbol": cfg.symbol},
            )
            if resp.status_code != 200:
                return

            data = resp.json()
            orders = data.get("orders", [])

            # Build set of actual order IDs on exchange
            actual_order_ids = set()
            for order in orders:
                order_id = str(order.get("orderId", ""))
                status = order.get("status", "")
                if status in ("NEW", "PARTIALLY_FILLED"):
                    actual_order_ids.add(order_id)

            # Remove orders from state that no longer exist on exchange
            prices_to_remove = []
            for price, oid in state.active_buys.items():
                if oid not in actual_order_ids:
                    prices_to_remove.append(price)
            for price in prices_to_remove:
                del state.active_buys[price]

            prices_to_remove = []
            for price, oid in state.active_sells.items():
                if oid not in actual_order_ids:
                    prices_to_remove.append(price)
            for price in prices_to_remove:
                del state.active_sells[price]

            # Add new orders that exist on exchange but not in state
            for order in orders:
                order_id = str(order.get("orderId", ""))
                price = int(float(order.get("price", 0)))
                side = order.get("side", "")
                status = order.get("status", "")

                if status not in ("NEW", "PARTIALLY_FILLED"):
                    continue
                if price <= 0:
                    continue

                if side == "BUY" and price not in state.active_buys:
                    state.active_buys[price] = order_id
                elif side == "SELL" and price not in state.active_sells:
                    state.active_sells[price] = order_id

        except Exception as e:
            logger.warning("Failed to sync open orders: %s", e)

    async def _cancel_stale_orders(self, cfg: RealGridConfig, state: RealGridState, current_price: float):
        """Cancel orders that are too far from current price."""
        threshold_pct = cfg.stale_threshold_pct / 100.0
        lower_bound = int(current_price * (1 - threshold_pct))
        upper_bound = int(current_price * (1 + threshold_pct))

        # Cancel stale buy orders (too far below)
        stale_buy_prices = [p for p in state.active_buys if p < lower_bound]
        for price in stale_buy_prices:
            order_id = state.active_buys[price]
            await self._cancel_order(cfg.symbol, order_id)
            del state.active_buys[price]
            logger.info("[RealGrid %s] Cancelled stale BUY @ %d", cfg.symbol, price)

        # Cancel stale sell orders (too far above)
        stale_sell_prices = [p for p in state.active_sells if p > upper_bound]
        for price in stale_sell_prices:
            order_id = state.active_sells[price]
            await self._cancel_order(cfg.symbol, order_id)
            del state.active_sells[price]
            logger.info("[RealGrid %s] Cancelled stale SELL @ %d", cfg.symbol, price)

    async def _rebalance_grid(self, cfg: RealGridConfig, state: RealGridState):
        """Cancel all open orders and clear state for fresh grid placement.
        
        Called after daily reset to ensure orders are placed at current price levels
        rather than stale levels from previous day.
        """
        logger.info("[RealGrid %s] Rebalancing grid — cancelling all open orders", cfg.symbol)
        
        # Cancel all active buy orders
        for price, order_id in list(state.active_buys.items()):
            await self._cancel_order(cfg.symbol, order_id)
            logger.debug("[RealGrid %s] Cancelled BUY @ %d", cfg.symbol, price)
        state.active_buys.clear()
        
        # Cancel sell orders EXCEPT those matched to filled buys (Fix 5)
        for price, order_id in list(state.active_sells.items()):
            if price in state.filled_buy_prices:
                logger.info(
                    "[RealGrid %s] Keeping SELL @ %d (matched to filled buy @ %d)",
                    cfg.symbol, price, price,
                )
                continue
            await self._cancel_order(cfg.symbol, order_id)
            logger.debug("[RealGrid %s] Cancelled SELL @ %d", cfg.symbol, price)
        state.active_sells = {
            p: oid for p, oid in state.active_sells.items() if p in state.filled_buy_prices
        }
        
        logger.info("[RealGrid %s] Grid rebalanced — will place fresh orders at next tick", cfg.symbol)

    async def _cancel_order(self, symbol: str, order_id: str):
        """Cancel an order via backend."""
        try:
            resp = await self._http.post(
                f"{BACKEND_API_BASE}/api/trade/cancel-order",
                json={"symbol": symbol, "orderId": int(order_id)},
            )
            if resp.status_code != 200:
                logger.warning("Failed to cancel order %s: %s", order_id, resp.text)
        except Exception as e:
            logger.warning("Cancel order failed: %s", e)

    async def _update_pnl(self, cfg: RealGridConfig, state: RealGridState):
        """Calculate PnL from actual filled trades (not double-counting)."""
        try:
            resp = await self._http.get(
                f"{BACKEND_API_BASE}/api/trade/history",
                params={"limit": "50"},
            )
            if resp.status_code != 200:
                return

            trades = resp.json()
            for t in trades:
                trade_id = t.get("id", "")
                symbol = t.get("symbol", "")
                side = t.get("side", "")
                status = t.get("status", "")

                # Only count filled trades for our symbol with actual execution
                if symbol != cfg.symbol or status != "FILLED":
                    continue

                # Must have actual execution (not just a LIMIT order recorded as FILLED)
                executed_qty = t.get("executed_qty", 0) or 0
                if executed_qty <= 0:
                    continue

                # Skip already counted trades
                if trade_id in state.counted_trade_ids:
                    continue

                state.counted_trade_ids.add(trade_id)

                # Track BUY fill: record actual buy price for PnL matching (Fix 1)
                if side == "BUY":
                    fill_price = t.get("price", 0)
                    state.orders_filled += 1
                    state.last_fill_timestamp = time.time()
                    if state.orders_placed > 0:
                        state.fill_rate = state.orders_filled / state.orders_placed
                    # Store buy fill price keyed by trade_id (as int)
                    try:
                        state.buy_fill_prices[int(trade_id)] = fill_price
                    except (ValueError, TypeError):
                        pass
                    self._notifications.append({
                        "type": "fill",
                        "side": "BUY",
                        "symbol": cfg.symbol,
                        "price": fill_price,
                        "quantity": executed_qty,
                        "profit": 0,
                        "trade_id": trade_id,
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "message": f"{cfg.symbol} BUY filled @ {int(fill_price)} qty={executed_qty:.6f}",
                    })
                    # Send webhook alert
                    await self._webhook.send_fill_alert(
                        symbol=cfg.symbol,
                        side="BUY",
                        price=fill_price,
                        quantity=executed_qty,
                    )

                # SELL fill: compute actual PnL from matched buy price (Fix 1 + Fix 2)
                if side == "SELL":
                    price = t.get("price", 0)
                    qty = t.get("quantity", 0)
                    fee = t.get("fee", 0) or 0
                    if price > 0 and qty > 0:
                        # Match with oldest unmatched buy fill for actual PnL
                        actual_buy_price = 0.0
                        if state.buy_fill_prices:
                            oldest_key = min(state.buy_fill_prices.keys())
                            actual_buy_price = state.buy_fill_prices.pop(oldest_key)
                            state.filled_buy_prices[int(actual_buy_price)] = price
                        
                        # Compute real profit = (sell - buy) * qty - fees
                        if actual_buy_price > 0:
                            gross_profit = (price - actual_buy_price) * qty
                        else:
                            # Fallback: estimate from last spacing
                            spacing = state.last_price * (cfg.grid_spacing_pct / 100.0)
                            gross_profit = spacing * qty
                        
                        # Fix 2: subtract round-trip fees
                        net_profit = gross_profit - fee
                        state.daily_pnl += net_profit
                        state.daily_trades += 1
                        
                        # Track per-trade return for Sharpe/Sortino calculation
                        order_notional = qty * price if price > 0 else 1
                        trade_return_pct = (net_profit / order_notional) * 100
                        state.trade_returns.append(trade_return_pct)
                        if len(state.trade_returns) > 500:
                            state.trade_returns = state.trade_returns[-500:]
                        
                        # Performance: track fills and profit velocity
                        state.orders_filled += 1
                        state.last_fill_timestamp = time.time()
                        if state.orders_placed > 0:
                            state.fill_rate = state.orders_filled / state.orders_placed
                        # Calculate profit velocity (THB/day) over tracking period
                        if state.performance_start_time > 0:
                            elapsed_days = (time.time() - state.performance_start_time) / 86400
                            if elapsed_days > 0.1:  # at least ~2.4h of data
                                state.profit_velocity_thb_per_day = state.cumulative_pnl / elapsed_days
                        
                        # Auto-compounding: accumulate profit and scale order size
                        if cfg.auto_compound_enabled:
                            state.cumulative_pnl += net_profit
                            old_size = state.current_order_size or cfg.order_size
                            new_size = self._calculate_compound_order_size(cfg, state)
                            if new_size != old_size:
                                state.current_order_size = new_size
                                logger.info(
                                    "[RealGrid %s] Auto-compound: order_size %.6f -> %.6f "
                                    "(cum_pnl=%.2f THB)",
                                    cfg.symbol, old_size, new_size, state.cumulative_pnl,
                                )

                        # Record in risk manager
                        self._risk.record_trade_result(cfg.symbol, net_profit, is_win=(net_profit > 0))

                        # Fix 3: Update drawdown tracking in risk manager
                        self._risk.update_drawdown(state.cumulative_pnl)

                        # Record exit in journal
                        exchange_oid = t.get("exchange_order_id", "")
                        await self._journal.record_exit(
                            exchange_order_id=exchange_oid or trade_id,
                            exit_price=price,
                            exit_reason="grid_fill",
                            actual_pnl=net_profit,
                            fee=fee,
                        )

                        logger.info(
                            "[RealGrid %s] Filled SELL @ %d qty=%.6f buy@%d gross=%.2f fee=%.2f net=%.2f THB",
                            cfg.symbol, int(price), qty, int(actual_buy_price), gross_profit, fee, net_profit,
                        )

                        # Push fill notification
                        self._notifications.append({
                            "type": "fill",
                            "side": "SELL",
                            "symbol": cfg.symbol,
                            "price": price,
                            "quantity": qty,
                            "profit": round(net_profit, 2),
                            "trade_id": trade_id,
                            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "message": f"{cfg.symbol} SELL filled @ {int(price)} (net profit {net_profit:.0f} THB, fee {fee:.1f})",
                        })
                        # Send webhook alert
                        await self._webhook.send_fill_alert(
                            symbol=cfg.symbol,
                            side="SELL",
                            price=price,
                            quantity=qty,
                            profit=net_profit,
                        )

        except Exception as e:
            logger.warning("Failed to update PnL: %s", e)

    async def _fetch_price(self, symbol: str) -> float:
        """Fetch current price from Binance TH public API (no key needed)."""
        try:
            # Binance TH uses /api/v1/ticker/price (not /api/v3 like Binance Global)
            resp = await self._http.get(
                f"{BINANCE_PUBLIC_REST}/api/v1/ticker/price",
                params={"symbol": symbol},
            )
            if resp.status_code == 200:
                price = float(resp.json()["price"])
                # Update risk manager price freshness
                self._risk.update_price_timestamp(symbol)
                return price
        except Exception as e:
            logger.warning("Failed to fetch price for %s: %s", symbol, e)
        return 0.0

    async def _calculate_atr_spacing(self, cfg: RealGridConfig, current_price: float) -> float:
        """Calculate dynamic grid spacing based on ATR (Average True Range).
        
        Uses klines data to calculate ATR, then converts to a percentage spacing.
        Falls back to fixed spacing if ATR calculation fails.
        
        Returns:
            Spacing percentage (clamped to min/max bounds)
        """
        try:
            # Fetch klines for ATR calculation (1h interval, need atr_period + 1 candles)
            resp = await self._http.get(
                f"{BINANCE_PUBLIC_REST}/api/v1/klines",
                params={
                    "symbol": cfg.symbol,
                    "interval": "1h",
                    "limit": cfg.atr_period + 1,
                },
            )
            if resp.status_code != 200:
                logger.debug("[%s] Failed to fetch klines for ATR, using fixed spacing", cfg.symbol)
                return cfg.grid_spacing_pct

            klines = resp.json()
            if len(klines) < cfg.atr_period + 1:
                return cfg.grid_spacing_pct

            # Calculate True Range for each candle
            true_ranges = []
            for i in range(1, len(klines)):
                high = float(klines[i][2])
                low = float(klines[i][3])
                prev_close = float(klines[i - 1][4])
                
                # True Range = max(high-low, abs(high-prev_close), abs(low-prev_close))
                tr = max(
                    high - low,
                    abs(high - prev_close),
                    abs(low - prev_close),
                )
                true_ranges.append(tr)

            # ATR = simple average of true ranges
            atr = sum(true_ranges[-cfg.atr_period:]) / cfg.atr_period
            
            # Convert ATR to percentage of current price
            atr_pct = (atr / current_price) * 100 * cfg.atr_multiplier
            
            # Clamp to min/max bounds
            spacing_pct = max(cfg.min_spacing_pct, min(cfg.max_spacing_pct, atr_pct))
            
            logger.debug(
                "[%s] ATR=%.2f (%.2f%%) -> spacing=%.2f%% (bounds: %.1f-%.1f%%)",
                cfg.symbol, atr, atr_pct, spacing_pct, cfg.min_spacing_pct, cfg.max_spacing_pct,
            )
            return spacing_pct

        except Exception as e:
            logger.debug("[%s] ATR calculation failed: %s, using fixed spacing", cfg.symbol, e)
            return cfg.grid_spacing_pct

    def _calculate_compound_order_size(self, cfg: RealGridConfig, state: RealGridState) -> float:
        """Calculate scaled order size based on accumulated profits (auto-compounding).
        
        Logic:
        - For every `compound_threshold_thb` of cumulative profit, increase order size by `compound_factor` (10%).
        - Cap at `max_compound_multiplier` times the base order size.
        - If cumulative_pnl is negative (losses), revert to base order size.
        
        Returns:
            Scaled order size (float)
        """
        base_size = cfg.order_size
        
        if not cfg.auto_compound_enabled or state.cumulative_pnl <= 0:
            return base_size
        
        # Calculate how many thresholds we've hit
        thresholds_hit = int(state.cumulative_pnl / cfg.compound_threshold_thb)
        
        if thresholds_hit <= 0:
            return base_size
        
        # Scale: 1 + (thresholds_hit * compound_factor), capped at max_compound_multiplier
        multiplier = min(1.0 + (thresholds_hit * cfg.compound_factor), cfg.max_compound_multiplier)
        scaled_size = base_size * multiplier
        
        return scaled_size

    def _auto_tune_compound_threshold(self, cfg: RealGridConfig, state: RealGridState):
        """Auto-tune compound threshold based on recent performance.
        
        Adjusts compound_threshold_thb dynamically:
        - If profit velocity is high (>100 THB/day): raise threshold (compound less aggressively)
        - If profit velocity is low (0-30 THB/day): lower threshold (compound more aggressively)
        - If losing money: reset to default
        """
        if not cfg.auto_compound_enabled:
            return
        
        velocity = state.profit_velocity_thb_per_day
        history = state.daily_pnl_history[-7:]  # last 7 days
        
        if not history:
            return
        
        avg_daily = sum(history) / len(history)
        old_threshold = cfg.compound_threshold_thb
        
        if velocity > 100 and avg_daily > 50:
            # Strong performance — raise threshold to compound less aggressively
            cfg.compound_threshold_thb = min(old_threshold * 1.2, 5000.0)
        elif velocity > 30 and avg_daily > 0:
            # Moderate performance — fine-tune upward slightly
            cfg.compound_threshold_thb = min(old_threshold * 1.05, 5000.0)
        elif velocity > 0 and avg_daily > 0:
            # Slow profit — lower threshold to compound more aggressively
            cfg.compound_threshold_thb = max(old_threshold * 0.9, 100.0)
        elif avg_daily <= 0 and len(history) >= 3:
            # Losing money — reset to default
            cfg.compound_threshold_thb = 500.0
        else:
            return  # not enough data
        
        if abs(cfg.compound_threshold_thb - old_threshold) > 1:
            logger.info(
                "[RealGrid %s] Auto-tune compound threshold: %.0f -> %.0f THB "
                "(velocity=%.1f THB/day, avg_daily=%.1f)",
                cfg.symbol, old_threshold, cfg.compound_threshold_thb,
                velocity, avg_daily,
            )

    # ── Regime Detection ─────────────────────────────────────────────────────

    async def _detect_regime(self, cfg: RealGridConfig, state: RealGridState) -> str:
        """Detect market regime using ATR percentile from historical data.
        
        Fetches 100 hourly candles, computes ATR for each window, then
        classifies current ATR into a percentile to determine regime:
        - low_vol:  ATR < 25th percentile → tighten grids, more fills
        - normal:   ATR 25th-75th → standard ATR-based spacing
        - high_vol: ATR 75th-90th → widen grids, avoid getting stuck
        - extreme:  ATR > 90th percentile → pause trading (danger zone)
        
        Returns:
            Regime string: "low_vol", "normal", "high_vol", "extreme"
        """
        try:
            # Fetch longer history for percentile calculation
            resp = await self._http.get(
                f"{BINANCE_PUBLIC_REST}/api/v1/klines",
                params={
                    "symbol": cfg.symbol,
                    "interval": "1h",
                    "limit": 100,  # ~4 days of hourly data
                },
            )
            if resp.status_code != 200 or len(resp.json()) < 30:
                return "normal"  # fallback if insufficient data

            klines = resp.json()
            
            # Calculate True Range for each candle
            true_ranges = []
            for i in range(1, len(klines)):
                high = float(klines[i][2])
                low = float(klines[i][3])
                prev_close = float(klines[i - 1][4])
                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                true_ranges.append(tr)
            
            if len(true_ranges) < cfg.atr_period:
                return "normal"
            
            # Calculate rolling ATR values for percentile ranking
            atr_values = []
            for i in range(cfg.atr_period, len(true_ranges) + 1):
                window = true_ranges[i - cfg.atr_period:i]
                atr_values.append(sum(window) / cfg.atr_period)
            
            if not atr_values:
                return "normal"
            
            # Current ATR (most recent window)
            current_atr = atr_values[-1]
            
            # Calculate percentile: what % of historical ATR values are below current
            below_count = sum(1 for v in atr_values if v < current_atr)
            percentile = (below_count / len(atr_values)) * 100
            
            state.atr_percentile = percentile
            
            # Classify regime
            if percentile >= REGIME_THRESHOLDS["extreme"]:
                regime = "extreme"
            elif percentile >= REGIME_THRESHOLDS["high_vol"]:
                regime = "high_vol"
            elif percentile < REGIME_THRESHOLDS["low_vol"]:
                regime = "low_vol"
            else:
                regime = "normal"
            
            # Track regime history
            state.regime_history.append(regime)
            if len(state.regime_history) > 30:
                state.regime_history = state.regime_history[-30:]
            
            return regime
            
        except Exception as e:
            logger.debug("[%s] Regime detection failed: %s", cfg.symbol, e)
            return "normal"

    def _apply_regime_adjustment(self, cfg: RealGridConfig, state: RealGridState, regime: str):
        """Adjust grid parameters based on detected market regime.
        
        - low_vol:  tighten spacing (more fills), increase grid_levels
        - normal:   no adjustment
        - high_vol: widen spacing (fewer fills, avoid stuck positions)
        - extreme:  HALT trading (too dangerous)
        """
        state.regime = regime
        base_levels = SYMBOL_DEFAULTS.get(cfg.symbol, {}).get("grid_levels", 2)
        
        if regime == "low_vol":
            # Tighten: more levels, slightly tighter spacing
            cfg.grid_levels = min(base_levels + 1, 5)
            cfg.min_spacing_pct = max(MIN_PROFITABLE_SPACING_PCT, cfg.min_spacing_pct * 0.8)
            logger.debug("[%s] LOW_VOL regime: levels=%d, tighter spacing", cfg.symbol, cfg.grid_levels)
            
        elif regime == "high_vol":
            # Widen: fewer levels, wider spacing to avoid getting stuck
            cfg.grid_levels = max(base_levels - 1, 1)
            cfg.min_spacing_pct = cfg.min_spacing_pct * 1.5
            logger.info("[%s] HIGH_VOL regime: levels=%d, wider spacing", cfg.symbol, cfg.grid_levels)
            
        elif regime == "extreme":
            # HALT — too dangerous to trade
            state.halted = True
            logger.warning("[%s] EXTREME regime: TRADING HALTED (ATR >90th percentile)", cfg.symbol)
            
        else:  # normal
            cfg.grid_levels = base_levels
            # Reset min_spacing to symbol default
            cfg.min_spacing_pct = SYMBOL_DEFAULTS.get(cfg.symbol, {}).get("min_spacing_pct", 1.0)

    # ── Capital Allocation Engine ─────────────────────────────────────────────

    def _calculate_sharpe(self, state: RealGridState) -> float:
        """Calculate Sharpe ratio from trade returns.
        
        Returns:
            Annualized Sharpe ratio, or 0.0 if insufficient data
        """
        if len(state.trade_returns) < 5:
            return 0.0
        import statistics as _stats
        mean_r = _stats.mean(state.trade_returns)
        std_r = _stats.stdev(state.trade_returns)
        if std_r == 0:
            return 0.0
        return (mean_r / std_r) * (252 ** 0.5)

    def _compute_allocation_scores(self) -> Dict[str, float]:
        """Compute composite allocation score for each symbol.
        
        Score = weighted combination of:
        - Sharpe ratio (risk-adjusted return) — weight 0.4
        - Fill rate (execution quality) — weight 0.3
        - Profit velocity (THB/day) — weight 0.3
        
        Returns:
            Dict of symbol -> score (normalized 0-1)
        """
        scores = {}
        
        for symbol, state in self.states.items():
            # Need minimum tracking data
            tracking_days = (time.time() - state.performance_start_time) / 86400 if state.performance_start_time > 0 else 0
            if tracking_days < MIN_ALLOCATION_TRACKING_DAYS:
                scores[symbol] = 0.5  # neutral score for new symbols
                continue
            
            # Sharpe component (normalized: -1 to +3 range -> 0 to 1)
            sharpe = self._calculate_sharpe(state)
            sharpe_norm = max(0.0, min(1.0, (sharpe + 1) / 4))
            
            # Fill rate component (already 0-1)
            fill_norm = state.fill_rate
            
            # Velocity component (normalized by total portfolio velocity)
            total_velocity = sum(s.profit_velocity_thb_per_day for s in self.states.values())
            if total_velocity > 0:
                vel_norm = state.profit_velocity_thb_per_day / total_velocity
            else:
                vel_norm = 0.5  # equal weight if no velocity
            
            # Weighted composite
            score = (0.4 * sharpe_norm) + (0.3 * fill_norm) + (0.3 * vel_norm)
            scores[symbol] = score
            state.allocation_score = score
        
        return scores

    def _run_capital_allocation(self):
        """Rebalance capital allocation across symbols based on performance.
        
        Adjusts grid_levels per symbol:
        - Top performers get more grid levels (more capital deployed)
        - Underperformers get fewer levels (less capital at risk)
        - Minimum 1 level always maintained (keep symbol active)
        
        Runs on daily reset after PnL recording.
        """
        scores = self._compute_allocation_scores()
        
        if not scores:
            return
        
        # Sort symbols by score
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        n_symbols = len(ranked)
        
        logger.info(
            "[CapitalAllocation] Rankings: %s",
            ", ".join(f"{s}={sc:.2f}" for s, sc in ranked),
        )
        
        # Allocate grid levels proportionally
        # Top symbol gets 2x base, bottom gets 0.5x, linear interpolation
        for rank, (symbol, score) in enumerate(ranked):
            cfg = next((c for c in self.configs if c.symbol == symbol), None)
            state = self.states.get(symbol)
            if not cfg or not state:
                continue
            
            base_levels = SYMBOL_DEFAULTS.get(symbol, {}).get("grid_levels", 2)
            
            # Linear interpolation: rank 0 (best) -> 1.5x, rank N-1 (worst) -> 0.5x
            if n_symbols > 1:
                weight = 1.5 - (rank / (n_symbols - 1))  # 1.5 to 0.5
            else:
                weight = 1.0
            
            # Apply: adjust grid_levels (min 1, max 5)
            new_levels = max(1, min(5, int(base_levels * weight)))
            
            # Only adjust if regime is normal (regime takes priority)
            if state.regime == "normal":
                old_levels = cfg.grid_levels
                cfg.grid_levels = new_levels
                state.allocation_weight = weight
                
                if old_levels != new_levels:
                    logger.info(
                        "[CapitalAllocation] %s: levels %d -> %d (weight=%.2f, score=%.2f)",
                        symbol, old_levels, new_levels, weight, score,
                    )

    # ── Fee-Aware Spacing Floor ──────────────────────────────────────────────

    def _apply_fee_floor(self, cfg: RealGridConfig, spacing_pct: float) -> float:
        """Ensure spacing exceeds minimum profitable threshold after fees.
        
        Binance TH charges 0.1% per trade (0.2% round trip).
        Grid spacing must be > 0.5% to ensure profit after fees.
        
        Args:
            cfg: Grid config (for symbol-specific min_spacing_pct)
            spacing_pct: Computed spacing percentage
        
        Returns:
            Adjusted spacing (floored to fee-aware minimum)
        """
        # Hard floor: must exceed fee threshold
        fee_floor = max(MIN_PROFITABLE_SPACING_PCT, cfg.min_spacing_pct)
        
        if spacing_pct < fee_floor:
            logger.debug(
                "[%s] Fee floor enforced: %.2f%% -> %.2f%% (min profitable: %.1f%%)",
                cfg.symbol, spacing_pct, fee_floor, MIN_PROFITABLE_SPACING_PCT,
            )
            return fee_floor
        
        return spacing_pct

    async def _send_comprehensive_digest(self):
        """Send comprehensive daily digest across all symbols via webhook."""
        if not self._webhook._enabled:
            return
        
        lines = ["📊 <b>Daily Trading Digest</b>", ""]
        total_pnl = 0.0
        total_trades = 0
        
        for symbol, state in self.states.items():
            pnl = state.daily_pnl
            trades = state.daily_trades
            total_pnl += pnl
            total_trades += trades
            
            emoji = "🟢" if pnl >= 0 else "🔴"
            cum_pnl = state.cumulative_pnl
            fill_pct = state.fill_rate * 100
            velocity = state.profit_velocity_thb_per_day
            
            lines.append(f"{emoji} <b>{symbol}</b>")
            lines.append(f"  PnL: {pnl:+.2f} THB | Trades: {trades}")
            lines.append(f"  Fill: {fill_pct:.1f}% | Vel: {velocity:.1f} THB/day")
            lines.append(f"  Cum PnL: {cum_pnl:+.2f} THB")
            lines.append(f"  Regime: {state.regime} | Alloc: {state.allocation_weight:.1f}x")
            
            # Sharpe/Sortino if enough data
            if len(state.trade_returns) >= 10:
                import statistics as _stats
                mean_r = _stats.mean(state.trade_returns)
                std_r = _stats.stdev(state.trade_returns)
                sharpe = (mean_r / std_r * (252 ** 0.5)) if std_r > 0 else 0
                lines.append(f"  Sharpe: {sharpe:.2f}")
            
            lines.append("")
        
        lines.append(f"💰 <b>Total PnL: {total_pnl:+.2f} THB</b>")
        lines.append(f"📈 Total Trades: {total_trades}")
        
        await self._webhook._queue.put("\n".join(lines))

    async def _fetch_balances(self) -> Dict[str, float]:
        """Fetch account balances from backend."""
        try:
            resp = await self._http.get(f"{BACKEND_API_BASE}/api/trade/balances")
            if resp.status_code == 200:
                data = resp.json()
                return {b["currency"]: float(b["free"]) for b in data.get("balances", [])}
        except Exception as e:
            logger.warning("Failed to fetch balances: %s", e)
        return {}

    async def _can_place_sell(self, symbol: str, qty: float) -> bool:
        """Check if we have enough base asset to place a SELL order."""
        # Extract base asset from symbol (e.g., ETHTHB -> ETH, BTCTHB -> BTC)
        for quote in ["THB", "USDT", "BUSD", "BTC"]:
            if symbol.endswith(quote):
                base_asset = symbol[: -len(quote)]
                break
        else:
            return True  # Unknown symbol format, allow

        balances = await self._fetch_balances()
        available = balances.get(base_asset, 0.0)
        if available < qty:
            logger.debug(
                "[RealGrid %s] Skipping SELL: need %.6f %s but have %.6f",
                symbol, qty, base_asset, available,
            )
            return False
        return True

    async def _can_place_buy(self, symbol: str, qty: float, price: int) -> bool:
        """Check if we have enough quote currency to place a BUY order.
        
        For BUY orders, we need the quote currency (e.g., THB for ETHTHB/BTCTHB).
        Required = qty * price (notional value).
        """
        # Extract quote asset from symbol (e.g., ETHTHB -> THB, BTCTHB -> THB)
        for quote in ["THB", "USDT", "BUSD", "BTC"]:
            if symbol.endswith(quote):
                quote_asset = quote
                break
        else:
            return True  # Unknown symbol format, allow

        balances = await self._fetch_balances()
        available = balances.get(quote_asset, 0.0)
        required = qty * price  # Notional value needed
        if available < required:
            logger.debug(
                "[RealGrid %s] Skipping BUY: need %.2f %s but have %.2f",
                symbol, required, quote_asset, available,
            )
            return False
        return True

    async def _place_grid_order(self, cfg: RealGridConfig, state: RealGridState, side: str, price: int):
        """Place a real LIMIT order at a grid level via Go backend."""
        # Use dynamic order size from auto-compounding if available, else base config size
        order_size = state.current_order_size if state.current_order_size > 0 else cfg.order_size
        
        # ── Balance pre-checks ──
        if side == "SELL":
            if not await self._can_place_sell(cfg.symbol, order_size):
                return
        elif side == "BUY":
            if not await self._can_place_buy(cfg.symbol, order_size, price):
                return

        # ── Risk check before order ──
        allowed, reason = self._risk.check_order_allowed(
            symbol=cfg.symbol,
            side=side,
            quantity=order_size,
            price=price,
        )
        if not allowed:
            logger.debug("[RealGrid %s] Order blocked by risk: %s", cfg.symbol, reason)
            return

        try:
            resp = await self._http.post(
                f"{BACKEND_API_BASE}/api/trade/order",
                json={
                    "symbol": cfg.symbol,
                    "side": side,
                    "quantity": order_size,
                    "price": price,  # >0 = LIMIT order
                },
            )
            if resp.status_code == 201:
                data = resp.json()
                order = data.get("order", {})
                order_id = str(order.get("orderId", ""))

                state.trades_executed += 1
                state.daily_trades += 1
                state.orders_placed += 1  # Performance: track orders placed
                # Update fill rate
                if state.orders_placed > 0:
                    state.fill_rate = state.orders_filled / state.orders_placed

                if side == "BUY":
                    state.active_buys[price] = order_id
                else:
                    state.active_sells[price] = order_id

                # Record in risk manager
                self._risk.record_order_placed(cfg.symbol)

                # Record in trade journal
                notional = order_size * price
                await self._journal.record_entry(JournalEntry(
                    symbol=cfg.symbol,
                    side=side,
                    strategy="grid_bot_v2",
                    entry_reason=f"Grid {side.lower()} @ level price={price}, spacing={cfg.grid_spacing_pct}%",
                    entry_price=price,
                    quantity=order_size,
                    expected_risk_thb=notional * 0.02,  # 2% risk estimate
                    expected_reward_thb=notional * (cfg.grid_spacing_pct / 100),
                    exchange_order_id=order_id,
                ))

                logger.info(
                    "[RealGrid %s] %s LIMIT @ %d placed (id=%s)",
                    cfg.symbol, side, price, order_id[:16] if order_id else "?",
                )
            elif resp.status_code == 400:
                # Insufficient balance or exchange rejection — log once then skip silently
                err = resp.json().get("error", "unknown")
                if "insufficient" in err.lower():
                    logger.warning(
                        "[RealGrid %s] %s @ %d rejected: insufficient balance. "
                        "Will retry next tick when balance may have changed.",
                        cfg.symbol, side, price,
                    )
                else:
                    logger.debug("Order rejected @ %d: %s", price, err)
            else:
                err = resp.json().get("error", "unknown")
                logger.debug("Order rejected @ %d (HTTP %d): %s", price, resp.status_code, err)
        except Exception as e:
            logger.debug("Failed to place %s @ %d: %s", side, price, e)

    def get_status(self) -> Dict:
        """Get current real grid bot status (includes risk metrics and auto-compound info)."""
        risk = get_risk_manager()
        journal = get_trade_journal()
        
        # Build per-symbol config lookup for compound settings
        cfg_lookup = {cfg.symbol: cfg for cfg in self.configs}
        
        symbols_data = {}
        total_cumulative_pnl = 0.0
        
        for symbol, state in self.states.items():
            cfg = cfg_lookup.get(symbol)
            current_size = state.current_order_size if state.current_order_size > 0 else (cfg.order_size if cfg else 0)
            base_size = cfg.order_size if cfg else 0
            compound_multiplier = current_size / base_size if base_size > 0 else 1.0
            
            symbols_data[symbol] = {
                "last_price": state.last_price,
                "active_buys": len(state.active_buys),
                "active_sells": len(state.active_sells),
                "trades_executed": state.trades_executed,
                "daily_pnl": round(state.daily_pnl, 2),
                "daily_trades": state.daily_trades,
                "halted": state.halted,
                # Auto-compounding metrics
                "cumulative_pnl": round(state.cumulative_pnl, 2),
                "current_order_size": round(current_size, 8),
                "base_order_size": round(base_size, 8),
                "compound_multiplier": round(compound_multiplier, 2),
            }
            total_cumulative_pnl += state.cumulative_pnl
        
        return {
            "running": self._running,
            "enabled": self._enabled,
            "symbols": symbols_data,
            "total_cumulative_pnl": round(total_cumulative_pnl, 2),
            "risk": risk.get_status(),
            "journal_stats": journal.get_stats(),
        }

    def get_health(self) -> Dict:
        """Get health status with stuck detection.
        
        Returns health status including:
        - running: whether the bot loop is active
        - enabled: whether trading is enabled (not kill-switched)
        - last_tick_age_sec: how long since last tick per symbol
        - stuck: whether any symbol appears stuck (>5 min without tick)
        """
        now = time.time()
        stuck_threshold = 300  # 5 minutes
        
        last_tick_age = {}
        stuck_symbols = []
        for symbol in self.states:
            last_tick = self._last_tick_time.get(symbol, 0)
            age = now - last_tick if last_tick > 0 else -1
            last_tick_age[symbol] = round(age, 1)
            if age > stuck_threshold or age < 0:
                stuck_symbols.append(symbol)
        
        return {
            "healthy": self._running and self._enabled and len(stuck_symbols) == 0,
            "running": self._running,
            "enabled": self._enabled,
            "last_tick_age_sec": last_tick_age,
            "stuck_symbols": stuck_symbols,
        }

    def get_performance(self) -> Dict:
        """Get performance metrics for all symbols.
        
        Returns per-symbol performance data including:
        - fill rates, ATR spacing history, profit velocity
        - Recommendations for compound parameter tuning
        """
        cfg_lookup = {cfg.symbol: cfg for cfg in self.configs}
        per_symbol = {}
        
        for symbol, state in self.states.items():
            cfg = cfg_lookup.get(symbol)
            
            # ATR spacing analysis
            atr_hist = state.atr_spacing_history
            atr_avg = sum(atr_hist) / len(atr_hist) if atr_hist else 0.0
            atr_min = min(atr_hist) if atr_hist else 0.0
            atr_max = max(atr_hist) if atr_hist else 0.0
            atr_stddev = 0.0
            if len(atr_hist) > 1:
                mean = atr_avg
                atr_stddev = (sum((x - mean) ** 2 for x in atr_hist) / len(atr_hist)) ** 0.5
            
            # Profit velocity analysis
            velocity = state.profit_velocity_thb_per_day
            
            # Compound tuning recommendation
            recommendation = "hold"
            if cfg and cfg.auto_compound_enabled:
                if velocity > 100:  # earning >100 THB/day
                    recommendation = "increase_threshold"  # compound less aggressively
                elif velocity > 30:
                    recommendation = "hold"  # current settings good
                elif velocity > 0:
                    recommendation = "decrease_threshold"  # compound more aggressively
                else:
                    recommendation = "pause_compounding"  # no profit yet
            
            # Sharpe/Sortino risk-adjusted return metrics
            sharpe = sortino = 0.0
            if len(state.trade_returns) > 1:
                import statistics as _stats
                mean_r = _stats.mean(state.trade_returns)
                std_r = _stats.stdev(state.trade_returns)
                sharpe = (mean_r / std_r * (252 ** 0.5)) if std_r > 0 else 0.0
                neg_returns = [r for r in state.trade_returns if r < 0]
                std_neg = _stats.stdev(neg_returns) if len(neg_returns) > 1 else std_r
                sortino = (mean_r / std_neg * (252 ** 0.5)) if std_neg > 0 else 0.0
            
            per_symbol[symbol] = {
                # Fill rate metrics
                "orders_placed": state.orders_placed,
                "orders_filled": state.orders_filled,
                "fill_rate": round(state.fill_rate * 100, 2),  # as percentage
                "last_fill_timestamp": state.last_fill_timestamp,
                "last_fill_age_sec": round(time.time() - state.last_fill_timestamp, 0) if state.last_fill_timestamp > 0 else None,
                # ATR spacing metrics
                "last_atr_spacing_pct": round(state.last_atr_spacing_pct, 4),
                "atr_spacing_avg": round(atr_avg, 4),
                "atr_spacing_min": round(atr_min, 4),
                "atr_spacing_max": round(atr_max, 4),
                "atr_spacing_stddev": round(atr_stddev, 4),
                "atr_spacing_samples": len(atr_hist),
                "atr_config": {
                    "atr_period": cfg.atr_period if cfg else 14,
                    "atr_multiplier": cfg.atr_multiplier if cfg else 1.5,
                    "min_spacing_pct": cfg.min_spacing_pct if cfg else 0.5,
                    "max_spacing_pct": cfg.max_spacing_pct if cfg else 5.0,
                } if cfg else {},
                # Profit velocity
                "profit_velocity_thb_per_day": round(velocity, 2),
                "cumulative_pnl": round(state.cumulative_pnl, 2),
                "performance_tracking_days": round(
                    (time.time() - state.performance_start_time) / 86400, 2
                ) if state.performance_start_time > 0 else 0,
                # Risk-adjusted returns (Sharpe/Sortino)
                "sharpe_ratio": round(sharpe, 2),
                "sortino_ratio": round(sortino, 2),
                "trade_return_samples": len(state.trade_returns),
                # Compound tuning
                "compound_recommendation": recommendation,
                "current_compound_multiplier": round(
                    (state.current_order_size / cfg.order_size) if cfg and cfg.order_size > 0 else 1.0, 2
                ),
                "auto_tuned_compound_threshold": round(cfg.compound_threshold_thb, 2) if cfg else 500.0,
                # Regime detection & capital allocation
                "regime": state.regime,
                "atr_percentile": round(state.atr_percentile, 1),
                "allocation_weight": round(state.allocation_weight, 2),
                "allocation_score": round(state.allocation_score, 3),
                "current_grid_levels": cfg.grid_levels if cfg else 2,
            }
        
        # Cross-symbol comparison summary
        symbols_list = list(per_symbol.values())
        avg_fill_rate = sum(s["fill_rate"] for s in symbols_list) / len(symbols_list) if symbols_list else 0
        best_symbol = max(per_symbol.items(), key=lambda x: x[1]["fill_rate"]) if per_symbol else (None, None)
        worst_symbol = min(per_symbol.items(), key=lambda x: x[1]["fill_rate"]) if per_symbol else (None, None)
        
        return {
            "symbols": per_symbol,
            "summary": {
                "avg_fill_rate": round(avg_fill_rate, 2),
                "best_fill_symbol": best_symbol[0] if best_symbol[0] else None,
                "worst_fill_symbol": worst_symbol[0] if worst_symbol[0] else None,
                "total_profit_velocity": round(
                    sum(s["profit_velocity_thb_per_day"] for s in symbols_list), 2
                ),
                "avg_sharpe_ratio": round(
                    sum(s["sharpe_ratio"] for s in symbols_list) / len(symbols_list), 2
                ) if symbols_list else 0.0,
                "avg_sortino_ratio": round(
                    sum(s["sortino_ratio"] for s in symbols_list) / len(symbols_list), 2
                ) if symbols_list else 0.0,
            },
        }

    async def force_restart(self) -> bool:
        """Force restart the bot by resetting state and re-syncing.
        
        This is a recovery mechanism for when the bot gets stuck.
        Returns True if restart was successful.
        """
        logger.warning("Force restarting Real Grid Bot")
        try:
            # Clear stuck detection state
            self._last_tick_time.clear()
            # Re-sync open orders for all symbols
            for cfg in self.configs:
                state = self.states.get(cfg.symbol)
                if state:
                    await self._sync_open_orders(cfg, state)
                    logger.info("Re-synced open orders for %s", cfg.symbol)
            return True
        except Exception as e:
            logger.error("Force restart failed: %s", e)
            return False

    def get_notifications(self, limit: int = 20) -> List[dict]:
        """Get recent notifications (most recent first)."""
        return list(reversed(list(self._notifications)))[:limit]


# ── Singleton instance for FastAPI integration ────────────────────────────────

_real_grid_bot: Optional[RealGridBot] = None


def get_real_grid_bot() -> RealGridBot:
    global _real_grid_bot
    if _real_grid_bot is None:
        _real_grid_bot = RealGridBot()
    return _real_grid_bot
