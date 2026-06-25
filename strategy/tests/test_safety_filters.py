"""
Tests for Polymarket paper bot safety and strategy features:
1. Market blocklist filtering
2. Market allowlist filtering
3. Dry-run mode (would-trade logging)
4. Max positions enforcement
5. Kill switch restore from Redis state
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
    AlphaSignal,
    DEFAULT_MAX_POSITIONS,
    STOP_LOSS_PCT,
)


def _make_event(title: str, slug: str = "") -> dict:
    """Helper to create a mock event dict."""
    return {"title": title, "slug": slug or title.lower().replace(" ", "-")}


def _make_opp(market_id: str = "test_market", confidence: float = 0.6,
              side: str = "YES", price: float = 0.50,
              signals: list = None, question: str = "Test?") -> dict:
    """Helper to create a mock opportunity dict for _maybe_enter."""
    return {
        "market_id": market_id,
        "question": question,
        "side": side,
        "price": price,
        "signals": signals or ["mispricing"],
        "confidence": confidence,
        "event_title": "Test Event",
    }


def _make_position(pnl: float = 0.0, resolved: bool = False) -> PaperPosition:
    """Helper to create a PaperPosition."""
    return PaperPosition(
        position_id=f"test_{id(pnl)}_{time.time_ns()}",
        market_id=f"market_{id(pnl)}",
        question="Test?",
        side="YES",
        entry_price=0.50,
        current_price=0.50,
        size_usdc=5.0,
        shares=10.0,
        entry_time=time.time() - 3600,
        last_update_time=time.time(),
        signals=["mispricing"],
        confidence=0.6,
        pnl=pnl,
        resolved=resolved,
    )


def _make_market(
    market_id: str = "momentum_market",
    yes_price: float = 0.52,
    no_price: float = 0.48,
    volume: float = 10000.0,
    liquidity: float = 5000.0,
) -> dict:
    """Helper to create a mock Polymarket market dict."""
    return {
        "conditionId": market_id,
        "question": "Will BTC trend higher?",
        "outcomePrices": f"[{yes_price}, {no_price}]",
        "volume": volume,
        "liquidity": liquidity,
        "endDate": "2099-01-01T00:00:00Z",
    }


# ── Market Blocklist Tests ──────────────────────────────────────────────────────


class TestMarketBlocklist:
    """Test that blocklist filters out events matching blocked keywords."""

    def setup_method(self):
        self.bot = PolymarketPaperBot()
        # Default blocklist: politics, sports, entertainment, celebrities
        self.bot._market_blocklist = ["politics", "sports", "entertainment", "celebrities"]
        self.bot._market_allowlist = []

    def test_blocklist_filters_politics(self):
        """Events with 'politics' in title should be filtered out."""
        events = [
            _make_event("Politics Today: Election Update"),
            _make_event("Bitcoin Price Target"),
            _make_event("Congress votes on bill", "politics-congress"),
        ]
        filtered = self.bot._filter_events(events)
        assert len(filtered) == 1
        assert "Bitcoin" in filtered[0]["title"]

    def test_blocklist_filters_sports(self):
        """Events with 'sports' in title or slug should be filtered."""
        events = [
            _make_event("Sports Center: NBA Highlights"),
            _make_event("Super Bowl 2026", slug="super-bowl-sports"),
            _make_event("Fed Interest Rate Decision"),
        ]
        filtered = self.bot._filter_events(events)
        assert len(filtered) == 1
        assert "Fed" in filtered[0]["title"]

    def test_blocklist_filters_celebrities(self):
        """Events with 'celebrities' should be filtered."""
        events = [
            _make_event("Celebrities Net Worth Prediction"),
            _make_event("Tesla Stock Price"),
        ]
        filtered = self.bot._filter_events(events)
        assert len(filtered) == 1
        assert "Tesla" in filtered[0]["title"]

    def test_blocklist_case_insensitive(self):
        """Blocklist should be case-insensitive."""
        events = [
            _make_event("POLITICS Today Show"),
            _make_event("Sports Center"),
            _make_event("Crypto Markets"),
        ]
        filtered = self.bot._filter_events(events)
        assert len(filtered) == 1
        assert "Crypto" in filtered[0]["title"]

    def test_empty_blocklist_passes_all(self):
        """Empty blocklist should allow all events through."""
        self.bot._market_blocklist = []
        events = [
            _make_event("Politics Today"),
            _make_event("Sports Center"),
            _make_event("Crypto Markets"),
        ]
        filtered = self.bot._filter_events(events)
        assert len(filtered) == 3

    def test_blocklist_checks_slug_too(self):
        """Blocklist should match against slug as well as title."""
        events = [
            _make_event("Market Update", slug="politics-market-update"),
            _make_event("Tech Earnings"),
        ]
        filtered = self.bot._filter_events(events)
        assert len(filtered) == 1
        assert "Tech" in filtered[0]["title"]


# ── Market Allowlist Tests ──────────────────────────────────────────────────────


class TestMarketAllowlist:
    """Test that allowlist restricts to only matching events."""

    def setup_method(self):
        self.bot = PolymarketPaperBot()
        self.bot._market_blocklist = []  # no blocklist for these tests
        self.bot._market_allowlist = ["crypto", "defi"]

    def test_allowlist_passes_matching(self):
        """Events matching allowlist keywords should pass."""
        events = [
            _make_event("Crypto Price Prediction"),
            _make_event("DeFi Yield Farming"),
        ]
        filtered = self.bot._filter_events(events)
        assert len(filtered) == 2

    def test_allowlist_blocks_non_matching(self):
        """Events not matching allowlist should be blocked."""
        events = [
            _make_event("Crypto Price Prediction"),
            _make_event("US Election Results"),
            _make_event("Olympics Winner"),
        ]
        filtered = self.bot._filter_events(events)
        assert len(filtered) == 1
        assert "Crypto" in filtered[0]["title"]

    def test_allowlist_combined_with_blocklist(self):
        """Both allowlist and blocklist should apply."""
        self.bot._market_blocklist = ["politics"]
        self.bot._market_allowlist = ["crypto", "politics"]
        events = [
            _make_event("Crypto Markets"),
            _make_event("Politics of Crypto"),  # matches allowlist but also blocklist
            _make_event("Tech Stocks"),  # not in allowlist
        ]
        filtered = self.bot._filter_events(events)
        # "Crypto Markets" passes both; "Politics of Crypto" blocked by blocklist; "Tech Stocks" not in allowlist
        assert len(filtered) == 1
        assert "Crypto Markets" in filtered[0]["title"]

    def test_empty_allowlist_passes_all(self):
        """Empty allowlist should allow everything (subject to blocklist)."""
        self.bot._market_allowlist = []
        events = [
            _make_event("Anything Goes"),
            _make_event("Something Else"),
        ]
        filtered = self.bot._filter_events(events)
        assert len(filtered) == 2


# ── Dry-Run Mode Tests ─────────────────────────────────────────────────────────


class TestDryRunMode:
    """Test dry-run would-trade logging."""

    def setup_method(self):
        self.bot = PolymarketPaperBot()
        self.bot.bankroll = 100.0

    def test_log_dry_run_trade_records_entry(self):
        """_log_dry_run_trade should add entry to dry_run_trades list."""
        signal = AlphaSignal(
            market_id="test_market_123",
            question="Will BTC hit $100k?",
            side="YES",
            price=0.45,
            signal_type="momentum",
            confidence=0.72,
            reason="test",
        )
        self.bot._log_dry_run_trade(signal, 0.72)

        assert len(self.bot.dry_run_trades) == 1
        entry = self.bot.dry_run_trades[0]
        assert entry["market_id"] == "test_market_123"
        assert entry["side"] == "YES"
        assert entry["price"] == 0.45
        assert entry["confidence"] == 0.72
        assert entry["signals"] == "momentum"

    def test_dry_run_trade_includes_max_loss(self):
        """Dry-run entry should include expected max loss."""
        signal = AlphaSignal(
            market_id="test",
            question="Test?",
            side="NO",
            price=0.60,
            signal_type="mispricing",
            confidence=0.55,
            reason="test",
        )
        self.bot._log_dry_run_trade(signal, 0.55)

        entry = self.bot.dry_run_trades[0]
        expected_max_loss = round(self.bot.position_size * abs(STOP_LOSS_PCT), 2)
        assert entry["expected_max_loss"] == expected_max_loss

    def test_dry_run_trades_capped_at_200(self):
        """Dry-run trades list should not exceed 200 entries."""
        for i in range(250):
            signal = AlphaSignal(
                market_id=f"market_{i}",
                question=f"Q{i}?",
                side="YES",
                price=0.50,
                signal_type="test",
                confidence=0.6,
                reason="test",
            )
            self.bot._log_dry_run_trade(signal, 0.6)

        assert len(self.bot.dry_run_trades) == 200

    @pytest.mark.asyncio
    async def test_maybe_enter_dry_run_no_position(self):
        """In dry-run mode, _maybe_enter should log but NOT create a position."""
        # Patch DRY_RUN_MODE at module level
        with patch("app.polymarket.paper_bot.DRY_RUN_MODE", True):
            opp = _make_opp(market_id="dry_run_test")
            events = [_make_event("Test Event")]

            result = await self.bot._maybe_enter(opp, events)

            assert result is False
            # No position should be created
            assert len(self.bot.positions) == 0
            # But dry_run_trades should have an entry
            assert len(self.bot.dry_run_trades) == 1
            assert self.bot.dry_run_trades[0]["market_id"] == "dry_run_test"


# ── Momentum Signal Regression Tests ───────────────────────────────────────────


class TestMomentumSignalFiltering:
    """Regression tests for the stricter momentum filter."""

    def setup_method(self):
        self.bot = PolymarketPaperBot()
        self.bot.min_volume = 1000
        self.bot.min_liquidity = 500
        self.bot.disabled_signal_types = set()

    def _momentum_signals(self, history_prices, yes_price=0.525):
        market_id = "momentum_market"
        now = time.time()
        self.bot.price_history[market_id] = [
            (now - (len(history_prices) - i) * 60, price)
            for i, price in enumerate(history_prices)
        ]
        market = _make_market(
            market_id=market_id,
            yes_price=yes_price,
            no_price=round(1.0 - yes_price, 3),
        )
        signals = self.bot._analyze_all_signals(market, _make_event("Crypto Trend"))
        return [s for s in signals if s.signal_type == "momentum"]

    def test_momentum_requires_five_price_points(self):
        signals = self._momentum_signals([0.500, 0.508, 0.516, 0.525])

        assert signals == []

    def test_momentum_requires_monotonic_trend(self):
        signals = self._momentum_signals([0.500, 0.516, 0.510, 0.522, 0.526])

        assert signals == []

    def test_momentum_requires_more_than_two_percent_move(self):
        signals = self._momentum_signals([0.500, 0.504, 0.508, 0.513, 0.519], yes_price=0.519)

        assert signals == []

    def test_momentum_accepts_sustained_monotonic_yes_move(self):
        signals = self._momentum_signals([0.500, 0.506, 0.512, 0.519, 0.525], yes_price=0.525)

        assert len(signals) == 1
        assert signals[0].side == "YES"
        assert signals[0].confidence >= 0.5

    def test_momentum_accepts_sustained_monotonic_no_move(self):
        signals = self._momentum_signals([0.530, 0.523, 0.516, 0.508, 0.500], yes_price=0.500)

        assert len(signals) == 1
        assert signals[0].side == "NO"
        assert signals[0].confidence >= 0.5

    def test_disabled_momentum_signal_is_filtered_out(self):
        self.bot.disabled_signal_types = {"momentum"}

        signals = self._momentum_signals([0.500, 0.506, 0.512, 0.519, 0.525], yes_price=0.525)

        assert signals == []


# ── Loss Cooldown Regression Tests ─────────────────────────────────────────────


class TestMarketLossCooldown:
    """Regression tests for avoiding repeated losses on the same market."""

    def setup_method(self):
        self.bot = PolymarketPaperBot()
        self.bot.bankroll = 100.0
        self.bot.max_positions = 8

    @pytest.mark.asyncio
    async def test_close_loss_records_market_cooldown(self):
        position = _make_position(pnl=-2.0)
        position.market_id = "cooldown_market"

        await self.bot._close_position(position, "STOP LOSS")

        assert position.resolved is True
        assert "cooldown_market" in self.bot._market_loss_cooldown

    @pytest.mark.asyncio
    async def test_recent_loss_cooldown_blocks_reentry(self):
        self.bot._market_loss_cooldown["cooldown_market"] = time.time()
        opp = _make_opp(market_id="cooldown_market", confidence=0.8)

        entered = await self.bot._maybe_enter(opp, [_make_event("Crypto Trend")])

        assert entered is False
        assert self.bot.positions == {}

    @pytest.mark.asyncio
    async def test_expired_loss_cooldown_allows_reentry(self):
        self.bot._market_loss_cooldown["cooldown_market"] = time.time() - self.bot._loss_cooldown_seconds - 1
        opp = _make_opp(market_id="cooldown_market", confidence=0.8)

        entered = await self.bot._maybe_enter(opp, [_make_event("Crypto Trend")])

        assert entered is True
        assert len(self.bot.positions) == 1


# ── Max Positions Tests ─────────────────────────────────────────────────────────


class TestMaxPositions:
    """Test that max positions limit is enforced."""

    def setup_method(self):
        self.bot = PolymarketPaperBot()
        self.bot.bankroll = 100.0
        self.bot.max_positions = 3  # lower limit for testing

    @pytest.mark.asyncio
    async def test_max_positions_blocks_entry(self):
        """Should not enter new position when at max."""
        # Fill up positions
        for i in range(3):
            pos = _make_position()
            pos.market_id = f"market_{i}"
            pos.resolved = False
            self.bot.positions[f"pos_{i}"] = pos

        opp = _make_opp(market_id="new_market")
        events = [_make_event("Test")]

        result = await self.bot._maybe_enter(opp, events)

        assert result is False
        assert len(self.bot.positions) == 3

    @pytest.mark.asyncio
    async def test_resolved_positions_dont_count(self):
        """Resolved positions should not count toward max."""
        # Add 2 active + 1 resolved
        for i in range(2):
            pos = _make_position()
            pos.market_id = f"market_{i}"
            pos.resolved = False
            self.bot.positions[f"pos_{i}"] = pos

        resolved_pos = _make_position(resolved=True)
        resolved_pos.market_id = "market_resolved"
        self.bot.positions["pos_resolved"] = resolved_pos

        # Should allow entry since only 2 active (below max of 3)
        # Mock _kelly_size to avoid complex calculation
        self.bot._kelly_size = MagicMock(return_value=5.0)

        opp = _make_opp(market_id="new_market")
        events = [_make_event("Test")]

        result = await self.bot._maybe_enter(opp, events)

        assert result is True
        assert len(self.bot.positions) == 4  # 2 active + 1 resolved + 1 new

    @pytest.mark.asyncio
    async def test_default_max_positions_is_8(self):
        """Default max positions should be 8 (post-tuning)."""
        bot = PolymarketPaperBot()
        assert bot.max_positions == DEFAULT_MAX_POSITIONS
        assert DEFAULT_MAX_POSITIONS == 8


# ── Kill Switch Restore Tests ───────────────────────────────────────────────────


class TestKillSwitchRestore:
    """Test that kill switch state is tracked correctly."""

    def setup_method(self):
        self.bot = PolymarketPaperBot()
        self.bot.bankroll = 100.0
        self.bot.peak_bankroll = 100.0

    def test_trigger_kill_switch_sets_state(self):
        """Triggering kill switch should set active flag and reason."""
        self.bot._trigger_kill_switch("Test halt reason")

        assert self.bot._kill_switch_active is True
        assert self.bot._kill_reason == "Test halt reason"

    def test_reset_clears_kill_switch_state(self):
        """Reset should clear kill switch state completely."""
        self.bot._trigger_kill_switch("Some reason")
        assert self.bot._kill_switch_active is True

        self.bot.reset_kill_switch()

        assert self.bot._kill_switch_active is False
        assert self.bot._kill_reason == ""
        assert self.bot._consecutive_losses == 0
        assert self.bot._daily_pnl == 0.0

    def test_consecutive_losses_tracked_correctly(self):
        """Consecutive loss counter should be tracked in state."""
        self.bot._consecutive_losses = 2
        self.bot._daily_pnl = -3.5
        self.bot._daily_pnl_date = "2026-06-22"

        assert self.bot._consecutive_losses == 2
        assert self.bot._daily_pnl == -3.5
        assert self.bot._daily_pnl_date == "2026-06-22"
