"""
Trade Journal
==============
Records every trade signal with full context:
- Entry/exit reasoning
- Expected risk/reward
- Actual P&L, fee, drawdown impact
- Strategy metadata

Persists to Go backend via HTTP (stored in PostgreSQL).
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

BACKEND_API_BASE = __import__("os").getenv("BACKEND_API_BASE", "http://backend:8080")


@dataclass
class JournalEntry:
    """A single trade journal entry."""
    symbol: str
    side: str  # BUY or SELL
    strategy: str  # e.g. "grid_bot_v2"
    entry_reason: str  # Why this trade was taken
    entry_price: float
    quantity: float
    expected_risk_thb: float = 0.0  # Max expected loss
    expected_reward_thb: float = 0.0  # Expected profit
    stop_loss_price: float = 0.0
    take_profit_price: float = 0.0
    # Filled later when trade closes
    exit_price: float = 0.0
    exit_reason: str = ""
    actual_pnl: float = 0.0
    fee: float = 0.0
    drawdown_impact_pct: float = 0.0
    # Metadata
    exchange_order_id: str = ""
    status: str = "OPEN"  # OPEN, CLOSED, CANCELLED
    created_at: float = 0.0
    closed_at: float = 0.0
    notes: str = ""

    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "strategy": self.strategy,
            "entry_reason": self.entry_reason,
            "entry_price": self.entry_price,
            "quantity": self.quantity,
            "expected_risk_thb": self.expected_risk_thb,
            "expected_reward_thb": self.expected_reward_thb,
            "stop_loss_price": self.stop_loss_price,
            "take_profit_price": self.take_profit_price,
            "exit_price": self.exit_price,
            "exit_reason": self.exit_reason,
            "actual_pnl": self.actual_pnl,
            "fee": self.fee,
            "drawdown_impact_pct": self.drawdown_impact_pct,
            "exchange_order_id": self.exchange_order_id,
            "status": self.status,
            "created_at": self.created_at,
            "closed_at": self.closed_at,
            "notes": self.notes,
        }


class TradeJournal:
    """
    Records and manages trade journal entries.
    Sends entries to Go backend for PostgreSQL persistence.
    """

    def __init__(self):
        self._entries: List[JournalEntry] = []
        self._http: Optional[httpx.AsyncClient] = None

    async def start(self, http_client: httpx.AsyncClient):
        """Share the HTTP client from the grid bot."""
        self._http = http_client

    async def record_entry(self, entry: JournalEntry) -> bool:
        """Record a new trade entry (when order is placed)."""
        entry.created_at = time.time()
        self._entries.append(entry)

        # Persist to backend
        if self._http:
            try:
                resp = await self._http.post(
                    f"{BACKEND_API_BASE}/api/journal/entry",
                    json=entry.to_dict(),
                )
                if resp.status_code == 201:
                    logger.info(
                        "Journal entry recorded: %s %s @ %d",
                        entry.symbol, entry.side, int(entry.entry_price),
                    )
                    return True
                else:
                    logger.warning("Journal persist failed: %s", resp.text)
            except Exception as e:
                logger.warning("Journal persist error: %s", e)

        return False

    async def record_exit(
        self,
        exchange_order_id: str,
        exit_price: float,
        exit_reason: str,
        actual_pnl: float,
        fee: float = 0.0,
        drawdown_impact_pct: float = 0.0,
    ) -> bool:
        """Record trade exit (when order is filled/closed)."""
        # Update local entry
        for entry in reversed(self._entries):
            if entry.exchange_order_id == exchange_order_id:
                entry.exit_price = exit_price
                entry.exit_reason = exit_reason
                entry.actual_pnl = actual_pnl
                entry.fee = fee
                entry.drawdown_impact_pct = drawdown_impact_pct
                entry.status = "CLOSED"
                entry.closed_at = time.time()
                break

        # Persist to backend
        if self._http:
            try:
                resp = await self._http.post(
                    f"{BACKEND_API_BASE}/api/journal/exit",
                    json={
                        "exchange_order_id": exchange_order_id,
                        "exit_price": exit_price,
                        "exit_reason": exit_reason,
                        "actual_pnl": actual_pnl,
                        "fee": fee,
                        "drawdown_impact_pct": drawdown_impact_pct,
                    },
                )
                if resp.status_code == 200:
                    logger.info(
                        "Journal exit recorded: order=%s pnl=%.2f",
                        exchange_order_id[:16] if exchange_order_id else "?",
                        actual_pnl,
                    )
                    return True
            except Exception as e:
                logger.warning("Journal exit persist error: %s", e)

        return False

    def get_recent_entries(self, limit: int = 20) -> List[Dict]:
        """Get recent journal entries (in-memory cache)."""
        return [e.to_dict() for e in self._entries[-limit:]]

    def get_stats(self) -> Dict:
        """Get journal statistics."""
        closed = [e for e in self._entries if e.status == "CLOSED"]
        open_entries = [e for e in self._entries if e.status == "OPEN"]

        total_pnl = sum(e.actual_pnl for e in closed)
        total_fees = sum(e.fee for e in closed)
        wins = [e for e in closed if e.actual_pnl > 0]
        losses = [e for e in closed if e.actual_pnl <= 0]

        avg_win = sum(e.actual_pnl for e in wins) / len(wins) if wins else 0
        avg_loss = sum(e.actual_pnl for e in losses) / len(losses) if losses else 0

        return {
            "total_entries": len(self._entries),
            "open_entries": len(open_entries),
            "closed_entries": len(closed),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": (len(wins) / len(closed) * 100) if closed else 0,
            "total_pnl": round(total_pnl, 2),
            "total_fees": round(total_fees, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "profit_factor": abs(avg_win / avg_loss) if avg_loss != 0 else 0,
        }


# ── Singleton ────────────────────────────────────────────────────────────────

_trade_journal: Optional[TradeJournal] = None


def get_trade_journal() -> TradeJournal:
    global _trade_journal
    if _trade_journal is None:
        _trade_journal = TradeJournal()
    return _trade_journal
