"""
Automated Grid Trading Bot
===========================
Places buy/sell orders at fixed price intervals (grid levels) around
the current market price. Uses Binance testnet public API for live
prices and the Go backend's PaperEngine for simulated execution.

No API keys needed — runs entirely on paper (fake money).

Usage:
    # As standalone script
    python -m app.grid_bot

    # Or via the FastAPI background task (auto-started with strategy service)
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


def validate_grid_config(cfg: GridConfig, ref_price: float = 0.0) -> List[str]:
    """Validate grid config safety constraints. Returns list of violations (empty = safe)."""
    violations = []
    if cfg.grid_levels < 1:
        violations.append(f"grid_levels must be >= 1, got {cfg.grid_levels}")
    if cfg.grid_levels > 5:
        violations.append(f"grid_levels={cfg.grid_levels} exceeds safety cap of 5")
    if cfg.order_size <= 0:
        violations.append(f"order_size must be > 0, got {cfg.order_size}")
    if cfg.max_position <= 0:
        violations.append(f"max_position must be > 0, got {cfg.max_position}")
    if cfg.grid_spacing_pct < 0.5:
        violations.append(f"grid_spacing_pct={cfg.grid_spacing_pct} below minimum 0.5%")
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
    """Conservative paper defaults — aligned with real_grid_bot.py BTCTHB config.

    Exposure per symbol: ~฿2,120 max (0.001 BTC × ฿2.1M).
    Total max exposure across all symbols: ~฿2,120.
    """
    return [
        GridConfig(
            symbol="BTCTHB",
            grid_spacing_pct=2.0,
            grid_levels=2,
            order_size=0.00005,    # ~฿106 per order
            max_position=0.001,    # ~฿2,120 max exposure
            max_notional=3000.0,   # ฿3,000 cap (≈$85)
        ),
    ]


@dataclass
class GridState:
    """Tracks active grid orders for a symbol."""
    symbol: str
    active_buys: Dict[float, str] = field(default_factory=dict)   # price -> order_id
    active_sells: Dict[float, str] = field(default_factory=dict)  # price -> order_id
    last_price: float = 0.0
    total_profit: float = 0.0
    trades_executed: int = 0


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

    async def start(self):
        """Start the grid bot."""
        self._running = True
        self._http = httpx.AsyncClient(timeout=10.0)
        logger.info("Grid Bot started with %d symbol(s)", len(self.configs))

        for cfg in self.configs:
            self.states[cfg.symbol] = GridState(symbol=cfg.symbol)

        # Reset paper engine to clean state
        await self._reset_paper_engine()

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

        logger.info("Grid Bot stopped. Total trades: %d", sum(s.trades_executed for s in self.states.values()))

    async def stop(self):
        """Stop the grid bot."""
        self._running = False
        if self._http:
            await self._http.aclose()

    async def _tick(self, cfg: GridConfig):
        """One tick: fetch price, update pending orders, evaluate grid, place orders."""
        price = await self._fetch_price(cfg.symbol)
        if price <= 0:
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

        spacing = price * (cfg.grid_spacing_pct / 100.0)

        logger.info(
            "[Grid %s] price=%.2f spacing=%.2f buys=%d sells=%d",
            cfg.symbol, price, spacing,
            len(state.active_buys), len(state.active_sells),
        )

        # ── Cancel stale orders outside active grid range ──
        await self._cancel_stale_orders(cfg, state, price, spacing)

        # ── Place orders at active grid levels ──
        for level in range(1, cfg.grid_levels + 1):
            buy_price = round(price - (spacing * level), 2)
            sell_price = round(price + (spacing * level), 2)

            # Place buy if not already active at this level
            if not state.active_buys.get(buy_price):
                await self._place_grid_order(cfg, state, "BUY", buy_price)

            # Place sell if not already active and we have position
            if not state.active_sells.get(sell_price):
                await self._place_grid_order(cfg, state, "SELL", sell_price)

        # Sync grid state with paper engine (reconcile filled vs pending)
        await self._sync_state(cfg, state, price)

    async def _cancel_stale_orders(self, cfg: GridConfig, state: GridState, price: float, spacing: float):
        """Cancel orders that are outside the current active grid range."""
        # Calculate active grid levels
        active_buy_prices = set()
        active_sell_prices = set()
        for level in range(1, cfg.grid_levels + 1):
            active_buy_prices.add(round(price - (spacing * level), 2))
            active_sell_prices.add(round(price + (spacing * level), 2))

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

    async def _place_grid_order(self, cfg: GridConfig, state: GridState, side: str, price: float):
        """Place a paper limit order at a grid level."""
        try:
            resp = await self._http.post(
                f"{PAPER_API_BASE}/api/paper/order",
                json={
                    "symbol": cfg.symbol,
                    "side": side,
                    "quantity": cfg.order_size,
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
                    if side == "SELL":
                        profit = (price - (price * 0.98)) * cfg.order_size  # approx
                        state.total_profit += profit
                    logger.info(
                        "[Grid %s] %s FILLED @ %.2f (qty=%.4f) profit=%.2f",
                        cfg.symbol, side, price, cfg.order_size, state.total_profit,
                    )
                else:
                    # PENDING — limit order waiting for price to touch
                    if side == "BUY":
                        state.active_buys[price] = order_id
                    else:
                        state.active_sells[price] = order_id
                    logger.debug(
                        "[Grid %s] %s PENDING @ %.2f (qty=%.4f)",
                        cfg.symbol, side, price, cfg.order_size,
                    )
            else:
                # Order rejected (insufficient balance, no position, etc.) — normal
                pass
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
                filled_prices = []
                for price, oid in list(state.active_buys.items()):
                    if oid not in pending_ids:
                        filled_prices.append(("BUY", price))
                        del state.active_buys[price]
                for price, oid in list(state.active_sells.items()):
                    if oid not in pending_ids:
                        filled_prices.append(("SELL", price))
                        del state.active_sells[price]

                if filled_prices:
                    logger.info(
                        "[Grid %s] Synced: %d orders filled/removed, "
                        "remaining buys=%d sells=%d",
                        cfg.symbol, len(filled_prices),
                        len(state.active_buys), len(state.active_sells),
                    )
        except Exception as e:
            logger.debug("Failed to sync state: %s", e)

    async def _reset_paper_engine(self):
        """Reset the paper trading engine to initial state."""
        try:
            resp = await self._http.post(f"{PAPER_API_BASE}/api/paper/reset")
            if resp.status_code == 200:
                logger.info("Paper engine reset to $10,000")
        except Exception as e:
            logger.warning("Failed to reset paper engine: %s", e)

    def get_status(self) -> Dict:
        """Get current grid bot status."""
        return {
            "running": self._running,
            "symbols": {
                symbol: {
                    "last_price": state.last_price,
                    "active_buys": len(state.active_buys),
                    "active_sells": len(state.active_sells),
                    "trades_executed": state.trades_executed,
                    "total_profit": round(state.total_profit, 2),
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
