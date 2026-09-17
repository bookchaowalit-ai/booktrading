from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.alpha.evaluator import SelectiveAlphaEvaluator
from app.alpha.journal import DecisionJournal, JournalConflictError, as_of_records
from app.alpha.models import AlphaAction, AlphaEvidence, AlphaObservation, AlphaSettlement, AlphaThesis, RiskBudget

NOW = datetime(2026, 9, 12, tzinfo=UTC)


def _thesis() -> AlphaThesis:
    return AlphaThesis(
        thesis_id="journal-thesis",
        market_group="prediction_binary",
        platform_id="world_xyz",
        instrument_id="journal-market",
        direction="buy_yes",
        hypothesis="A journal test thesis with explicit risk.",
        fair_value=0.7,
        max_entry_price=0.55,
        target_exit_price=0.65,
        invalidation_price=0.4,
        max_loss=0.65,
        capital_at_risk=0.65,
        confidence=0.9,
        evidence=(
            AlphaEvidence(
                evidence_id="journal-evidence",
                source="fixture",
                observed_at=NOW,
                summary="Journal fixture evidence.",
            ),
        ),
        created_at=NOW,
        strategy_version="prediction_binary_v1",
        expected_edge=0.1,
        status="active",
    )


def _observation(observation_id: str = "journal-observation", price: float = 0.5) -> AlphaObservation:
    return AlphaObservation(
        observation_id=observation_id,
        thesis_id="journal-thesis",
        platform_id="world_xyz",
        instrument_id="journal-market",
        observed_at=NOW,
        price=price,
        cost_per_unit=0.01,
        available_size=1.0,
        quote_age_seconds=1.0,
    )


def _evaluator() -> SelectiveAlphaEvaluator:
    return SelectiveAlphaEvaluator(
        RiskBudget(
            starting_capital=1000.0,
            max_total_risk=100.0,
            max_trade_risk=10.0,
            max_open_positions=3,
            min_confidence=0.65,
            min_expected_edge=0.05,
            max_quote_age_seconds=30.0,
        )
    )


def test_journal_records_selected_and_rejected_decisions_and_settles_idempotently():
    thesis = _thesis()
    evaluator = _evaluator()
    selected = evaluator.evaluate(thesis, _observation())
    rejected = evaluator.evaluate(thesis, _observation("journal-watch", price=0.6))
    journal = DecisionJournal()

    journal.register_thesis(thesis)
    selected_record = journal.record_decision(selected)
    rejected_record = journal.record_decision(rejected)
    settlement = AlphaSettlement(
        outcome="win",
        realized_pnl=0.08,
        settled_at=NOW + timedelta(minutes=10),
    )
    settled = journal.settle(selected.decision_id, settlement)

    assert selected_record.outcome.value == "pending"
    assert rejected_record.action is AlphaAction.WATCH
    assert rejected_record.outcome.value == "not_taken"
    assert settled.is_settled
    assert journal.settle(selected.decision_id, settlement) == settled
    summary = journal.summary()
    assert summary.decision_count == 2
    assert summary.paper_trade_count == 1
    assert summary.watch_count == 1
    assert summary.not_taken_count == 1
    assert summary.wins == 1
    assert summary.realized_pnl == pytest.approx(0.08)
    assert summary.win_rate == pytest.approx(1.0)


def test_journal_rejects_conflicting_reuse_of_settlement():
    thesis = _thesis()
    decision = _evaluator().evaluate(thesis, _observation())
    journal = DecisionJournal()
    journal.record_decision(decision, thesis=thesis)

    with pytest.raises(JournalConflictError):
        journal.settle(
            decision.decision_id,
            AlphaSettlement(
                outcome="loss",
                realized_pnl=-0.05,
                settled_at=NOW + timedelta(minutes=10),
            ),
        )
        journal.settle(
            decision.decision_id,
            AlphaSettlement(
                outcome="win",
                realized_pnl=0.08,
                settled_at=NOW + timedelta(minutes=10),
            ),
        )


def test_as_of_slice_does_not_expose_future_settlement():
    thesis = _thesis()
    decision = _evaluator().evaluate(thesis, _observation())
    journal = DecisionJournal()
    journal.record_decision(decision, thesis=thesis)
    journal.settle(
        decision.decision_id,
        AlphaSettlement(
            outcome="win",
            realized_pnl=0.08,
            settled_at=NOW + timedelta(hours=1),
        ),
    )

    visible = as_of_records(journal.records, NOW + timedelta(minutes=1))

    assert visible[0].outcome.value == "pending"
    assert visible[0].realized_pnl is None
    assert visible[0].settled_at is None
