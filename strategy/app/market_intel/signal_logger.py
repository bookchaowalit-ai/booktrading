"""
Signal Performance Tracker — logs signals and evaluates their profitability over time.
Uses Redis for persistence. Automatically evaluates signals at 24h and 7d intervals.
"""
import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

import httpx

logger = logging.getLogger(__name__)

# Redis keys
SIGNAL_LOG_KEY = "signal_tracker:log:v1"
SIGNAL_INDEX_KEY = "signal_tracker:index:v1"  # For quick lookups

# Evaluation intervals
EVAL_24H = timedelta(hours=24)
EVAL_7D = timedelta(days=7)

# Max signals to store (prevent memory bloat)
MAX_SIGNALS = 5000

# Quote suffixes to strip when resolving base asset
_QUOTE_SUFFIXES = ("USDT", "THB", "BUSD", "BTC", "ETH", "BNB")

# Signal types considered bullish (price going up = correct)
_BULLISH_SIGNAL_TYPES = {"buy", "long", "opportunity", "momentum", "volume_spike", "trending_degen", "airdrop_free"}
# Signal types considered bearish (price going down = correct)
_BEARISH_SIGNAL_TYPES = {"sell", "short"}
# Neutral/unresolvable types (evaluated as correct if any movement > 1%)
_NEUTRAL_SIGNAL_TYPES = {"liquidity_gap"}


def _extract_base_asset(symbol: str) -> str:
    """Extract the base asset from a trading pair symbol.
    E.g. 'BTCTHB' -> 'BTC', 'ETHUSDT' -> 'ETH', 'AAPL' -> 'AAPL'.
    Returns the original symbol if no quote suffix matches.
    """
    upper = symbol.upper()
    for suffix in _QUOTE_SUFFIXES:
        if upper.endswith(suffix) and len(upper) > len(suffix):
            return upper[: -len(suffix)]
    return upper


class SignalLogger:
    """Logs market signals and tracks their performance over time."""

    def __init__(self, redis_client=None):
        self._redis = redis_client

    async def _load_log(self) -> Dict[str, Dict[str, Any]]:
        """Load signal log from Redis."""
        if not self._redis:
            return {}
        try:
            raw = await self._redis.get(SIGNAL_LOG_KEY)
            if raw:
                return json.loads(raw)
        except Exception as e:
            logger.warning(f"Failed to load signal log: {e}")
        return {}

    async def _save_log(self, data: Dict[str, Dict[str, Any]]):
        """Save signal log to Redis."""
        if not self._redis:
            return
        try:
            # Trim to MAX_SIGNALS (keep most recent)
            if len(data) > MAX_SIGNALS:
                sorted_items = sorted(data.items(), key=lambda x: x[1].get("timestamp", ""))
                data = dict(sorted_items[-MAX_SIGNALS:])
            await self._redis.set(SIGNAL_LOG_KEY, json.dumps(data))
        except Exception as e:
            logger.warning(f"Failed to save signal log: {e}")

    async def log_signal(
        self,
        symbol: str,
        market_type: str,
        source: str,
        signal_type: str,
        severity: str,
        title: str,
        price_at_signal: float,
        confidence: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Log a new signal for performance tracking."""
        data = await self._load_log()
        signal_id = str(uuid.uuid4())[:12]
        
        signal_entry = {
            "signal_id": signal_id,
            "symbol": symbol,
            "market_type": market_type,
            "source": source,
            "signal_type": signal_type,
            "severity": severity,
            "title": title,
            "price_at_signal": price_at_signal,
            "confidence": confidence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "eval_24h": None,  # Will be filled by evaluation
            "eval_7d": None,   # Will be filled by evaluation
            "metadata": metadata or {},
        }
        
        data[signal_id] = signal_entry
        await self._save_log(data)
        return signal_entry

    async def evaluate_signals(self, current_prices: Dict[str, float]) -> Dict[str, Any]:
        """
        Evaluate logged signals against current prices.
        Updates 24h and 7d evaluations for signals that have aged enough.
        Returns summary of evaluations.
        """
        data = await self._load_log()
        now = datetime.now(timezone.utc)
        evaluated_count = 0
        mature_count = 0
        matched_count = 0
        
        for signal_id, signal in data.items():
            ts = signal.get("timestamp", "")
            if not ts:
                continue
            
            try:
                signal_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue
            
            age = now - signal_time
            symbol = signal.get("symbol", "")
            price_at_signal = signal.get("price_at_signal", 0)
            
            if price_at_signal <= 0:
                continue
            
            # Check if signal needs evaluation (skip if already evaluated or not mature enough)
            needs_24h = age >= EVAL_24H and signal.get("eval_24h") is None
            needs_7d = age >= EVAL_7D and signal.get("eval_7d") is None
            if not needs_24h and not needs_7d:
                continue
            
            mature_count += 1
            
            # Try raw symbol first, then base asset (e.g. BTCTHB -> BTC)
            current_price = current_prices.get(symbol, 0)
            if current_price <= 0:
                base = _extract_base_asset(symbol)
                current_price = current_prices.get(base, 0)
            if current_price <= 0:
                continue
            
            matched_count += 1
            
            # Calculate % change
            pct_change = ((current_price - price_at_signal) / price_at_signal) * 100
            
            # Determine signal direction
            sig_type = signal.get("signal_type", "")
            if sig_type in _BULLISH_SIGNAL_TYPES:
                correct = pct_change > 0
            elif sig_type in _BEARISH_SIGNAL_TYPES:
                correct = pct_change < 0
            else:
                # Neutral signals: correct if any meaningful movement (>1%)
                correct = abs(pct_change) > 1.0
            
            # Evaluate 24h
            if age >= EVAL_24H and signal.get("eval_24h") is None:
                signal["eval_24h"] = {
                    "price_at_eval": current_price,
                    "pct_change": round(pct_change, 2),
                    "evaluated_at": now.isoformat(),
                    "correct": correct,
                }
                evaluated_count += 1
            
            # Evaluate 7d
            if age >= EVAL_7D and signal.get("eval_7d") is None:
                signal["eval_7d"] = {
                    "price_at_eval": current_price,
                    "pct_change": round(pct_change, 2),
                    "evaluated_at": now.isoformat(),
                    "correct": correct,
                }
                evaluated_count += 1
        
        if evaluated_count > 0:
            await self._save_log(data)
        
        # Log evaluation stats
        if mature_count > 0:
            logger.info(f"Signal evaluation: {mature_count} mature, {matched_count} matched prices, {evaluated_count} evaluated")
        
        return {"evaluated": evaluated_count, "total_signals": len(data)}

    async def get_signals(
        self,
        limit: int = 100,
        source: Optional[str] = None,
        market_type: Optional[str] = None,
        evaluated_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """Get logged signals with optional filters."""
        data = await self._load_log()
        signals = list(data.values())
        
        # Apply filters
        if source:
            signals = [s for s in signals if s.get("source") == source]
        if market_type:
            signals = [s for s in signals if s.get("market_type") == market_type]
        if evaluated_only:
            signals = [s for s in signals if s.get("eval_24h") is not None or s.get("eval_7d") is not None]
        
        # Sort by timestamp (most recent first)
        signals.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return signals[:limit]

    async def get_performance_stats(self) -> Dict[str, Any]:
        """
        Calculate performance statistics:
        - Total signals logged
        - Accuracy by source (24h and 7d)
        - Accuracy by market type
        - Average % change for correct vs incorrect signals
        """
        data = await self._load_log()
        
        stats = {
            "total_signals": len(data),
            "evaluated_24h": 0,
            "evaluated_7d": 0,
            "by_source": {},
            "by_market_type": {},
            "accuracy_24h": {"correct": 0, "incorrect": 0, "rate": 0.0},
            "accuracy_7d": {"correct": 0, "incorrect": 0, "rate": 0.0},
        }
        
        for signal in data.values():
            source = signal.get("source", "unknown")
            market_type = signal.get("market_type", "unknown")
            
            # Init source/market buckets
            if source not in stats["by_source"]:
                stats["by_source"][source] = {"total": 0, "correct_24h": 0, "incorrect_24h": 0}
            if market_type not in stats["by_market_type"]:
                stats["by_market_type"][market_type] = {"total": 0, "correct_24h": 0, "incorrect_24h": 0}
            
            stats["by_source"][source]["total"] += 1
            stats["by_market_type"][market_type]["total"] += 1
            
            # 24h evaluation
            eval_24h = signal.get("eval_24h")
            if eval_24h:
                stats["evaluated_24h"] += 1
                if eval_24h.get("correct"):
                    stats["accuracy_24h"]["correct"] += 1
                    stats["by_source"][source]["correct_24h"] += 1
                    stats["by_market_type"][market_type]["correct_24h"] += 1
                else:
                    stats["accuracy_24h"]["incorrect"] += 1
                    stats["by_source"][source]["incorrect_24h"] += 1
                    stats["by_market_type"][market_type]["incorrect_24h"] += 1
            
            # 7d evaluation
            eval_7d = signal.get("eval_7d")
            if eval_7d:
                stats["evaluated_7d"] += 1
                if eval_7d.get("correct"):
                    stats["accuracy_7d"]["correct"] += 1
                else:
                    stats["accuracy_7d"]["incorrect"] += 1
        
        # Calculate accuracy rates
        if stats["accuracy_24h"]["correct"] + stats["accuracy_24h"]["incorrect"] > 0:
            total_24h = stats["accuracy_24h"]["correct"] + stats["accuracy_24h"]["incorrect"]
            stats["accuracy_24h"]["rate"] = round(stats["accuracy_24h"]["correct"] / total_24h * 100, 1)
        
        if stats["accuracy_7d"]["correct"] + stats["accuracy_7d"]["incorrect"] > 0:
            total_7d = stats["accuracy_7d"]["correct"] + stats["accuracy_7d"]["incorrect"]
            stats["accuracy_7d"]["rate"] = round(stats["accuracy_7d"]["correct"] / total_7d * 100, 1)
        
        return stats


# Singleton
_logger_instance: Optional[SignalLogger] = None


def get_signal_logger(redis_client=None) -> SignalLogger:
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = SignalLogger(redis_client=redis_client)
    return _logger_instance
