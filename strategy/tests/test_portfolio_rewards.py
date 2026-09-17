from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.portfolio.ledger import PaperPortfolioLedger
from app.portfolio.rewards import convert_airdrop_tasks, sync_airdrop_tracker_to_ledger

NOW = datetime(2026, 9, 12, 1, 0, tzinfo=UTC)


def _task(**overrides):
    task = {
        "task_id": "task-1",
        "name": "Example Airdrop",
        "chain": "Base",
        "estimated_value": "$500-1000",
        "cost": "Gas fees only (~$5-20)",
        "url": "https://example.com/airdrop",
        "status": "not_started",
        "created_at": "2026-09-12T00:00:00Z",
        "updated_at": "2026-09-12T00:10:00Z",
    }
    task.update(overrides)
    return task


def test_airdrop_tasks_become_conservative_reward_entries():
    report = convert_airdrop_tasks(
        (
            _task(),
            _task(task_id="completed-1", status="completed"),
            _task(
                task_id="claimed-1",
                status="claimed",
                realized_value=12.0,
                actual_cost=1.5,
                estimated_value="$12-20",
            ),
            _task(task_id="bad-status", status="mystery"),
            _task(task_id="bad-url", url="https://user:password@example.com/airdrop"),
            object(),
        ),
        now=NOW,
    )

    assert len(report.entries) == 3
    assert len(report.quarantined) == 3
    assert report.entries[0].status.value == "candidate"
    assert report.entries[0].estimated_value == pytest.approx(500.0)
    assert report.entries[0].cost == pytest.approx(0.0)
    assert report.entries[1].status.value == "eligible"
    assert report.entries[1].realized_value is None
    assert report.entries[2].status.value == "claimed"
    assert report.entries[2].realized_net_value == pytest.approx(10.5)
    assert report.quarantined[0]["task_id"] == "bad-status"
    assert report.quarantined[2]["task_id"] == "row-5"
    assert report.as_dict()["execution_enabled"] is False


@pytest.mark.asyncio
async def test_tracker_sync_is_read_only_and_idempotent_in_the_ledger():
    class FakeTracker:
        async def list_tasks(self):
            return [_task(task_id="sync-1", status="eligible", estimated_value="$25-50")]

    ledger = PaperPortfolioLedger()
    first = await sync_airdrop_tracker_to_ledger(FakeTracker(), ledger, now=NOW)
    second = await sync_airdrop_tracker_to_ledger(FakeTracker(), ledger, now=NOW)

    assert len(first.entries) == 1
    assert len(second.entries) == 1
    assert len(ledger.rewards) == 1
    snapshot = ledger.snapshot(as_of=NOW)
    assert snapshot.rewards_pending_estimate == pytest.approx(25.0)
    assert snapshot.rewards_realized_net == pytest.approx(0.0)
