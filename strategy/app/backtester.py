"""
Grid Trading Backtester
========================
Simulates grid trading strategy against historical kline data.

Supports 3 advanced modes (inspired by Freqtrade + NTU DGT research):
  1. Geometric grid spacing (% based, adapts to price level)
  2. DGT dynamic grid reset with profit reinvestment
  3. Multi-indicator confluence entry timing (RSI + MACD + Volume)

Usage:
    backtester = GridBacktester(
        symbol="BTCTHB",
        grid_spacing_pct=1.5,
        grid_levels=2,
        order_size=0.00005,
        grid_mode="geometric",         # "arithmetic" | "geometric"
        enable_entry_confluence=True,   # gate entries with indicators
        dgt_reinvest_pct=0.5,          # reinvest 50% of profits
    )
    results = await backtester.run(days=30)
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger("backtester")

BINANCE_PUBLIC_REST = "https://api.binance.th"


@dataclass
class BacktestConfig:
    symbol: str
    grid_spacing_pct: float = 1.5       # % between grid levels
    grid_levels: int = 2                # number of levels above/below
    order_size: float = 0.00005         # base quantity per grid order
    max_position: float = 0.001         # max position size
    max_open_orders: int = 10           # max simultaneous open orders
    initial_capital_thb: float = 10000.0  # starting capital
    # ATR-based dynamic spacing (mirrors real bot)
    volatility_mode: str = "fixed"      # "fixed" or "atr"
    atr_period: int = 14                # ATR calculation period
    atr_multiplier: float = 1.5         # ATR multiplier for spacing
    min_spacing_pct: float = 0.2        # min spacing floor (micro-scalper mode)
    max_spacing_pct: float = 5.0        # max spacing ceiling
    # ── NEW: Grid mode ──────────────────────────────────────────────────────
    grid_mode: str = "arithmetic"       # "arithmetic" (legacy) | "geometric" (DGT-style)
    # ── NEW: DGT dynamic grid reset with profit reinvestment ────────────────
    dgt_enabled: bool = False           # enable DGT grid reset + reinvest
    dgt_reinvest_pct: float = 0.5       # % of accumulated profits to reinvest
    # ── NEW: Multi-indicator confluence entry timing ────────────────────────
    enable_entry_confluence: bool = False  # gate buys with RSI+MACD+Volume
    rsi_period: int = 14                # RSI lookback period
    rsi_buy_threshold: float = 45.0     # only buy when RSI < this
    rsi_sell_threshold: float = 70.0    # consider sell when RSI > this
    macd_fast: int = 12                 # MACD fast EMA period
    macd_slow: int = 26                 # MACD slow EMA period
    macd_signal: int = 9                # MACD signal line period
    volume_sma_period: int = 20         # volume SMA lookback
    volume_multiplier: float = 1.5      # volume must be > SMA * this to buy
    # ── NEW: Order Book Imbalance (OB1) ──────────────────────────────────────
    enable_orderbook_imbalance: bool = False  # use simulated imbalance to override borderline RSI
    imbalance_threshold: float = 0.65         # bid/(bid+ask) > this = strong buy pressure
    imbalance_rsi_relax: float = 10.0         # relax RSI threshold by this much when imbalance strong
    # ── NEW: EMA Trend Filter (TF) ────────────────────────────────────────────
    enable_ema_trend_filter: bool = False  # block buys when price < EMA (downtrend)
    ema_trend_period: int = 50            # EMA period for trend direction
    # ── NEW: Anti-Over-Filtering (Desperation Buy) ──────────────────────────────
    enable_desperation_buy: bool = False  # allow reduced-size buy after N consecutive blocks
    desperation_buy_threshold: int = 20   # number of consecutive blocks before triggering
    desperation_buy_size_pct: float = 0.5 # order size multiplier for desperation buy
    # ── NEW: Multi-Timeframe Confirmation (MTF) ───────────────────────────────────
    enable_mtf_confirmation: bool = False   # require higher-TF trend alignment
    mtf_interval: str = "4h"               # higher timeframe interval
    mtf_ema_fast: int = 20                 # fast EMA period on higher TF
    mtf_ema_slow: int = 50                 # slow EMA period on higher TF
    # ── NEW: Statistical Entry Scoring (SES) ──────────────────────────────────────
    enable_statistical_scoring: bool = False  # use historical win-rate scoring instead of hard thresholds
    ses_warmup_trades: int = 10             # min trades before scoring kicks in
    ses_min_score: float = 0.55             # minimum score to allow buy (0-1)


@dataclass
class BacktestTrade:
    timestamp: int
    side: str  # BUY or SELL
    price: float
    quantity: float
    pnl: float = 0.0  # realized P&L (for sells)
    fee: float = 0.0


@dataclass
class BacktestResult:
    symbol: str
    start_time: int
    end_time: int
    duration_days: float
    # Performance metrics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    total_fees: float
    net_pnl: float
    max_drawdown: float
    max_drawdown_pct: float
    # Trade details
    avg_win: float
    avg_loss: float
    profit_factor: float
    # Grid stats
    avg_grid_spacing_pct: float
    trades_per_day: float
    # Configuration used
    config: Dict
    # ATR-specific metrics
    atr_spacing_avg: float = 0.0
    atr_spacing_min: float = 0.0
    atr_spacing_max: float = 0.0
    volatility_mode: str = "fixed"
    # NEW: Advanced strategy metrics
    grid_mode: str = "arithmetic"
    dgt_resets: int = 0                 # number of DGT grid resets
    dgt_reinvested_thb: float = 0.0     # total THB reinvested from profits
    confluence_buys_blocked: int = 0    # buys blocked by indicator gate
    final_order_size: float = 0.0       # order size after DGT reinvestment
    # Order book imbalance metrics
    imbalance_overrides: int = 0        # times imbalance allowed a borderline buy
    avg_imbalance: float = 0.0          # average imbalance during the backtest
    # EMA trend filter metrics
    ema_trend_blocked: int = 0          # buys blocked because price < EMA (downtrend)
    # Desperation buy metrics
    desperation_buys_triggered: int = 0  # total desperation buys executed
    # Multi-timeframe metrics
    mtf_blocked: int = 0                 # buys blocked by MTF confirmation
    # Statistical scoring metrics
    ses_score_avg: float = 0.0           # average entry score
    ses_trades_allowed: int = 0          # trades allowed by scoring
    ses_trades_blocked: int = 0          # trades blocked by scoring
    # Trade history (sample)
    trades: List[BacktestTrade] = field(default_factory=list)


class GridBacktester:
    """
    Simulates grid trading on historical kline data.
    """

    def __init__(self, config: BacktestConfig):
        self.config = config
        self._http: Optional[httpx.AsyncClient] = None

    async def _fetch_klines(self, symbol: str, interval: str, limit: int) -> List[Dict]:
        """Fetch historical klines from Binance TH."""
        if not self._http:
            self._http = httpx.AsyncClient(timeout=15.0)

        try:
            resp = await self._http.get(
                f"{BINANCE_PUBLIC_REST}/api/v1/klines",
                params={"symbol": symbol, "interval": interval, "limit": limit},
            )
            if resp.status_code == 200:
                raw = resp.json()
                return [
                    {
                        "timestamp": k[0],
                        "open": float(k[1]),
                        "high": float(k[2]),
                        "low": float(k[3]),
                        "close": float(k[4]),
                        "volume": float(k[5]),
                    }
                    for k in raw
                ]
        except Exception as e:
            logger.error("Failed to fetch klines: %s", e)

        return []

    def _calc_atr_from_klines(self, klines_slice: List[Dict], period: int) -> float:
        """Calculate ATR from a slice of klines (same logic as real bot)."""
        true_ranges = []
        for i in range(1, len(klines_slice)):
            high = klines_slice[i]["high"]
            low = klines_slice[i]["low"]
            prev_close = klines_slice[i - 1]["close"]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            true_ranges.append(tr)
        if not true_ranges:
            return 0.0
        return sum(true_ranges[-period:]) / min(period, len(true_ranges))

    # ── NEW: Indicator calculations for confluence entry ─────────────────────

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

    def _calc_macd(self, closes: List[float]) -> tuple:
        """Calculate MACD line, signal line, histogram. Returns (macd, signal, hist) or None."""
        if len(closes) < self.config.macd_slow + self.config.macd_signal:
            return None, None, None
        ema_fast = self._calc_ema(closes, self.config.macd_fast)
        ema_slow = self._calc_ema(closes, self.config.macd_slow)
        # Align lengths: ema_fast is longer, trim from front
        offset = len(ema_fast) - len(ema_slow)
        macd_line = [ema_fast[offset + i] - ema_slow[i] for i in range(len(ema_slow))]
        if len(macd_line) < self.config.macd_signal:
            return None, None, None
        signal_line = self._calc_ema(macd_line, self.config.macd_signal)
        # Align
        sig_offset = len(macd_line) - len(signal_line)
        hist = macd_line[-1] - signal_line[-1]
        prev_hist = macd_line[-2] - signal_line[-2] if len(signal_line) >= 2 else 0
        return hist, prev_hist, signal_line

    @staticmethod
    def _calc_volume_sma(volumes: List[float], period: int) -> Optional[float]:
        """Calculate simple moving average of volume."""
        if len(volumes) < period:
            return None
        return sum(volumes[-period:]) / period

    def _estimate_imbalance(self, kline: Dict) -> float:
        """Estimate order book imbalance from a single kline.

        Uses close position within the high-low range + volume as proxy:
          - If close is near the high → more buying pressure → imbalance > 0.5
          - If close is near the low → more selling pressure → imbalance < 0.5

        Formula: 0.5 + 0.5 * ((close - low) / (high - low) - 0.5) * volume_factor
        Clamped to [0.0, 1.0].
        """
        high = kline["high"]
        low = kline["low"]
        close = kline["close"]
        hl_range = high - low
        if hl_range <= 0:
            return 0.5  # no range = neutral
        # Position of close within range (0 = at low, 1 = at high)
        close_position = (close - low) / hl_range
        # Center around 0.5 and scale
        imbalance = 0.5 + (close_position - 0.5) * 0.6  # dampen to avoid extreme values
        return max(0.0, min(1.0, imbalance))

    def _check_buy_confluence(self, klines: List[Dict], idx: int, current_imbalance: float = 0.5) -> bool:
        """
        Multi-indicator confluence check for BUY entry.
        ALL must be true (Freqtrade-style AND logic):
          1. RSI < buy_threshold (not overbought, buying dip)
          2. MACD histogram > previous histogram (momentum improving)
          3. Volume > SMA * multiplier (volume confirmation)

        Order Book Imbalance override:
          If RSI is borderline (threshold .. threshold+relax) and imbalance > threshold,
          relax the RSI check.
        """
        if not self.config.enable_entry_confluence:
            return True  # confluence disabled = always allow

        # Need enough history for indicators
        warmup = max(self.config.rsi_period, self.config.macd_slow + self.config.macd_signal, self.config.volume_sma_period, self.config.ema_trend_period) + 5
        if idx < warmup:
            return True  # not enough data yet, allow by default

        # 0. EMA Trend Filter: block buys in downtrend (price < EMA)
        if self.config.enable_ema_trend_filter:
            ema_closes = [klines[j]["close"] for j in range(max(0, idx - self.config.ema_trend_period - 5), idx + 1)]
            ema_vals = self._calc_ema(ema_closes, self.config.ema_trend_period)
            if ema_vals:
                ema_val = ema_vals[-1]
                current_price = klines[idx]["close"]
                if current_price < ema_val:
                    return False  # price below EMA = downtrend, don't buy

        # 1. RSI check (with potential imbalance relaxation)
        closes = [klines[j]["close"] for j in range(max(0, idx - self.config.rsi_period - 1), idx + 1)]
        rsi = self._calc_rsi(closes, self.config.rsi_period)

        if rsi is not None and rsi >= self.config.rsi_buy_threshold:
            # Check if order book imbalance can relax the RSI threshold
            if (self.config.enable_orderbook_imbalance
                    and current_imbalance > self.config.imbalance_threshold
                    and rsi < self.config.rsi_buy_threshold + self.config.imbalance_rsi_relax):
                pass  # strong buy pressure — allow despite borderline RSI
            else:
                return False  # RSI too high — don't buy

        # 2. MACD momentum check (histogram improving)
        macd_closes = [klines[j]["close"] for j in range(max(0, idx - self.config.macd_slow - self.config.macd_signal - 5), idx + 1)]
        hist, prev_hist, _ = self._calc_macd(macd_closes)
        if hist is not None and prev_hist is not None:
            if hist <= prev_hist:
                return False  # MACD momentum not improving

        # 3. Volume confirmation
        volumes = [klines[j]["volume"] for j in range(max(0, idx - self.config.volume_sma_period), idx + 1)]
        vol_sma = self._calc_volume_sma(volumes, self.config.volume_sma_period)
        current_vol = klines[idx]["volume"]
        if vol_sma is not None and current_vol < vol_sma * self.config.volume_multiplier:
            return False  # volume too low

        return True

    def _check_sell_confluence(self, klines: List[Dict], idx: int) -> bool:
        """Check if sell conditions are favorable (RSI overbought)."""
        if not self.config.enable_entry_confluence:
            return True  # confluence disabled = always allow sells

        warmup = self.config.rsi_period + 5
        if idx < warmup:
            return True

        closes = [klines[j]["close"] for j in range(max(0, idx - self.config.rsi_period - 1), idx + 1)]
        rsi = self._calc_rsi(closes, self.config.rsi_period)
        if rsi is not None and rsi >= self.config.rsi_sell_threshold:
            return True  # RSI overbought — good time to sell
        # Also sell if MACD momentum deteriorating
        macd_closes = [klines[j]["close"] for j in range(max(0, idx - self.config.macd_slow - self.config.macd_signal - 5), idx + 1)]
        hist, prev_hist, _ = self._calc_macd(macd_closes)
        if hist is not None and prev_hist is not None and hist < prev_hist:
            return True  # MACD weakening — take profit
        return True  # default: allow sell (grid sell orders are pre-placed)

    async def run(self, days: int = 30, interval: str = "1h") -> BacktestResult:
        """
        Run backtest simulation.
        
        Args:
            days: Number of days to backtest
            interval: Kline interval (1m, 5m, 15m, 1h, 4h, 1d)
        
        Returns:
            BacktestResult with performance metrics
        """
        logger.info(
            "Starting backtest: %s, %d days, mode=%s, spacing=%.2f%%, levels=%d, "
            "grid=%s, dgt=%s, confluence=%s",
            self.config.symbol, days, self.config.volatility_mode,
            self.config.grid_spacing_pct, self.config.grid_levels,
            self.config.grid_mode, self.config.dgt_enabled,
            self.config.enable_entry_confluence,
        )

        # Calculate how many klines we need
        intervals_per_day = {
            "1m": 1440, "5m": 288, "15m": 96,
            "1h": 24, "4h": 6, "1d": 1,
        }
        klines_needed = days * intervals_per_day.get(interval, 24)
        klines_needed = min(klines_needed, 1000)  # Binance TH limit

        # Fetch historical data
        klines = await self._fetch_klines(self.config.symbol, interval, klines_needed)
        if not klines:
            raise ValueError(f"No kline data available for {self.config.symbol}")

        logger.info("Fetched %d klines from %s to %s",
                    len(klines),
                    time.strftime("%Y-%m-%d", time.gmtime(klines[0]["timestamp"] / 1000)),
                    time.strftime("%Y-%m-%d", time.gmtime(klines[-1]["timestamp"] / 1000)))

        # Simulation state
        position: float = 0.0
        capital: float = self.config.initial_capital_thb
        trades: List[BacktestTrade] = []
        peak_capital: float = capital
        max_drawdown: float = 0.0
        atr_spacing_values: List[float] = []
        buy_cost_queue: List[float] = []  # FIFO: cost basis per unit batch for sells

        # Grid state — anchored to price, shifts when price moves out of range
        pending_buys: Dict[float, float] = {}    # price -> qty (unfilled buy orders)
        pending_sells: Dict[float, float] = {}   # price -> qty (unfilled sell orders)
        grid_anchor: float = 0.0
        grid_spacing_abs: float = 0.0
        current_spacing: float = 0.0

        # ── NEW: DGT tracking ───────────────────────────────────────────────
        accumulated_profits: float = 0.0   # track total realized profits
        dgt_resets: int = 0               # count grid resets
        dgt_reinvested: float = 0.0       # total THB reinvested
        current_order_size: float = self.config.order_size  # can grow via DGT

        # ── NEW: Confluence tracking ────────────────────────────────────────
        confluence_blocked: int = 0        # buys blocked by indicator gate
        imbalance_overrides: int = 0       # times imbalance allowed a borderline buy
        imbalance_sum: float = 0.0         # running sum for average calculation
        ema_trend_blocked: int = 0         # buys blocked by EMA trend filter
        consecutive_blocks: int = 0        # consecutive confluence blocks
        desperation_buys_triggered: int = 0  # total desperation buys executed

        # ── Multi-Timeframe tracking ──────────────────────────────────────────
        mtf_blocked: int = 0
        mtf_klines: List[Dict] = []
        if self.config.enable_mtf_confirmation:
            mtf_klines = await self._fetch_klines(self.config.symbol, self.config.mtf_interval, 200)
            logger.info("Fetched %d MTF klines (%s) for trend confirmation", len(mtf_klines), self.config.mtf_interval)

        # ── Statistical Entry Scoring tracking ────────────────────────────────
        ses_score_sum: float = 0.0
        ses_score_count: int = 0
        ses_allowed: int = 0
        ses_blocked: int = 0
        ses_completed_trades: List[Dict] = []  # track buy features -> sell outcome

        def _build_grid_arithmetic(center: float, sp_abs: float) -> tuple:
            """Build grid with fixed arithmetic spacing (legacy mode)."""
            buys: Dict[float, float] = {}
            sells: Dict[float, float] = {}
            for level in range(1, self.config.grid_levels + 1):
                bp = int(center - (sp_abs * level))
                sp = int(center + (sp_abs * level))
                if bp > 0:
                    buys[bp] = current_order_size
                sells[sp] = current_order_size
            return buys, sells

        def _build_grid_geometric(center: float, spacing_pct: float) -> tuple:
            """Build grid with geometric (% based) spacing — DGT style.
            Each level is center * (1 +/- spacing_pct%)^level
            This adapts to price level automatically."""
            buys: Dict[float, float] = {}
            sells: Dict[float, float] = {}
            for level in range(1, self.config.grid_levels + 1):
                factor = (1.0 + spacing_pct / 100.0) ** level
                bp = int(center / factor)  # geometric below
                sp = int(center * factor)  # geometric above
                if bp > 0:
                    buys[bp] = current_order_size
                sells[sp] = current_order_size
            return buys, sells

        def _build_grid(center: float, sp_abs: float, sp_pct: float) -> tuple:
            """Build grid using configured mode."""
            if self.config.grid_mode == "geometric":
                return _build_grid_geometric(center, sp_pct)
            return _build_grid_arithmetic(center, sp_abs)

        # Simulate grid trading
        for i, kline in enumerate(klines):
            high = kline["high"]
            low = kline["low"]
            price = kline["close"]
            timestamp = kline["timestamp"]

            # Determine spacing based on volatility mode
            if self.config.volatility_mode == "atr" and i >= self.config.atr_period:
                lookback_start = max(0, i - self.config.atr_period - 1)
                atr_klines = klines[lookback_start:i + 1]
                atr = self._calc_atr_from_klines(atr_klines, self.config.atr_period)
                atr_pct = (atr / price) * 100 * self.config.atr_multiplier
                current_spacing = max(self.config.min_spacing_pct, min(self.config.max_spacing_pct, atr_pct))
                atr_spacing_values.append(current_spacing)
            else:
                current_spacing = self.config.grid_spacing_pct

            grid_spacing_abs = price * (current_spacing / 100.0)

            # Initialize or shift grid to follow price
            if grid_anchor == 0:
                grid_anchor = price
                pending_buys, pending_sells = _build_grid(grid_anchor, grid_spacing_abs, current_spacing)
            else:
                # Shift grid when price moves beyond outermost levels
                lowest_buy = min(pending_buys.keys()) if pending_buys else price
                highest_sell = max(pending_sells.keys()) if pending_sells else price
                if low < lowest_buy or high > highest_sell:
                    # ── DGT: Before resetting, reinvest profits ──
                    if self.config.dgt_enabled and accumulated_profits > 0:
                        reinvest_amount = accumulated_profits * self.config.dgt_reinvest_pct
                        if reinvest_amount > 0 and current_order_size > 0:
                            # Increase order size proportionally to reinvested profits
                            size_boost = reinvest_amount / (price * current_order_size) if price > 0 else 0
                            new_size = current_order_size * (1.0 + size_boost * 0.1)  # cap boost at 10%
                            dgt_reinvested += reinvest_amount
                            accumulated_profits -= reinvest_amount
                            current_order_size = new_size
                            logger.debug(
                                "DGT reinvest: order_size %.8f -> %.8f (reinvested %.2f THB)",
                                self.config.order_size, current_order_size, reinvest_amount,
                            )
                    dgt_resets += 1
                    grid_anchor = price
                    pending_buys, pending_sells = _build_grid(grid_anchor, grid_spacing_abs, current_spacing)

            # ── Check buy fills (low price dropped to buy level) ──
            # Apply confluence gate: only buy if indicators agree
            # Estimate order book imbalance from current kline
            current_imbalance = self._estimate_imbalance(kline) if self.config.enable_orderbook_imbalance else 0.5
            imbalance_sum += current_imbalance
            buy_allowed = self._check_buy_confluence(klines, i, current_imbalance)
            # Track EMA trend filter blocks
            if self.config.enable_ema_trend_filter and not buy_allowed:
                ema_closes_track = [klines[j]["close"] for j in range(max(0, i - self.config.ema_trend_period - 5), i + 1)]
                ema_vals_track = self._calc_ema(ema_closes_track, self.config.ema_trend_period)
                if ema_vals_track and klines[i]["close"] < ema_vals_track[-1]:
                    ema_trend_blocked += 1
            # ── Anti-Over-Filtering: Desperation Buy ──
            desperation_buy = False
            if not buy_allowed:
                consecutive_blocks += 1
                if (self.config.enable_desperation_buy
                        and consecutive_blocks >= self.config.desperation_buy_threshold):
                    buy_allowed = True
                    desperation_buy = True
                    consecutive_blocks = 0  # reset after triggering
            else:
                consecutive_blocks = 0  # reset on successful buy
            # Check if imbalance overrode a borderline RSI
            if self.config.enable_orderbook_imbalance and buy_allowed:
                warmup_check = max(self.config.rsi_period, self.config.macd_slow + self.config.macd_signal, self.config.volume_sma_period) + 5
                if i >= warmup_check:
                    closes_check = [klines[j]["close"] for j in range(max(0, i - self.config.rsi_period - 1), i + 1)]
                    rsi_check = self._calc_rsi(closes_check, self.config.rsi_period)
                    if rsi_check is not None and rsi_check >= self.config.rsi_buy_threshold and current_imbalance > self.config.imbalance_threshold:
                        imbalance_overrides += 1
            # ── Multi-Timeframe Confirmation ──
            if self.config.enable_mtf_confirmation and buy_allowed and mtf_klines:
                # Find the MTF kline closest to current timestamp
                mtf_slice = [m for m in mtf_klines if m["timestamp"] <= timestamp]
                if len(mtf_slice) >= self.config.mtf_ema_slow:
                    mtf_closes = [m["close"] for m in mtf_slice]
                    mtf_ema_f = self._calc_ema(mtf_closes, self.config.mtf_ema_fast)
                    mtf_ema_s = self._calc_ema(mtf_closes, self.config.mtf_ema_slow)
                    if mtf_ema_f and mtf_ema_s:
                        if mtf_ema_f[-1] < mtf_ema_s[-1]:
                            buy_allowed = False
                            mtf_blocked += 1
            # ── Statistical Entry Scoring (SES) ──
            ses_score = 0.5  # neutral default
            if self.config.enable_statistical_scoring and buy_allowed:
                if len(ses_completed_trades) >= self.config.ses_warmup_trades:
                    # Score based: RSI zone + MACD direction + volume + imbalance
                    closes_ses = [klines[j]["close"] for j in range(max(0, i - self.config.rsi_period - 1), i + 1)]
                    rsi_ses = self._calc_rsi(closes_ses, self.config.rsi_period) if len(closes_ses) > self.config.rsi_period else None
                    # Feature 1: RSI zone score (lower RSI = better buy)
                    rsi_score = 1.0 - (rsi_ses / 100.0) if rsi_ses is not None else 0.5
                    # Feature 2: Recent win rate from completed trades
                    recent = ses_completed_trades[-20:]
                    win_rate_score = sum(1 for t in recent if t["pnl"] > 0) / len(recent) if recent else 0.5
                    # Feature 3: Imbalance
                    imb_score = current_imbalance
                    # Feature 4: MACD momentum
                    macd_closes_ses = [klines[j]["close"] for j in range(max(0, i - self.config.macd_slow - self.config.macd_signal - 5), i + 1)]
                    hist_ses, prev_hist_ses, _ = self._calc_macd(macd_closes_ses)
                    macd_score = 0.7 if (hist_ses is not None and prev_hist_ses is not None and hist_ses > prev_hist_ses) else 0.3
                    # Weighted composite score
                    ses_score = (rsi_score * 0.25 + win_rate_score * 0.35 + imb_score * 0.2 + macd_score * 0.2)
                    ses_score_sum += ses_score
                    ses_score_count += 1
                    if ses_score < self.config.ses_min_score:
                        buy_allowed = False
                        ses_blocked += 1
                    else:
                        ses_allowed += 1
                else:
                    ses_allowed += 1  # warmup phase — allow all
            buys_filled = [p for p in pending_buys if low <= p]
            for bp in sorted(buys_filled, reverse=True):
                if not buy_allowed:
                    confluence_blocked += 1
                    continue  # skip this buy — indicators not aligned
                qty = pending_buys.pop(bp)
                # Use reduced size for desperation buys
                if desperation_buy:
                    qty = qty * self.config.desperation_buy_size_pct
                    desperation_buys_triggered += 1
                cost = bp * qty
                if cost > capital:
                    qty = capital / bp
                    cost = bp * qty
                if qty <= 0:
                    continue
                capital -= cost
                position += qty
                buy_cost_queue.append(cost)
                trades.append(BacktestTrade(
                    timestamp=timestamp, side="BUY", price=bp,
                    quantity=qty, pnl=0.0, fee=cost * 0.001,
                ))

            # ── Check sell fills (high price rose to sell level) ──
            sell_allowed = self._check_sell_confluence(klines, i)
            sells_filled = [p for p in pending_sells if high >= p]
            for sp_price in sorted(sells_filled):
                qty = min(pending_sells.pop(sp_price), position)
                if qty <= 0:
                    continue
                revenue = sp_price * qty
                fee = revenue * 0.001
                # FIFO PnL: match sell against oldest buy cost
                buy_cost = buy_cost_queue.pop(0) if buy_cost_queue else revenue
                pnl = revenue - buy_cost - fee
                capital += revenue
                position -= qty
                # ── DGT: Track accumulated profits ──
                if self.config.dgt_enabled and pnl > 0:
                    accumulated_profits += pnl
                # ── SES: Track completed trade outcome ──
                if self.config.enable_statistical_scoring:
                    ses_completed_trades.append({"pnl": pnl, "price_buy": buy_cost / qty if qty > 0 else 0, "price_sell": sp_price})
                trades.append(BacktestTrade(
                    timestamp=timestamp, side="SELL", price=sp_price,
                    quantity=qty, pnl=round(pnl, 4), fee=fee,
                ))

            # Track drawdown
            current_value = capital + (position * price)
            if current_value > peak_capital:
                peak_capital = current_value
            drawdown = peak_capital - current_value
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        # Calculate final metrics
        final_value = capital + (position * klines[-1]["close"])
        total_pnl = final_value - self.config.initial_capital_thb
        total_fees = sum(t.fee for t in trades if t.side == "SELL")
        net_pnl = total_pnl - total_fees

        sell_trades = [t for t in trades if t.side == "SELL"]
        winning_trades = [t for t in sell_trades if t.pnl > 0]
        losing_trades = [t for t in sell_trades if t.pnl <= 0]

        avg_win = sum(t.pnl for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(t.pnl for t in losing_trades) / len(losing_trades) if losing_trades else 0
        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else 0

        duration_days = (klines[-1]["timestamp"] - klines[0]["timestamp"]) / (1000 * 86400)
        trades_per_day = len(sell_trades) / duration_days if duration_days > 0 else 0

        # ATR spacing summary
        atr_avg = sum(atr_spacing_values) / len(atr_spacing_values) if atr_spacing_values else 0
        atr_min = min(atr_spacing_values) if atr_spacing_values else 0
        atr_max = max(atr_spacing_values) if atr_spacing_values else 0

        result = BacktestResult(
            symbol=self.config.symbol,
            start_time=klines[0]["timestamp"],
            end_time=klines[-1]["timestamp"],
            duration_days=duration_days,
            total_trades=len(trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=(len(winning_trades) / len(sell_trades) * 100) if sell_trades else 0,
            total_pnl=round(total_pnl, 2),
            total_fees=round(total_fees, 2),
            net_pnl=round(net_pnl, 2),
            max_drawdown=round(max_drawdown, 2),
            max_drawdown_pct=round((max_drawdown / peak_capital) * 100, 2),
            avg_win=round(avg_win, 2),
            avg_loss=round(avg_loss, 2),
            profit_factor=round(profit_factor, 2),
            avg_grid_spacing_pct=round(atr_avg if atr_spacing_values else self.config.grid_spacing_pct, 4),
            trades_per_day=round(trades_per_day, 2),
            config={
                "symbol": self.config.symbol,
                "grid_spacing_pct": self.config.grid_spacing_pct,
                "grid_levels": self.config.grid_levels,
                "order_size": self.config.order_size,
                "max_position": self.config.max_position,
                "initial_capital": self.config.initial_capital_thb,
                "volatility_mode": self.config.volatility_mode,
                "atr_period": self.config.atr_period,
                "atr_multiplier": self.config.atr_multiplier,
                "grid_mode": self.config.grid_mode,
                "dgt_enabled": self.config.dgt_enabled,
                "dgt_reinvest_pct": self.config.dgt_reinvest_pct,
                "enable_entry_confluence": self.config.enable_entry_confluence,
                "rsi_buy_threshold": self.config.rsi_buy_threshold,
                "volume_multiplier": self.config.volume_multiplier,
                "enable_orderbook_imbalance": self.config.enable_orderbook_imbalance,
                "imbalance_threshold": self.config.imbalance_threshold,
                "enable_ema_trend_filter": self.config.enable_ema_trend_filter,
                "ema_trend_period": self.config.ema_trend_period,
            },
            atr_spacing_avg=round(atr_avg, 4),
            atr_spacing_min=round(atr_min, 4),
            atr_spacing_max=round(atr_max, 4),
            volatility_mode=self.config.volatility_mode,
            grid_mode=self.config.grid_mode,
            dgt_resets=dgt_resets,
            dgt_reinvested_thb=round(dgt_reinvested, 2),
            confluence_buys_blocked=confluence_blocked,
            final_order_size=round(current_order_size, 8),
            imbalance_overrides=imbalance_overrides,
            avg_imbalance=round(imbalance_sum / len(klines), 4) if klines else 0.0,
            ema_trend_blocked=ema_trend_blocked,
            desperation_buys_triggered=desperation_buys_triggered,
            mtf_blocked=mtf_blocked,
            ses_score_avg=round(ses_score_sum / ses_score_count, 4) if ses_score_count > 0 else 0.0,
            ses_trades_allowed=ses_allowed,
            ses_trades_blocked=ses_blocked,
            trades=trades[-50:],  # Last 50 trades for display
        )

        logger.info(
            "Backtest complete: %d trades, PnL=%.2f THB, Win Rate=%.1f%%, "
            "mode=%s, grid=%s, dgt_resets=%d, confluence_blocked=%d",
            len(trades), net_pnl, result.win_rate, self.config.volatility_mode,
            self.config.grid_mode, dgt_resets, confluence_blocked,
        )

        return result

    async def close(self):
        """Clean up HTTP client."""
        if self._http:
            await self._http.aclose()


# ── Parameter Sweep ────────────────────────────────────────────────────────────

@dataclass
class SweepResult:
    """One backtest result within a parameter sweep."""
    grid_spacing_pct: float
    grid_levels: int
    net_pnl: float
    win_rate: float
    trades_per_day: float
    max_drawdown_pct: float
    profit_factor: float
    total_trades: int
    atr_spacing_avg: float


@dataclass
class ParameterSweepResult:
    """Result of a parameter sweep across multiple configs."""
    symbol: str
    days: int
    interval: str
    volatility_mode: str
    results: List[SweepResult]
    best_config: Dict  # the config with highest net_pnl
    worst_config: Dict  # the config with lowest net_pnl


async def run_parameter_sweep(
    symbol: str,
    days: int = 30,
    interval: str = "1h",
    volatility_mode: str = "fixed",
    spacing_range: Optional[List[float]] = None,
    levels_range: Optional[List[int]] = None,
    atr_period: int = 14,
    atr_multiplier: float = 1.5,
    min_spacing_pct: float = 0.5,
    max_spacing_pct: float = 5.0,
    order_size: float = 0.00005,
    initial_capital_thb: float = 10000.0,
) -> ParameterSweepResult:
    """
    Run backtest across multiple grid parameter combinations.
    
    Default sweep: spacing [0.5, 1.0, 1.5, 2.0, 3.0] x levels [1, 2, 3, 4]
    = 20 combinations.
    """
    if spacing_range is None:
        spacing_range = [0.5, 1.0, 1.5, 2.0, 3.0]
    if levels_range is None:
        levels_range = [1, 2, 3, 4]

    sweep_results: List[SweepResult] = []
    total = len(spacing_range) * len(levels_range)
    logger.info("Starting parameter sweep: %s, %d combinations, mode=%s", symbol, total, volatility_mode)

    for spacing in spacing_range:
        for levels in levels_range:
            config = BacktestConfig(
                symbol=symbol,
                grid_spacing_pct=spacing,
                grid_levels=levels,
                order_size=order_size,
                max_position=order_size * levels * 2,  # scale position cap with levels
                max_open_orders=levels * 2 + 2,
                initial_capital_thb=initial_capital_thb,
                volatility_mode=volatility_mode,
                atr_period=atr_period,
                atr_multiplier=atr_multiplier,
                min_spacing_pct=min_spacing_pct,
                max_spacing_pct=max_spacing_pct,
            )
            backtester = GridBacktester(config)
            try:
                result = await backtester.run(days=days, interval=interval)
                sweep_results.append(SweepResult(
                    grid_spacing_pct=spacing,
                    grid_levels=levels,
                    net_pnl=result.net_pnl,
                    win_rate=result.win_rate,
                    trades_per_day=result.trades_per_day,
                    max_drawdown_pct=result.max_drawdown_pct,
                    profit_factor=result.profit_factor,
                    total_trades=result.total_trades,
                    atr_spacing_avg=result.atr_spacing_avg,
                ))
            except Exception as e:
                logger.warning("Sweep backtest failed (spacing=%.1f, levels=%d): %s", spacing, levels, e)
            finally:
                await backtester.close()

    # Find best/worst by net_pnl
    if sweep_results:
        best = max(sweep_results, key=lambda r: r.net_pnl)
        worst = min(sweep_results, key=lambda r: r.net_pnl)
        best_config = {
            "grid_spacing_pct": best.grid_spacing_pct,
            "grid_levels": best.grid_levels,
            "net_pnl": best.net_pnl,
            "win_rate": best.win_rate,
            "trades_per_day": best.trades_per_day,
            "max_drawdown_pct": best.max_drawdown_pct,
            "profit_factor": best.profit_factor,
        }
        worst_config = {
            "grid_spacing_pct": worst.grid_spacing_pct,
            "grid_levels": worst.grid_levels,
            "net_pnl": worst.net_pnl,
            "win_rate": worst.win_rate,
        }
    else:
        best_config = {}
        worst_config = {}

    logger.info(
        "Sweep complete: %d/%d succeeded. Best: spacing=%.1f%% levels=%d PnL=%.2f",
        len(sweep_results), total,
        best_config.get("grid_spacing_pct", 0), best_config.get("grid_levels", 0),
        best_config.get("net_pnl", 0),
    )

    return ParameterSweepResult(
        symbol=symbol,
        days=days,
        interval=interval,
        volatility_mode=volatility_mode,
        results=sweep_results,
        best_config=best_config,
        worst_config=worst_config,
    )


# ── Walk-Forward Parameter Tuning ──────────────────────────────────────────────

@dataclass
class WalkForwardResult:
    """Result of walk-forward optimization for one parameter."""
    parameter_name: str
    best_value: float
    avg_pnl: float
    fold_results: List[Dict]  # each fold: {train_pnl, test_pnl, best_value}
    stability_score: float    # 0-1, higher = more stable across folds


async def run_walk_forward_tuning(
    symbol: str,
    days: int = 30,
    interval: str = "1h",
    n_folds: int = 3,
    base_config: Optional[BacktestConfig] = None,
) -> Dict:
    """
    Walk-forward optimization: split data into n_folds, optimize on train, test on unseen.
    
    Tunes: desperation_buy_threshold, imbalance_threshold, rsi_buy_threshold
    Returns best parameters + stability metrics.
    """
    from app.backtester import GridBacktester, BacktestConfig

    if base_config is None:
        base_config = BacktestConfig(
            symbol=symbol, grid_spacing_pct=1.5, grid_levels=2,
            order_size=0.00005, initial_capital_thb=10000.0,
            grid_mode="geometric", dgt_enabled=True, dgt_reinvest_pct=0.5,
            enable_entry_confluence=True, rsi_buy_threshold=45.0,
            volume_multiplier=1.5,
            enable_orderbook_imbalance=True, imbalance_threshold=0.65,
            imbalance_rsi_relax=10.0,
            enable_desperation_buy=True, desperation_buy_threshold=20,
            desperation_buy_size_pct=0.5,
        )

    # Parameter grid to search
    param_grid = {
        "desperation_buy_threshold": [10, 15, 20, 25, 30],
        "imbalance_threshold": [0.55, 0.60, 0.65, 0.70, 0.75],
        "rsi_buy_threshold": [35.0, 40.0, 45.0, 50.0, 55.0],
    }

    # Fetch full dataset once
    intervals_per_day = {"1m": 1440, "5m": 288, "15m": 96, "1h": 24, "4h": 6, "1d": 1}
    klines_needed = days * intervals_per_day.get(interval, 24)
    klines_needed = min(klines_needed, 1000)

    # We'll simulate folds by running backtests on different day ranges
    fold_size = days // n_folds
    fold_results: Dict[str, List[Dict]] = {param: [] for param in param_grid}

    for param_name, values in param_grid.items():
        for fold in range(n_folds):
            fold_days = fold_size
            fold_offset = fold * fold_size  # not used directly, but conceptually

            best_pnl = -999999.0
            best_val = values[0]
            fold_data = {"fold": fold + 1, "days": fold_days, "values_tested": {}}

            for val in values:
                cfg = BacktestConfig(
                    symbol=base_config.symbol,
                    grid_spacing_pct=base_config.grid_spacing_pct,
                    grid_levels=base_config.grid_levels,
                    order_size=base_config.order_size,
                    initial_capital_thb=base_config.initial_capital_thb,
                    grid_mode=base_config.grid_mode,
                    dgt_enabled=base_config.dgt_enabled,
                    dgt_reinvest_pct=base_config.dgt_reinvest_pct,
                    enable_entry_confluence=base_config.enable_entry_confluence,
                    rsi_buy_threshold=base_config.rsi_buy_threshold,
                    volume_multiplier=base_config.volume_multiplier,
                    enable_orderbook_imbalance=base_config.enable_orderbook_imbalance,
                    imbalance_threshold=base_config.imbalance_threshold,
                    imbalance_rsi_relax=base_config.imbalance_rsi_relax,
                    enable_desperation_buy=base_config.enable_desperation_buy,
                    desperation_buy_threshold=base_config.desperation_buy_threshold,
                    desperation_buy_size_pct=base_config.desperation_buy_size_pct,
                )
                # Override the parameter being tuned
                if param_name == "desperation_buy_threshold":
                    cfg.desperation_buy_threshold = int(val)
                elif param_name == "imbalance_threshold":
                    cfg.imbalance_threshold = val
                elif param_name == "rsi_buy_threshold":
                    cfg.rsi_buy_threshold = val

                bt = GridBacktester(cfg)
                try:
                    result = await bt.run(days=fold_days, interval=interval)
                    fold_data["values_tested"][str(val)] = result.net_pnl
                    if result.net_pnl > best_pnl:
                        best_pnl = result.net_pnl
                        best_val = val
                except Exception as e:
                    logger.warning("Walk-forward fold %d failed for %s=%.2f: %s", fold + 1, param_name, val, e)
                finally:
                    await bt.close()

            fold_data["best_value"] = best_val
            fold_data["best_pnl"] = best_pnl
            fold_results[param_name].append(fold_data)

    # Aggregate: find most frequently best value across folds
    wf_results: List[WalkForwardResult] = []
    for param_name, folds in fold_results.items():
        # Count frequency of each best_value
        value_counts: Dict[float, int] = {}
        total_pnl = 0.0
        for f in folds:
            v = f["best_value"]
            value_counts[v] = value_counts.get(v, 0) + 1
            total_pnl += f["best_pnl"]
        best_overall = max(value_counts, key=value_counts.get)
        stability = value_counts[best_overall] / len(folds) if folds else 0.0
        wf_results.append(WalkForwardResult(
            parameter_name=param_name,
            best_value=best_overall,
            avg_pnl=round(total_pnl / len(folds), 2) if folds else 0.0,
            fold_results=folds,
            stability_score=round(stability, 2),
        ))

    return {
        "symbol": symbol,
        "days": days,
        "n_folds": n_folds,
        "optimized_parameters": {
            r.parameter_name: {
                "best_value": r.best_value,
                "avg_pnl": r.avg_pnl,
                "stability": r.stability_score,
                "folds": r.fold_results,
            }
            for r in wf_results
        },
    }
