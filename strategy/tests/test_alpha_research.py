from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.alpha.models import AlphaEvidence
from app.alpha.research import (
    AlphaResearchCase,
    AlphaResearchConfig,
    AlphaResearchError,
    load_alpha_cases,
    run_alpha_research,
)

FIXTURE = Path(__file__).parent / "fixtures" / "alpha" / "prediction_binary_cases.jsonl"
FORWARD_START = datetime(2026, 9, 13, tzinfo=UTC)


def test_alpha_fixture_replay_separates_train_and_forward_evidence():
    cases = load_alpha_cases(FIXTURE)
    report = run_alpha_research(
        cases,
        config=AlphaResearchConfig(forward_start=FORWARD_START),
    )

    assert report.case_count == 6
    assert report.train_case_count == 3
    assert report.forward_case_count == 3
    assert report.train_summary.paper_trade_count == 1
    assert report.train_summary.watch_count == 1
    assert report.train_summary.wait_count == 1
    assert report.train_summary.realized_pnl == pytest.approx(0.08)
    assert report.forward_summary.paper_trade_count == 2
    assert report.forward_summary.wait_count == 1
    assert report.forward_summary.settled_trade_count == 2
    assert report.forward_summary.realized_pnl == pytest.approx(0.01)
    assert report.forward_summary.win_rate == pytest.approx(0.5)
    assert report.forward_summary.max_drawdown == pytest.approx(0.05)
    assert report.forward_gate == "PAPER_EVIDENCE_REVIEW_REQUIRED"
    assert report.pending_paper_trade_count == 0
    assert report.open_risk_at_end == pytest.approx(0.0)
    assert len(report.journal_events) == 12
    journal_payload = report.as_dict(include_journal=True)
    assert journal_payload["journal_event_count"] == 12
    assert any(
        event.get("event_type") == "alpha_decision" and event["decision"]["action"] == "WAIT"
        for event in journal_payload["journal_events"]
    )
    assert report.execution_enabled is False
    assert report.as_dict()["execution_enabled"] is False


def test_alpha_replay_rejects_out_of_order_cases():
    cases = load_alpha_cases(FIXTURE)

    with pytest.raises(AlphaResearchError, match="ordered by observation timestamp"):
        run_alpha_research(
            (cases[1], cases[0]),
            config=AlphaResearchConfig(forward_start=FORWARD_START),
        )


def test_alpha_replay_requires_forward_sample_before_review_gate():
    cases = load_alpha_cases(FIXTURE)[:3]
    report = run_alpha_research(
        cases,
        config=AlphaResearchConfig(forward_start=FORWARD_START),
    )

    assert report.forward_case_count == 0
    assert report.forward_gate == "INSUFFICIENT_FORWARD_CASES"


def test_alpha_case_rejects_future_evidence_to_prevent_lookahead():
    case = load_alpha_cases(FIXTURE)[0]
    future_evidence = AlphaEvidence(
        evidence_id="future-evidence",
        source="fixture",
        observed_at=datetime(2026, 9, 12, 0, 1, tzinfo=UTC),
        summary="Evidence that arrived after the decision quote.",
    )
    future_thesis = replace(case.thesis, evidence=(future_evidence,))

    with pytest.raises(ValueError, match="observed after"):
        AlphaResearchCase(
            case_id="future-evidence-case",
            thesis=future_thesis,
            observation=case.observation,
        )
