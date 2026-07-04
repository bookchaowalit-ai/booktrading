"""
DCA (Dollar Cost Averaging) Accumulation Bot
==============================================
Buys assets at regular intervals using THB, with smart dip-buying:
- Base buy amount every interval
- 2x buy when price drops >3% from average
- 3x buy when price drops >7% from average
- Sells portion when price spikes >10% above average (take profit)

Works GREAT in bear markets because it accumulates more when prices are low.
When market recovers, all those cheap buys become profitable.

Uses Binance TH spot trading via Go backend /api/trade endpoints.
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger("dca_bot")

BINANCE_PUBLIC_REST = os.getenv("BINANCE_PRICE_API", "https://api.binance.th")
BACKEND_API_BASE = os.getenv("BACKEND_API_BASE", "http://backend:8080")
BINANCE_TH_MAINNET = os.getenv("BINANCE_TH_USE_TESTNET", "false").lower() != "true"


@dataclass
class DCAConfig:
    symbol: str               # e.g. "BTCTHB"
    base_amount_thb: float = 100.0      # base THB to spend per interval (must meet 100 THB min notional)
    interval_sec: int = 300             # buy every N seconds (default 5 min)
    dip_threshold_1_pct: float = 3.0    # 2x buy when price drops this %
    dip_threshold_2_pct: float = 7.0    # 3x buy when price drops this %
    spike_threshold_pct: float = 10.0   # sell portion when price spikes this %
    spike_sell_pct: float = 0.15        # sell 15% of holdings on spike
    lookback_periods: int = 50          # periods for average price calculation
    max_holdings_base: float = 0.01     # max base asset to hold
    min_notional_thb: float = 100.0     # Binance TH minimum order value
    poll_interval_sec: int = 30         # how often to check prices
    step_size: float = 0.00001          # Binance TH stepSize for quantity rounding
    tick_size: float = 1.0              # Binance TH tickSize for price rounding


# Binance TH step sizes per symbol
DCA_SYMBOL_SPECS = {
    "BTCTHB": {"step_size": 0.00001, "tick_size": 0.01},
    "ETHTHB": {"step_size": 0.0001, "tick_size": 1.0},
    "BNBTHB": {"step_size": 0.01, "tick_size": 0.01},
    "SOLTHB": {"step_size": 0.01, "tick_size": 0.01},
    "XRPTHB": {"step_size": 0.01, "tick_size": 0.01},
}


@dataclass
class DCAState:
    symbol: str
    total_bought_base: float = 0.0       # total base asset bought
    total_spent_thb: float = 0.0         # total THB spent
    total_sold_base: float = 0.0         # total base asset sold
    total_received_thb: float = 0.0      # total THB received from sells
    total_trades: int = 0
    buy_trades: int = 0
    sell_trades: int = 0
    last_buy_time: float = 0.0
    last_sell_time: float = 0.0
    avg_buy_price: float = 0.0           # weighted average buy price
    price_history: List[float] = field(default_factory=list)
    unrealized_pnl_thb: float = 0.0
    realized_pnl_thb: float = 0.0
    halted: bool = False


class DCABot:
    """DCA Accumulation Bot — buys dips, takes profits on spikes."""

    def __init__(self):
        self.configs: List[DCAConfig] = []
        self.states: Dict[str, DCAState] = {}
        self._http: Optional[httpx.AsyncClient] = None
        self._redis = None
        self._running = False

    def set_redis(self, redis_client):
        self._redis = redis_client

    def add_config(self, cfg: DCAConfig):
        self.configs.append(cfg)
        self.states[cfg.symbol] = DCAState(symbol=cfg.symbol)

    async def start(self):
        """Start the DCA bot."""
        self._running = True
        self._http = httpx.AsyncClient(timeout=30)

        # Load existing states from Redis
        await self._load_states()

        logger.info("DCA Bot started with %d symbols: %s",
                     len(self.configs), [c.symbol for c in self.configs])

        # Run all DCA configs concurrently
        tasks = [self._run_symbol(cfg) for cfg in self.configs]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def stop(self):
        self._running = False
        if self._http:
            await self._http.aclose()

    async def _run_symbol(self, cfg: DCAConfig):
        """Main loop for one symbol."""
        state = self.states[cfg.symbol]

        while self._running:
            try:
                # Fetch current price
                price = await self._get_price(cfg.symbol)
                if price <= 0:
                    await asyncio.sleep(cfg.poll_interval_sec)
                    continue

                # Update price history
                state.price_history.append(price)
                if len(state.price_history) > cfg.lookback_periods:
                    state.price_history = state.price_history[-cfg.lookback_periods:]

                # Calculate average price
                avg_price = sum(state.price_history) / len(state.price_history) if state.price_history else price
                pct_from_avg = ((price - avg_price) / avg_price) * 100 if avg_price > 0 else 0

                # Update unrealized PnL
                holdings = state.total_bought_base - state.total_sold_base
                state.unrealized_pnl_thb = holdings * price - (state.total_spent_thb - state.total_received_thb)

                # Decision logic
                elapsed = time.time() - state.last_buy_time

                if pct_from_avg <= -cfg.dip_threshold_2_pct:
                    # Deep dip — 3x buy
                    if elapsed >= cfg.interval_sec:
                        buy_amount = cfg.base_amount_thb * 3.0
                        await self._execute_buy(cfg, state, price, buy_amount, "DEEP_DIP")
                elif pct_from_avg <= -cfg.dip_threshold_1_pct:
                    # Dip — 2x buy
                    if elapsed >= cfg.interval_sec:
                        buy_amount = cfg.base_amount_thb * 2.0
                        await self._execute_buy(cfg, state, price, buy_amount, "DIP")
                elif pct_from_avg >= cfg.spike_threshold_pct:
                    # Spike — sell portion
                    if holdings > 0 and state.last_sell_time < state.last_buy_time:
                        sell_base = holdings * (cfg.spike_sell_pct / 100)
                        await self._execute_sell(cfg, state, price, sell_base, "SPIKE_PROFIT")
                else:
                    # Normal — regular DCA buy
                    if elapsed >= cfg.interval_sec:
                        await self._execute_buy(cfg, state, price, cfg.base_amount_thb, "DCA")

                # Save state and log
                await self._save_state(cfg.symbol)
                logger.info(
                    "[DCA %s] price=%.2f avg=%.2f diff=%+.1f%% holdings=%.6f "
                    "realized=%.2f unrealized=%.2f trades=%d",
                    cfg.symbol, price, avg_price, pct_from_avg, holdings,
                    state.realized_pnl_thb, state.unrealized_pnl_thb, state.total_trades
                )

            except Exception as e:
                logger.error("[DCA %s] Error: %s", cfg.symbol, e, exc_info=True)

            await asyncio.sleep(cfg.poll_interval_sec)

    async def _execute_buy(self, cfg: DCAConfig, state: DCAState, price: float,
                           amount_thb: float, reason: str):
        """Execute a BUY order."""
        if amount_thb < cfg.min_notional_thb:
            logger.debug("[DCA %s] Buy amount %.2f THB below minimum %.2f", cfg.symbol, amount_thb, cfg.min_notional_thb)
            return

        # Calculate quantity and round to step_size (Binance TH requirement)
        qty = amount_thb / price
        qty = round(qty / cfg.step_size) * cfg.step_size
        # Format to avoid floating point issues
        qty = float(f"{qty:.10g}")
        if qty <= 0:
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

        # Check if we have enough THB
        balances = await self._fetch_balances()
        thb_free = balances.get("THB", 0)
        actual_cost = qty * rounded_price
        if thb_free < actual_cost:
            logger.warning("[DCA %s] Insufficient THB: need %.2f, have %.2f", cfg.symbol, actual_cost, thb_free)
            return

        if not BINANCE_TH_MAINNET:
            logger.info("[DCA %s] PAPER %s BUY qty=%.6f price=%.2f amount=%.2f THB (%s)",
                        cfg.symbol, reason, qty, rounded_price, actual_cost, reason)
            state.total_bought_base += qty
            state.total_spent_thb += actual_cost
            state.buy_trades += 1
            state.total_trades += 1
            state.last_buy_time = time.time()
            if state.avg_buy_price > 0:
                state.avg_buy_price = (state.avg_buy_price * (state.total_bought_base - qty) + rounded_price * qty) / state.total_bought_base
            else:
                state.avg_buy_price = rounded_price
            return

        try:
            resp = await self._http.post(
                f"{BACKEND_API_BASE}/api/trade/order",
                json={
                    "symbol": cfg.symbol,
                    "side": "BUY",
                    "quantity": qty,
                    "price": rounded_price,
                },
            )
            if resp.status_code == 201:
                data = resp.json()
                order = data.get("order", {})
                filled_qty = float(order.get("executedQty") or qty)
                filled_cost = float(order.get("cummulativeQuoteQty") or amount_thb)
                state.total_bought_base += filled_qty
                state.total_spent_thb += filled_cost
                state.buy_trades += 1
                state.total_trades += 1
                state.last_buy_time = time.time()
                # Update weighted avg buy price
                total_base = state.total_bought_base
                if total_base > 0:
                    state.avg_buy_price = state.total_spent_thb / total_base
                logger.info("[DCA %s] REAL %s BUY filled=%.6f price=%.2f cost=%.2f THB (orderId=%s)",
                            cfg.symbol, reason, filled_qty, price, filled_cost,
                            order.get("orderId", "?"))
            else:
                logger.warning("[DCA %s] BUY order failed: %s %s", cfg.symbol, resp.status_code, resp.text)
        except Exception as e:
            logger.error("[DCA %s] BUY failed: %s", cfg.symbol, e)

    async def _execute_sell(self, cfg: DCAConfig, state: DCAState, price: float,
                            qty: float, reason: str):
        """Execute a SELL order."""
        if qty <= 0:
            return

        # Check minimum notional
        notional = qty * price
        if notional < cfg.min_notional_thb:
            logger.debug("[DCA %s] Sell notional %.2f THB below minimum", cfg.symbol, notional)
            return

        # Check we have the asset
        base_asset = cfg.symbol.replace("THB", "")
        balances = await self._fetch_balances()
        asset_free = balances.get(base_asset, 0)
        if asset_free < qty:
            qty = asset_free * 0.95  # sell 95% of what we have (safety margin)
            if qty * price < cfg.min_notional_thb:
                logger.warning("[DCA %s] Insufficient %s: have %.6f", cfg.symbol, base_asset, asset_free)
                return

        if not BINANCE_TH_MAINNET:
            proceeds = qty * price
            profit = (price - state.avg_buy_price) * qty
            state.total_sold_base += qty
            state.total_received_thb += proceeds
            state.realized_pnl_thb += profit
            state.sell_trades += 1
            state.total_trades += 1
            state.last_sell_time = time.time()
            logger.info("[DCA %s] PAPER %s SELL qty=%.6f price=%.2f profit=%.2f THB",
                        cfg.symbol, reason, qty, price, profit)
            return

        try:
            resp = await self._http.post(
                f"{BACKEND_API_BASE}/api/trade/order",
                json={
                    "symbol": cfg.symbol,
                    "side": "SELL",
                    "quantity": qty,
                    "price": price,
                },
            )
            if resp.status_code == 201:
                data = resp.json()
                order = data.get("order", {})
                filled_qty = float(order.get("executedQty") or qty)
                filled_cost = float(order.get("cummulativeQuoteQty") or qty * price)
                profit = (price - state.avg_buy_price) * filled_qty
                state.total_sold_base += filled_qty
                state.total_received_thb += filled_cost
                state.realized_pnl_thb += profit
                state.sell_trades += 1
                state.total_trades += 1
                state.last_sell_time = time.time()
                logger.info("[DCA %s] REAL %s SELL filled=%.6f price=%.2f profit=%.2f THB (orderId=%s)",
                            cfg.symbol, reason, filled_qty, price, profit,
                            order.get("orderId", "?"))
            else:
                logger.warning("[DCA %s] SELL order failed: %s %s", cfg.symbol, resp.status_code, resp.text)
        except Exception as e:
            logger.error("[DCA %s] SELL failed: %s", cfg.symbol, e)

    async def _get_price(self, symbol: str) -> float:
        """Get current price from Binance TH."""
        try:
            resp = await self._http.get(
                f"{BINANCE_PUBLIC_REST}/api/v1/ticker/price",
                params={"symbol": symbol},
            )
            if resp.status_code == 200:
                return float(resp.json()["price"])
        except Exception as e:
            logger.warning("Failed to get price for %s: %s", symbol, e)
        return 0.0

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

    async def _save_state(self, symbol: str):
        """Persist state to Redis."""
        if not self._redis:
            return
        state = self.states[symbol]
        data = {
            "total_bought_base": state.total_bought_base,
            "total_spent_thb": state.total_spent_thb,
            "total_sold_base": state.total_sold_base,
            "total_received_thb": state.total_received_thb,
            "total_trades": state.total_trades,
            "buy_trades": state.buy_trades,
            "sell_trades": state.sell_trades,
            "last_buy_time": state.last_buy_time,
            "last_sell_time": state.last_sell_time,
            "avg_buy_price": state.avg_buy_price,
            "realized_pnl_thb": state.realized_pnl_thb,
            "unrealized_pnl_thb": state.unrealized_pnl_thb,
            "halted": state.halted,
        }
        try:
            await self._redis.hset(f"dca_bot:{symbol}:state", mapping={
                k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                for k, v in data.items()
            })
        except Exception as e:
            logger.warning("Failed to save DCA state for %s: %s", symbol, e)

    async def _load_states(self):
        """Load states from Redis."""
        if not self._redis:
            return
        for cfg in self.configs:
            try:
                data = await self._redis.hgetall(f"dca_bot:{cfg.symbol}:state")
                if data:
                    state = self.states[cfg.symbol]
                    state.total_bought_base = float(data.get("total_bought_base", 0))
                    state.total_spent_thb = float(data.get("total_spent_thb", 0))
                    state.total_sold_base = float(data.get("total_sold_base", 0))
                    state.total_received_thb = float(data.get("total_received_thb", 0))
                    state.total_trades = int(data.get("total_trades", 0))
                    state.buy_trades = int(data.get("buy_trades", 0))
                    state.sell_trades = int(data.get("sell_trades", 0))
                    state.last_buy_time = float(data.get("last_buy_time", 0))
                    state.last_sell_time = float(data.get("last_sell_time", 0))
                    state.avg_buy_price = float(data.get("avg_buy_price", 0))
                    state.realized_pnl_thb = float(data.get("realized_pnl_thb", 0))
                    state.unrealized_pnl_thb = float(data.get("unrealized_pnl_thb", 0))
                    state.halted = data.get("halted", "false").lower() == "true"
                    logger.info("[DCA %s] Loaded state: trades=%d bought=%.6f spent=%.2f",
                                cfg.symbol, state.total_trades, state.total_bought_base, state.total_spent_thb)
            except Exception as e:
                logger.warning("Failed to load DCA state for %s: %s", cfg.symbol, e)

    def get_status(self) -> Dict:
        """Get status of all DCA bots."""
        result = {}
        for cfg in self.configs:
            state = self.states[cfg.symbol]
            holdings = state.total_bought_base - state.total_sold_base
            result[cfg.symbol] = {
                "symbol": cfg.symbol,
                "total_trades": state.total_trades,
                "buy_trades": state.buy_trades,
                "sell_trades": state.sell_trades,
                "holdings_base": holdings,
                "avg_buy_price": state.avg_buy_price,
                "total_spent_thb": state.total_spent_thb,
                "total_received_thb": state.total_received_thb,
                "realized_pnl_thb": state.realized_pnl_thb,
                "unrealized_pnl_thb": state.unrealized_pnl_thb,
                "total_pnl_thb": state.realized_pnl_thb + state.unrealized_pnl_thb,
                "halted": state.halted,
                "last_buy_time": state.last_buy_time,
            }
        return result


# Singleton
_dca_bot: Optional[DCABot] = None


def get_dca_bot() -> DCABot:
    global _dca_bot
    if _dca_bot is None:
        _dca_bot = DCABot()
        # Configure DCA for available THB pairs on Binance TH
        # Conservative: 50 THB per buy every 5 minutes
        # These work in bear markets by accumulating cheap assets
        symbols = os.getenv("DCA_SYMBOLS", "BTCTHB,ETHTHB").split(",")
        base_amount = float(os.getenv("DCA_BASE_AMOUNT_THB", "100"))
        interval = int(os.getenv("DCA_INTERVAL_SEC", "300"))

        for sym in symbols:
            sym = sym.strip()
            if sym:
                specs = DCA_SYMBOL_SPECS.get(sym, {"step_size": 0.00001, "tick_size": 1.0})
                _dca_bot.add_config(DCAConfig(
                    symbol=sym,
                    base_amount_thb=base_amount,
                    interval_sec=interval,
                    step_size=specs["step_size"],
                    tick_size=specs["tick_size"],
                ))
    return _dca_bot
