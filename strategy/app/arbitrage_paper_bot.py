"""
Arbitrage Paper Bot
===================
Simulates cross-exchange arbitrage trading between:
- Binance Global (USDT pairs → convert to THB)
- Binance Thailand (THB pairs)
- Bitkub (THB pairs)

Monitors price spreads and simulates buy/sell when spread > fees.
Tracks paper PnL to evaluate arbitrage profitability.

Key considerations:
- Transfer time between exchanges (not instant)
- Withdrawal fees (varies by asset)
- Trading fees: ~0.1% per trade × 2 = 0.2% round trip
- Slippage on larger orders
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger("arbitrage_paper")

# Exchange API endpoints (public, no auth needed)
BINANCE_GLOBAL = "https://api.binance.com"
BINANCE_TH = "https://api.binance.th"
BITKUB = "https://api.bitkub.com"

# Trading fees (maker/taker average)
TRADING_FEE_PCT = 0.001  # 0.1% per trade
ROUND_TRIP_FEE_PCT = TRADING_FEE_PCT * 2  # 0.2% for buy + sell

# Minimum spread to trigger paper trade (after fees)
MIN_SPREAD_PCT = 0.3  # 0.3% minimum profit after 0.2% fees

# Paper trading capital
PAPER_CAPITAL_THB = 10000.0  # 10k THB for paper arbitrage

# Pairs to monitor (must be available on multiple exchanges)
ARBITRAGE_PAIRS = {
    "BTC": {
        "binance_global": "BTCUSDT",
        "binance_th": "BTCTHB",
        "bitkub": "THB_BTC",
    },
    "ETH": {
        "binance_global": "ETHUSDT",
        "binance_th": "ETHTHB",
        "bitkub": "THB_ETH",
    },
    "SOL": {
        "binance_global": "SOLUSDT",
        "binance_th": "SOLTHB",
        "bitkub": "THB_SOL",
    },
    "BNB": {
        "binance_global": "BNBUSDT",
        "binance_th": "BNBTHB",
        "bitkub": "THB_BNB",
    },
    "XRP": {
        "binance_global": "XRPUSDT",
        "binance_th": "XRPTHB",
        "bitkub": "THB_XRP",
    },
}


@dataclass
class ExchangePrice:
    """Price data from a single exchange."""
    exchange: str
    symbol: str
    price_thb: float  # Normalized to THB
    price_raw: float  # Original price (USDT or THB)
    timestamp: float
    volume_24h: float = 0.0


@dataclass
class ArbitrageOpportunity:
    """An identified arbitrage opportunity."""
    asset: str
    buy_exchange: str
    sell_exchange: str
    buy_price_thb: float
    sell_price_thb: float
    spread_pct: float  # After fees
    gross_spread_pct: float  # Before fees
    timestamp: float
    executed: bool = False
    pnl_thb: float = 0.0


@dataclass
class PaperTrade:
    """A simulated arbitrage trade."""
    id: str
    asset: str
    buy_exchange: str
    sell_exchange: str
    buy_price_thb: float
    sell_price_thb: float
    quantity: float
    capital_thb: float
    fees_thb: float
    pnl_thb: float
    pnl_pct: float
    opened_at: float
    closed_at: Optional[float] = None


@dataclass
class ArbitrageState:
    """Paper bot state."""
    capital_thb: float = PAPER_CAPITAL_THB
    peak_capital_thb: float = PAPER_CAPITAL_THB
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl_thb: float = 0.0
    total_fees_thb: float = 0.0
    opportunities_found: int = 0
    opportunities_executed: int = 0
    last_scan_at: float = 0.0
    trades: List[dict] = field(default_factory=list)
    recent_opportunities: List[dict] = field(default_factory=list)


class ArbitragePaperBot:
    """
    Paper trading bot for cross-exchange arbitrage.
    
    Monitors price differences between exchanges and simulates
    trades when the spread exceeds fees + minimum profit threshold.
    """

    def __init__(self, redis_client=None):
        self._http: Optional[httpx.AsyncClient] = None
        self._redis = redis_client
        self._running = False
        self._scan_interval = 30  # seconds
        self._state = ArbitrageState()
        self._usdt_thb_rate: float = 0.0  # Cached USDT/THB rate
        self._usdt_thb_updated: float = 0.0
        self._bitkub_cache: Dict[str, float] = {}  # symbol -> last price
        self._bitkub_updated: float = 0.0
        
        # Load state from Redis
        self._state_key = "arbitrage_paper:state"

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=15.0)
        return self._http

    async def start(self):
        """Start the arbitrage paper bot."""
        await self._load_state()
        self._running = True
        logger.info(
            "[ArbPaper] Started — capital=%.2f THB, scan_interval=%ds, min_spread=%.2f%%",
            self._state.capital_thb, self._scan_interval, MIN_SPREAD_PCT
        )
        asyncio.create_task(self._main_loop())

    async def stop(self):
        """Stop the arbitrage paper bot."""
        self._running = False
        if self._http and not self._http.is_closed:
            await self._http.aclose()
        logger.info("[ArbPaper] Stopped")

    async def _main_loop(self):
        """Main scanning loop."""
        while self._running:
            try:
                await self._scan_once()
                await self._save_state()
            except Exception as e:
                logger.error("[ArbPaper] Loop error: %s", e, exc_info=True)
            await asyncio.sleep(self._scan_interval)

    async def _scan_once(self):
        """Scan all pairs for arbitrage opportunities."""
        client = await self._get_client()
        
        # Update USDT/THB rate first (needed for Binance Global conversion)
        await self._update_usdt_thb_rate(client)
        
        for asset, symbols in ARBITRAGE_PAIRS.items():
            try:
                prices = await self._fetch_all_prices(client, asset, symbols)
                if len(prices) < 2:
                    continue
                
                # Find best arbitrage
                opp = self._find_arbitrage(asset, prices)
                if opp:
                    self._state.opportunities_found += 1
                    self._state.recent_opportunities.append({
                        "asset": opp.asset,
                        "buy_exchange": opp.buy_exchange,
                        "sell_exchange": opp.sell_exchange,
                        "buy_price": opp.buy_price_thb,
                        "sell_price": opp.sell_price_thb,
                        "spread_pct": opp.spread_pct,
                        "timestamp": datetime.fromtimestamp(opp.timestamp, tz=timezone.utc).isoformat(),
                    })
                    # Keep only last 50 opportunities
                    self._state.recent_opportunities = self._state.recent_opportunities[-50:]
                    
                    # Execute paper trade if profitable
                    if opp.spread_pct > 0 and self._state.capital_thb > 100:
                        await self._execute_paper_trade(opp)
                
            except Exception as e:
                logger.warning("[ArbPaper] Error scanning %s: %s", asset, e)
        
        self._state.last_scan_at = time.time()

    async def _update_usdt_thb_rate(self, client: httpx.AsyncClient):
        """Fetch USDT/THB rate from Binance TH."""
        # Cache for 5 minutes
        if self._usdt_thb_rate > 0 and (time.time() - self._usdt_thb_updated) < 300:
            return
        
        try:
            resp = await client.get(
                f"{BINANCE_TH}/api/v1/ticker/price",
                params={"symbol": "USDTTHB"}
            )
            if resp.status_code == 200:
                self._usdt_thb_rate = float(resp.json()["price"])
                self._usdt_thb_updated = time.time()
                logger.debug("[ArbPaper] USDT/THB rate: %.4f", self._usdt_thb_rate)
        except Exception as e:
            logger.warning("[ArbPaper] Failed to fetch USDT/THB rate: %s", e)
            # Fallback: use approximate rate
            if self._usdt_thb_rate == 0:
                self._usdt_thb_rate = 34.5  # Approximate fallback

    async def _fetch_all_prices(
        self, client: httpx.AsyncClient, asset: str, symbols: Dict[str, str]
    ) -> List[ExchangePrice]:
        """Fetch prices from all exchanges for an asset."""
        prices = []
        now = time.time()
        
        # Binance Global (USDT → THB)
        if "binance_global" in symbols:
            try:
                resp = await client.get(
                    f"{BINANCE_GLOBAL}/api/v3/ticker/price",
                    params={"symbol": symbols["binance_global"]}
                )
                if resp.status_code == 200:
                    raw_price = float(resp.json()["price"])
                    thb_price = raw_price * self._usdt_thb_rate
                    prices.append(ExchangePrice(
                        exchange="binance_global",
                        symbol=symbols["binance_global"],
                        price_thb=thb_price,
                        price_raw=raw_price,
                        timestamp=now,
                    ))
            except Exception as e:
                logger.debug("[ArbPaper] Binance Global %s error: %s", asset, e)
        
        # Binance Thailand (THB)
        if "binance_th" in symbols:
            try:
                resp = await client.get(
                    f"{BINANCE_TH}/api/v1/ticker/price",
                    params={"symbol": symbols["binance_th"]}
                )
                if resp.status_code == 200:
                    raw_price = float(resp.json()["price"])
                    prices.append(ExchangePrice(
                        exchange="binance_th",
                        symbol=symbols["binance_th"],
                        price_thb=raw_price,
                        price_raw=raw_price,
                        timestamp=now,
                    ))
            except Exception as e:
                logger.debug("[ArbPaper] Binance TH %s error: %s", asset, e)
        
        # Bitkub (THB) — fetch all tickers once, cache 30s
        if "bitkub" in symbols:
            try:
                if (time.time() - self._bitkub_updated) > 30 or not self._bitkub_cache:
                    resp = await client.get(f"{BITKUB}/api/market/ticker")
                    if resp.status_code == 200:
                        data = resp.json()
                        for sym_key, ticker_info in data.items():
                            last = float(ticker_info.get("last", 0))
                            if last > 0:
                                self._bitkub_cache[sym_key] = last
                        self._bitkub_updated = time.time()
                
                raw_price = self._bitkub_cache.get(symbols["bitkub"], 0)
                if raw_price > 0:
                    prices.append(ExchangePrice(
                        exchange="bitkub",
                        symbol=symbols["bitkub"],
                        price_thb=raw_price,
                        price_raw=raw_price,
                        timestamp=now,
                    ))
            except Exception as e:
                logger.debug("[ArbPaper] Bitkub %s error: %s", asset, e)
        
        return prices

    def _find_arbitrage(self, asset: str, prices: List[ExchangePrice]) -> Optional[ArbitrageOpportunity]:
        """Find the best arbitrage opportunity among prices."""
        if len(prices) < 2:
            return None
        
        # Sort by price (cheapest first)
        sorted_prices = sorted(prices, key=lambda p: p.price_thb)
        cheapest = sorted_prices[0]
        most_expensive = sorted_prices[-1]
        
        # Calculate spreads
        gross_spread_pct = ((most_expensive.price_thb - cheapest.price_thb) / cheapest.price_thb) * 100
        net_spread_pct = gross_spread_pct - (ROUND_TRIP_FEE_PCT * 100)
        
        return ArbitrageOpportunity(
            asset=asset,
            buy_exchange=cheapest.exchange,
            sell_exchange=most_expensive.exchange,
            buy_price_thb=cheapest.price_thb,
            sell_price_thb=most_expensive.price_thb,
            spread_pct=net_spread_pct,
            gross_spread_pct=gross_spread_pct,
            timestamp=time.time(),
        )

    async def _execute_paper_trade(self, opp: ArbitrageOpportunity):
        """Execute a simulated arbitrage trade."""
        # Use 10% of available capital per trade
        trade_capital = min(self._state.capital_thb * 0.1, 2000)  # Max 2000 THB per trade
        
        if trade_capital < 100:
            return  # Too small to trade
        
        # Calculate quantity
        quantity = trade_capital / opp.buy_price_thb
        
        # Calculate fees
        buy_notional = trade_capital
        sell_notional = quantity * opp.sell_price_thb
        fees = (buy_notional + sell_notional) * TRADING_FEE_PCT
        
        # Calculate PnL
        gross_profit = sell_notional - buy_notional
        net_profit = gross_profit - fees
        
        # Update state
        self._state.capital_thb += net_profit
        self._state.total_trades += 1
        self._state.total_pnl_thb += net_profit
        self._state.total_fees_thb += fees
        self._state.opportunities_executed += 1
        
        if net_profit > 0:
            self._state.winning_trades += 1
        else:
            self._state.losing_trades += 1
        
        if self._state.capital_thb > self._state.peak_capital_thb:
            self._state.peak_capital_thb = self._state.capital_thb
        
        # Record trade
        trade = {
            "id": f"arb_{self._state.total_trades:04d}",
            "asset": opp.asset,
            "buy_exchange": opp.buy_exchange,
            "sell_exchange": opp.sell_exchange,
            "buy_price": opp.buy_price_thb,
            "sell_price": opp.sell_price_thb,
            "quantity": quantity,
            "capital": trade_capital,
            "fees": fees,
            "pnl": net_profit,
            "pnl_pct": (net_profit / trade_capital) * 100,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._state.trades.append(trade)
        # Keep only last 100 trades
        self._state.trades = self._state.trades[-100:]
        
        opp.executed = True
        opp.pnl_thb = net_profit
        
        logger.info(
            "[ArbPaper] TRADE #%d: %s | Buy %s @ %.2f → Sell %s @ %.2f | "
            "PnL: %.2f THB (%.3f%%) | Capital: %.2f THB",
            self._state.total_trades,
            opp.asset,
            opp.buy_exchange, opp.buy_price_thb,
            opp.sell_exchange, opp.sell_price_thb,
            net_profit, (net_profit / trade_capital) * 100,
            self._state.capital_thb,
        )

    async def _save_state(self):
        """Save state to Redis."""
        if not self._redis:
            return
        try:
            state_dict = {
                "capital_thb": self._state.capital_thb,
                "peak_capital_thb": self._state.peak_capital_thb,
                "total_trades": self._state.total_trades,
                "winning_trades": self._state.winning_trades,
                "losing_trades": self._state.losing_trades,
                "total_pnl_thb": self._state.total_pnl_thb,
                "total_fees_thb": self._state.total_fees_thb,
                "opportunities_found": self._state.opportunities_found,
                "opportunities_executed": self._state.opportunities_executed,
                "last_scan_at": self._state.last_scan_at,
                "trades": self._state.trades[-20:],  # Last 20 trades
                "recent_opportunities": self._state.recent_opportunities[-20:],  # Last 20 opps
            }
            await self._redis.set(self._state_key, json.dumps(state_dict))
        except Exception as e:
            logger.warning("[ArbPaper] Failed to save state: %s", e)

    async def _load_state(self):
        """Load state from Redis."""
        if not self._redis:
            return
        try:
            data = await self._redis.get(self._state_key)
            if data:
                state_dict = json.loads(data)
                self._state.capital_thb = state_dict.get("capital_thb", PAPER_CAPITAL_THB)
                self._state.peak_capital_thb = state_dict.get("peak_capital_thb", PAPER_CAPITAL_THB)
                self._state.total_trades = state_dict.get("total_trades", 0)
                self._state.winning_trades = state_dict.get("winning_trades", 0)
                self._state.losing_trades = state_dict.get("losing_trades", 0)
                self._state.total_pnl_thb = state_dict.get("total_pnl_thb", 0.0)
                self._state.total_fees_thb = state_dict.get("total_fees_thb", 0.0)
                self._state.opportunities_found = state_dict.get("opportunities_found", 0)
                self._state.opportunities_executed = state_dict.get("opportunities_executed", 0)
                self._state.trades = state_dict.get("trades", [])
                self._state.recent_opportunities = state_dict.get("recent_opportunities", [])
                logger.info(
                    "[ArbPaper] Loaded state — capital=%.2f THB, trades=%d, PnL=%.2f THB",
                    self._state.capital_thb, self._state.total_trades, self._state.total_pnl_thb
                )
        except Exception as e:
            logger.warning("[ArbPaper] Failed to load state: %s", e)

    def get_status(self) -> dict:
        """Get current bot status."""
        drawdown_pct = 0.0
        if self._state.peak_capital_thb > 0:
            drawdown_pct = ((self._state.peak_capital_thb - self._state.capital_thb) / self._state.peak_capital_thb) * 100
        
        win_rate = 0.0
        if self._state.total_trades > 0:
            win_rate = (self._state.winning_trades / self._state.total_trades) * 100
        
        return {
            "running": self._running,
            "capital_thb": round(self._state.capital_thb, 2),
            "peak_capital_thb": round(self._state.peak_capital_thb, 2),
            "pnl_thb": round(self._state.total_pnl_thb, 2),
            "pnl_pct": round((self._state.total_pnl_thb / PAPER_CAPITAL_THB) * 100, 3),
            "drawdown_pct": round(drawdown_pct, 2),
            "total_trades": self._state.total_trades,
            "winning_trades": self._state.winning_trades,
            "losing_trades": self._state.losing_trades,
            "win_rate": round(win_rate, 1),
            "total_fees_thb": round(self._state.total_fees_thb, 2),
            "opportunities_found": self._state.opportunities_found,
            "opportunities_executed": self._state.opportunities_executed,
            "last_scan_at": self._state.last_scan_at,
            "usdt_thb_rate": round(self._usdt_thb_rate, 4) if self._usdt_thb_rate else None,
            "min_spread_pct": MIN_SPREAD_PCT,
            "scan_interval_sec": self._scan_interval,
            "recent_trades": self._state.trades[-5:],  # Last 5 trades
            "recent_opportunities": self._state.recent_opportunities[-5:],  # Last 5 opps
        }

    def reset(self):
        """Reset paper bot state."""
        self._state = ArbitrageState()
        if self._redis:
            asyncio.create_task(self._redis.delete(self._state_key))
        logger.info("[ArbPaper] State reset")


# Singleton instance
_arb_paper_bot: Optional[ArbitragePaperBot] = None


def get_arb_paper_bot() -> ArbitragePaperBot:
    """Get or create the singleton arbitrage paper bot."""
    global _arb_paper_bot
    if _arb_paper_bot is None:
        _arb_paper_bot = ArbitragePaperBot()
    return _arb_paper_bot
