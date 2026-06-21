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
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger("paper_grid_bot")

# ── Configuration ─────────────────────────────────────────────────────────────

BINANCE_TESTNET_REST = "https://testnet.binance.vision"
PAPER_API_BASE = os.getenv("PAPER_API_BASE", "http://backend:8080")

# Grid parameters per symbol
@dataclass
class GridConfig:
    symbol: str
    grid_spacing_pct: float = 2.0      # % between grid levels
    grid_levels: int = 5               # number of levels above/below
    order_size: float = 0.001          # base quantity per grid order
    max_position: float = 0.05         # max position size
    poll_interval_sec: int = 30        # how often to check prices


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
        self.configs = configs or [
            GridConfig(symbol="BTCUSDT", grid_spacing_pct=1.5, grid_levels=5, order_size=0.001, max_position=0.05),
            GridConfig(symbol="ETHUSDT", grid_spacing_pct=2.0, grid_levels=5, order_size=0.01, max_position=0.5),
        ]
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
        """One tick: fetch price, evaluate grid, place orders."""
        price = await self._fetch_price(cfg.symbol)
        if price <= 0:
            return

        state = self.states[cfg.symbol]
        state.last_price = price
        spacing = price * (cfg.grid_spacing_pct / 100.0)

        logger.info(
            "[Grid %s] price=%.2f spacing=%.2f buys=%d sells=%d",
            cfg.symbol, price, spacing,
            len(state.active_buys), len(state.active_sells),
        )

        # Check which grid levels should have orders
        for level in range(1, cfg.grid_levels + 1):
            buy_price = round(price - (spacing * level), 2)
            sell_price = round(price + (spacing * level), 2)

            # Place buy if not already active
            if buy_price not in state.active_buys:
                await self._place_grid_order(cfg, state, "BUY", buy_price)

            # Place sell if not already active and we have position
            if sell_price not in state.active_sells:
                await self._place_grid_order(cfg, state, "SELL", sell_price)

        # Check portfolio to see which orders filled
        await self._sync_state(cfg, state, price)

    async def _fetch_price(self, symbol: str) -> float:
        """Fetch current price from Binance testnet (public, no key needed)."""
        try:
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
        """Place a paper order at a grid level."""
        try:
            resp = await self._http.post(
                f"{PAPER_API_BASE}/api/paper/order",
                json={
                    "symbol": cfg.symbol,
                    "side": side,
                    "quantity": cfg.order_size,
                    "limit_price": price,
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
                    if side == "BUY":
                        state.active_buys[price] = order_id
                    else:
                        state.active_sells[price] = order_id
            else:
                # Order rejected (insufficient balance, no position, etc.) — normal
                pass
        except Exception as e:
            logger.debug("Failed to place %s order @ %.2f: %s", side, price, e)

    async def _sync_state(self, cfg: GridConfig, state: GridState, current_price: float):
        """Sync grid state with paper engine portfolio."""
        try:
            resp = await self._http.get(f"{PAPER_API_BASE}/api/paper/portfolio")
            if resp.status_code == 200:
                portfolio = resp.json()
                positions = {p["symbol"]: p for p in portfolio.get("positions", [])}
                pos = positions.get(cfg.symbol)
                if pos:
                    # Clean up filled orders from active tracking
                    filled_buys = [p for p in state.active_buys if p < current_price * 0.99]
                    filled_sells = [p for p in state.active_sells if p > current_price * 1.01]
                    for p in filled_buys:
                        del state.active_buys[p]
                    for p in filled_sells:
                        del state.active_sells[p]
        except Exception:
            pass

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
