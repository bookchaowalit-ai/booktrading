"""
Trend Following Bot
====================
Uses EMA crossover + ADX to ride trends in any direction.
- BUY when fast EMA crosses above slow EMA (uptrend)
- SELL when fast EMA crosses below slow EMA (downtrend)
- Only trades when ADX > 25 (strong trend exists)
- Works in both bull AND bear markets

Uses Binance TH spot trading via Go backend /api/trade endpoints.
Spot-only: can't short, but can sell holdings to avoid bear market losses
and re-buy at lower prices (swing trading).
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger("trend_bot")

BINANCE_PUBLIC_REST = os.getenv("BINANCE_PRICE_API", "https://api.binance.th")
BACKEND_API_BASE = os.getenv("BACKEND_API_BASE", "http://backend:8080")
BINANCE_TH_MAINNET = os.getenv("BINANCE_TH_USE_TESTNET", "false").lower() != "true"


@dataclass
class TrendConfig:
    symbol: str
    ema_fast: int = 9                 # fast EMA period
    ema_slow: int = 21                # slow EMA period
    adx_period: int = 14              # ADX period for trend strength
    adx_min: float = 20.0             # minimum ADX for trend confirmation
    order_amount_thb: float = 100.0   # THB per trade
    min_notional_thb: float = 100.0   # Binance TH minimum order value
    poll_interval_sec: int = 60       # check every minute
    kline_interval: str = "1h"        # candlestick interval
    kline_limit: int = 100            # number of candles to fetch
    stop_loss_pct: float = 5.0        # stop loss at -5%
    take_profit_pct: float = 8.0      # take profit at +8%
    max_position_thb: float = 500.0   # max position value in THB
    step_size: float = 0.00001        # Binance TH stepSize for quantity rounding
    tick_size: float = 1.0            # Binance TH tickSize for price rounding


# Binance TH step sizes per symbol
TREND_SYMBOL_SPECS = {
    "BTCTHB": {"step_size": 0.00001, "tick_size": 0.01},
    "ETHTHB": {"step_size": 0.0001, "tick_size": 1.0},
    "BNBTHB": {"step_size": 0.01, "tick_size": 0.01},
    "SOLTHB": {"step_size": 0.01, "tick_size": 0.01},
    "XRPTHB": {"step_size": 0.01, "tick_size": 0.01},
}


@dataclass
class TrendState:
    symbol: str
    position_base: float = 0.0         # current base asset held
    position_cost_thb: float = 0.0     # cost basis in THB
    entry_price: float = 0.0           # average entry price
    total_trades: int = 0
    win_trades: int = 0
    loss_trades: int = 0
    realized_pnl_thb: float = 0.0
    last_signal: str = "NEUTRAL"       # LONG, SHORT (sell), NEUTRAL
    last_signal_time: float = 0.0
    current_trend: str = "NONE"        # UP, DOWN, NONE
    adx_value: float = 0.0
    halted: bool = False


def _ema(values: List[float], period: int) -> List[float]:
    """Calculate EMA series."""
    if len(values) < period:
        return []
    multiplier = 2.0 / (period + 1)
    ema_vals = [sum(values[:period]) / period]  # SMA as first EMA value
    for v in values[period:]:
        ema_vals.append((v - ema_vals[-1]) * multiplier + ema_vals[-1])
    return ema_vals


def _adx(highs: List[float], lows: List[float], closes: List[float], period: int) -> float:
    """Calculate current ADX value."""
    if len(closes) < period + 1:
        return 0.0

    plus_dm = []
    minus_dm = []
    tr_list = []

    for i in range(1, len(closes)):
        high_diff = highs[i] - highs[i-1]
        low_diff = lows[i-1] - lows[i]
        plus_dm.append(max(high_diff, 0) if high_diff > low_diff else 0)
        minus_dm.append(max(low_diff, 0) if low_diff > high_diff else 0)
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
        tr_list.append(tr)

    if len(tr_list) < period:
        return 0.0

    # Smoothed averages
    atr = sum(tr_list[:period]) / period
    plus_di_smooth = sum(plus_dm[:period]) / period
    minus_di_smooth = sum(minus_dm[:period]) / period

    plus_di_list = []
    minus_di_list = []
    dx_list = []

    for i in range(period, len(tr_list)):
        atr = (atr * (period - 1) + tr_list[i]) / period
        plus_di_smooth = (plus_di_smooth * (period - 1) + plus_dm[i]) / period
        minus_di_smooth = (minus_di_smooth * (period - 1) + minus_dm[i]) / period

        plus_di = (plus_di_smooth / atr * 100) if atr > 0 else 0
        minus_di = (minus_di_smooth / atr * 100) if atr > 0 else 0
        plus_di_list.append(plus_di)
        minus_di_list.append(minus_di)

        di_sum = plus_di + minus_di
        dx = (abs(plus_di - minus_di) / di_sum * 100) if di_sum > 0 else 0
        dx_list.append(dx)

    if len(dx_list) < period:
        return dx_list[-1] if dx_list else 0.0

    adx = sum(dx_list[-period:]) / period
    return adx


class TrendFollowingBot:
    """Trend Following Bot — rides trends up and down."""

    def __init__(self):
        self.configs: List[TrendConfig] = []
        self.states: Dict[str, TrendState] = {}
        self._http: Optional[httpx.AsyncClient] = None
        self._redis = None
        self._running = False

    def set_redis(self, redis_client):
        self._redis = redis_client

    def add_config(self, cfg: TrendConfig):
        self.configs.append(cfg)
        self.states[cfg.symbol] = TrendState(symbol=cfg.symbol)

    async def start(self):
        self._running = True
        self._http = httpx.AsyncClient(timeout=30)
        await self._load_states()

        logger.info("Trend Following Bot started with %d symbols: %s",
                     len(self.configs), [c.symbol for c in self.configs])

        tasks = [self._run_symbol(cfg) for cfg in self.configs]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def stop(self):
        self._running = False
        if self._http:
            await self._http.aclose()

    async def _run_symbol(self, cfg: TrendConfig):
        """Main loop for one symbol."""
        state = self.states[cfg.symbol]

        while self._running:
            try:
                # Fetch klines
                klines = await self._get_klines(cfg.symbol, cfg.kline_interval, cfg.kline_limit)
                if not klines or len(klines) < cfg.ema_slow + 5:
                    logger.debug("[Trend %s] Not enough klines (%d)", cfg.symbol, len(klines) if klines else 0)
                    await asyncio.sleep(cfg.poll_interval_sec)
                    continue

                closes = [k["close"] for k in klines]
                highs = [k["high"] for k in klines]
                lows = [k["low"] for k in klines]
                current_price = closes[-1]

                # Calculate indicators
                ema_fast_vals = _ema(closes, cfg.ema_fast)
                ema_slow_vals = _ema(closes, cfg.ema_slow)
                adx_val = _adx(highs, lows, closes, cfg.adx_period)

                if not ema_fast_vals or not ema_slow_vals:
                    await asyncio.sleep(cfg.poll_interval_sec)
                    continue

                # Align lengths (ema_fast is longer than ema_slow)
                offset = len(ema_fast_vals) - len(ema_slow_vals)
                ema_fast_curr = ema_fast_vals[-1]
                ema_fast_prev = ema_fast_vals[-2] if len(ema_fast_vals) >= 2 else ema_fast_curr
                ema_slow_curr = ema_slow_vals[-1]
                ema_slow_prev = ema_slow_vals[-2] if len(ema_slow_vals) >= 2 else ema_slow_curr

                state.adx_value = adx_val
                has_trend = adx_val >= cfg.adx_min

                # Determine trend direction
                if ema_fast_curr > ema_slow_curr and ema_fast_prev <= ema_slow_prev:
                    state.current_trend = "UP"
                elif ema_fast_curr < ema_slow_curr and ema_fast_prev >= ema_slow_prev:
                    state.current_trend = "DOWN"
                elif ema_fast_curr > ema_slow_curr:
                    state.current_trend = "UP"
                elif ema_fast_curr < ema_slow_curr:
                    state.current_trend = "DOWN"
                else:
                    state.current_trend = "NONE"

                # Check stop loss / take profit
                if state.position_base > 0 and state.entry_price > 0:
                    pnl_pct = ((current_price - state.entry_price) / state.entry_price) * 100

                    if pnl_pct <= -cfg.stop_loss_pct:
                        # Stop loss triggered
                        await self._execute_sell(cfg, state, current_price, state.position_base, "STOP_LOSS")
                    elif pnl_pct >= cfg.take_profit_pct:
                        # Take profit
                        await self._execute_sell(cfg, state, current_price, state.position_base, "TAKE_PROFIT")
                    elif has_trend and state.current_trend == "DOWN":
                        # Trend reversed to DOWN — sell to avoid losses
                        await self._execute_sell(cfg, state, current_price, state.position_base, "TREND_REVERSAL")
                    # Trading signals (only when trend is strong enough)
                    elif has_trend and state.current_trend == "UP" and state.position_base == 0:
                        # Uptrend confirmed — BUY
                        await self._execute_buy(cfg, state, current_price, cfg.order_amount_thb, "TREND_UP")
                    elif not has_trend and state.position_base == 0:
                        # No trend — skip
                        pass

                elif state.position_base == 0 and has_trend and state.current_trend == "UP":
                    # No position, uptrend starting — enter
                    await self._execute_buy(cfg, state, current_price, cfg.order_amount_thb, "TREND_UP")

                # Save state
                await self._save_state(cfg.symbol)
                logger.info(
                    "[Trend %s] price=%.2f ema_fast=%.2f ema_slow=%.2f adx=%.1f trend=%s "
                    "position=%.6f pnl=%.2f trades=%d",
                    cfg.symbol, current_price, ema_fast_curr, ema_slow_curr, adx_val,
                    state.current_trend, state.position_base,
                    state.realized_pnl_thb, state.total_trades
                )

            except Exception as e:
                logger.error("[Trend %s] Error: %s", cfg.symbol, e, exc_info=True)

            await asyncio.sleep(cfg.poll_interval_sec)

    async def _execute_buy(self, cfg: TrendConfig, state: TrendState, price: float,
                           amount_thb: float, reason: str):
        """Execute a BUY order."""
        # Round quantity to step_size (Binance TH requirement)
        qty = amount_thb / price
        qty = round(qty / cfg.step_size) * cfg.step_size
        qty = float(f"{qty:.10g}")
        if qty <= 0 or amount_thb < cfg.min_notional_thb:
            return

        # Round price to tick_size
        rounded_price = round(price / cfg.tick_size) * cfg.tick_size
        rounded_price = float(f"{rounded_price:.10g}")

        # Ensure notional >= min_notional after rounding (Binance TH rejects with 503)
        notional = qty * rounded_price
        if notional < cfg.min_notional_thb:
            qty += cfg.step_size
            qty = float(f"{qty:.10g}")
            notional = qty * rounded_price

        # Check max position
        current_value = state.position_base * rounded_price
        actual_cost = qty * rounded_price
        if current_value + actual_cost > cfg.max_position_thb:
            logger.debug("[Trend %s] Would exceed max position %.2f THB", cfg.symbol, cfg.max_position_thb)
            return

        # Check balance
        balances = await self._fetch_balances()
        thb_free = balances.get("THB", 0)
        if thb_free < actual_cost:
            logger.warning("[Trend %s] Insufficient THB: need %.2f, have %.2f", cfg.symbol, actual_cost, thb_free)
            return

        if not BINANCE_TH_MAINNET:
            state.position_base += qty
            state.position_cost_thb += actual_cost
            state.entry_price = state.position_cost_thb / state.position_base if state.position_base > 0 else 0
            state.total_trades += 1
            state.last_signal = "BUY"
            state.last_signal_time = time.time()
            logger.info("[Trend %s] PAPER BUY qty=%.6f price=%.2f (%s)", cfg.symbol, qty, rounded_price, reason)
            return

        try:
            resp = await self._http.post(
                f"{BACKEND_API_BASE}/api/trade/order",
                json={"symbol": cfg.symbol, "side": "BUY", "quantity": qty, "price": rounded_price},
            )
            if resp.status_code == 201:
                data = resp.json()
                order = data.get("order", {})
                filled_qty = float(order.get("executedQty") or qty)
                filled_cost = float(order.get("cummulativeQuoteQty") or amount_thb)
                state.position_base += filled_qty
                state.position_cost_thb += filled_cost
                state.entry_price = state.position_cost_thb / state.position_base if state.position_base > 0 else 0
                state.total_trades += 1
                state.last_signal = "BUY"
                state.last_signal_time = time.time()
                logger.info("[Trend %s] REAL BUY qty=%.6f price=%.2f cost=%.2f (%s) orderId=%s",
                            cfg.symbol, filled_qty, price, filled_cost, reason, order.get("orderId", "?"))
            else:
                logger.warning("[Trend %s] BUY failed: %s %s", cfg.symbol, resp.status_code, resp.text)
        except Exception as e:
            logger.error("[Trend %s] BUY failed: %s", cfg.symbol, e)

    async def _execute_sell(self, cfg: TrendConfig, state: TrendState, price: float,
                            qty: float, reason: str):
        """Execute a SELL order."""
        if qty <= 0:
            return

        # Round quantity to step_size (Binance TH requirement)
        qty = round(qty / cfg.step_size) * cfg.step_size
        qty = float(f"{qty:.10g}")
        if qty <= 0:
            return

        # Round price to tick_size
        rounded_price = round(price / cfg.tick_size) * cfg.tick_size
        rounded_price = float(f"{rounded_price:.10g}")

        notional = qty * rounded_price
        if notional < cfg.min_notional_thb:
            return

        base_asset = cfg.symbol.replace("THB", "")
        balances = await self._fetch_balances()
        asset_free = balances.get(base_asset, 0)
        if asset_free < qty:
            qty = asset_free * 0.95
            # Re-round after adjustment
            qty = round(qty / cfg.step_size) * cfg.step_size
            qty = float(f"{qty:.10g}")
            if qty * rounded_price < cfg.min_notional_thb:
                return

        if not BINANCE_TH_MAINNET:
            proceeds = qty * rounded_price
            profit = (rounded_price - state.entry_price) * qty
            state.position_base -= qty
            state.position_cost_thb -= qty * state.entry_price
            state.realized_pnl_thb += profit
            state.total_trades += 1
            if profit >= 0:
                state.win_trades += 1
            else:
                state.loss_trades += 1
            state.last_signal = "SELL"
            state.last_signal_time = time.time()
            if state.position_base <= 0:
                state.position_base = 0
                state.position_cost_thb = 0
                state.entry_price = 0
            logger.info("[Trend %s] PAPER SELL qty=%.6f price=%.2f pnl=%.2f (%s)",
                        cfg.symbol, qty, rounded_price, profit, reason)
            return

        try:
            resp = await self._http.post(
                f"{BACKEND_API_BASE}/api/trade/order",
                json={"symbol": cfg.symbol, "side": "SELL", "quantity": qty, "price": rounded_price},
            )
            if resp.status_code == 201:
                data = resp.json()
                order = data.get("order", {})
                filled_qty = float(order.get("executedQty") or qty)
                filled_cost = float(order.get("cummulativeQuoteQty") or qty * price)
                profit = (price - state.entry_price) * filled_qty
                state.position_base -= filled_qty
                state.position_cost_thb -= filled_qty * state.entry_price
                state.realized_pnl_thb += profit
                state.total_trades += 1
                if profit >= 0:
                    state.win_trades += 1
                else:
                    state.loss_trades += 1
                state.last_signal = "SELL"
                state.last_signal_time = time.time()
                if state.position_base <= 0:
                    state.position_base = 0
                    state.position_cost_thb = 0
                    state.entry_price = 0
                logger.info("[Trend %s] REAL SELL qty=%.6f price=%.2f pnl=%.2f (%s) orderId=%s",
                            cfg.symbol, filled_qty, price, profit, reason, order.get("orderId", "?"))
            else:
                logger.warning("[Trend %s] SELL failed: %s %s", cfg.symbol, resp.status_code, resp.text)
        except Exception as e:
            logger.error("[Trend %s] SELL failed: %s", cfg.symbol, e)

    async def _get_klines(self, symbol: str, interval: str, limit: int) -> List[Dict]:
        """Fetch klines from Binance TH."""
        try:
            resp = await self._http.get(
                f"{BINANCE_PUBLIC_REST}/api/v1/klines",
                params={"symbol": symbol, "interval": interval, "limit": limit},
            )
            if resp.status_code == 200:
                raw = resp.json()
                return [
                    {
                        "open": float(k[1]),
                        "high": float(k[2]),
                        "low": float(k[3]),
                        "close": float(k[4]),
                        "volume": float(k[5]),
                    }
                    for k in raw
                ]
        except Exception as e:
            logger.warning("Failed to get klines for %s: %s", symbol, e)
        return []

    async def _fetch_balances(self) -> Dict[str, float]:
        try:
            resp = await self._http.get(f"{BACKEND_API_BASE}/api/trade/balances")
            if resp.status_code == 200:
                data = resp.json()
                return {b["currency"]: float(b["free"]) for b in data.get("balances", [])}
        except Exception as e:
            logger.warning("Failed to fetch balances: %s", e)
        return {}

    async def _save_state(self, symbol: str):
        if not self._redis:
            return
        state = self.states[symbol]
        data = {
            "position_base": state.position_base,
            "position_cost_thb": state.position_cost_thb,
            "entry_price": state.entry_price,
            "total_trades": state.total_trades,
            "win_trades": state.win_trades,
            "loss_trades": state.loss_trades,
            "realized_pnl_thb": state.realized_pnl_thb,
            "last_signal": state.last_signal,
            "last_signal_time": state.last_signal_time,
            "current_trend": state.current_trend,
            "adx_value": state.adx_value,
            "halted": state.halted,
        }
        try:
            await self._redis.hset(f"trend_bot:{symbol}:state", mapping={
                k: str(v) for k, v in data.items()
            })
        except Exception as e:
            logger.warning("Failed to save trend state for %s: %s", symbol, e)

    async def _load_states(self):
        if not self._redis:
            return
        for cfg in self.configs:
            try:
                data = await self._redis.hgetall(f"trend_bot:{cfg.symbol}:state")
                if data:
                    state = self.states[cfg.symbol]
                    state.position_base = float(data.get("position_base", 0))
                    state.position_cost_thb = float(data.get("position_cost_thb", 0))
                    state.entry_price = float(data.get("entry_price", 0))
                    state.total_trades = int(data.get("total_trades", 0))
                    state.win_trades = int(data.get("win_trades", 0))
                    state.loss_trades = int(data.get("loss_trades", 0))
                    state.realized_pnl_thb = float(data.get("realized_pnl_thb", 0))
                    state.last_signal = data.get("last_signal", "NEUTRAL")
                    state.last_signal_time = float(data.get("last_signal_time", 0))
                    state.current_trend = data.get("current_trend", "NONE")
                    state.adx_value = float(data.get("adx_value", 0))
                    state.halted = data.get("halted", "false").lower() == "true"
                    logger.info("[Trend %s] Loaded state: trades=%d position=%.6f pnl=%.2f",
                                cfg.symbol, state.total_trades, state.position_base, state.realized_pnl_thb)
            except Exception as e:
                logger.warning("Failed to load trend state for %s: %s", cfg.symbol, e)

    def get_status(self) -> Dict:
        result = {}
        for cfg in self.configs:
            state = self.states[cfg.symbol]
            result[cfg.symbol] = {
                "symbol": cfg.symbol,
                "total_trades": state.total_trades,
                "win_trades": state.win_trades,
                "loss_trades": state.loss_trades,
                "win_rate_pct": (state.win_trades / state.total_trades * 100) if state.total_trades > 0 else 0,
                "position_base": state.position_base,
                "entry_price": state.entry_price,
                "realized_pnl_thb": state.realized_pnl_thb,
                "current_trend": state.current_trend,
                "adx_value": state.adx_value,
                "last_signal": state.last_signal,
                "halted": state.halted,
            }
        return result


_trend_bot: Optional[TrendFollowingBot] = None


def get_trend_bot() -> TrendFollowingBot:
    global _trend_bot
    if _trend_bot is None:
        _trend_bot = TrendFollowingBot()
        symbols = os.getenv("TREND_SYMBOLS", "BTCTHB,ETHTHB,BNBTHB").split(",")
        amount = float(os.getenv("TREND_ORDER_AMOUNT_THB", "100"))
        for sym in symbols:
            sym = sym.strip()
            if sym:
                specs = TREND_SYMBOL_SPECS.get(sym, {"step_size": 0.00001, "tick_size": 1.0})
                _trend_bot.add_config(TrendConfig(
                    symbol=sym,
                    order_amount_thb=amount,
                    step_size=specs["step_size"],
                    tick_size=specs["tick_size"],
                ))
    return _trend_bot
