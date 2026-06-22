"""
Polymarket Paper Trading Bot — Multi-Signal Alpha Engine.

Scans prediction markets for multiple alpha signals:
1. Mispricing: Yes+No deviation > threshold (arbitrage edge)
2. Momentum: Price trending toward 1.0 (likely winner, ride the trend)
3. Time-decay: Near resolution with high confidence (safe bets)
4. Extreme value: Cheap YES/NO with real probability (asymmetric payoff)
5. Volume spike: Sudden volume increase (smart money moving)
6. Cross-market: Crypto/stock moves predicting Polymarket outcomes

Strategy:
- Score each market across all signals
- Enter positions on highest-confidence opportunities
- Track P&L as prices move
- Auto-resolve when markets close

Author: BookFinance Strategy Module
"""
import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple

import httpx

logger = logging.getLogger("poly_bot")

# ── Configuration ──────────────────────────────────────────────────────────────

GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"

# Paper trading defaults — tuned for alpha
DEFAULT_SCAN_INTERVAL = 120  # 2 minutes (faster = catch moves quicker)
DEFAULT_MAX_POSITIONS = 15  # more positions for diversification
DEFAULT_POSITION_SIZE_USDC = 5.0  # $5 per position (paper)
DEFAULT_MIN_DEVIATION = 0.002  # 0.2% mispricing threshold (Polymarket is efficient)
DEFAULT_MIN_LIQUIDITY = 200  # min $200 liquidity (was $500)
DEFAULT_MIN_VOLUME = 500  # min $500 volume (was $1000)

# Kelly criterion for position sizing
KELLY_FRACTION = 0.25  # quarter-Kelly (conservative)
DEFAULT_BANKROLL_USDC = 100.0  # starting paper bankroll
MIN_BANKROLL_USDC = 10.0  # minimum bankroll before we stop trading

# Alpha signal weights (confidence scoring)
SIGNAL_WEIGHTS = {
    "mispricing": 0.15,
    "momentum": 0.15,
    "time_decay": 0.15,
    "extreme_value": 0.08,
    "volume_spike": 0.10,
    "cross_market": 0.10,
    "news_sentiment": 0.12,
    "liquidity_alpha": 0.15,
}

# Max positions per signal type (diversity cap)
MAX_POSITIONS_PER_SIGNAL = 4

# Minimum confidence to enter a position
MIN_ENTRY_CONFIDENCE = 0.40

# Exit logic
TAKE_PROFIT_PCT = 0.20  # 20% gain → close
STOP_LOSS_PCT = -0.15  # 15% loss → close
MAX_HOLD_DAYS = 14  # force close after 14 days if no edge

# News RSS feeds for sentiment signal
NEWS_FEEDS = [
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "https://feeds.reuters.com/reuters/worldNews",
    "https://feeds.bbci.co.uk/news/politics/rss.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
]


@dataclass
class PaperPosition:
    """Simulated position in a prediction market."""
    position_id: str
    market_id: str
    question: str
    side: str  # "YES" or "NO"
    entry_price: float
    current_price: float
    size_usdc: float
    shares: float  # size_usdc / entry_price
    entry_time: float
    last_update_time: float
    event_title: str = ""
    end_date: Optional[str] = None
    resolved: bool = False
    pnl: float = 0.0
    pnl_pct: float = 0.0
    signals: List[str] = field(default_factory=list)  # which signals triggered
    confidence: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "position_id": self.position_id,
            "market_id": self.market_id,
            "question": self.question,
            "side": self.side,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "size_usdc": self.size_usdc,
            "shares": self.shares,
            "entry_time": self.entry_time,
            "last_update_time": self.last_update_time,
            "event_title": self.event_title,
            "end_date": self.end_date,
            "resolved": self.resolved,
            "pnl": round(self.pnl, 4),
            "pnl_pct": round(self.pnl_pct, 4),
            "signals": self.signals,
            "confidence": round(self.confidence, 3),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "PaperPosition":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class PaperTrade:
    """Record of a paper trade execution."""
    trade_id: str
    position_id: str
    market_id: str
    question: str
    side: str
    action: str  # "OPEN" or "CLOSE"
    price: float
    size_usdc: float
    shares: float
    pnl: float
    timestamp: float
    signals: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "trade_id": self.trade_id,
            "position_id": self.position_id,
            "market_id": self.market_id,
            "question": self.question,
            "side": self.side,
            "action": self.action,
            "price": self.price,
            "size_usdc": self.size_usdc,
            "shares": self.shares,
            "pnl": round(self.pnl, 4),
            "timestamp": self.timestamp,
            "signals": self.signals,
        }


@dataclass
class AlphaSignal:
    """A detected alpha signal for a market."""
    signal_type: str
    market_id: str
    question: str
    side: str  # "YES" or "NO"
    confidence: float  # 0-1
    price: float
    reason: str
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "signal_type": self.signal_type,
            "market_id": self.market_id,
            "question": self.question,
            "side": self.side,
            "confidence": round(self.confidence, 3),
            "price": self.price,
            "reason": self.reason,
            "metadata": self.metadata,
        }


class PolymarketPaperBot:
    """
    Multi-signal alpha engine for Polymarket prediction markets.
    Scores markets across 6 signal dimensions and trades highest-confidence opportunities.
    """

    def __init__(self):
        self.scan_interval = int(os.getenv("POLY_SCAN_INTERVAL", str(DEFAULT_SCAN_INTERVAL)))
        self.max_positions = int(os.getenv("POLY_MAX_POSITIONS", str(DEFAULT_MAX_POSITIONS)))
        self.position_size = float(os.getenv("POLY_POSITION_SIZE", str(DEFAULT_POSITION_SIZE_USDC)))
        self.min_deviation = float(os.getenv("POLY_MIN_DEVIATION", str(DEFAULT_MIN_DEVIATION)))
        self.min_liquidity = float(os.getenv("POLY_MIN_LIQUIDITY", str(DEFAULT_MIN_LIQUIDITY)))
        self.min_volume = float(os.getenv("POLY_MIN_VOLUME", str(DEFAULT_MIN_VOLUME)))

        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._redis = None

        # State
        self.positions: Dict[str, PaperPosition] = {}
        self.trades: List[PaperTrade] = []
        self.total_pnl: float = 0.0
        self.total_trades: int = 0
        self.winning_trades: int = 0
        self.scan_count: int = 0
        self.last_scan_time: float = 0.0
        self.start_time: float = 0.0
        self.opportunities_found: int = 0

        # Bankroll tracking (Kelly criterion)
        self.bankroll: float = float(os.getenv("POLY_BANKROLL", str(DEFAULT_BANKROLL_USDC)))
        self.peak_bankroll: float = self.bankroll

        # Alpha signals feed (recent signals for dashboard)
        self.recent_signals: List[AlphaSignal] = []
        self.max_signals = 500  # increased to capture all signal types

        # Price history for momentum detection (market_id -> [(timestamp, yes_price)])
        self.price_history: Dict[str, List[Tuple[float, float]]] = {}
        self.max_history = 50  # keep last 50 price points per market

        # Volume history for spike detection (market_id -> [volumes])
        self.volume_history: Dict[str, List[float]] = {}
        # Volume delta history for spike detection (market_id -> [deltas])
        self.volume_delta_history: Dict[str, List[float]] = {}

        # Notifications
        self.notifications: List[Dict] = []
        self.max_notifications = 50

        # Cross-market data cache (updated externally or via scan)
        self._crypto_snapshot: Dict[str, float] = {}  # symbol -> change_pct

        # News headlines cache
        self._news_headlines: List[str] = []
        self._news_last_fetch: float = 0.0
        self._news_fetch_interval: float = 600  # fetch news every 10 min

    def set_redis(self, redis):
        """Set Redis connection for state persistence."""
        self._redis = redis

    async def start(self):
        """Start the paper trading bot."""
        if self._running:
            logger.warning("PolymarketPaperBot already running")
            return

        self._running = True
        self.start_time = time.time()
        logger.info(
            "Starting Polymarket Alpha Engine: interval=%ds max_pos=%d size=$%.2f signals=7",
            self.scan_interval, self.max_positions, self.position_size,
        )

        await self._restore_state()
        self._task = asyncio.create_task(self._scan_loop())

    async def stop(self):
        """Stop the paper trading bot."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Polymarket Alpha Engine stopped")

    async def _scan_loop(self):
        """Main scan loop."""
        while self._running:
            try:
                await self._scan_and_trade()
                self.scan_count += 1
                self.last_scan_time = time.time()
                await self._save_state()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Polymarket scan error: %s", e, exc_info=True)

            await asyncio.sleep(self.scan_interval)

    async def _scan_and_trade(self):
        """Single scan cycle: multi-signal alpha detection."""
        logger.info("Alpha scan #%d started", self.scan_count + 1)

        # Fetch active events
        events = await self._fetch_events()
        if not events:
            logger.info("No events fetched, skipping scan")
            return

        # Fetch cross-market data (crypto moves)
        await self._fetch_crypto_snapshot()

        # Fetch news headlines for sentiment signal
        await self._fetch_news_headlines()

        # Analyze each market with multi-signal engine
        all_signals: List[AlphaSignal] = []
        
        # Diagnostic: track dormant signal metrics (run on scan #40 to see actual values)
        diagnostic_scan = (self.scan_count + 1) == 40
        diagnostic_stats = {
            "max_deviation": 0.0,
            "max_price_move": 0.0,
            "max_vol_delta_ratio": 0.0,
            "crypto_keyword_matches": 0,
            "vol_delta_markets": 0,
            "vol_delta_total": 0,
        } if diagnostic_scan else None

        for event in events:
            for market in event.get("markets", []):
                signals = self._analyze_all_signals(market, event)
                if signals:
                    all_signals.extend(signals)
                
                # Diagnostic: collect metrics for dormant signals
                if diagnostic_scan:
                    outcome_prices = market.get("outcomePrices", "[]")
                    if isinstance(outcome_prices, str):
                        try:
                            outcome_prices = json.loads(outcome_prices)
                        except Exception:
                            continue
                    if len(outcome_prices) >= 2:
                        yes_price = float(outcome_prices[0])
                        no_price = float(outcome_prices[1])
                        total = yes_price + no_price
                        dev = abs(total - 1.0)
                        diagnostic_stats["max_deviation"] = max(diagnostic_stats["max_deviation"], dev)
                        
                        mid = market.get("conditionId", "")
                        history = self.price_history.get(mid, [])
                        if len(history) >= 2:
                            recent = [p for _, p in history[-5:]]
                            if len(recent) >= 2:
                                move = abs(recent[-1] - recent[0])
                                diagnostic_stats["max_price_move"] = max(diagnostic_stats["max_price_move"], move)
                        
                        vol_deltas = self.volume_delta_history.get(mid, [])
                        if vol_deltas:
                            diagnostic_stats["vol_delta_markets"] += 1
                            diagnostic_stats["vol_delta_total"] += len(vol_deltas)
                        if len(vol_deltas) >= 2:
                            avg_delta = sum(vol_deltas[-5:]) / len(vol_deltas[-5:])
                            latest_delta = vol_deltas[-1]
                            if avg_delta > 0:
                                ratio = latest_delta / avg_delta
                                diagnostic_stats["max_vol_delta_ratio"] = max(diagnostic_stats["max_vol_delta_ratio"], ratio)
                        
                        # Check crypto keyword match
                        if self._crypto_snapshot:
                            question = market.get("question", "").lower()
                            event_title = event.get("title", "").lower()
                            text = f"{question} {event_title}"
                            words = set(text.split())
                            import re
                            words = {re.sub(r'[^a-z0-9]', '', w) for w in words}
                            crypto_kw = {"bitcoin", "btc", "crypto", "ethereum", "eth", "solana", "sol", "xrp", "ripple", "binance", "bnb", "dogecoin", "doge", "blockchain", "web3", "token", "mining", "defi", "nft"}
                            if any(kw in words for kw in crypto_kw):
                                diagnostic_stats["crypto_keyword_matches"] += 1
        
        if diagnostic_scan and diagnostic_stats:
            logger.info("=== DIAGNOSTIC SCAN #40 ===")
            logger.info("Max mispricing deviation: %.4f (threshold: %.4f)", diagnostic_stats["max_deviation"], self.min_deviation)
            logger.info("Max price move in history: %.4f (threshold: 0.005)", diagnostic_stats["max_price_move"])
            logger.info("Volume delta markets: %d, total deltas: %d, max ratio: %.2f (threshold: 1.5)",
                        diagnostic_stats["vol_delta_markets"], diagnostic_stats["vol_delta_total"],
                        diagnostic_stats["max_vol_delta_ratio"])
            logger.info("Crypto keyword matches: %d (crypto tracking: %s)", diagnostic_stats["crypto_keyword_matches"], "yes" if self._crypto_snapshot else "no")
            logger.info("Crypto snapshot: %s", {k: round(v, 2) for k, v in self._crypto_snapshot.items()} if self._crypto_snapshot else "EMPTY")

        # Record recent signals
        self.recent_signals = all_signals[:self.max_signals]

        # Score and rank opportunities
        scored = self._score_opportunities(all_signals)

        # Enter positions on top opportunities (with signal diversity cap)
        entered = 0
        signal_type_counts = {}
        for pos in self.positions.values():
            if not pos.resolved:
                for sig in pos.signals:
                    signal_type_counts[sig] = signal_type_counts.get(sig, 0) + 1

        for opp in scored:
            if opp["confidence"] >= MIN_ENTRY_CONFIDENCE:
                # Check diversity cap: don't over-concentrate on one signal type
                primary_signal = opp["signals"][0] if opp["signals"] else "unknown"
                if signal_type_counts.get(primary_signal, 0) >= MAX_POSITIONS_PER_SIGNAL:
                    continue  # skip — already have enough of this signal type
                success = await self._maybe_enter(opp, events)
                if success:
                    entered += 1
                    signal_type_counts[primary_signal] = signal_type_counts.get(primary_signal, 0) + 1

        # Update existing positions with latest prices
        await self._update_positions(events)

        # Update price/volume history
        self._update_history(events)

        self.opportunities_found += len(scored)

        logger.info(
            "Alpha scan #%d: events=%d signals=%d opportunities=%d entered=%d pnl=$%.4f",
            self.scan_count + 1, len(events), len(all_signals),
            len(scored), entered, self.total_pnl,
        )
        
        # Debug logging: signal confidence distribution every 5 scans
        if (self.scan_count + 1) % 5 == 0 and all_signals:
            from collections import defaultdict
            sig_stats = defaultdict(lambda: {"count": 0, "min_conf": 1.0, "max_conf": 0.0, "sum_conf": 0.0})
            for sig in all_signals:
                stats = sig_stats[sig.signal_type]
                stats["count"] += 1
                stats["min_conf"] = min(stats["min_conf"], sig.confidence)
                stats["max_conf"] = max(stats["max_conf"], sig.confidence)
                stats["sum_conf"] += sig.confidence
            for sig_type, stats in sorted(sig_stats.items()):
                avg_conf = stats["sum_conf"] / stats["count"] if stats["count"] > 0 else 0
                logger.info(
                    "Signal debug #%d: %s count=%d conf_min=%.3f conf_max=%.3f conf_avg=%.3f",
                    self.scan_count + 1, sig_type, stats["count"],
                    stats["min_conf"], stats["max_conf"], avg_conf,
                )
            # Volume delta accumulation stats
            vd_counts = [len(v) for v in self.volume_delta_history.values() if v]
            logger.info(
                "Volume delta #%d: markets_with_deltas=%d total_deltas=%d max_deltas_per_market=%d",
                self.scan_count + 1, len(vd_counts), sum(vd_counts),
                max(vd_counts) if vd_counts else 0,
            )

    def _analyze_all_signals(self, market: Dict, event: Dict) -> List[AlphaSignal]:
        """Run all signal detectors on a market."""
        signals = []

        # Parse prices
        outcome_prices = market.get("outcomePrices", "[]")
        if isinstance(outcome_prices, str):
            try:
                outcome_prices = json.loads(outcome_prices)
            except Exception:
                return []

        if len(outcome_prices) < 2:
            return []

        yes_price = float(outcome_prices[0])
        no_price = float(outcome_prices[1])
        total = yes_price + no_price
        volume = float(market.get("volume", 0) or 0)
        liquidity = float(market.get("liquidity", 0) or 0)
        market_id = market.get("conditionId", "")
        question = market.get("question", "")
        end_date = market.get("endDate", "")

        if total == 0:
            return []

        # Skip very low liquidity/volume markets
        if volume < self.min_volume * 0.5 or liquidity < self.min_liquidity * 0.5:
            return []

        # Signal 1: Mispricing (Yes + No != 1.0)
        deviation = abs(total - 1.0)
        if deviation >= self.min_deviation:
            side = "YES" if yes_price <= no_price else "NO"
            entry_price = yes_price if side == "YES" else no_price
            conf = min(deviation * 200, 1.0)  # 0.2% dev = 0.40 conf, 0.5% = 1.0
            signals.append(AlphaSignal(
                signal_type="mispricing",
                market_id=market_id,
                question=question,
                side=side,
                confidence=conf,
                price=entry_price,
                reason=f"Yes+No={total:.4f} (dev={deviation:.2%}). Buy {side} @ {entry_price:.3f}",
                metadata={"deviation": deviation, "total": total, "yes_price": yes_price, "no_price": no_price},
            ))
        elif deviation > 0.001:  # Log near-misses for debugging
            logger.debug(f"Mispricing near-miss: dev={deviation:.4f} < {self.min_deviation} for {question[:40]}")

        # Signal 2: Momentum (price trending — detect early moves)
        history = self.price_history.get(market_id, [])
        if len(history) >= 2:  # lowered from 3 to catch earlier moves
            recent_prices = [p for _, p in history[-5:]]
            if len(recent_prices) >= 2:
                trend_yes = recent_prices[-1] - recent_prices[0]
                if abs(trend_yes) > 0.005:  # >0.5% move (lowered from 1%)
                    if trend_yes > 0 and yes_price > 0.30:  # lowered from 0.50
                        conf = min(abs(trend_yes) * 50, 0.85)  # 1% = 0.50, 2% = 0.85
                        signals.append(AlphaSignal(
                            signal_type="momentum",
                            market_id=market_id,
                            question=question,
                            side="YES",
                            confidence=conf,
                            price=yes_price,
                            reason=f"YES momentum: {recent_prices[0]:.3f} → {yes_price:.3f} (+{trend_yes:.1%})",
                            metadata={"trend": trend_yes, "history_len": len(history)},
                        ))
                    elif trend_yes < 0 and no_price > 0.30:  # lowered from 0.50
                        conf = min(abs(trend_yes) * 50, 0.85)  # 1% = 0.50, 2% = 0.85
                        signals.append(AlphaSignal(
                            signal_type="momentum",
                            market_id=market_id,
                            question=question,
                            side="NO",
                            confidence=conf,
                            price=no_price,
                            reason=f"NO momentum: YES dropping {trend_yes:.1%}, NO rising",
                            metadata={"trend": trend_yes, "history_len": len(history)},
                        ))

        # Signal 3: Time-decay (near resolution with high confidence price)
        if end_date and yes_price > 0:
            try:
                from datetime import datetime
                end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                now = datetime.now(end_dt.tzinfo) if end_dt.tzinfo else datetime.utcnow()
                days_to_end = (end_dt - now).total_seconds() / 86400

                if 0 < days_to_end < 7:  # within 7 days of resolution
                    if yes_price > 0.85 or yes_price < 0.15:
                        # High confidence near resolution — likely to resolve in favor
                        side = "YES" if yes_price > 0.85 else "NO"
                        entry_price = yes_price if side == "YES" else no_price
                        # Closer to resolution + higher confidence = higher signal
                        time_factor = max(0.3, 1.0 - days_to_end / 7)
                        price_factor = abs(entry_price - 0.5) * 4  # 0.85 → 0.14, 0.95 → 0.18
                        conf = min(time_factor * price_factor * 3, 0.95)
                        signals.append(AlphaSignal(
                            signal_type="time_decay",
                            market_id=market_id,
                            question=question,
                            side=side,
                            confidence=conf,
                            price=entry_price,
                            reason=f"Resolves in {days_to_end:.1f}d. {side} @ {entry_price:.3f} likely to win.",
                            metadata={"days_to_end": days_to_end, "end_date": end_date},
                        ))
            except Exception:
                pass

        # Signal 4: Extreme value (cheap side with REAL probability — not lottery tickets)
        if 0.03 < yes_price < 0.20 and volume > self.min_volume * 2:
            # YES is cheap but has significant volume = market sees real chance
            # Quality filter: higher volume = more confident signal
            vol_quality = min(volume / 10000, 1.0)  # $10k+ vol = full quality
            conf = min((0.20 - yes_price) * 3 * vol_quality, 0.65)
            if conf > 0.20:
                signals.append(AlphaSignal(
                    signal_type="extreme_value",
                    market_id=market_id,
                    question=question,
                    side="YES",
                    confidence=conf,
                    price=yes_price,
                    reason=f"Value: YES @ {yes_price:.3f} (potential {1/yes_price:.1f}x). Vol=${volume:.0f} quality={vol_quality:.0%}",
                    metadata={"upside": 1 / yes_price if yes_price > 0 else 0, "vol_quality": vol_quality},
                ))
        if 0.03 < no_price < 0.20 and volume > self.min_volume * 2:
            vol_quality = min(volume / 10000, 1.0)
            conf = min((0.20 - no_price) * 3 * vol_quality, 0.65)
            if conf > 0.20:
                signals.append(AlphaSignal(
                    signal_type="extreme_value",
                    market_id=market_id,
                    question=question,
                    side="NO",
                    confidence=conf,
                    price=no_price,
                    reason=f"Value: NO @ {no_price:.3f} (potential {1/no_price:.1f}x). Vol=${volume:.0f} quality={vol_quality:.0%}",
                    metadata={"upside": 1 / no_price if no_price > 0 else 0, "vol_quality": vol_quality},
                ))

        # Signal 5: Volume spike (sudden increase in volume rate = smart money)
        # Use volume deltas (rate of change) instead of cumulative volume
        vol_deltas = self.volume_delta_history.get(market_id, [])
        if len(vol_deltas) >= 2:
            avg_delta = sum(vol_deltas[-5:]) / len(vol_deltas[-5:])
            latest_delta = vol_deltas[-1]
            if avg_delta > 0 and latest_delta > avg_delta * 1.5:
                spike_ratio = latest_delta / avg_delta
                conf = min((spike_ratio - 1.0) * 2.0, 0.8)  # 1.5x = 0.50, 2x = 0.80
                # Buy the side that's favored by price
                side = "YES" if yes_price > 0.5 else "NO"
                entry_price = yes_price if side == "YES" else no_price
                signals.append(AlphaSignal(
                    signal_type="volume_spike",
                    market_id=market_id,
                    question=question,
                    side=side,
                    confidence=conf,
                    price=entry_price,
                    reason=f"Volume spike: delta ${latest_delta:.0f} vs avg ${avg_delta:.0f} ({spike_ratio:.1f}x). Smart money on {side}.",
                    metadata={"latest_delta": latest_delta, "avg_delta": avg_delta, "spike_ratio": spike_ratio},
                ))

        # Signal 6: Cross-market correlation (crypto moves → prediction markets)
        if self._crypto_snapshot:
            q_lower = question.lower()
            event_title = event.get("title", "").lower()
            # Combine question + event title for broader matching
            text_to_search = f"{q_lower} {event_title}"
            # Use word boundary matching to avoid false positives (e.g., "sol" in "dissolved")
            q_words = set(text_to_search.split())
            # Strip punctuation from words for cleaner matching
            import re
            q_words = {re.sub(r'[^a-z0-9]', '', w) for w in q_words}
            crypto_keywords = {
                "bitcoin": "BTCUSDT", "btc": "BTCUSDT", "crypto": "BTCUSDT",
                "ethereum": "ETHUSDT", "eth": "ETHUSDT",
                "solana": "SOLUSDT", "sol": "SOLUSDT",
                "xrp": "XRPUSDT", "ripple": "XRPUSDT",
                "binance": "BNBUSDT", "bnb": "BNBUSDT",
                "dogecoin": "DOGEUSDT", "doge": "DOGEUSDT",
                "stablecoin": "BTCUSDT", "usdt": "BTCUSDT", "usdc": "BTCUSDT",
                "defi": "ETHUSDT", "nft": "ETHUSDT",
                # Broader crypto-related terms
                "blockchain": "BTCUSDT", "web3": "ETHUSDT", "token": "BTCUSDT",
                "mining": "BTCUSDT", "halving": "BTCUSDT", "satoshi": "BTCUSDT",
            }
            matched_symbol = None
            for keyword, symbol in crypto_keywords.items():
                if keyword in q_words:  # exact word match only
                    matched_symbol = symbol
                    break
            
            if matched_symbol and self.scan_count < 50:
                logger.info("Cross-market keyword hit: '%s' -> %s, crypto_change=%s, yes=%.3f",
                            matched_symbol, matched_symbol,
                            self._crypto_snapshot.get(matched_symbol, '?'), yes_price)

            if matched_symbol and matched_symbol in self._crypto_snapshot:
                crypto_change = self._crypto_snapshot[matched_symbol]
                if abs(crypto_change) > 0.1:  # >0.1% move in crypto
                    # If crypto pumped, YES for "will BTC hit X?" should be more likely
                    if crypto_change > 0 and yes_price < 0.85:
                        conf = min(abs(crypto_change) * 5.0, 0.75)  # 0.1% = 0.50, 0.15%+ = 0.75 (capped)
                        signals.append(AlphaSignal(
                            signal_type="cross_market",
                            market_id=market_id,
                            question=question,
                            side="YES",
                            confidence=conf,
                            price=yes_price,
                            reason=f"{matched_symbol} up {crypto_change:.1f}% — {question[:40]} more likely YES",
                            metadata={"crypto_symbol": matched_symbol, "crypto_change": crypto_change},
                        ))
                    elif crypto_change < 0 and yes_price > 0.15:
                        conf = min(abs(crypto_change) * 5.0, 0.75)  # 0.1% = 0.50, 0.15%+ = 0.75 (capped)
                        signals.append(AlphaSignal(
                            signal_type="cross_market",
                            market_id=market_id,
                            question=question,
                            side="NO",
                            confidence=conf,
                            price=no_price,
                            reason=f"{matched_symbol} down {abs(crypto_change):.1f}% — {question[:40]} more likely NO",
                            metadata={"crypto_symbol": matched_symbol, "crypto_change": crypto_change},
                        ))
                elif self.scan_count < 50:  # Debug: log near-misses while tuning
                    logger.info("Cross-market near-miss: %s change=%.2f%% (threshold: 0.1%%) for %s",
                                matched_symbol, crypto_change, question[:50])

        # Signal 7: News sentiment (breaking news matching market keywords)
        if self._news_headlines:
            # Lower threshold: 3+ char words for better entity matching (Ukraine, Trump, BTC, etc.)
            q_words = set(w.lower() for w in question.split() if len(w) >= 3)
            # Remove common stop words
            stop_words = {"the", "and", "for", "are", "but", "not", "you", "all", "can", "had", "her", "was", "one", "our", "out", "has", "have", "been", "some", "them", "than", "its", "over", "such", "that", "this", "with", "will", "each", "from", "they", "into", "would", "when", "what", "there", "their", "which", "could", "going", "about", "after", "before", "between", "through", "under", "until", "where", "while", "will", "by", "do", "if", "in", "is", "it", "of", "on", "to", "up", "as", "at", "an", "or"}
            q_words -= stop_words
            if q_words:
                for headline in self._news_headlines:
                    h_lower = headline.lower()
                    # Count matching words (substring match for entities)
                    matches = sum(1 for w in q_words if w in h_lower)
                    if matches >= 1:  # at least 1 meaningful word match
                        # More matches = higher confidence
                        sentiment_boost = min(0.25 + matches * 0.12, 0.65)
                        if yes_price > 0.4:
                            signals.append(AlphaSignal(
                                signal_type="news_sentiment",
                                market_id=market_id,
                                question=question,
                                side="YES",
                                confidence=sentiment_boost,
                                price=yes_price,
                                reason=f"News match ({matches} words): \"{headline[:60]}\" → YES likely",
                                metadata={"matching_words": matches, "headline": headline[:80]},
                            ))
                        elif no_price > 0.4:
                            signals.append(AlphaSignal(
                                signal_type="news_sentiment",
                                market_id=market_id,
                                question=question,
                                side="NO",
                                confidence=sentiment_boost,
                                price=no_price,
                                reason=f"News match ({matches} words): \"{headline[:60]}\" → NO likely",
                                metadata={"matching_words": matches, "headline": headline[:80]},
                            ))
                        break  # only use first matching headline

        # Signal 8: Liquidity alpha (illiquid market + high price = stale odds, edge)
        # If liquidity is low but volume is decent, market may be mispriced
        if liquidity > 0 and volume > self.min_volume * 3:
            liq_ratio = liquidity / volume
            if liq_ratio < 0.05:  # very low liquidity relative to volume = stale market
                # Price is likely stale — bet toward 0.50 (mean reversion)
                if yes_price > 0.70:
                    side = "NO"
                    entry_price = no_price
                    dist = yes_price - 0.50
                elif 0.05 < yes_price < 0.30:  # min 5c floor — no lottery tickets
                    side = "YES"
                    entry_price = yes_price
                    dist = 0.50 - yes_price
                else:
                    side = None
                    entry_price = 0
                    dist = 0

                if side and dist > 0.05:
                    conf = min(dist * 2 * (1.0 / max(liq_ratio * 10, 0.1)), 0.70)
                    if conf > 0.20:
                        signals.append(AlphaSignal(
                            signal_type="liquidity_alpha",
                            market_id=market_id,
                            question=question,
                            side=side,
                            confidence=conf,
                            price=entry_price,
                            reason=f"Stale market: liq/vol={liq_ratio:.3f}, price={entry_price:.3f}. Mean reversion to 0.50.",
                            metadata={"liq_vol_ratio": liq_ratio, "distance_to_mid": dist},
                        ))

        return signals

    def _score_opportunities(self, signals: List[AlphaSignal]) -> List[Dict]:
        """Aggregate signals per market and rank by composite confidence."""
        # Group signals by (market_id, side)
        grouped: Dict[Tuple[str, str], List[AlphaSignal]] = {}
        for sig in signals:
            key = (sig.market_id, sig.side)
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(sig)

        scored = []
        for (market_id, side), sigs in grouped.items():
            # Weighted composite confidence
            total_weight = 0
            weighted_conf = 0
            signal_types = []
            best_price = 0

            for sig in sigs:
                weight = SIGNAL_WEIGHTS.get(sig.signal_type, 0.1)
                weighted_conf += sig.confidence * weight
                total_weight += weight
                signal_types.append(sig.signal_type)
                best_price = sig.price

            composite_conf = weighted_conf / total_weight if total_weight > 0 else 0

            # Bonus for multiple signals agreeing
            if len(sigs) >= 3:
                composite_conf = min(composite_conf * 1.3, 1.0)
            elif len(sigs) >= 2:
                composite_conf = min(composite_conf * 1.15, 1.0)

            scored.append({
                "market_id": market_id,
                "side": side,
                "confidence": composite_conf,
                "price": best_price,
                "signals": signal_types,
                "signal_count": len(sigs),
                "question": sigs[0].question,
                "event_title": sigs[0].metadata.get("event_title", ""),
                "reasons": [s.reason for s in sigs],
            })

        # Sort by confidence descending
        scored.sort(key=lambda x: -x["confidence"])
        return scored

    def _kelly_size(self, confidence: float, price: float) -> float:
        """Calculate position size using quarter-Kelly criterion.
        
        Kelly formula: f* = (bp - q) / b
        where b = odds (payout / stake), p = win prob, q = 1 - p
        For prediction markets: b = (1 - price) / price, p = confidence
        """
        if price <= 0 or price >= 1 or confidence <= 0:
            return self.position_size  # fallback to default
        
        b = (1.0 - price) / price  # implied odds
        q = 1.0 - confidence
        kelly_pct = (b * confidence - q) / b
        
        # Quarter-Kelly (conservative) and capped
        kelly_pct = max(0, min(kelly_pct * KELLY_FRACTION, 0.10))  # max 10% of bankroll
        
        # Size based on current bankroll
        size = self.bankroll * kelly_pct
        
        # Floor and cap
        size = max(min(size, self.position_size * 2), 1.0)  # min $1, max 2x default
        size = min(size, self.bankroll * 0.10)  # never more than 10% of bankroll
        
        return round(size, 2)

    async def _maybe_enter(self, opp: Dict, events: List[Dict]) -> bool:
        """Enter a paper position if conditions met."""
        # Check bankroll
        if self.bankroll < MIN_BANKROLL_USDC:
            logger.warning("Bankroll too low ($%.2f < $%.0f), skipping entry", self.bankroll, MIN_BANKROLL_USDC)
            return False

        # Check if we already have a position in this market
        for pos in self.positions.values():
            if pos.market_id == opp["market_id"] and not pos.resolved:
                return False

        # Check max positions
        active_positions = sum(1 for p in self.positions.values() if not p.resolved)
        if active_positions >= self.max_positions:
            return False

        # Create paper position — Kelly criterion sizing
        position_id = f"poly_{uuid.uuid4().hex[:12]}"
        entry_price = opp["price"]
        size = self._kelly_size(opp["confidence"], entry_price)
        shares = size / entry_price if entry_price > 0 else 0

        position = PaperPosition(
            position_id=position_id,
            market_id=opp["market_id"],
            question=opp["question"],
            side=opp["side"],
            entry_price=entry_price,
            current_price=entry_price,
            size_usdc=size,
            shares=shares,
            entry_time=time.time(),
            last_update_time=time.time(),
            event_title=opp.get("event_title", ""),
            end_date=opp.get("end_date"),
            signals=opp["signals"],
            confidence=opp["confidence"],
        )

        self.positions[position_id] = position

        # Record trade
        trade = PaperTrade(
            trade_id=f"pt_{uuid.uuid4().hex[:12]}",
            position_id=position_id,
            market_id=opp["market_id"],
            question=opp["question"],
            side=opp["side"],
            action="OPEN",
            price=entry_price,
            size_usdc=size,
            shares=shares,
            pnl=0.0,
            timestamp=time.time(),
            signals=opp["signals"],
        )
        self.trades.append(trade)
        self.total_trades += 1

        # Deduct from bankroll
        self.bankroll -= size

        # Notification
        signal_str = "+".join(opp["signals"][:3])
        self._notify(
            f"ALPHA OPEN {opp['side']} @ {entry_price:.3f} [{signal_str}] conf={opp['confidence']:.0%} | {opp['question'][:50]}",
            level="success",
            metadata={"position_id": position_id, "confidence": opp["confidence"], "signals": opp["signals"]},
        )

        logger.info(
            "Alpha OPEN: %s %s @ %.3f conf=%.0%% signals=%s | %s",
            opp["side"], opp["market_id"][:12], entry_price,
            opp["confidence"] * 100, "+".join(opp["signals"]),
            opp["question"][:50],
        )
        return True

    async def _update_positions(self, events: List[Dict]):
        """Update current prices and P&L for all open positions."""
        price_map: Dict[str, Dict[str, float]] = {}
        for event in events:
            for market in event.get("markets", []):
                mid = market.get("conditionId", "")
                if not mid:
                    continue

                outcome_prices = market.get("outcomePrices", "[]")
                if isinstance(outcome_prices, str):
                    try:
                        outcome_prices = json.loads(outcome_prices)
                    except Exception:
                        continue

                if len(outcome_prices) >= 2:
                    price_map[mid] = {
                        "yes": float(outcome_prices[0]),
                        "no": float(outcome_prices[1]),
                    }

                # Check if resolved
                if market.get("resolved", False):
                    for pos in self.positions.values():
                        if pos.market_id == mid and not pos.resolved:
                            await self._resolve_position(pos, market)

        # Update prices for open positions
        for pos in self.positions.values():
            if pos.resolved:
                continue

            if pos.market_id in price_map:
                prices = price_map[pos.market_id]
                if pos.side == "YES":
                    pos.current_price = prices.get("yes", pos.current_price)
                else:
                    pos.current_price = prices.get("no", pos.current_price)

                pos.last_update_time = time.time()

                # Calculate P&L
                if pos.entry_price > 0:
                    pos.pnl = (pos.current_price - pos.entry_price) * pos.shares
                    pos.pnl_pct = ((pos.current_price - pos.entry_price) / pos.entry_price) * 100

                # Check exit conditions
                await self._check_exit(pos)

        # Update total P&L
        self.total_pnl = sum(p.pnl for p in self.positions.values())

    async def _check_exit(self, position: PaperPosition):
        """Check if position should be closed (take profit / stop loss / time)."""
        if position.resolved:
            return

        reason = None

        # Take profit
        if position.pnl_pct >= TAKE_PROFIT_PCT * 100:
            reason = f"TAKE PROFIT: +{position.pnl_pct:.1f}% (target: {TAKE_PROFIT_PCT*100:.0f}%)"

        # Stop loss
        elif position.pnl_pct <= STOP_LOSS_PCT * 100:
            reason = f"STOP LOSS: {position.pnl_pct:.1f}% (limit: {STOP_LOSS_PCT*100:.0f}%)"

        # Max hold time exceeded
        elif (time.time() - position.entry_time) > MAX_HOLD_DAYS * 86400:
            reason = f"MAX HOLD: {MAX_HOLD_DAYS}d exceeded, closing stale position"

        if reason:
            await self._close_position(position, reason)

    async def _close_position(self, position: PaperPosition, reason: str):
        """Close a paper position."""
        position.resolved = True

        if position.pnl > 0:
            self.winning_trades += 1

        # Return capital + P&L to bankroll
        self.bankroll += position.size_usdc + position.pnl
        self.peak_bankroll = max(self.peak_bankroll, self.bankroll)

        trade = PaperTrade(
            trade_id=f"pt_{uuid.uuid4().hex[:12]}",
            position_id=position.position_id,
            market_id=position.market_id,
            question=position.question,
            side=position.side,
            action="CLOSE",
            price=position.current_price,
            size_usdc=position.size_usdc,
            shares=position.shares,
            pnl=position.pnl,
            timestamp=time.time(),
            signals=position.signals,
        )
        self.trades.append(trade)

        result = "WIN" if position.pnl > 0 else "LOSS"
        self._notify(
            f"{result} ({reason}): {position.side} PnL=${position.pnl:.4f} ({position.pnl_pct:.1f}%) | {position.question[:50]}",
            level="success" if position.pnl > 0 else "warning",
            metadata={"position_id": position.position_id, "pnl": position.pnl, "reason": reason},
        )

        logger.info(
            "Alpha %s (%s): %s PnL=$%.4f (%.1f%%) signals=%s | %s",
            result, reason[:20], position.side, position.pnl, position.pnl_pct,
            "+".join(position.signals), position.question[:50],
        )

    async def _resolve_position(self, position: PaperPosition, market: Dict):
        """Resolve a position when market ends."""
        outcome_prices = market.get("outcomePrices", "[]")
        if isinstance(outcome_prices, str):
            try:
                outcome_prices = json.loads(outcome_prices)
            except Exception:
                return

        if len(outcome_prices) < 2:
            return

        yes_price = float(outcome_prices[0])
        no_price = float(outcome_prices[1])

        if position.side == "YES":
            final_price = yes_price
        else:
            final_price = no_price

        position.current_price = final_price
        position.resolved = True
        position.pnl = (final_price - position.entry_price) * position.shares
        position.pnl_pct = ((final_price - position.entry_price) / position.entry_price) * 100

        if position.pnl > 0:
            self.winning_trades += 1

        # Return capital + P&L to bankroll
        self.bankroll += position.size_usdc + position.pnl
        self.peak_bankroll = max(self.peak_bankroll, self.bankroll)

        trade = PaperTrade(
            trade_id=f"pt_{uuid.uuid4().hex[:12]}",
            position_id=position.position_id,
            market_id=position.market_id,
            question=position.question,
            side=position.side,
            action="CLOSE",
            price=final_price,
            size_usdc=position.size_usdc,
            shares=position.shares,
            pnl=position.pnl,
            timestamp=time.time(),
            signals=position.signals,
        )
        self.trades.append(trade)

        result = "WIN" if position.pnl > 0 else "LOSS"
        self._notify(
            f"{result}: {position.side} @ {position.entry_price:.3f} -> {final_price:.3f} | PnL: ${position.pnl:.4f} | {position.question[:50]}",
            level="success" if position.pnl > 0 else "warning",
            metadata={"position_id": position.position_id, "pnl": position.pnl},
        )

        logger.info(
            "Alpha %s: %s PnL=$%.4f (%.1f%%) signals=%s | %s",
            result, position.side, position.pnl, position.pnl_pct,
            "+".join(position.signals), position.question[:50],
        )

    def _update_history(self, events: List[Dict]):
        """Update price and volume history for momentum/volume detection."""
        for event in events:
            for market in event.get("markets", []):
                mid = market.get("conditionId", "")
                if not mid:
                    continue

                outcome_prices = market.get("outcomePrices", "[]")
                if isinstance(outcome_prices, str):
                    try:
                        outcome_prices = json.loads(outcome_prices)
                    except Exception:
                        continue

                if len(outcome_prices) >= 2:
                    yes_price = float(outcome_prices[0])
                    if mid not in self.price_history:
                        self.price_history[mid] = []
                    self.price_history[mid].append((time.time(), yes_price))
                    # Trim history
                    if len(self.price_history[mid]) > self.max_history:
                        self.price_history[mid] = self.price_history[mid][-self.max_history:]

                volume = float(market.get("volume", 0) or 0)
                if mid not in self.volume_history:
                    self.volume_history[mid] = []
                    # Seed baseline on first encounter so volume_spike can fire next scan
                    if volume > 0:
                        self.volume_history[mid].append(volume)
                self.volume_history[mid].append(volume)
                if len(self.volume_history[mid]) > self.max_history:
                    self.volume_history[mid] = self.volume_history[mid][-self.max_history:]
                
                # Compute volume delta (rate of change) for spike detection
                if mid not in self.volume_delta_history:
                    self.volume_delta_history[mid] = []
                if len(self.volume_history[mid]) >= 2:
                    delta = self.volume_history[mid][-1] - self.volume_history[mid][-2]
                    if delta > 0:
                        self.volume_delta_history[mid].append(delta)
                        if len(self.volume_delta_history[mid]) > self.max_history:
                            self.volume_delta_history[mid] = self.volume_delta_history[mid][-self.max_history:]

    async def _fetch_events(self) -> List[Dict]:
        """Fetch active events from Polymarket Gamma API (paginated, up to 150)."""
        all_events = []
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                for offset in range(0, 150, 50):  # 3 pages x 50 = 150 events
                    resp = await client.get(
                        f"{GAMMA_API}/events",
                        params={"limit": 50, "offset": offset, "active": "true", "closed": "false"},
                    )
                    resp.raise_for_status()
                    page = resp.json()
                    if not page:
                        break  # no more pages
                    all_events.extend(page)
        except Exception as e:
            logger.error("Failed to fetch Polymarket events: %s", e)
        return all_events

    async def _fetch_crypto_snapshot(self):
        """Fetch current crypto price changes for cross-market signals."""
        # Try multiple Binance endpoints
        endpoints = [
            "https://api.binance.com/api/v3/ticker/24hr",
            "https://api1.binance.com/api/v3/ticker/24hr",
            "https://api2.binance.com/api/v3/ticker/24hr",
        ]
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                for endpoint in endpoints:
                    try:
                        resp = await client.get(endpoint)
                        if resp.status_code != 200:
                            continue
                        data = resp.json()
                        target_symbols = {"BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "DOGEUSDT"}
                        for item in data:
                            symbol = item.get("symbol", "")
                            if symbol in target_symbols:
                                change_pct = float(item.get("priceChangePercent", 0))
                                self._crypto_snapshot[symbol] = change_pct
                        if self._crypto_snapshot:
                            break  # got data, stop trying endpoints
                    except Exception:
                        continue
        except Exception as e:
            logger.debug("Crypto snapshot failed: %s", e)

    async def _fetch_news_headlines(self):
        """Fetch latest news headlines for sentiment signal."""
        now = time.time()
        if now - self._news_last_fetch < self._news_fetch_interval:
            return  # use cached headlines

        headlines = []
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                for feed_url in NEWS_FEEDS:
                    try:
                        resp = await client.get(feed_url)
                        if resp.status_code != 200:
                            continue
                        # Simple XML parsing without lxml dependency
                        import re
                        titles = re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>', resp.text)
                        if not titles:
                            titles = re.findall(r'<title>(.*?)</title>', resp.text)
                        headlines.extend(titles[:15])  # top 15 per feed
                    except Exception:
                        continue
        except Exception as e:
            logger.debug("News fetch failed: %s", e)

        if headlines:
            self._news_headlines = headlines[:50]  # keep top 50
            self._news_last_fetch = now
            logger.debug("Fetched %d news headlines", len(headlines))

    def _notify(self, message: str, level: str = "info", metadata: Optional[Dict] = None):
        """Add notification to recent list."""
        self.notifications.append({
            "timestamp": time.time(),
            "level": level,
            "message": message,
            "metadata": metadata or {},
        })
        if len(self.notifications) > self.max_notifications:
            self.notifications = self.notifications[-self.max_notifications:]

    # ── State Persistence ──────────────────────────────────────────────────────

    async def _save_state(self):
        """Persist state to Redis."""
        if not self._redis:
            return
        try:
            data = {
                "positions": {k: v.to_dict() for k, v in self.positions.items()},
                "trades": [t.to_dict() for t in self.trades[-200:]],
                "total_pnl": self.total_pnl,
                "total_trades": self.total_trades,
                "winning_trades": self.winning_trades,
                "scan_count": self.scan_count,
                "last_scan_time": self.last_scan_time,
                "start_time": self.start_time,
                "opportunities_found": self.opportunities_found,
                "bankroll": self.bankroll,
                "peak_bankroll": self.peak_bankroll,
            }
            await self._redis.set("poly_paper:state", json.dumps(data))
        except Exception as e:
            logger.debug("Failed to save poly paper state: %s", e)

    async def _restore_state(self) -> bool:
        """Restore state from Redis."""
        if not self._redis:
            return False
        try:
            raw = await self._redis.get("poly_paper:state")
            if not raw:
                return False
            data = json.loads(raw)

            for pid, pdata in data.get("positions", {}).items():
                self.positions[pid] = PaperPosition.from_dict(pdata)

            for tdata in data.get("trades", []):
                self.trades.append(PaperTrade(**{
                    k: v for k, v in tdata.items() if k in PaperTrade.__dataclass_fields__
                }))

            self.total_pnl = data.get("total_pnl", 0.0)
            self.total_trades = data.get("total_trades", 0)
            self.winning_trades = data.get("winning_trades", 0)
            self.scan_count = data.get("scan_count", 0)
            self.last_scan_time = data.get("last_scan_time", 0.0)
            self.start_time = data.get("start_time", 0.0)
            self.opportunities_found = data.get("opportunities_found", 0)
            self.bankroll = data.get("bankroll", self.bankroll)
            self.peak_bankroll = data.get("peak_bankroll", self.bankroll)

            logger.info(
                "Restored alpha state: positions=%d trades=%d pnl=$%.4f",
                len(self.positions), len(self.trades), self.total_pnl,
            )
            return True
        except Exception as e:
            logger.warning("Failed to restore alpha state: %s", e)
            return False

    # ── Public API ─────────────────────────────────────────────────────────────

    def get_status(self) -> Dict:
        """Get bot status summary."""
        active = sum(1 for p in self.positions.values() if not p.resolved)
        resolved = sum(1 for p in self.positions.values() if p.resolved)
        win_rate = (self.winning_trades / resolved * 100) if resolved > 0 else 0
        uptime = time.time() - self.start_time if self.start_time > 0 else 0

        return {
            "running": self._running,
            "uptime_seconds": round(uptime),
            "scan_count": self.scan_count,
            "scan_interval": self.scan_interval,
            "last_scan_time": self.last_scan_time,
            "config": {
                "max_positions": self.max_positions,
                "position_size_usdc": self.position_size,
                "min_deviation": self.min_deviation,
                "min_liquidity": self.min_liquidity,
                "min_volume": self.min_volume,
                "scan_interval": self.scan_interval,
            },
            "positions": {
                "active": active,
                "resolved": resolved,
                "total": len(self.positions),
            },
            "performance": {
                "total_pnl": round(self.total_pnl, 4),
                "total_trades": self.total_trades,
                "winning_trades": self.winning_trades,
                "win_rate_pct": round(win_rate, 1),
                "opportunities_found": self.opportunities_found,
            },
            "alpha": {
                "signals_detected": len(self.recent_signals),
                "signal_types": list(SIGNAL_WEIGHTS.keys()),
                "crypto_tracking": {k: round(v, 2) for k, v in self._crypto_snapshot.items()},
                "price_history_markets": len(self.price_history),
                "news_headlines": len(self._news_headlines),
                "diversity_cap": MAX_POSITIONS_PER_SIGNAL,
                "exit_rules": {
                    "take_profit_pct": TAKE_PROFIT_PCT * 100,
                    "stop_loss_pct": abs(STOP_LOSS_PCT) * 100,
                    "max_hold_days": MAX_HOLD_DAYS,
                },
                "bankroll": {
                    "current": round(self.bankroll, 2),
                    "peak": round(self.peak_bankroll, 2),
                    "kelly_fraction": KELLY_FRACTION,
                },
            },
        }

    def get_positions(self, active_only: bool = False) -> List[Dict]:
        """Get all positions."""
        positions = self.positions.values()
        if active_only:
            positions = [p for p in positions if not p.resolved]
        else:
            positions = list(positions)

        positions.sort(key=lambda p: p.entry_time, reverse=True)
        return [p.to_dict() for p in positions]

    def get_trades(self, limit: int = 50) -> List[Dict]:
        """Get recent trades."""
        return [t.to_dict() for t in reversed(self.trades[-limit:])]

    def get_notifications(self, limit: int = 20) -> List[Dict]:
        """Get recent notifications."""
        return self.notifications[-limit:]

    def get_performance(self) -> Dict:
        """Get detailed performance metrics."""
        active = [p for p in self.positions.values() if not p.resolved]
        resolved = [p for p in self.positions.values() if p.resolved]

        realized_pnl = sum(p.pnl for p in resolved)
        unrealized_pnl = sum(p.pnl for p in active)

        yes_positions = [p for p in active if p.side == "YES"]
        no_positions = [p for p in active if p.side == "NO"]

        if resolved:
            avg_hold = sum(
                (p.last_update_time - p.entry_time) for p in resolved
            ) / len(resolved) / 3600
        else:
            avg_hold = 0

        # Signal performance breakdown
        signal_wins = {}
        signal_losses = {}
        for p in resolved:
            for sig in p.signals:
                if p.pnl > 0:
                    signal_wins[sig] = signal_wins.get(sig, 0) + 1
                else:
                    signal_losses[sig] = signal_losses.get(sig, 0) + 1

        return {
            "total_pnl": round(self.total_pnl, 4),
            "realized_pnl": round(realized_pnl, 4),
            "unrealized_pnl": round(unrealized_pnl, 4),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": len(resolved) - self.winning_trades,
            "win_rate_pct": round(
                (self.winning_trades / len(resolved) * 100) if resolved else 0, 1
            ),
            "active_positions": len(active),
            "yes_positions": len(yes_positions),
            "no_positions": len(no_positions),
            "avg_hold_hours": round(avg_hold, 1),
            "opportunities_found": self.opportunities_found,
            "scan_count": self.scan_count,
            "bankroll": {
                "current": round(self.bankroll, 2),
                "peak": round(self.peak_bankroll, 2),
                "drawdown_pct": round((1 - self.bankroll / self.peak_bankroll) * 100, 1) if self.peak_bankroll > 0 else 0,
            },
            "signal_performance": {
                sig: {
                    "wins": signal_wins.get(sig, 0),
                    "losses": signal_losses.get(sig, 0),
                    "total": signal_wins.get(sig, 0) + signal_losses.get(sig, 0),
                }
                for sig in SIGNAL_WEIGHTS.keys()
            },
        }

    def get_signals(self, limit: int = 30) -> List[Dict]:
        """Get recent alpha signals."""
        return [s.to_dict() for s in self.recent_signals[:limit]]


# ── Singleton ──────────────────────────────────────────────────────────────────

_poly_paper_bot: Optional[PolymarketPaperBot] = None


def get_poly_paper_bot() -> PolymarketPaperBot:
    global _poly_paper_bot
    if _poly_paper_bot is None:
        _poly_paper_bot = PolymarketPaperBot()
    return _poly_paper_bot
