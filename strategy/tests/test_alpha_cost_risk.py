from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

from app.alpha import AlphaResearchConfig, DecisionJournal, SelectiveAlphaEvaluator, load_alpha_cases


def inputs():
    case = load_alpha_cases(Path(__file__).parent / "fixtures/alpha/prediction_binary_cases.jsonl")[0]
    evaluator = SelectiveAlphaEvaluator(AlphaResearchConfig(forward_start=case.observation.observed_at).risk_budget)
    return case, evaluator


def test_cost_can_destroy_edge_and_missing_cost_blocks():
    case, evaluator = inputs()
    decision = evaluator.evaluate(case.thesis, replace(case.observation, cost_per_unit=0.2))
    assert decision.expected_edge == pytest.approx(-0.08)
    assert decision.action != "TRADE_PAPER"
    assert evaluator.evaluate(case.thesis, replace(case.observation, cost_per_unit=None)).action == "WAIT"


def test_risk_is_full_purchase_cost_not_claimed_stop_loss():
    case, evaluator = inputs()
    decision = evaluator.evaluate(replace(case.thesis, target_units=10), replace(case.observation, available_size=10))
    assert decision.risk_amount == pytest.approx(5.1)
    assert "thesis_loss_budget_exceeded" in decision.reason_codes
    assert decision.action == "WAIT"


def test_direct_evaluator_rejects_future_evidence_and_ages_quote():
    case, evaluator = inputs()
    evidence = replace(case.thesis.evidence[0], observed_at=case.observation.observed_at + timedelta(seconds=1))
    decision = evaluator.evaluate(replace(case.thesis, evidence=(evidence,)), case.observation)
    assert "future_evidence" in decision.reason_codes
    later = evaluator.evaluate(case.thesis, case.observation, now=case.observation.observed_at + timedelta(seconds=40))
    assert "stale_quote" in later.reason_codes


@pytest.mark.parametrize("risk", [float("nan"), float("inf"), -1])
def test_nonfinite_or_negative_exposure_is_rejected(risk):
    case, evaluator = inputs()
    with pytest.raises(ValueError):
        evaluator.evaluate(case.thesis, case.observation, open_risk=risk)


def test_journal_preserves_cost_basis_and_retry_after_settlement():
    case, evaluator = inputs()
    decision = evaluator.evaluate(case.thesis, case.observation)
    journal = DecisionJournal()
    journal.record_decision(decision, thesis=case.thesis)
    settled = journal.settle(decision.decision_id, case.settlement)
    assert journal.record_decision(decision) == settled
    event = journal.export_events()[-1]
    assert event["evaluation"]["metadata"]["cost_per_unit"] == 0.01
    assert event["decision"]["risk_amount"] == pytest.approx(0.51)
