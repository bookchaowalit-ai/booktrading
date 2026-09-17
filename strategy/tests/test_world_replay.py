from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.world.models import WorldMarket
from app.world.replay import (
    WorldReplayConfig,
    WorldReplayError,
    WorldReplayFrame,
    WorldReplayRunner,
    WorldSettlement,
    load_replay_fixture,
)

FIXTURE = Path(__file__).parent / "fixtures" / "world_markets" / "replay.jsonl"


def test_fixture_replay_is_deterministic_and_resolves_after_entry():
    frames = load_replay_fixture(FIXTURE)
    runner = WorldReplayRunner(config=WorldReplayConfig(fee_bps_per_leg=50.0))

    first = runner.run(frames)
    second = runner.run(frames)

    assert first.as_dict() == second.as_dict()
    assert first.frame_count == 3
    assert first.market_observations == 2
    assert first.invalid_market_observations == 0
    assert first.signal_count == 1
    assert first.buy_both_signal_count == 1
    assert first.entry_count == 1
    assert first.resolved_entry_count == 1
    assert first.unresolved_entry_count == 0
    assert first.net_pnl == pytest.approx(0.0553)
    assert first.as_dict()["assumptions"] == {
        "fee_bps_per_leg": 50.0,
        "max_quote_age_seconds": 30.0,
        "max_open_positions": 100,
        "min_net_edge": 0.0,
        "slippage_bps_per_leg": 0.0,
        "target_units": 1.0,
        "unknown_size_fill_ratio": 1.0,
    }
    assert first.trades[0]["status"] == "resolved"
    assert first.trades[0]["resolved_at"] == "2026-09-12T00:15:00+00:00"


def test_replay_rejects_out_of_order_frames():
    frames = load_replay_fixture(FIXTURE)

    with pytest.raises(WorldReplayError, match="ordered by observed_at"):
        WorldReplayRunner().run((frames[1], frames[0]))


def test_replay_processes_same_timestamp_settlement_before_quotes():
    market = WorldMarket(
        ticker="SAME-TIME",
        question="Same timestamp settlement?",
        status="active",
        yes_bid=0.42,
        yes_ask=0.44,
        no_bid=0.48,
        no_ask=0.50,
        volume=5_000,
        liquidity=2_000,
        strike_date="2026-09-12T00:00:00Z",
        resolution_source="provider_rulebook",
    )
    frame = WorldReplayFrame(
        observed_at=datetime(2026, 9, 12, tzinfo=UTC),
        markets=(market,),
        settlements=(WorldSettlement(ticker="SAME-TIME", payout=1.0),),
    )

    report = WorldReplayRunner().run((frame,))

    assert report.signal_count == 1
    assert report.entry_count == 0


def test_replay_accounts_for_available_size_and_partial_fill():
    market = WorldMarket(
        ticker="PARTIAL",
        question="Partial fill?",
        status="active",
        yes_bid=0.42,
        yes_ask=0.44,
        no_bid=0.48,
        no_ask=0.50,
        yes_ask_size=0.4,
        no_ask_size=0.8,
        volume=5_000,
        liquidity=2_000,
        strike_date="2026-09-12T00:15:00Z",
        resolution_source="provider_rulebook",
        updated_at=datetime(2026, 9, 12, 0, 0, tzinfo=UTC),
    )
    frames = (
        WorldReplayFrame(observed_at=datetime(2026, 9, 12, tzinfo=UTC), markets=(market,)),
        WorldReplayFrame(
            observed_at=datetime(2026, 9, 12, 0, 15, tzinfo=UTC),
            settlements=(WorldSettlement(ticker="PARTIAL", payout=1.0),),
        ),
    )

    report = WorldReplayRunner(config=WorldReplayConfig(fee_bps_per_leg=50.0)).run(frames)

    assert report.entry_count == 1
    assert report.partial_fill_entry_count == 1
    assert report.trades[0]["filled_units"] == pytest.approx(0.4)
    assert report.trades[0]["payout"] == pytest.approx(0.4)
    assert report.net_pnl == pytest.approx(0.02212)


def test_replay_skips_signal_when_quote_is_stale():
    market = WorldMarket(
        ticker="STALE",
        question="Stale quote?",
        status="active",
        yes_bid=0.42,
        yes_ask=0.44,
        no_bid=0.48,
        no_ask=0.50,
        volume=5_000,
        liquidity=2_000,
        strike_date="2026-09-12T00:15:00Z",
        resolution_source="provider_rulebook",
        updated_at=datetime(2026, 9, 12, tzinfo=UTC),
    )

    report = WorldReplayRunner().run(
        (WorldReplayFrame(observed_at=datetime(2026, 9, 12, 0, 1, tzinfo=UTC), markets=(market,)),)
    )

    assert report.signal_count == 1
    assert report.stale_signal_count == 1
    assert report.entry_count == 0
