"""
Automated Grid Trading Bot
===========================
Places buy/sell orders at grid levels around the current market price.

Supports 3 advanced modes (backtest-validated, inspired by Freqtrade + NTU DGT):
  1. Geometric grid spacing (% based, adapts to price level)
  2. DGT dynamic grid reset with profit reinvestment
  3. Multi-indicator confluence entry timing (RSI + MACD + Volume)

Uses Binance testnet public API for live prices and the Go backend's
PaperEngine for simulated execution. No API keys needed — paper mode.

Usage:
    python -m app.grid_bot
"""

import asyncio
import logging
import math
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger("paper_grid_bot")

# ── Configuration ─────────────────────────────────────────────────────────────

BINANCE_TESTNET_REST = "https://testnet.binance.vision"
PAPER_API_BASE = os.getenv("PAPER_API_BASE", "http://backend:8080")

# Safety cap: max notional exposure per symbol (paper mode), in quote currency
# For THB pairs: ฿3,000 ≈ $85. For USD pairs: $100.
# Aligned with real_grid_bot.py BTCTHB config (max_position=0.001 BTC ≈ ฿2,120).
DEFAULT_MAX_NOTIONAL = float(os.getenv("GRID_MAX_NOTIONAL", "3000.0"))

# Grid parameters per symbol
@dataclass
class GridConfig:
    symbol: str
    grid_spacing_pct: float = 2.0      # % between grid levels
    grid_levels: int = 2               # number of levels above/below (conservative)
    order_size: float = 0.00005        # base quantity per grid order
    max_position: float = 0.001        # max position size in base asset
    poll_interval_sec: int = 60        # how often to check prices
    max_notional: float = DEFAULT_MAX_NOTIONAL  # safety cap in quote currency (THB or USD)
    price_decimals: int = 2            # decimal places for limit prices (0 = integer)
    min_notional: float = 100.0        # exchange minimum notional (quote currency)
    qty_decimals: int = 6              # decimal places for quantity (step size)
    # ── Advanced strategy modes (backtest-validated) ──────────────────────
    grid_mode: str = "geometric"       # "arithmetic" | "geometric" (DGT-style)
    dgt_enabled: bool = True           # DGT grid reset + profit reinvestment
    dgt_reinvest_pct: float = 0.5      # % of accumulated profits to reinvest
    enable_entry_confluence: bool = True # gate buys with RSI+MACD+Volume
    rsi_period: int = 14               # RSI lookback period
    rsi_buy_threshold: float = 45.0    # only buy when RSI < this
    rsi_sell_threshold: float = 70.0   # consider sell when RSI > this
    macd_fast: int = 12                # MACD fast EMA period
    macd_slow: int = 26                # MACD slow EMA period
    macd_signal: int = 9               # MACD signal line period
    volume_sma_period: int = 20        # volume SMA lookback
    volume_multiplier: float = 1.5     # volume must be > SMA * this to buy
    # ── Order Book Imbalance (OB1) ─────────────────────────────────────────
    enable_orderbook_imbalance: bool = True   # use order book depth to override borderline RSI
    orderbook_depth_limit: int = 20           # number of depth levels to fetch (5, 10, 20)
    imbalance_threshold: float = 0.65         # bid_volume / (bid+ask) > this = strong buy pressure
    imbalance_rsi_relax: float = 10.0         # relax RSI threshold by this much when imbalance is strong
    # ── EMA Trend Filter (TF) ─────────────────────────────────────────────
    enable_ema_trend_filter: bool = False  # block buys when price < EMA (downtrend) — DISABLED: too restrictive in backtest
    ema_trend_period: int = 50            # EMA period for trend direction (15m × 50 ≈ 12.5h lookback)
    # ── Anti-Over-Filtering (Desperation Buy) ─────────────────────────────
    enable_desperation_buy: bool = True   # allow reduced-size buy after N consecutive confluence blocks
    desperation_buy_threshold: int = 20   # number of consecutive blocks before triggering
    desperation_buy_size_pct: float = 0.5 # order size multiplier for desperation buy (0.5 = half size)
    # ── Adaptive Grid Spacing (ATR-based) ───────────────────────────────────
    enable_adaptive_spacing: bool = False  # use ATR to dynamically adjust grid spacing
    atr_period: int = 14                   # ATR lookback period (15m candles)
    atr_multiplier: float = 1.5            # ATR multiplier for spacing calculation
    min_spacing_pct: float = 0.2           # minimum spacing floor (%) — micro-scalper mode
    max_spacing_pct: float = 5.0           # maximum spacing ceiling (%)


def validate_grid_config(cfg: GridConfig, ref_price: float = 0.0) -> List[str]:
    """Validate grid config safety constraints. Returns list of violations (empty = safe)."""
    violations = []
    if cfg.grid_levels < 1:
        violations.append(f"grid_levels must be >= 1, got {cfg.grid_levels}")
    if cfg.grid_levels > 6:
        violations.append(f"grid_levels={cfg.grid_levels} exceeds safety cap of 6")
    if cfg.order_size <= 0:
        violations.append(f"order_size must be > 0, got {cfg.order_size}")
    if cfg.max_position <= 0:
        violations.append(f"max_position must be > 0, got {cfg.max_position}")
    if cfg.grid_spacing_pct < 0.2:
        violations.append(f"grid_spacing_pct={cfg.grid_spacing_pct} below minimum 0.2%")
    if cfg.max_notional <= 0:
        violations.append(f"max_notional must be > 0, got {cfg.max_notional}")
    # Check max exposure if we have a reference price
    if ref_price > 0:
        max_exposure = cfg.max_position * ref_price
        if max_exposure > cfg.max_notional:
            violations.append(
                f"max exposure {max_exposure:,.2f} exceeds cap {cfg.max_notional:,.2f} "
                f"(max_position={cfg.max_position} × price={ref_price:,.2f})"
            )
    return violations


def safe_paper_defaults() -> List[GridConfig]:
    """Conservative paper defaults — mixed THB + USDT pairs.

    THB pairs (Binance TH): ฿1,000-2,120 max exposure each.
    USDT pairs (Binance Global): $100-250 max exposure each.
    Total max exposure: ~฿8,000 + ~$700.
    Tighter spacing (1.5%) for alt-pairs to increase fill probability.
    USDT pairs have much higher liquidity → more fills.
    """
    return [
        # ── THB pairs (Binance TH) ──────────────────────────────────────────
        GridConfig(
            symbol="BTCTHB",
            grid_spacing_pct=0.3,     # micro-scalper: tight grids for bear market
            grid_levels=5,            # more levels = more fills on small oscillations
            order_size=0.00002,       # smaller per-order, more frequent scalps
            max_position=0.001,       # ~฿2,120 max exposure
            max_notional=3000.0,      # ฿3,000 cap (≈$85)
            price_decimals=0,         # tickSize=1.0, integer prices
            min_notional=500.0,       # Binance TH: ฿500 minimum for BTC
            qty_decimals=6,
            rsi_buy_threshold=45.0,
            volume_multiplier=1.2,
            imbalance_threshold=0.60,
            desperation_buy_threshold=8,
        ),
        GridConfig(
            symbol="ETHTHB",
            grid_spacing_pct=0.3,     # micro-scalper: tight grids for bear market
            grid_levels=5,
            order_size=0.0008,        # smaller per-order
            max_position=0.02,        # ~฿1,085 max exposure
            max_notional=1500.0,      # ฿1,500 cap (≈$42)
            price_decimals=0,         # tickSize=1.0, integer prices
            min_notional=500.0,       # Binance TH: ฿500 minimum for ETH
            qty_decimals=5,
            rsi_buy_threshold=45.0,
            volume_multiplier=1.2,
            imbalance_threshold=0.60,
            desperation_buy_threshold=8,
        ),
        GridConfig(
            symbol="SOLTHB",
            grid_spacing_pct=0.3,     # micro-scalper: tight grids for bear market
            grid_levels=5,
            order_size=0.02,          # smaller per-order
            max_position=0.5,         # ~฿1,112 max exposure
            max_notional=1500.0,      # ฿1,500 cap (≈$42)
            price_decimals=2,         # tickSize=0.01
            min_notional=100.0,       # Binance TH: ฿100 minimum
            qty_decimals=3,
            rsi_buy_threshold=45.0,
            volume_multiplier=1.2,
            imbalance_threshold=0.60,
            desperation_buy_threshold=8,
        ),
        GridConfig(
            symbol="XRPTHB",
            grid_spacing_pct=0.3,     # micro-scalper: tight grids for bear market
            grid_levels=5,
            order_size=1.5,           # smaller per-order
            max_position=30.0,        # ~฿1,023 max exposure
            max_notional=1500.0,      # ฿1,500 cap (≈$42)
            price_decimals=2,         # tickSize=0.01
            min_notional=100.0,       # Binance TH: ฿100 minimum
            qty_decimals=1,
            rsi_buy_threshold=45.0,
            volume_multiplier=1.2,
            imbalance_threshold=0.60,
            desperation_buy_threshold=8,
        ),
        GridConfig(
            symbol="BNBTHB",
            grid_spacing_pct=0.3,     # micro-scalper: tight grids for bear market
            grid_levels=5,
            order_size=0.005,         # smaller per-order
            max_position=0.1,         # ~฿1,855 max exposure
            max_notional=2000.0,      # ฿2,000 cap (≈$56)
            price_decimals=2,         # tickSize=0.01
            min_notional=500.0,       # Binance TH: ฿500 minimum for BNB
            qty_decimals=4,
            rsi_buy_threshold=45.0,
            volume_multiplier=1.2,
            imbalance_threshold=0.60,
            desperation_buy_threshold=8,
        ),
        # ── USDT pairs (Binance Global — micro-scalper for bear market) ───────
        GridConfig(
            symbol="BTCUSDT",
            grid_spacing_pct=0.3,     # micro-scalper: tight grids for bear market
            grid_levels=5,            # more levels = more fills on small oscillations
            order_size=0.0016,        # ~$96 per order at BTC ~$60k
            max_position=0.008,       # ~$480 max exposure
            max_notional=500.0,       # $500 cap
            price_decimals=2,         # tickSize=0.01
            min_notional=10.0,        # Binance Global $10 minimum
            qty_decimals=6,
            rsi_buy_threshold=45.0,
            volume_multiplier=1.2,
            imbalance_threshold=0.60,
            desperation_buy_threshold=8,
        ),
        GridConfig(
            symbol="ETHUSDT",
            grid_spacing_pct=0.3,
            grid_levels=5,
            order_size=0.06,          # ~$95 per order at ETH ~$1,580
            max_position=0.3,         # ~$474 max exposure
            max_notional=500.0,
            price_decimals=2,
            min_notional=10.0,
            qty_decimals=5,
            rsi_buy_threshold=45.0,
            volume_multiplier=1.2,
            imbalance_threshold=0.60,
            desperation_buy_threshold=8,
        ),
        GridConfig(
            symbol="SOLUSDT",
            grid_spacing_pct=0.3,
            grid_levels=5,
            order_size=1.4,           # ~$99 per order at SOL ~$70
            max_position=6.9,         # ~$496 max exposure (6.9 × $72)
            max_notional=500.0,
            price_decimals=2,
            min_notional=10.0,        # Binance Global $10 minimum
            qty_decimals=3,
            rsi_buy_threshold=45.0,
            volume_multiplier=1.2,
            imbalance_threshold=0.60,
            desperation_buy_threshold=8,
        ),
        GridConfig(
            symbol="XRPUSDT",
            grid_spacing_pct=0.3,
            grid_levels=5,
            order_size=200.0,         # ~$210 per order at XRP ~$1.05
            max_position=470.0,       # ~$498 max exposure (470 × $1.06)
            max_notional=500.0,
            price_decimals=4,         # tickSize=0.0001
            min_notional=10.0,        # Binance Global $10 minimum
            qty_decimals=1,
            rsi_buy_threshold=45.0,
            volume_multiplier=1.2,
            imbalance_threshold=0.60,
            desperation_buy_threshold=8,
        ),
        GridConfig(
            symbol="BNBUSDT",
            grid_spacing_pct=0.3,
            grid_levels=5,
            order_size=0.17,          # ~$102 per order at BNB ~$600
            max_position=0.85,        # ~$510 max exposure
            max_notional=500.0,
            price_decimals=2,         # tickSize=0.01
            min_notional=10.0,        # Binance Global $10 minimum
            qty_decimals=3,
            rsi_buy_threshold=45.0,
            volume_multiplier=1.2,
            imbalance_threshold=0.60,
            desperation_buy_threshold=8,
        ),
    ]


@dataclass
class GridState:
    """Tracks active grid orders for a symbol."""
    symbol: str
    active_buys: Dict[float, str] = field(default_factory=dict)   # price -> order_id
    active_sells: Dict[float, str] = field(default_factory=dict)  # price -> order_id
    filled_buys: Dict[float, float] = field(default_factory=dict)   # price -> qty (filled, awaiting sell)
    filled_sells: Dict[float, float] = field(default_factory=dict)  # price -> qty (filled, awaiting buy)
    grid_anchor: float = 0.0          # price at which current grid was built
    last_price: float = 0.0
    total_profit: float = 0.0
    trades_executed: int = 0
    # ── DGT tracking ──────────────────────────────────────────────────────
    accumulated_profits: float = 0.0   # realized profits waiting for reinvestment
    dgt_resets: int = 0               # number of DGT grid resets
    dgt_reinvested: float = 0.0       # total THB reinvested from profits
    current_order_size: float = 0.0   # order size (grows via DGT reinvestment)
    # ── Confluence tracking ───────────────────────────────────────────────
    confluence_buys_blocked: int = 0   # buys blocked by indicator gate
    # ── Order Book Imbalance tracking ─────────────────────────────────────
    last_imbalance: float = 0.0        # latest bid/(bid+ask) ratio
    imbalance_overrides: int = 0       # times imbalance allowed a borderline buy
    # ── EMA Trend Filter tracking ─────────────────────────────────────────
    ema_trend_blocked: int = 0         # buys blocked because price < EMA (downtrend)
    last_ema: float = 0.0              # latest EMA value for diagnostics
    # ── Desperation Buy tracking ──────────────────────────────────────────
    consecutive_blocks: int = 0        # consecutive confluence blocks (resets on successful buy)
    desperation_buys_triggered: int = 0  # total desperation buys executed
    # ── Kline history for indicators ──────────────────────────────────────
    kline_closes: List[float] = field(default_factory=list)
    kline_volumes: List[float] = field(default_factory=list)
    kline_highs: List[float] = field(default_factory=list)
    kline_lows: List[float] = field(default_factory=list)


class GridBot:
    """
    Automated grid trading bot that:
    1. Fetches live price from Binance testnet
    2. Places grid buy orders below current price
    3. Places grid sell orders above current price
    4. When a buy fills, places a sell one grid level up
    5. When a sell fills, places a buy one grid level down
    """

    def __init__(self, configs: Optional[List[GridConfig]] = None):
        self.configs = configs if configs is not None else safe_paper_defaults()
        # Validate all configs at startup
        for cfg in self.configs:
            violations = validate_grid_config(cfg)
            if violations:
                raise ValueError(
                    f"Unsafe grid config for {cfg.symbol}: {'; '.join(violations)}"
                )
        self.states: Dict[str, GridState] = {}
        self._running = False
        self._http: Optional[httpx.AsyncClient] = None
        self._kline_http: Optional[httpx.AsyncClient] = None  # separate client for klines

    async def start(self):
        """Start the grid bot."""
        self._running = True
        self._http = httpx.AsyncClient(timeout=10.0)
        self._kline_http = httpx.AsyncClient(timeout=15.0)
        logger.info(
            "Grid Bot started with %d symbol(s) | mode=%s dgt=%s confluence=%s",
            len(self.configs),
            self.configs[0].grid_mode if self.configs else "?",
            self.configs[0].dgt_enabled if self.configs else "?",
            self.configs[0].enable_entry_confluence if self.configs else "?",
        )

        for cfg in self.configs:
            self.states[cfg.symbol] = GridState(
                symbol=cfg.symbol,
                current_order_size=cfg.order_size,
            )

        # Reset paper engine to clean state
        await self._reset_paper_engine()

        # Seed initial positions so SELL orders don't get "insufficient position" errors
        await self._seed_positions()

        while self._running:
            try:
                for cfg in self.configs:
                    await self._tick(cfg)
                await asyncio.sleep(self.configs[0].poll_interval_sec)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Grid Bot error: %s", e, exc_info=True)
                await asyncio.sleep(10)

        logger.info(
            "Grid Bot stopped. Total trades: %d, DGT resets: %d, reinvested: %.2f",
            sum(s.trades_executed for s in self.states.values()),
            sum(s.dgt_resets for s in self.states.values()),
            sum(s.dgt_reinvested for s in self.states.values()),
        )

    async def stop(self):
        """Stop the grid bot."""
        self._running = False
        if self._http:
            await self._http.aclose()
        if self._kline_http:
            await self._kline_http.aclose()

    async def _tick(self, cfg: GridConfig):
        """One tick: fetch price, update pending orders, evaluate grid, place orders."""
        price = await self._fetch_price(cfg.symbol)
        if price <= 0:
            logger.warning("[Grid %s] Price fetch failed — skipping tick", cfg.symbol)
            return

        # Runtime safety check: validate exposure against live price
        violations = validate_grid_config(cfg, ref_price=price)
        if violations:
            logger.error(
                "[Grid %s] SAFETY VIOLATION at price %.2f: %s — skipping tick",
                cfg.symbol, price, "; ".join(violations),
            )
            return

        state = self.states[cfg.symbol]
        state.last_price = price

        # ── Update paper engine with current price ──
        # This triggers pending limit order fills if price touched the level
        try:
            await self._http.post(
                f"{PAPER_API_BASE}/api/paper/update-price",
                json={"symbol": cfg.symbol, "price": price},
            )
        except Exception:
            pass

        # ── Sync state FIRST — reconcile filled orders from paper engine ──
        await self._sync_state(cfg, state, price)

        # ── Fetch klines for confluence indicators + adaptive spacing (rolling window) ──
        if cfg.enable_entry_confluence or cfg.enable_adaptive_spacing:
            await self._update_kline_history(cfg, state)

        # ── Fetch order book depth for imbalance signal ──
        if cfg.enable_orderbook_imbalance:
            await self._fetch_orderbook_depth(cfg, state)

        # ── Query Brain for intelligence directive ──
        brain_directive = None
        try:
            from app.brain.brain import get_brain
            brain = get_brain()
            brain_directive = await brain.get_directive(cfg.symbol, current_price=price)
        except Exception as e:
            logger.debug("Brain query failed for %s (using defaults): %s", cfg.symbol, e)

        # Apply Brain modulation to grid spacing
        spacing_pct = cfg.grid_spacing_pct / 100.0
        spacing_multiplier = brain_directive.spacing_multiplier if brain_directive else 1.0
        center_offset_pct = brain_directive.center_offset_pct if brain_directive else 0.0
        pause_buys = brain_directive.pause_buys if brain_directive else False
        pause_sells = brain_directive.pause_sells if brain_directive else False

        # ── Adaptive Grid Spacing: ATR-based dynamic spacing ──
        if cfg.enable_adaptive_spacing and len(state.kline_closes) >= cfg.atr_period + 1:
            atr = self._calc_atr(state.kline_highs, state.kline_lows, state.kline_closes, cfg.atr_period)
            if atr > 0 and price > 0:
                atr_pct = (atr / price) * 100 * cfg.atr_multiplier
                adaptive_pct = max(cfg.min_spacing_pct, min(cfg.max_spacing_pct, atr_pct))
                spacing_pct = adaptive_pct / 100.0
                logger.debug(
                    "[Adaptive %s] ATR=%.2f atr_pct=%.2f%% spacing=%.2f%% (min=%.2f max=%.2f)",
                    cfg.symbol, atr, atr_pct, adaptive_pct, cfg.min_spacing_pct, cfg.max_spacing_pct,
                )

        effective_spacing_pct = spacing_pct * spacing_multiplier

        # Apply center offset (shifts the grid center up or down)
        center_price = price * (1.0 + center_offset_pct / 100.0)

        if brain_directive:
            logger.info(
                "[Brain→Grid %s] spacing_mult=%.2f offset=%.2f%% pause_b=%s pause_s=%s conf=%.2f",
                cfg.symbol, spacing_multiplier, center_offset_pct,
                pause_buys, pause_sells, brain_directive.confidence,
            )

        # ── Grid shift logic: rebuild only when price moves beyond grid range ──
        needs_rebuild = False
        if state.grid_anchor == 0:
            needs_rebuild = True  # First tick
        else:
            # Check if price moved beyond outermost grid levels
            if cfg.grid_mode == "geometric":
                outer_factor = (1.0 + effective_spacing_pct) ** cfg.grid_levels
                outermost_buy = center_price / outer_factor
                outermost_sell = center_price * outer_factor
            else:
                spacing_abs = price * effective_spacing_pct
                outermost_buy = center_price - (spacing_abs * cfg.grid_levels)
                outermost_sell = center_price + (spacing_abs * cfg.grid_levels)
            if price < outermost_buy or price > outermost_sell:
                needs_rebuild = True
                logger.info(
                    "[Grid %s] Price %.2f outside grid [%.2f - %.2f] — rebuilding",
                    cfg.symbol, price, outermost_buy, outermost_sell,
                )

        if needs_rebuild:
            # ── DGT: Before resetting, reinvest accumulated profits ──
            if cfg.dgt_enabled and state.accumulated_profits > 0:
                reinvest_amount = state.accumulated_profits * cfg.dgt_reinvest_pct
                if reinvest_amount > 0 and state.current_order_size > 0:
                    size_boost = reinvest_amount / (price * state.current_order_size) if price > 0 else 0
                    new_size = state.current_order_size * (1.0 + size_boost * 0.1)  # cap boost at 10%
                    state.dgt_reinvested += reinvest_amount
                    state.accumulated_profits -= reinvest_amount
                    state.current_order_size = new_size
                    logger.info(
                        "[DGT %s] Reinvested %.2f THB, order_size %.8f -> %.8f",
                        cfg.symbol, reinvest_amount, cfg.order_size, state.current_order_size,
                    )
            state.dgt_resets += 1
            # Cancel all stale orders outside new grid range
            await self._cancel_stale_orders(cfg, state, center_price, effective_spacing_pct)
            state.grid_anchor = price
        else:
            # Only cancel orders that drifted outside active range (minor cleanup)
            await self._cancel_stale_orders(cfg, state, center_price, effective_spacing_pct)

        # ── Confluence check: gate buy entries with indicators ──
        buy_allowed = True
        imbalance_override = False
        desperation_buy = False
        if cfg.enable_entry_confluence and not pause_buys:
            buy_allowed, imbalance_override = self._check_buy_confluence(cfg, state)
            if not buy_allowed:
                state.confluence_buys_blocked += 1
                state.consecutive_blocks += 1
                logger.debug(
                    "[Confluence %s] Buy BLOCKED — indicators not aligned (blocked=%d, consecutive=%d)",
                    cfg.symbol, state.confluence_buys_blocked, state.consecutive_blocks,
                )
                # ── Anti-Over-Filtering: Desperation Buy ──
                if (cfg.enable_desperation_buy
                        and state.consecutive_blocks >= cfg.desperation_buy_threshold):
                    buy_allowed = True
                    desperation_buy = True
                    logger.info(
                        "[Desperation %s] Allowing buy after %d consecutive blocks (threshold=%d)",
                        cfg.symbol, state.consecutive_blocks, cfg.desperation_buy_threshold,
                    )
            elif imbalance_override:
                state.imbalance_overrides += 1
                state.consecutive_blocks = 0  # reset on successful buy
                logger.info(
                    "[OB1 %s] Buy ALLOWED via order book imbalance override (%.2f > %.2f)",
                    cfg.symbol, state.last_imbalance, cfg.imbalance_threshold,
                )
            else:
                state.consecutive_blocks = 0  # reset on normal buy

        logger.info(
            "[Grid %s] price=%.2f center=%.2f spacing=%.2f%% mode=%s "
            "buys=%d sells=%d filled_b=%d filled_s=%d dgt_resets=%d conf_blocked=%d",
            cfg.symbol, price, center_price, effective_spacing_pct * 100,
            cfg.grid_mode,
            len(state.active_buys), len(state.active_sells),
            len(state.filled_buys), len(state.filled_sells),
            state.dgt_resets, state.confluence_buys_blocked,
        )

        # ── Place orders at active grid levels ──
        rnd = cfg.price_decimals
        for level in range(1, cfg.grid_levels + 1):
            if cfg.grid_mode == "geometric":
                # Geometric: center * (1 +/- pct%)^level
                factor = (1.0 + effective_spacing_pct) ** level
                buy_price = round(center_price / factor, rnd)
                sell_price = round(center_price * factor, rnd)
            else:
                # Arithmetic (legacy): center +/- fixed_amount * level
                spacing_abs = price * effective_spacing_pct
                buy_price = round(center_price - (spacing_abs * level), rnd)
                sell_price = round(center_price + (spacing_abs * level), rnd)

            # Place buy if not already active, not already filled at this price
            # Apply confluence gate: only place buy if indicators agree
            if not pause_buys and buy_allowed and buy_price not in state.active_buys and buy_price not in state.filled_buys:
                # Use reduced size for desperation buys
                buy_size = None
                if desperation_buy:
                    base_size = state.current_order_size if state.current_order_size > 0 else cfg.order_size
                    buy_size = base_size * cfg.desperation_buy_size_pct
                    state.desperation_buys_triggered += 1
                    state.consecutive_blocks = 0  # reset after triggering
                    logger.info(
                        "[Desperation %s] Placing reduced-size BUY @ %.2f (size=%.6f, %.0f%% of normal)",
                        cfg.symbol, buy_price, buy_size, cfg.desperation_buy_size_pct * 100,
                    )
                await self._place_grid_order(cfg, state, "BUY", buy_price, size_override=buy_size)

            # Place sell if not already active, not already filled at this price
            if not pause_sells and sell_price not in state.active_sells and sell_price not in state.filled_sells:
                await self._place_grid_order(cfg, state, "SELL", sell_price)

    async def _cancel_stale_orders(self, cfg: GridConfig, state: GridState, price: float, spacing_pct: float):
        """Cancel orders that are outside the current active grid range."""
        # Calculate active grid levels
        active_buy_prices = set()
        active_sell_prices = set()
        rnd = cfg.price_decimals
        for level in range(1, cfg.grid_levels + 1):
            if cfg.grid_mode == "geometric":
                factor = (1.0 + spacing_pct) ** level
                active_buy_prices.add(round(price / factor, rnd))
                active_sell_prices.add(round(price * factor, rnd))
            else:
                spacing_abs = price * spacing_pct
                active_buy_prices.add(round(price - (spacing_abs * level), rnd))
                active_sell_prices.add(round(price + (spacing_abs * level), rnd))

        # Cancel stale BUY orders (price no longer in active grid)
        stale_buy_prices = [p for p in state.active_buys if p not in active_buy_prices]
        for buy_price in stale_buy_prices:
            order_id = state.active_buys.pop(buy_price, None)
            if order_id:
                await self._cancel_order(order_id)
                logger.debug("[Grid %s] Cancelled stale BUY @ %.2f", cfg.symbol, buy_price)

        # Cancel stale SELL orders (price no longer in active grid)
        stale_sell_prices = [p for p in state.active_sells if p not in active_sell_prices]
        for sell_price in stale_sell_prices:
            order_id = state.active_sells.pop(sell_price, None)
            if order_id:
                await self._cancel_order(order_id)
                logger.debug("[Grid %s] Cancelled stale SELL @ %.2f", cfg.symbol, sell_price)

        if stale_buy_prices or stale_sell_prices:
            logger.info(
                "[Grid %s] Cancelled %d stale buys, %d stale sells",
                cfg.symbol, len(stale_buy_prices), len(stale_sell_prices),
            )

    async def _cancel_order(self, order_id: str):
        """Cancel a pending order in the paper engine."""
        try:
            await self._http.post(
                f"{PAPER_API_BASE}/api/paper/cancel",
                json={"order_id": order_id},
            )
        except Exception as e:
            logger.debug("Failed to cancel order %s: %s", order_id, e)

    async def _fetch_price(self, symbol: str) -> float:
        """Fetch current price from Binance TH API (for THB pairs) or fallback to testnet."""
        try:
            # THB pairs are only available on Binance TH
            if symbol.endswith("THB"):
                resp = await self._http.get(
                    "https://api.binance.th/api/v1/ticker/price",
                    params={"symbol": symbol},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return float(data["price"])
                else:
                    logger.warning("Binance TH price fetch failed for %s: %d", symbol, resp.status_code)
            else:
                # Non-THB pairs: try Binance testnet first
                resp = await self._http.get(
                    f"{BINANCE_TESTNET_REST}/api/v3/ticker/price",
                    params={"symbol": symbol},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return float(data["price"])
                else:
                    # Fallback: use Binance global public API
                    resp2 = await self._http.get(
                        "https://api.binance.com/api/v3/ticker/price",
                        params={"symbol": symbol},
                    )
                    if resp2.status_code == 200:
                        return float(resp2.json()["price"])
        except Exception as e:
            logger.warning("Failed to fetch price for %s: %s", symbol, e)
        return 0.0

    async def _place_grid_order(self, cfg: GridConfig, state: GridState, side: str, price: float, size_override: float = None):
        """Place a paper limit order at a grid level."""
        try:
            # ── Dynamic quantity: use DGT-adjusted order size ──
            effective_qty = size_override if size_override is not None else (state.current_order_size if state.current_order_size > 0 else cfg.order_size)
            notional = effective_qty * price
            if notional < cfg.min_notional and price > 0:
                # Scale up quantity to meet minimum notional
                raw_qty = cfg.min_notional / price
                factor = 10 ** cfg.qty_decimals
                effective_qty = math.ceil(raw_qty * factor) / factor
                notional = effective_qty * price

            resp = await self._http.post(
                f"{PAPER_API_BASE}/api/paper/order",
                json={
                    "symbol": cfg.symbol,
                    "side": side,
                    "quantity": effective_qty,
                    "limit_price": price,
                    "current_price": state.last_price,  # Market price for realistic simulation
                },
            )
            if resp.status_code == 201:
                order = resp.json()
                order_id = order.get("id", "")
                status = order.get("status", "")

                if status == "FILLED":
                    state.trades_executed += 1
                    if side == "BUY":
                        state.filled_buys[price] = effective_qty
                        logger.info(
                            "[Grid %s] BUY FILLED @ %.2f (qty=%.6f) — awaiting sell",
                            cfg.symbol, price, effective_qty,
                        )
                    else:
                        # SELL filled — calculate profit from oldest buy
                        buy_cost = 0.0
                        if state.filled_buys:
                            oldest_buy_price = min(state.filled_buys.keys())
                            buy_cost = oldest_buy_price * state.filled_buys.pop(oldest_buy_price)
                        else:
                            buy_cost = price * effective_qty  # fallback
                        profit = (price * effective_qty) - buy_cost - (price * effective_qty * 0.001)
                        state.total_profit += profit
                        state.filled_sells[price] = effective_qty
                        # ── DGT: Track accumulated profits for reinvestment ──
                        if cfg.dgt_enabled and profit > 0:
                            state.accumulated_profits += profit
                        logger.info(
                            "[Grid %s] SELL FILLED @ %.2f (qty=%.6f) profit=%.2f acc_profit=%.2f",
                            cfg.symbol, price, effective_qty, profit, state.accumulated_profits,
                        )
                else:
                    # PENDING — limit order waiting for price to touch
                    if side == "BUY":
                        state.active_buys[price] = order_id
                    else:
                        state.active_sells[price] = order_id
                    logger.debug(
                        "[Grid %s] %s PENDING @ %.2f (qty=%.6f)",
                        cfg.symbol, side, price, effective_qty,
                    )
            else:
                # Order rejected — log the reason for diagnostics
                try:
                    err_body = resp.json()
                    err_msg = err_body.get("error", "unknown")
                except Exception:
                    err_msg = f"HTTP {resp.status_code}"
                logger.warning(
                    "[Grid %s] %s rejected @ %.2f (qty=%.6f notional=%.2f): %s",
                    cfg.symbol, side, price, effective_qty, notional, err_msg,
                )
        except Exception as e:
            logger.debug("Failed to place %s order @ %.2f: %s", side, price, e)

    async def _sync_state(self, cfg: GridConfig, state: GridState, current_price: float):
        """Sync grid state with paper engine — reconcile filled vs pending orders."""
        try:
            # Query open (pending) orders from paper engine
            resp = await self._http.get(f"{PAPER_API_BASE}/api/paper/orders")
            if resp.status_code == 200:
                open_orders = resp.json()
                # Build set of order IDs that are still pending for this symbol
                pending_ids = {
                    o["id"] for o in open_orders
                    if o.get("symbol") == cfg.symbol and o.get("status") == "PENDING"
                }
                # Remove grid levels whose orders are no longer pending (filled or cancelled)
                newly_filled_buys = []
                newly_fill_sells = []
                for price, oid in list(state.active_buys.items()):
                    if oid not in pending_ids:
                        newly_fill_buys.append(price)
                        del state.active_buys[price]
                for price, oid in list(state.active_sells.items()):
                    if oid not in pending_ids:
                        newly_fill_sells.append(price)
                        del state.active_sells[price]

                # Track newly filled buys (awaiting corresponding sell)
                for price in newly_fill_buys:
                    if price not in state.filled_buys:
                        # Estimate qty from DGT-adjusted order size
                        base_qty = state.current_order_size if state.current_order_size > 0 else cfg.order_size
                        raw_qty = cfg.min_notional / price if price > 0 else base_qty
                        factor = 10 ** cfg.qty_decimals
                        est_qty = math.ceil(raw_qty * factor) / factor
                        state.filled_buys[price] = max(est_qty, base_qty)
                        state.trades_executed += 1
                        logger.info(
                            "[Grid %s] BUY filled (detected via sync) @ %.2f",
                            cfg.symbol, price,
                        )

                # Track newly filled sells (match against oldest buy)
                for price in newly_fill_sells:
                    if price not in state.filled_sells:
                        raw_qty = cfg.min_notional / price if price > 0 else (state.current_order_size if state.current_order_size > 0 else cfg.order_size)
                        factor = 10 ** cfg.qty_decimals
                        base_qty = state.current_order_size if state.current_order_size > 0 else cfg.order_size
                        est_qty = math.ceil(raw_qty * factor) / factor
                        qty = max(est_qty, base_qty)
                        # Calculate profit
                        buy_cost = 0.0
                        if state.filled_buys:
                            oldest_buy_price = min(state.filled_buys.keys())
                            buy_cost = oldest_buy_price * state.filled_buys.pop(oldest_buy_price)
                        else:
                            buy_cost = price * qty
                        profit = (price * qty) - buy_cost - (price * qty * 0.001)
                        state.total_profit += profit
                        # ── DGT: Track accumulated profits for reinvestment ──
                        if cfg.dgt_enabled and profit > 0:
                            state.accumulated_profits += profit
                        state.filled_sells[price] = qty
                        state.trades_executed += 1
                        logger.info(
                            "[Grid %s] SELL filled (detected via sync) @ %.2f profit=%.2f",
                            cfg.symbol, price, profit,
                        )

                if newly_fill_buys or newly_fill_sells:
                    logger.info(
                        "[Grid %s] Synced: %d buys + %d sells filled, "
                        "remaining pending buys=%d sells=%d total_filled_b=%d filled_s=%d",
                        cfg.symbol, len(newly_fill_buys), len(newly_fill_sells),
                        len(state.active_buys), len(state.active_sells),
                        len(state.filled_buys), len(state.filled_sells),
                    )
        except Exception as e:
            logger.debug("Failed to sync state: %s", e)

    # ── Kline history + Confluence indicators ────────────────────────────────

    async def _update_kline_history(self, cfg: GridConfig, state: GridState):
        """Fetch recent klines to maintain rolling close/volume/high/low history for indicators."""
        try:
            if cfg.symbol.endswith("THB"):
                url = "https://api.binance.th/api/v1/klines"
            else:
                url = "https://api.binance.com/api/v3/klines"
            limit = max(
                cfg.macd_slow + cfg.macd_signal,
                cfg.rsi_period,
                cfg.volume_sma_period,
                cfg.atr_period + 5 if cfg.enable_adaptive_spacing else 0,
            ) + 10
            resp = await self._kline_http.get(
                url, params={"symbol": cfg.symbol, "interval": "15m", "limit": limit},
            )
            if resp.status_code == 200:
                raw = resp.json()
                state.kline_closes = [float(k[4]) for k in raw]
                state.kline_volumes = [float(k[5]) for k in raw]
                state.kline_highs = [float(k[2]) for k in raw]
                state.kline_lows = [float(k[3]) for k in raw]
        except Exception as e:
            logger.debug("Kline fetch failed for %s: %s", cfg.symbol, e)

    @staticmethod
    def _calc_atr(highs: List[float], lows: List[float], closes: List[float], period: int) -> float:
        """Calculate Average True Range from kline high/low/close arrays."""
        if len(closes) < period + 1 or not highs or not lows:
            return 0.0
        true_ranges = []
        for i in range(1, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            true_ranges.append(tr)
        if not true_ranges:
            return 0.0
        return sum(true_ranges[-period:]) / min(period, len(true_ranges))

    @staticmethod
    def _calc_rsi(closes: List[float], period: int = 14) -> Optional[float]:
        """Calculate RSI from close prices."""
        if len(closes) < period + 1:
            return None
        gains, losses = [], []
        for i in range(1, len(closes)):
            delta = closes[i] - closes[i - 1]
            gains.append(max(delta, 0))
            losses.append(max(-delta, 0))
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    @staticmethod
    def _calc_ema(values: List[float], period: int) -> List[float]:
        """Calculate EMA series from values."""
        if len(values) < period:
            return []
        multiplier = 2.0 / (period + 1)
        ema = [sum(values[:period]) / period]  # SMA seed
        for v in values[period:]:
            ema.append((v - ema[-1]) * multiplier + ema[-1])
        return ema

    def _calc_macd(self, closes: List[float], cfg: GridConfig) -> tuple:
        """Calculate MACD histogram. Returns (hist, prev_hist) or (None, None)."""
        if len(closes) < cfg.macd_slow + cfg.macd_signal:
            return None, None
        ema_fast = self._calc_ema(closes, cfg.macd_fast)
        ema_slow = self._calc_ema(closes, cfg.macd_slow)
        offset = len(ema_fast) - len(ema_slow)
        macd_line = [ema_fast[offset + i] - ema_slow[i] for i in range(len(ema_slow))]
        if len(macd_line) < cfg.macd_signal:
            return None, None
        signal_line = self._calc_ema(macd_line, cfg.macd_signal)
        sig_offset = len(macd_line) - len(signal_line)
        hist = macd_line[-1] - signal_line[-1]
        prev_hist = macd_line[-2] - signal_line[-2] if len(signal_line) >= 2 else 0
        return hist, prev_hist

    def _check_buy_confluence(self, cfg: GridConfig, state: GridState) -> tuple:
        """
        Multi-indicator confluence check for BUY entry (Freqtrade-style AND logic).
        ALL must be true:
          1. RSI < buy_threshold (buying dip, not overbought)
          2. MACD histogram > previous histogram (momentum improving)
          3. Volume > SMA * multiplier (volume confirmation)

        Order Book Imbalance override:
          If RSI is borderline (threshold .. threshold+relax) and imbalance > threshold,
          relax the RSI check (strong buy pressure in the order book).

        Returns: (buy_allowed: bool, imbalance_override: bool)
        """
        closes = state.kline_closes
        volumes = state.kline_volumes
        warmup = max(cfg.rsi_period, cfg.macd_slow + cfg.macd_signal, cfg.volume_sma_period, cfg.ema_trend_period) + 5
        if len(closes) < warmup:
            return True, False  # not enough data yet, allow by default

        # 0. EMA Trend Filter: block buys in downtrend (price < EMA)
        if cfg.enable_ema_trend_filter:
            ema_vals = self._calc_ema(closes, cfg.ema_trend_period)
            if ema_vals:
                ema_val = ema_vals[-1]
                state.last_ema = ema_val
                current_price = closes[-1]
                if current_price < ema_val:
                    state.ema_trend_blocked += 1
                    logger.debug(
                        "[Trend %s] Buy BLOCKED — price %.2f < EMA(%d) %.2f (downtrend, blocked=%d)",
                        cfg.symbol, current_price, cfg.ema_trend_period, ema_val,
                        state.ema_trend_blocked,
                    )
                    return False, False

        # 1. RSI check (with potential imbalance relaxation)
        rsi = self._calc_rsi(closes, cfg.rsi_period)
        rsi_threshold = cfg.rsi_buy_threshold
        imbalance_overrode = False

        if rsi is not None and rsi >= rsi_threshold:
            # Check if order book imbalance can relax the RSI threshold
            if (cfg.enable_orderbook_imbalance
                    and state.last_imbalance > cfg.imbalance_threshold
                    and rsi < rsi_threshold + cfg.imbalance_rsi_relax):
                imbalance_overrode = True  # strong buy pressure — relax RSI
            else:
                return False, False  # RSI too high, no override

        # 2. MACD momentum check
        hist, prev_hist = self._calc_macd(closes, cfg)
        if hist is not None and prev_hist is not None and hist <= prev_hist:
            return False, False

        # 3. Volume confirmation
        if len(volumes) >= cfg.volume_sma_period:
            vol_sma = sum(volumes[-cfg.volume_sma_period:]) / cfg.volume_sma_period
            current_vol = volumes[-1] if volumes else 0
            if vol_sma > 0 and current_vol < vol_sma * cfg.volume_multiplier:
                return False, False

        return True, imbalance_overrode

    # ── Order Book Depth + Imbalance ────────────────────────────────────────

    async def _fetch_orderbook_depth(self, cfg: GridConfig, state: GridState):
        """Fetch order book depth and calculate bid/ask volume imbalance.

        Imbalance ratio = bid_volume / (bid_volume + ask_volume)
        - > 0.5 = more buy pressure (bids heavier)
        - > 0.65 = strong buy pressure
        - < 0.35 = strong sell pressure
        """
        try:
            if cfg.symbol.endswith("THB"):
                url = "https://api.binance.th/api/v1/depth"
            else:
                url = "https://api.binance.com/api/v3/depth"

            resp = await self._http.get(
                url, params={"symbol": cfg.symbol, "limit": cfg.orderbook_depth_limit},
            )
            if resp.status_code == 200:
                data = resp.json()
                bids = data.get("bids", [])  # [[price, qty], ...]
                asks = data.get("asks", [])

                bid_volume = sum(float(b[1]) for b in bids) if bids else 0.0
                ask_volume = sum(float(a[1]) for a in asks) if asks else 0.0
                total = bid_volume + ask_volume

                if total > 0:
                    state.last_imbalance = bid_volume / total
                else:
                    state.last_imbalance = 0.5  # neutral if no data

                logger.debug(
                    "[OB1 %s] depth=%d bid_vol=%.4f ask_vol=%.4f imbalance=%.3f",
                    cfg.symbol, cfg.orderbook_depth_limit,
                    bid_volume, ask_volume, state.last_imbalance,
                )
        except Exception as e:
            logger.debug("Order book depth fetch failed for %s: %s", cfg.symbol, e)

    async def _reset_paper_engine(self):
        """Reset the paper trading engine to initial state."""
        try:
            resp = await self._http.post(f"{PAPER_API_BASE}/api/paper/reset")
            if resp.status_code == 200:
                logger.info("Paper engine reset to $50,000")
        except Exception as e:
            logger.warning("Failed to reset paper engine: %s", e)

    async def _seed_positions(self):
        """Seed initial positions for all symbols so SELL orders can execute.

        Without seeding, the Go PaperEngine rejects SELL orders because no BUY
        has filled yet → no position exists. We place a seed position sized to
        cover at least one grid level's worth of sell orders (based on min_notional).
        """
        seeded = 0
        for cfg in self.configs:
            try:
                price = await self._fetch_price(cfg.symbol)
                if price <= 0:
                    logger.warning("[Seed %s] Price fetch failed — skipping seed", cfg.symbol)
                    continue

                # Calculate the quantity the grid bot will actually use for SELL orders.
                # Mirror _place_grid_order logic: start from order_size, scale up only if
                # order_size * price < min_notional.
                effective_qty = cfg.order_size
                if effective_qty * price < cfg.min_notional and price > 0:
                    raw_qty = cfg.min_notional / price
                    factor = 10 ** cfg.qty_decimals
                    effective_qty = math.ceil(raw_qty * factor) / factor
                # Seed enough for grid_levels sells (so all SELL orders can execute)
                seed_qty = effective_qty * cfg.grid_levels

                resp = await self._http.post(
                    f"{PAPER_API_BASE}/api/paper/seed",
                    json={
                        "symbol": cfg.symbol,
                        "quantity": seed_qty,
                        "price": price,
                    },
                )
                if resp.status_code == 200:
                    seeded += 1
                    logger.info(
                        "[Seed %s] Position seeded: qty=%.6f price=%.2f cost=%.2f",
                        cfg.symbol, seed_qty, price, seed_qty * price,
                    )
                else:
                    err = resp.json().get("error", "unknown")
                    logger.warning("[Seed %s] Seed failed: %s", cfg.symbol, err)
            except Exception as e:
                logger.warning("[Seed %s] Seed error: %s", cfg.symbol, e)

        logger.info("Seeded %d/%d symbol positions", seeded, len(self.configs))

    def get_status(self) -> Dict:
        """Get current grid bot status with DGT + confluence metrics."""
        return {
            "running": self._running,
            "symbols": {
                symbol: {
                    "last_price": state.last_price,
                    "grid_anchor": state.grid_anchor,
                    "active_buys": len(state.active_buys),
                    "active_sells": len(state.active_sells),
                    "filled_buys": len(state.filled_buys),
                    "filled_sells": len(state.filled_sells),
                    "trades_executed": state.trades_executed,
                    "total_profit": round(state.total_profit, 2),
                    # DGT metrics
                    "dgt_resets": state.dgt_resets,
                    "dgt_reinvested": round(state.dgt_reinvested, 2),
                    "accumulated_profits": round(state.accumulated_profits, 2),
                    "current_order_size": round(state.current_order_size, 8),
                    # Confluence metrics
                    "confluence_buys_blocked": state.confluence_buys_blocked,
                    # Order book imbalance metrics
                    "last_imbalance": round(state.last_imbalance, 4),
                    "imbalance_overrides": state.imbalance_overrides,
                    # EMA trend filter metrics
                    "ema_trend_blocked": state.ema_trend_blocked,
                    "last_ema": round(state.last_ema, 2),
                    # Desperation buy metrics
                    "consecutive_blocks": state.consecutive_blocks,
                    "desperation_buys_triggered": state.desperation_buys_triggered,
                }
                for symbol, state in self.states.items()
            },
        }


# ── Singleton instance for FastAPI integration ────────────────────────────────

_grid_bot: Optional[GridBot] = None


def get_grid_bot() -> GridBot:
    global _grid_bot
    if _grid_bot is None:
        _grid_bot = GridBot()
    return _grid_bot


# ── Standalone entry point ────────────────────────────────────────────────────

async def main():
    """Run the grid bot standalone."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    bot = GridBot()
    try:
        await bot.start()
    except KeyboardInterrupt:
        await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
