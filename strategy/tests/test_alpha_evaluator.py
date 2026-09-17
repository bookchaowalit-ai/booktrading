from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.alpha.evaluator import SelectiveAlphaEvaluator
from app.alpha.models import AlphaAction, AlphaEvidence, AlphaObservation, AlphaThesis, RiskBudget

NOW = datetime(2026, 9, 12, tzinfo=UTC)


def _thesis(**overrides: object) -> AlphaThesis:
    values: dict[str, object] = {
        "thesis_id": "thesis-one",
        "market_group": "prediction_binary",
        "platform_id": "world_xyz",
        "instrument_id": "market-one",
        "direction": "buy_yes",
        "hypothesis": "A bounded evidence signal supports a price below fair value.",
        "fair_value": 0.62,
        "max_entry_price": 0.55,
        "target_exit_price": 0.6,
        "invalidation_price": 0.4,
        "max_loss": 0.65,
        "capital_at_risk": 0.65,
        "confidence": 0.8,
        "evidence": (
            AlphaEvidence(
                evidence_id="evidence-one",
                source="fixture",
                observed_at=NOW,
                summary="Bounded fixture evidence.",
            ),
        ),
        "created_at": NOW,
        "strategy_version": "prediction_binary_v1",
        "expected_edge": 0.08,
        "target_units": 1.0,
        "status": "active",
    }
    values.update(overrides)
    return AlphaThesis(**values)


def _observation(**overrides: object) -> AlphaObservation:
    values: dict[str, object] = {
        "observation_id": "observation-one",
        "thesis_id": "thesis-one",
        "platform_id": "world_xyz",
        "instrument_id": "market-one",
        "observed_at": NOW,
        "price": 0.5,
        "cost_per_unit": 0.01,
        "available_size": 1.0,
        "quote_age_seconds": 2.0,
        "market_status": "active",
    }
    values.update(overrides)
    return AlphaObservation(**values)


def _evaluator(**overrides: object) -> SelectiveAlphaEvaluator:
    values: dict[str, object] = {
        "starting_capital": 1000.0,
        "max_total_risk": 100.0,
        "max_trade_risk": 10.0,
        "max_open_positions": 3,
        "min_confidence": 0.65,
        "min_expected_edge": 0.05,
        "max_quote_age_seconds": 30.0,
    }
    values.update(overrides)
    return SelectiveAlphaEvaluator(RiskBudget(**values))


def test_evaluator_returns_paper_trade_only_when_all_gates_pass():
    decision = _evaluator().evaluate(_thesis(), _observation())

    assert decision.action is AlphaAction.TRADE_PAPER
    assert decision.expected_edge == pytest.approx(0.11)
    assert decision.risk_amount == pytest.approx(0.51)
    assert decision.execution_enabled is False
    assert "paper_only_gate_passed" in decision.reason_codes


def test_evaluator_watches_price_outside_entry_instead_of_chasing():
    decision = _evaluator().evaluate(_thesis(), _observation(price=0.58))

    assert decision.action is AlphaAction.WATCH
    assert "entry_above_max_price" in decision.reason_codes
    assert decision.execution_enabled is False


def test_evaluator_waits_for_stale_or_unknown_quote_and_size():
    stale = _evaluator().evaluate(_thesis(), _observation(quote_age_seconds=31.0))
    unknown = _evaluator().evaluate(_thesis(), _observation(quote_age_seconds=None, available_size=None))

    assert stale.action is AlphaAction.WAIT
    assert "stale_quote" in stale.reason_codes
    assert unknown.action is AlphaAction.WAIT
    assert "quote_age_unknown" in unknown.reason_codes
    assert "available_size_unknown" in unknown.reason_codes


def test_evaluator_waits_when_open_risk_would_breach_budget():
    decision = _evaluator(max_total_risk=0.05, max_trade_risk=0.05).evaluate(_thesis(), _observation(), open_risk=0.01)

    assert decision.action is AlphaAction.WAIT
    assert "total_risk_budget_exceeded" in decision.reason_codes


def test_evaluator_rejects_unsupported_direction_at_model_boundary():
    with pytest.raises(ValueError, match="direction"):
        _thesis(direction="buy_both")


def test_evaluator_metadata_cannot_carry_credentials():
    with pytest.raises(ValueError, match="secret"):
        _thesis(metadata={"api_key": "must-not-be-stored"})
