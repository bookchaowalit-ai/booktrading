from __future__ import annotations

from pathlib import Path

import pytest

from app.portfolio.integrations import (
    PortfolioIntegrationError,
    replay_world_to_portfolio,
    world_report_to_paper_trades,
)
from app.portfolio.ledger import PaperPortfolioLedger
from app.world.replay import WorldReplayReport, load_replay_fixture

FIXTURE = Path(__file__).parent / "fixtures" / "world_markets" / "replay.jsonl"


def test_world_replay_is_recorded_in_the_shared_paper_ledger():
    frames = load_replay_fixture(FIXTURE)
    ledger = PaperPortfolioLedger()

    first = replay_world_to_portfolio(frames, ledger=ledger)
    second = replay_world_to_portfolio(frames, ledger=ledger)

    assert first.market_report.net_pnl == pytest.approx(0.0553)
    assert first.portfolio_snapshot.paper_realized_pnl == pytest.approx(0.0553)
    assert first.portfolio_snapshot.reporting_currency == "USD"
    assert first.paper_trade_ids == second.paper_trade_ids
    assert first.portfolio_snapshot.as_dict() == second.portfolio_snapshot.as_dict()
    assert len(ledger.trades) == 1
    assert ledger.trades[0].metadata["synthetic_legs"] == 2


def test_world_zero_payout_becomes_a_valid_losing_paper_trade():
    report = WorldReplayReport(
        frame_count=1,
        market_observations=1,
        invalid_market_observations=0,
        signal_count=1,
        buy_both_signal_count=1,
        entry_count=1,
        resolved_entry_count=1,
        unresolved_entry_count=0,
        gross_pnl=-0.9,
        net_pnl=-0.91,
        win_rate=0.0,
        max_drawdown=0.91,
        stale_signal_count=0,
        partial_fill_entry_count=0,
        unresolved_cost=0.0,
        max_open_exposure=0.91,
        assumptions={},
        trades=(
            {
                "ticker": "ZERO-PAYOUT",
                "entered_at": "2026-09-12T00:00:00+00:00",
                "yes_ask": 0.45,
                "no_ask": 0.45,
                "filled_units": 1.0,
                "fill_ratio": 1.0,
                "quote_age_seconds": 0.0,
                "gross_cost": 0.9,
                "fees": 0.01,
                "slippage": 0.0,
                "total_cost": 0.91,
                "payout": 0.0,
                "resolved_at": "2026-09-12T00:15:00+00:00",
                "gross_pnl": -0.9,
                "net_pnl": -0.91,
                "status": "resolved",
            },
        ),
    )

    trades = world_report_to_paper_trades(report)

    assert trades[0].exit_price == 0.0
    assert trades[0].net_pnl == pytest.approx(-0.91)


def test_world_report_conversion_quarantines_malformed_records():
    report = WorldReplayReport(
        frame_count=1,
        market_observations=0,
        invalid_market_observations=0,
        signal_count=0,
        buy_both_signal_count=0,
        entry_count=1,
        resolved_entry_count=0,
        unresolved_entry_count=1,
        gross_pnl=0.0,
        net_pnl=0.0,
        win_rate=0.0,
        max_drawdown=0.0,
        stale_signal_count=0,
        partial_fill_entry_count=0,
        unresolved_cost=0.0,
        max_open_exposure=0.0,
        assumptions={},
        trades=({"ticker": "BROKEN", "status": "unresolved"},),
    )

    with pytest.raises(PortfolioIntegrationError, match="filled_units"):
        world_report_to_paper_trades(report)
