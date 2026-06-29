"""
Flash Crash Circuit Breaker
============================
Detects sudden price drops (>3% in one tick interval) and halts buy orders
for the affected symbol. Prevents placing buys into catastrophic declines.

Auto-recovery after cooldown period (configurable, default 5 minutes).
"""

import logging
import time
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger("circuit_breaker")


@dataclass
class CircuitBreakerState:
    """Tracks circuit breaker state for a single symbol."""
    symbol: str
    last_price: float = 0.0
    prev_price: float = 0.0
    triggered: bool = False
    triggered_at: float = 0.0
    drop_pct: float = 0.0
    cooldown_sec: float = 300.0  # 5 minutes default


class CircuitBreaker:
    """
    Flash crash detection and buy-halt mechanism.

    Usage:
        cb = CircuitBreaker(drop_threshold_pct=3.0, cooldown_sec=300)

        # Each grid tick, before placing orders:
        cb.update_price("BTCUSDT", current_price)
        if cb.is_triggered("BTCUSDT"):
            # Skip buy orders for this symbol
            pass

        # Check status:
        status = cb.get_status()
    """

    def __init__(self, drop_threshold_pct: float = 3.0, cooldown_sec: float = 300.0):
        """
        Args:
            drop_threshold_pct: Price drop % that triggers the breaker (e.g., 3.0 = 3%)
            cooldown_sec: Seconds to wait before auto-recovery after trigger
        """
        self.drop_threshold_pct = drop_threshold_pct
        self.cooldown_sec = cooldown_sec
        self._states: Dict[str, CircuitBreakerState] = {}

    def update_price(self, symbol: str, price: float) -> bool:
        """
        Update the price for a symbol and check for crash.

        Returns:
            True if circuit breaker is currently triggered for this symbol
        """
        if symbol not in self._states:
            self._states[symbol] = CircuitBreakerState(
                symbol=symbol,
                cooldown_sec=self.cooldown_sec,
            )

        state = self._states[symbol]
        now = time.time()

        # Check if we should auto-recover from triggered state
        if state.triggered:
            elapsed = now - state.triggered_at
            if elapsed >= self.cooldown_sec:
                logger.info(
                    "[CircuitBreaker %s] Auto-recovered after %.0fs (drop was %.2f%%)",
                    symbol, elapsed, state.drop_pct,
                )
                state.triggered = False
                state.drop_pct = 0.0
                state.triggered_at = 0.0
            else:
                # Still in cooldown — update prices but stay triggered
                state.prev_price = state.last_price
                state.last_price = price
                return True

        # Normal operation: track price history
        state.prev_price = state.last_price
        state.last_price = price

        # Need at least 2 prices to detect a drop
        if state.prev_price <= 0:
            return False

        # Calculate price change %
        change_pct = ((price - state.prev_price) / state.prev_price) * 100.0

        # Check for crash (negative change = drop)
        if change_pct < -self.drop_threshold_pct:
            state.triggered = True
            state.triggered_at = now
            state.drop_pct = abs(change_pct)
            logger.warning(
                "[CircuitBreaker %s] TRIGGERED! Price dropped %.2f%% (%.2f → %.2f) "
                "— halting buys for %.0fs cooldown",
                symbol, abs(change_pct), state.prev_price, price, self.cooldown_sec,
            )
            return True

        return False

    def is_triggered(self, symbol: str) -> bool:
        """Check if circuit breaker is currently triggered for a symbol."""
        state = self._states.get(symbol)
        if not state:
            return False

        # Check for auto-recovery
        if state.triggered:
            elapsed = time.time() - state.triggered_at
            if elapsed >= self.cooldown_sec:
                logger.info(
                    "[CircuitBreaker %s] Auto-recovered after %.0fs",
                    symbol, elapsed,
                )
                state.triggered = False
                state.drop_pct = 0.0
                state.triggered_at = 0.0
                return False
            return True

        return False

    def get_status(self) -> Dict[str, dict]:
        """Get circuit breaker status for all symbols."""
        return {
            symbol: {
                "triggered": self.is_triggered(symbol),
                "last_price": state.last_price,
                "prev_price": state.prev_price,
                "drop_pct": state.drop_pct,
                "triggered_at": state.triggered_at,
                "cooldown_remaining": max(0, self.cooldown_sec - (time.time() - state.triggered_at))
                    if state.triggered else 0.0,
            }
            for symbol, state in self._states.items()
        }

    def reset(self, symbol: Optional[str] = None):
        """Reset circuit breaker for a symbol (or all if symbol=None)."""
        if symbol:
            if symbol in self._states:
                self._states[symbol].triggered = False
                self._states[symbol].drop_pct = 0.0
                self._states[symbol].triggered_at = 0.0
                logger.info("[CircuitBreaker %s] Manually reset", symbol)
        else:
            for sym in self._states:
                self._states[sym].triggered = False
                self._states[sym].drop_pct = 0.0
                self._states[sym].triggered_at = 0.0
            logger.info("[CircuitBreaker] All symbols reset")
