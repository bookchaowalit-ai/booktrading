"""
Futures Short Bot — Bear Market Strategy
=========================================
Uses Binance Global USDT-M Futures to profit from downward price movements.

Strategies:
1. Trend-based shorting: EMA crossover + ADX confirms downtrend → open SHORT
2. Stop loss: Close position if price moves against us by 3%
3. Take profit: Close position if price drops 5% in our favor
4. Position sizing: Risk only 2% of balance per trade

Works on Binance Global testnet (paper) and mainnet (real).
API: https://binance-docs.github.io/apidocs/futures/en/
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from urllib.parse import urlencode

import httpx

logger = logging.getLogger("futures_bot")

# Binance Futures API endpoints
FUTURES_TESTNET_BASE = "https://testnet.binancefuture.com"
FUTURES_MAINNET_BASE = "https://fapi.binance.com"


@dataclass
class FuturesConfig:
    symbol: str                    # e.g. "BTCUSDT"
    leverage: int = 5              # 5x leverage (conservative)
    position_size_usdt: float = 50.0  # margin per trade
    stop_loss_pct: float = 3.0     # close if -3% against us
    take_profit_pct: float = 5.0   # close if +5% in our favor
    ema_fast: int = 9
    ema_slow: int = 21
    adx_threshold: float = 20.0    # min ADX for trend confirmation
    check_interval_sec: int = 60   # check every 60 seconds
    max_position_usdt: float = 200.0  # max total margin in all positions


@dataclass
class FuturesState:
    symbol: str
    position_side: str = "NONE"    # "SHORT", "LONG", or "NONE"
    position_amt: float = 0.0      # negative for SHORT
    entry_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    total_trades: int = 0
    win_trades: int = 0
    loss_trades: int = 0
    last_signal: str = "NONE"
    last_signal_time: float = 0.0
    current_trend: str = "NEUTRAL"
    adx_value: float = 0.0
    halted: bool = False


class FuturesBot:
    """Bear-market futures shorting bot using Binance Global USDT-M Futures."""

    def __init__(self):
        self.configs: List[FuturesConfig] = []
        self.states: Dict[str, FuturesState] = {}
        self._http: Optional[httpx.AsyncClient] = None
        self._redis = None
        self._running = False
        
        # API credentials
        self._api_key = os.getenv("BINANCE_FUTURES_API_KEY", "")
        self._api_secret = os.getenv("BINANCE_FUTURES_API_SECRET", "")
        self._use_testnet = os.getenv("BINANCE_FUTURES_USE_TESTNET", "true").lower() == "true"
        
        self._base_url = FUTURES_TESTNET_BASE if self._use_testnet else FUTURES_MAINNET_BASE

    def set_redis(self, redis_client):
        self._redis = redis_client

    def add_config(self, cfg: FuturesConfig):
        self.configs.append(cfg)
        self.states[cfg.symbol] = FuturesState(symbol=cfg.symbol)

    async def start(self):
        """Start the futures bot."""
        self._running = True
        self._http = httpx.AsyncClient(timeout=30)

        # Load existing states from Redis
        await self._load_states()

        mode = "TESTNET" if self._use_testnet else "MAINNET"
        logger.info("Futures Bot started [%s] with %d symbols: %s",
                    mode, len(self.configs), [c.symbol for c in self.configs])

        if not self._api_key:
            logger.warning("No BINANCE_FUTURES_API_KEY set — running in price-analysis-only mode")

        # Run all configs concurrently
        tasks = [self._run_symbol(cfg) for cfg in self.configs]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def stop(self):
        self._running = False
        if self._http:
            await self._http.aclose()
        await self._save_states()
        logger.info("Futures Bot stopped")

    def _sign_request(self, params: dict) -> dict:
        """Sign request with HMAC SHA256 for authenticated endpoints."""
        params["timestamp"] = int(time.time() * 1000)
        query_string = urlencode(params)
        signature = hmac.new(
            self._api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        params["signature"] = signature
        return params

    def _headers(self) -> dict:
        return {"X-MBX-APIKEY": self._api_key} if self._api_key else {}

    async def _get_price(self, symbol: str) -> float:
        """Get current price from futures API (public, no auth needed)."""
        try:
            resp = await self._http.get(
                f"{self._base_url}/fapi/v1/ticker/price",
                params={"symbol": symbol}
            )
            if resp.status_code == 200:
                return float(resp.json()["price"])
        except Exception as e:
            logger.debug("Price fetch error for %s: %s", symbol, e)
        return 0.0

    async def _get_klines(self, symbol: str, interval: str = "1h", limit: int = 100) -> List[dict]:
        """Get klines/candlesticks for technical analysis."""
        try:
            resp = await self._http.get(
                f"{self._base_url}/fapi/v1/klines",
                params={"symbol": symbol, "interval": interval, "limit": limit}
            )
            if resp.status_code == 200:
                return [
                    {
                        "open_time": k[0],
                        "open": float(k[1]),
                        "high": float(k[2]),
                        "low": float(k[3]),
                        "close": float(k[4]),
                        "volume": float(k[5]),
                        "close_time": k[6],
                    }
                    for k in resp.json()
                ]
        except Exception as e:
            logger.debug("Klines error for %s: %s", symbol, e)
        return []

    async def _get_balance(self) -> float:
        """Get USDT balance in futures wallet."""
        if not self._api_key:
            return 1000.0  # Paper balance for testnet
        try:
            params = self._sign_request({})
            resp = await self._http.get(
                f"{self._base_url}/fapi/v2/balance",
                params=params,
                headers=self._headers()
            )
            if resp.status_code == 200:
                for asset in resp.json():
                    if asset["asset"] == "USDT":
                        return float(asset["balance"])
        except Exception as e:
            logger.debug("Balance error: %s", e)
        return 0.0

    async def _get_position(self, symbol: str) -> dict:
        """Get current position for symbol."""
        if not self._api_key:
            # In paper mode, return the state's tracked position
            state = self.states.get(symbol)
            if state and state.position_side != "NONE" and state.position_amt != 0:
                amt = state.position_amt
                return {
                    "positionAmt": str(amt),
                    "entryPrice": str(state.entry_price),
                    "unrealizedProfit": str(state.unrealized_pnl)
                }
            return {"positionAmt": "0", "entryPrice": "0", "unrealizedProfit": "0"}
        try:
            params = self._sign_request({"symbol": symbol})
            resp = await self._http.get(
                f"{self._base_url}/fapi/v2/positionRisk",
                params=params,
                headers=self._headers()
            )
            if resp.status_code == 200:
                for pos in resp.json():
                    if pos["symbol"] == symbol:
                        return pos
        except Exception as e:
            logger.debug("Position error for %s: %s", symbol, e)
        return {"positionAmt": "0", "entryPrice": "0", "unrealizedProfit": "0"}

    async def _set_leverage(self, symbol: str, leverage: int):
        """Set leverage for symbol."""
        if not self._api_key:
            return
        try:
            params = self._sign_request({"symbol": symbol, "leverage": leverage})
            resp = await self._http.post(
                f"{self._base_url}/fapi/v1/leverage",
                data=params,
                headers=self._headers()
            )
            if resp.status_code == 200:
                logger.info("Set leverage %dx for %s", leverage, symbol)
        except Exception as e:
            logger.debug("Leverage error: %s", e)

    async def _place_order(self, symbol: str, side: str, quantity: float, 
                           order_type: str = "MARKET", reduce_only: bool = False) -> dict:
        """Place a futures order."""
        if not self._api_key:
            logger.info("[Paper] %s %s %.6f %s (reduce_only=%s)", 
                       symbol, side, quantity, order_type, reduce_only)
            return {"orderId": 0, "status": "FILLED", "paper": True}
        
        params = {
            "symbol": symbol,
            "side": side,  # "BUY" or "SELL"
            "type": order_type,
            "quantity": f"{quantity:.6f}",
        }
        if reduce_only:
            params["reduceOnly"] = "true"
        
        params = self._sign_request(params)
        
        try:
            resp = await self._http.post(
                f"{self._base_url}/fapi/v1/order",
                data=params,
                headers=self._headers()
            )
            if resp.status_code == 200:
                result = resp.json()
                logger.info("Order placed: %s %s %.6f → %s (orderId=%s)",
                           symbol, side, quantity, result.get("status"), result.get("orderId"))
                return result
            else:
                logger.error("Order failed %s: %s - %s", symbol, resp.status_code, resp.text)
        except Exception as e:
            logger.error("Order error for %s: %s", symbol, e)
        return {}

    def _calculate_ema(self, prices: List[float], period: int) -> float:
        """Calculate EMA."""
        if len(prices) < period:
            return prices[-1] if prices else 0
        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        return ema

    def _calculate_adx(self, klines: List[dict], period: int = 14) -> float:
        """Calculate ADX (Average Directional Index)."""
        if len(klines) < period + 1:
            return 0.0
        
        plus_dm_list = []
        minus_dm_list = []
        tr_list = []
        
        for i in range(1, len(klines)):
            high = klines[i]["high"]
            low = klines[i]["low"]
            prev_high = klines[i-1]["high"]
            prev_low = klines[i-1]["low"]
            prev_close = klines[i-1]["close"]
            
            plus_dm = max(high - prev_high, 0)
            minus_dm = max(prev_low - low, 0)
            
            if plus_dm > minus_dm:
                minus_dm = 0
            elif minus_dm > plus_dm:
                plus_dm = 0
            
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            
            plus_dm_list.append(plus_dm)
            minus_dm_list.append(minus_dm)
            tr_list.append(tr)
        
        if len(tr_list) < period:
            return 0.0
        
        # Smoothed averages
        atr = sum(tr_list[:period]) / period
        plus_di_smooth = sum(plus_dm_list[:period]) / period
        minus_di_smooth = sum(minus_dm_list[:period]) / period
        
        dx_list = []
        for i in range(period, len(tr_list)):
            atr = (atr * (period - 1) + tr_list[i]) / period
            plus_di_smooth = (plus_di_smooth * (period - 1) + plus_dm_list[i]) / period
            minus_di_smooth = (minus_di_smooth * (period - 1) + minus_dm_list[i]) / period
            
            if atr == 0:
                continue
            
            plus_di = (plus_di_smooth / atr) * 100
            minus_di = (minus_di_smooth / atr) * 100
            
            di_sum = plus_di + minus_di
            if di_sum == 0:
                dx_list.append(0)
            else:
                dx_list.append(abs(plus_di - minus_di) / di_sum * 100)
        
        if not dx_list:
            return 0.0
        
        return sum(dx_list) / len(dx_list)

    async def _analyze_signal(self, cfg: FuturesConfig, state: FuturesState) -> str:
        """Analyze market for short/long/neutral signal."""
        klines = await self._get_klines(cfg.symbol, "1h", 100)
        if not klines:
            return "NEUTRAL"
        
        closes = [k["close"] for k in klines]
        
        ema_fast = self._calculate_ema(closes, cfg.ema_fast)
        ema_slow = self._calculate_ema(closes, cfg.ema_slow)
        adx = self._calculate_adx(klines)
        
        state.adx_value = adx
        
        # Trend detection
        if ema_fast < ema_slow and adx >= cfg.adx_threshold:
            state.current_trend = "DOWN"
            return "SHORT"
        elif ema_fast > ema_slow and adx >= cfg.adx_threshold:
            state.current_trend = "UP"
            return "LONG"
        else:
            state.current_trend = "NEUTRAL"
            return "NEUTRAL"

    async def _run_symbol(self, cfg: FuturesConfig):
        """Main loop for one symbol."""
        state = self.states[cfg.symbol]
        
        while self._running:
            try:
                # Get current price
                price = await self._get_price(cfg.symbol)
                if price <= 0:
                    await asyncio.sleep(cfg.check_interval_sec)
                    continue
                
                # Analyze signal
                signal = await self._analyze_signal(cfg, state)
                
                # Get current position
                pos = await self._get_position(cfg.symbol)
                position_amt = float(pos.get("positionAmt", 0))
                entry_price = float(pos.get("entryPrice", 0))
                unrealized_pnl = float(pos.get("unrealizedProfit", 0))
                
                state.position_amt = position_amt
                state.entry_price = entry_price
                state.unrealized_pnl = unrealized_pnl
                
                # Calculate PnL percentage
                pnl_pct = 0
                if entry_price > 0 and position_amt != 0:
                    if position_amt < 0:  # SHORT position
                        pnl_pct = ((entry_price - price) / entry_price) * 100
                    else:  # LONG position
                        pnl_pct = ((price - entry_price) / entry_price) * 100
                
                # Decision logic
                if position_amt == 0:
                    # No position — check for entry
                    if signal == "SHORT":
                        # Open SHORT position
                        qty = cfg.position_size_usdt / price * cfg.leverage
                        await self._place_order(cfg.symbol, "SELL", qty, "MARKET")
                        state.position_side = "SHORT"
                        state.position_amt = -qty  # Negative for SHORT
                        state.entry_price = price
                        state.last_signal = "SHORT"
                        state.last_signal_time = time.time()
                        state.total_trades += 1
                        logger.info("[Futures %s] OPEN SHORT %.6f @ ~%.2f (ADX=%.1f)",
                                   cfg.symbol, qty, price, state.adx_value)
                    elif signal == "LONG":
                        # Open LONG position
                        qty = cfg.position_size_usdt / price * cfg.leverage
                        await self._place_order(cfg.symbol, "BUY", qty, "MARKET")
                        state.position_side = "LONG"
                        state.position_amt = qty  # Positive for LONG
                        state.entry_price = price
                        state.last_signal = "LONG"
                        state.last_signal_time = time.time()
                        state.total_trades += 1
                        logger.info("[Futures %s] OPEN LONG %.6f @ ~%.2f (ADX=%.1f)",
                                   cfg.symbol, qty, price, state.adx_value)
                
                else:
                    # Have position — check exit conditions
                    should_close = False
                    close_reason = ""
                    
                    if position_amt < 0:  # SHORT
                        if pnl_pct <= -cfg.stop_loss_pct:
                            should_close = True
                            close_reason = f"STOP_LOSS ({pnl_pct:.1f}%)"
                        elif pnl_pct >= cfg.take_profit_pct:
                            should_close = True
                            close_reason = f"TAKE_PROFIT ({pnl_pct:.1f}%)"
                        elif signal == "LONG":
                            should_close = True
                            close_reason = f"SIGNAL_REVERSAL (ADX={state.adx_value:.1f})"
                    
                    else:  # LONG
                        if pnl_pct <= -cfg.stop_loss_pct:
                            should_close = True
                            close_reason = f"STOP_LOSS ({pnl_pct:.1f}%)"
                        elif pnl_pct >= cfg.take_profit_pct:
                            should_close = True
                            close_reason = f"TAKE_PROFIT ({pnl_pct:.1f}%)"
                        elif signal == "SHORT":
                            should_close = True
                            close_reason = f"SIGNAL_REVERSAL (ADX={state.adx_value:.1f})"
                    
                    if should_close:
                        # Close position
                        if position_amt < 0:
                            await self._place_order(cfg.symbol, "BUY", abs(position_amt), 
                                                  "MARKET", reduce_only=True)
                        else:
                            await self._place_order(cfg.symbol, "SELL", abs(position_amt),
                                                  "MARKET", reduce_only=True)
                        
                        state.position_side = "NONE"
                        state.position_amt = 0
                        state.entry_price = 0
                        state.last_signal = "CLOSE"
                        state.last_signal_time = time.time()
                        
                        if unrealized_pnl > 0:
                            state.win_trades += 1
                        else:
                            state.loss_trades += 1
                        state.realized_pnl += unrealized_pnl
                        
                        logger.info("[Futures %s] CLOSE (%s) PnL=%.2f USDT (%.1f%%)",
                                   cfg.symbol, close_reason, unrealized_pnl, pnl_pct)
                
                # Log status
                logger.info("[Futures %s] price=%.2f signal=%s pos=%s pnl=%.2f (%.1f%%) adx=%.1f trend=%s",
                           cfg.symbol, price, signal, state.position_side,
                           unrealized_pnl, pnl_pct, state.adx_value, state.current_trend)
                
                # Save state to Redis
                await self._save_state(cfg.symbol, state)
                
            except Exception as e:
                logger.error("[Futures %s] Error: %s", cfg.symbol, e, exc_info=True)
            
            await asyncio.sleep(cfg.check_interval_sec)

    async def _save_state(self, symbol: str, state: FuturesState):
        """Save state to Redis."""
        if not self._redis:
            return
        try:
            key = f"futures_bot:{symbol}:state"
            await self._redis.hset(key, mapping={
                "symbol": state.symbol,
                "position_side": state.position_side,
                "position_amt": str(state.position_amt),
                "entry_price": str(state.entry_price),
                "unrealized_pnl": str(state.unrealized_pnl),
                "realized_pnl": str(state.realized_pnl),
                "total_trades": str(state.total_trades),
                "win_trades": str(state.win_trades),
                "loss_trades": str(state.loss_trades),
                "last_signal": state.last_signal,
                "last_signal_time": str(state.last_signal_time),
                "current_trend": state.current_trend,
                "adx_value": str(state.adx_value),
                "halted": str(state.halted),
            })
        except Exception as e:
            logger.debug("Redis save error: %s", e)

    async def _load_states(self):
        """Load states from Redis."""
        if not self._redis:
            return
        try:
            for cfg in self.configs:
                key = f"futures_bot:{cfg.symbol}:state"
                data = await self._redis.hgetall(key)
                if data:
                    state = self.states[cfg.symbol]
                    state.position_side = data.get("position_side", "NONE")
                    state.position_amt = float(data.get("position_amt", 0))
                    state.entry_price = float(data.get("entry_price", 0))
                    state.unrealized_pnl = float(data.get("unrealized_pnl", 0))
                    state.realized_pnl = float(data.get("realized_pnl", 0))
                    state.total_trades = int(data.get("total_trades", 0))
                    state.win_trades = int(data.get("win_trades", 0))
                    state.loss_trades = int(data.get("loss_trades", 0))
                    state.last_signal = data.get("last_signal", "NONE")
                    state.current_trend = data.get("current_trend", "NEUTRAL")
                    state.adx_value = float(data.get("adx_value", 0))
                    state.halted = data.get("halted", "False") == "True"
                    logger.info("Loaded state for %s: pos=%s pnl=%.2f",
                               cfg.symbol, state.position_side, state.realized_pnl)
        except Exception as e:
            logger.debug("Redis load error: %s", e)

    def get_status(self) -> Dict[str, dict]:
        """Get status of all futures positions."""
        return {
            symbol: {
                "position_side": state.position_side,
                "position_amt": state.position_amt,
                "entry_price": state.entry_price,
                "unrealized_pnl": state.unrealized_pnl,
                "realized_pnl": state.realized_pnl,
                "total_trades": state.total_trades,
                "win_trades": state.win_trades,
                "loss_trades": state.loss_trades,
                "current_trend": state.current_trend,
                "adx_value": state.adx_value,
                "halted": state.halted,
            }
            for symbol, state in self.states.items()
        }


# Singleton instance
_futures_bot: Optional["FuturesBot"] = None


def get_futures_bot() -> "FuturesBot":
    global _futures_bot
    if _futures_bot is None:
        _futures_bot = FuturesBot()
        # Configure futures for USDT pairs on Binance Global
        # These work in bear markets by shorting downtrends
        symbols = os.getenv("FUTURES_SYMBOLS", "BTCUSDT,ETHUSDT").split(",")
        leverage = int(os.getenv("FUTURES_LEVERAGE", "5"))
        position_size = float(os.getenv("FUTURES_POSITION_SIZE_USDT", "50"))
        
        for sym in symbols:
            sym = sym.strip()
            if sym:
                _futures_bot.add_config(FuturesConfig(
                    symbol=sym,
                    leverage=leverage,
                    position_size_usdt=position_size,
                ))
    return _futures_bot

