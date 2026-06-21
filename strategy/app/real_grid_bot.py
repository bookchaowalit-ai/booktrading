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
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

import httpx

from app.risk_manager import get_risk_manager
from app.trade_journal import get_trade_journal, JournalEntry

logger = logging.getLogger("real_grid_bot")

# ── Configuration ─────────────────────────────────────────────────────────────

BINANCE_PUBLIC_REST = os.getenv("BINANCE_PRICE_API", "https://api.binance.th")
BACKEND_API_BASE = os.getenv("BACKEND_API_BASE", "http://backend:8080")


@dataclass
class RealGridConfig:
    symbol: str
    grid_spacing_pct: float = 1.5       # % between grid levels
    grid_levels: int = 3                # number of levels above/below (conservative)
    order_size: float = 0.00005         # base quantity per grid order (~104 THB)
    max_position: float = 0.001         # max position size in base asset
    poll_interval_sec: int = 60         # how often to check prices
    max_daily_loss_usd: float = 50.0    # stop trading if daily loss exceeds this
    max_open_orders: int = 10           # max simultaneous open orders
    stale_threshold_pct: float = 5.0    # cancel orders >5% away from current price


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
                grid_spacing_pct=1.5,
                grid_levels=2,            # 2 levels above/below (conservative)
                order_size=0.00005,     # ~104 THB at ~2,087,000 THB/BTC (min 100 THB)
                max_position=0.001,     # max ~2,087 THB exposure
                max_daily_loss_usd=50.0,
            )
            for sym in real_symbols
        ]
        self.states: Dict[str, RealGridState] = {}
        self._running = False
        self._http: Optional[httpx.AsyncClient] = None
        self._enabled = True  # master kill switch

    async def start(self):
        """Start the real grid bot."""
        self._running = True
        self._http = httpx.AsyncClient(timeout=15.0)

        # Initialize risk manager and trade journal
        self._risk = get_risk_manager()
        self._journal = get_trade_journal()
        await self._journal.start(self._http)

        logger.info("Real Grid Bot v2 started with %d symbol(s)", len(self.configs))

        for cfg in self.configs:
            self.states[cfg.symbol] = RealGridState(
                symbol=cfg.symbol,
                last_daily_reset=time.time(),
            )

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

        # Daily reset
        if time.time() - state.last_daily_reset > 86400:
            state.daily_pnl = 0.0
            state.daily_trades = 0
            state.last_daily_reset = time.time()
            state.halted = False
            state.counted_trade_ids.clear()

        # Safety: daily loss limit
        if state.daily_pnl < -cfg.max_daily_loss_usd:
            if not state.halted:
                logger.warning(
                    "[RealGrid %s] Daily loss limit hit: $%.2f — HALTING",
                    cfg.symbol, state.daily_pnl,
                )
                state.halted = True
            return

        if state.halted:
            return

        # Step 1: Sync open orders from Binance TH
        await self._sync_open_orders(cfg, state)

        # Step 2: Fetch current price
        price = await self._fetch_price(cfg.symbol)
        if price <= 0:
            return

        state.last_price = price

        # Step 3: Cancel stale orders (too far from current price)
        await self._cancel_stale_orders(cfg, state, price)

        # Step 4: Calculate PnL from filled trades
        await self._update_pnl(cfg, state)

        # Step 5: Place new grid orders
        spacing = price * (cfg.grid_spacing_pct / 100.0)
        
        logger.info(
            "[RealGrid %s] price=%d spacing=%d buys=%d sells=%d pnl=$%.2f",
            cfg.symbol, int(price), int(spacing),
            len(state.active_buys), len(state.active_sells),
            state.daily_pnl,
        )

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

                # For sells, calculate profit (approximate: spacing * qty)
                if side == "SELL":
                    price = t.get("price", 0)
                    qty = t.get("quantity", 0)
                    if price > 0 and qty > 0:
                        # Approximate profit = grid_spacing * qty
                        spacing = state.last_price * (cfg.grid_spacing_pct / 100.0)
                        profit = spacing * qty
                        state.daily_pnl += profit
                        state.daily_trades += 1

                        # Record in risk manager
                        self._risk.record_trade_result(cfg.symbol, profit, is_win=(profit > 0))

                        # Record exit in journal
                        exchange_oid = t.get("exchange_order_id", "")
                        await self._journal.record_exit(
                            exchange_order_id=exchange_oid or trade_id,
                            exit_price=price,
                            exit_reason="grid_fill",
                            actual_pnl=profit,
                            fee=t.get("fee", 0) or 0,
                        )

                        logger.info(
                            "[RealGrid %s] Filled SELL @ %d qty=%.6f profit~=%.2f THB",
                            cfg.symbol, int(price), qty, profit,
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

    async def _place_grid_order(self, cfg: RealGridConfig, state: RealGridState, side: str, price: int):
        """Place a real LIMIT order at a grid level via Go backend."""
        # ── Risk check before order ──
        allowed, reason = self._risk.check_order_allowed(
            symbol=cfg.symbol,
            side=side,
            quantity=cfg.order_size,
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
                    "quantity": cfg.order_size,
                    "price": price,  # >0 = LIMIT order
                },
            )
            if resp.status_code == 201:
                data = resp.json()
                order = data.get("order", {})
                order_id = str(order.get("orderId", ""))

                state.trades_executed += 1
                state.daily_trades += 1

                if side == "BUY":
                    state.active_buys[price] = order_id
                else:
                    state.active_sells[price] = order_id

                # Record in risk manager
                self._risk.record_order_placed(cfg.symbol)

                # Record in trade journal
                notional = cfg.order_size * price
                await self._journal.record_entry(JournalEntry(
                    symbol=cfg.symbol,
                    side=side,
                    strategy="grid_bot_v2",
                    entry_reason=f"Grid {side.lower()} @ level price={price}, spacing={cfg.grid_spacing_pct}%",
                    entry_price=price,
                    quantity=cfg.order_size,
                    expected_risk_thb=notional * 0.02,  # 2% risk estimate
                    expected_reward_thb=notional * (cfg.grid_spacing_pct / 100),
                    exchange_order_id=order_id,
                ))

                logger.info(
                    "[RealGrid %s] %s LIMIT @ %d placed (id=%s)",
                    cfg.symbol, side, price, order_id[:16] if order_id else "?",
                )
            else:
                err = resp.json().get("error", "unknown")
                logger.debug("Order rejected @ %d: %s", price, err)
        except Exception as e:
            logger.debug("Failed to place %s @ %d: %s", side, price, e)

    def get_status(self) -> Dict:
        """Get current real grid bot status (includes risk metrics)."""
        risk = get_risk_manager()
        journal = get_trade_journal()
        return {
            "running": self._running,
            "enabled": self._enabled,
            "symbols": {
                symbol: {
                    "last_price": state.last_price,
                    "active_buys": len(state.active_buys),
                    "active_sells": len(state.active_sells),
                    "trades_executed": state.trades_executed,
                    "daily_pnl": round(state.daily_pnl, 2),
                    "daily_trades": state.daily_trades,
                    "halted": state.halted,
                }
                for symbol, state in self.states.items()
            },
            "risk": risk.get_status(),
            "journal_stats": journal.get_stats(),
        }


# ── Singleton instance for FastAPI integration ────────────────────────────────

_real_grid_bot: Optional[RealGridBot] = None


def get_real_grid_bot() -> RealGridBot:
    global _real_grid_bot
    if _real_grid_bot is None:
        _real_grid_bot = RealGridBot()
    return _real_grid_bot
