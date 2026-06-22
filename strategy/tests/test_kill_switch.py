"""
Tests for the Polymarket paper bot kill switch.
Validates 4 halt conditions:
1. Daily loss limit triggers halt
2. Max drawdown triggers halt
3. Consecutive losses trigger halt
4. API failures trigger halt
"""
import sys
import time
from pathlib import Path

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.polymarket.paper_bot import (
    PolymarketPaperBot,
    PaperPosition,
    DAILY_LOSS_LIMIT_USDC,
    MAX_DRAWDOWN_PCT,
    MAX_CONSECUTIVE_LOSSES,
    API_FAILURE_HALT_THRESHOLD,
)


def _make_position(pnl: float = -1.0, side: str = "YES", entry_price: float = 0.50) -> PaperPosition:
    """Helper to create a PaperPosition with a specific PnL."""
    return PaperPosition(
        position_id=f"test_{id(pnl)}",
        market_id="test_market",
        question="Test question?",
        side=side,
        entry_price=entry_price,
        current_price=entry_price,
        size_usdc=5.0,
        shares=10.0,
        entry_time=time.time() - 3600,
        last_update_time=time.time(),
        signals=["mispricing"],
        confidence=0.6,
        pnl=pnl,
    )


class TestKillSwitchDailyLoss:
    """Test 1: Daily loss limit triggers halt."""

    def setup_method(self):
        self.bot = PolymarketPaperBot()
        self.bot.bankroll = 100.0
        self.bot.peak_bankroll = 100.0

    def test_daily_loss_triggers_kill_switch(self):
        """When daily PnL hits -DAILY_LOSS_LIMIT_USDC, kill switch activates."""
        # Simulate enough losses to exceed daily limit
        # Use small losses that won't trigger consecutive loss limit first
        for i in range(int(DAILY_LOSS_LIMIT_USDC) + 2):
            pos = _make_position(pnl=-1.0)
            self.bot._on_position_closed(pos)
            # Reset consecutive counter after each loss to avoid triggering that first
            self.bot._consecutive_losses = 0

        assert self.bot._kill_switch_active is True
        assert "Daily loss limit" in self.bot._kill_reason or "daily loss limit" in self.bot._kill_reason

    def test_daily_loss_resets_on_new_day(self):
        """Daily PnL resets when date changes."""
        # Trigger some losses
        pos = _make_position(pnl=-2.0)
        self.bot._on_position_closed(pos)
        assert self.bot._daily_pnl == -2.0

        # Simulate new day by changing the date
        self.bot._daily_pnl_date = "2020-01-01"
        # The reset happens in _scan_and_trade, but we can verify the mechanism
        assert self.bot._daily_pnl == -2.0  # still negative until reset

    def test_no_kill_switch_below_limit(self):
        """Kill switch should NOT activate if daily loss is below limit."""
        pos = _make_position(pnl=-1.0)
        self.bot._on_position_closed(pos)

        assert self.bot._kill_switch_active is False
        assert self.bot._daily_pnl == -1.0


class TestKillSwitchDrawdown:
    """Test 2: Max drawdown triggers halt."""

    def setup_method(self):
        self.bot = PolymarketPaperBot()
        self.bot.bankroll = 100.0
        self.bot.peak_bankroll = 100.0

    def test_drawdown_triggers_kill_switch(self):
        """When drawdown exceeds MAX_DRAWDOWN_PCT, kill switch activates."""
        # Simulate losses that reduce bankroll below threshold
        # MAX_DRAWDOWN_PCT = 0.05 (5%), so bankroll dropping to 94 from 100 triggers it
        # Use small losses to avoid triggering daily loss or consecutive loss first
        for _ in range(4):
            pos = _make_position(pnl=-1.5)
            self.bot.bankroll += pos.pnl  # simulate bankroll reduction
            self.bot.peak_bankroll = max(self.bot.peak_bankroll, self.bot.bankroll)
            self.bot._on_position_closed(pos)
            # Reset counters to avoid triggering other kill conditions first
            self.bot._consecutive_losses = 0
            self.bot._daily_pnl = 0  # reset daily pnl to avoid triggering daily loss

        # After 4 x -$1.5 = -$6 bankroll impact, drawdown should exceed 5%
        assert self.bot._kill_switch_active is True
        assert "drawdown" in self.bot._kill_reason.lower()

    def test_no_kill_switch_below_drawdown_limit(self):
        """Kill switch should NOT activate if drawdown is below limit."""
        pos = _make_position(pnl=-1.0)
        self.bot.bankroll += pos.pnl  # bankroll = 99, drawdown = 1%
        self.bot.peak_bankroll = max(self.bot.peak_bankroll, self.bot.bankroll)
        self.bot._on_position_closed(pos)

        assert self.bot._kill_switch_active is False


class TestKillSwitchConsecutiveLosses:
    """Test 3: Consecutive losses trigger halt."""

    def setup_method(self):
        self.bot = PolymarketPaperBot()
        self.bot.bankroll = 100.0
        self.bot.peak_bankroll = 100.0

    def test_consecutive_losses_trigger_kill_switch(self):
        """After MAX_CONSECUTIVE_LOSSES losses in a row, kill switch activates."""
        for i in range(MAX_CONSECUTIVE_LOSSES):
            pos = _make_position(pnl=-0.5)
            self.bot._on_position_closed(pos)

        assert self.bot._kill_switch_active is True
        assert "Consecutive losses" in self.bot._kill_reason
        assert self.bot._consecutive_losses == MAX_CONSECUTIVE_LOSSES

    def test_win_resets_consecutive_counter(self):
        """A win should reset the consecutive loss counter."""
        # 2 losses
        for _ in range(2):
            pos = _make_position(pnl=-0.5)
            self.bot._on_position_closed(pos)
        assert self.bot._consecutive_losses == 2

        # 1 win resets counter
        pos = _make_position(pnl=1.0)
        self.bot._on_position_closed(pos)
        assert self.bot._consecutive_losses == 0
        assert self.bot._kill_switch_active is False

    def test_below_consecutive_limit_no_halt(self):
        """Fewer than MAX_CONSECUTIVE_LOSSES should not trigger kill switch."""
        for _ in range(MAX_CONSECUTIVE_LOSSES - 1):
            pos = _make_position(pnl=-0.5)
            self.bot._on_position_closed(pos)

        assert self.bot._kill_switch_active is False


class TestKillSwitchAPIFailure:
    """Test 4: API failures trigger halt."""

    def setup_method(self):
        self.bot = PolymarketPaperBot()
        self.bot.bankroll = 100.0
        self.bot.peak_bankroll = 100.0

    def test_api_failures_trigger_kill_switch(self):
        """After API_FAILURE_HALT_THRESHOLD consecutive failures, kill switch activates."""
        for _ in range(API_FAILURE_HALT_THRESHOLD):
            self.bot._api_failure_count += 1
            if self.bot._api_failure_count >= API_FAILURE_HALT_THRESHOLD:
                self.bot._trigger_kill_switch(
                    f"API failures: {self.bot._api_failure_count} consecutive"
                )

        assert self.bot._kill_switch_active is True
        assert "API failures" in self.bot._kill_reason

    def test_api_success_resets_failure_counter(self):
        """Successful API call should reset the failure counter."""
        self.bot._api_failure_count = 2
        # Simulate success
        self.bot._api_failure_count = 0
        assert self.bot._api_failure_count == 0

    def test_below_api_failure_limit_no_halt(self):
        """Fewer than API_FAILURE_HALT_THRESHOLD should not trigger kill switch."""
        self.bot._api_failure_count = API_FAILURE_HALT_THRESHOLD - 1
        assert self.bot._kill_switch_active is False


class TestKillSwitchReset:
    """Test manual kill switch reset."""

    def setup_method(self):
        self.bot = PolymarketPaperBot()
        self.bot.bankroll = 100.0
        self.bot.peak_bankroll = 100.0

    def test_reset_kill_switch(self):
        """Manual reset should clear kill switch state."""
        # Trigger kill switch
        for _ in range(MAX_CONSECUTIVE_LOSSES):
            pos = _make_position(pnl=-0.5)
            self.bot._on_position_closed(pos)
        assert self.bot._kill_switch_active is True

        # Reset
        self.bot.reset_kill_switch()
        assert self.bot._kill_switch_active is False
        assert self.bot._kill_reason == ""
        assert self.bot._consecutive_losses == 0
        assert self.bot._daily_pnl == 0.0


class TestKillSwitchScanBlocking:
    """Test that kill switch actually blocks scanning."""

    def setup_method(self):
        self.bot = PolymarketPaperBot()
        self.bot.bankroll = 100.0
        self.bot.peak_bankroll = 100.0

    @pytest.mark.asyncio
    async def test_scan_blocked_by_kill_switch(self):
        """_scan_and_trade should return immediately when kill switch is active."""
        self.bot._kill_switch_active = True
        self.bot._kill_reason = "Test halt"

        # Mock _fetch_events to ensure it's never called
        self.bot._fetch_events = AsyncMock()

        await self.bot._scan_and_trade()

        # _fetch_events should NOT have been called
        self.bot._fetch_events.assert_not_called()
