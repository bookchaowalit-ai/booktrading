from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.portfolio.replay import PortfolioReplayError, load_portfolio_fixture, replay_portfolio_fixture

FIXTURE = Path(__file__).parent / "fixtures" / "portfolio" / "events.jsonl"


def test_portfolio_fixture_replay_keeps_paper_and_reward_totals_separate():
    report = replay_portfolio_fixture(
        FIXTURE,
        as_of=datetime(2026, 9, 12, 1, 0, tzinfo=UTC),
        marks={"BTC-USDT": 102},
    )

    assert report.event_count == 4
    assert report.paper_trade_count == 2
    assert report.reward_count == 2
    assert report.snapshot.paper_realized_pnl == pytest.approx(0.97)
    assert report.snapshot.paper_unrealized_pnl == pytest.approx(3.4)
    assert report.snapshot.rewards_realized_net == pytest.approx(12.0)
    assert report.snapshot.rewards_pending_estimate == pytest.approx(25.0)
    assert report.as_dict()["execution_enabled"] is False


def test_portfolio_fixture_rejects_unsupported_versions(tmp_path: Path):
    fixture = tmp_path / "bad.jsonl"
    fixture.write_text('{"event_version":99,"event_type":"reward","event_id":"x"}\n', encoding="utf-8")

    with pytest.raises(PortfolioReplayError, match="unsupported event_version"):
        load_portfolio_fixture(fixture)
