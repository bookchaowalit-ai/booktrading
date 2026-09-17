import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import UTC, datetime

import pytest

from app.alpha.durable_journal import DurablePaperJournal
from app.alpha.models import SettlementProof

NOW = datetime(2026, 9, 12, tzinfo=UTC)


def result(risk, positions):
    action = "TRADE_PAPER" if positions == 0 else "WAIT"
    decision = {
        "platform_id": "world_xyz",
        "action": action,
        "risk_amount": 0.51,
        "reason_codes": ["test"],
        "metadata": {"target_units": 1.0},
    }
    return {
        "decision": decision,
        "observation": {"price": 0.5, "cost_per_unit": 0.01, "metadata": {"ticker": "one"}},
        "journal_events": [
            {
                "event_type": "alpha_decision",
                "evaluation": deepcopy(decision),
                "decision": {**decision, "outcome": "pending" if positions == 0 else "not_taken"},
            }
        ],
    }


def test_restart_returns_original_without_reevaluation(tmp_path):
    path = tmp_path / "paper.sqlite"
    first = DurablePaperJournal(path).review({"id": 1}, {"version": 1}, result)

    def unexpected(*args):
        raise AssertionError("must not evaluate retry")

    second = DurablePaperJournal(path).review({"id": 1}, {"version": 1}, unexpected)
    assert second["journal_request_id"] == first["journal_request_id"]
    assert second["journal_retry"] is True


def test_concurrent_requests_reserve_only_one_position(tmp_path):
    journal = DurablePaperJournal(tmp_path / "paper.sqlite")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda i: journal.review({"id": i}, {}, result), [1, 2]))
    assert sorted(r["decision"]["action"] for r in results) == ["TRADE_PAPER", "WAIT"]
    assert max(r["portfolio"]["open_risk_after"] for r in results) == 0.51


def test_failure_rolls_back_policy_and_reservation(tmp_path):
    journal = DurablePaperJournal(tmp_path / "paper.sqlite")

    def broken(*args):
        raise ValueError("invalid snapshot")

    with pytest.raises(ValueError):
        journal.review({"id": 1}, {"version": 1}, broken)
    recovered = journal.review({"id": 1}, {"version": 2}, result)
    assert recovered["portfolio"]["open_risk_before"] == 0


def test_policy_cannot_silently_change(tmp_path):
    journal = DurablePaperJournal(tmp_path / "paper.sqlite")
    journal.review({"id": 1}, {"version": 1}, result)
    with pytest.raises(ValueError, match="policy differs"):
        journal.review({"id": 2}, {"version": 2}, result)


def test_same_instrument_is_blocked_even_with_capacity(tmp_path):
    journal = DurablePaperJournal(tmp_path / "paper.sqlite")

    def evaluate(risk, count):
        return result(0, 0)

    journal.review({"id": 1}, {}, evaluate)
    second = journal.review({"id": 2}, {}, evaluate)
    assert second["decision"]["action"] == "WAIT"
    assert second["journal_events"][0]["decision"]["outcome"] == "not_taken"
    assert second["portfolio"]["open_positions_after"] == 1


def test_settlement_verifies_binary_proof_releases_risk_and_is_idempotent(tmp_path):
    db_path = tmp_path / "paper.sqlite"
    journal = DurablePaperJournal(db_path)
    opened = journal.review({"id": 1}, {}, result)
    proof_bytes = json.dumps({"ticker": "one", "payout_per_unit": 1.0}).encode()
    proof_path = tmp_path / "settlement.json"
    proof_path.write_bytes(proof_bytes)
    proof = SettlementProof(
        evidence_id="official-settlement",
        source="fixture",
        object_key="settlement.json",
        raw_sha256=hashlib.sha256(proof_bytes).hexdigest(),
        source_url="https://example.org/settlement",
        observed_at=NOW,
        summary="Synthetic binary settlement",
        metadata={"ticker": "one"},
    )

    settled = journal.settle_binary(
        opened["journal_request_id"],
        payout_per_unit=1.0,
        proof=proof,
        read_evidence=lambda _: proof_path.read_bytes(),
        settled_at=NOW,
    )

    assert settled["settlement"]["outcome"] == "win"
    assert settled["settlement"]["realized_pnl"] == pytest.approx(0.49)
    assert settled["reconciliation"]["released_risk"] == pytest.approx(0.51)
    assert settled["reconciliation"]["open_risk_after"] == 0.0
    assert settled["portfolio"]["open_positions_after_settlement"] == 0
    assert settled["paper_trade"]["account_scope"] == "paper-default"
    assert settled["paper_trade"]["net_pnl"] == pytest.approx(0.49)
    assert settled["finance_projection"]["signed_amount"] == pytest.approx(0.49)
    assert settled["finance_projection"]["cash_effect"] is False
    assert settled["finance_projection"]["posting_status"] == "separate_paper_lane"
    assert settled["journal_events"][0]["decision"]["outcome"] == "win"

    retry = journal.settle_binary(
        opened["journal_request_id"],
        payout_per_unit=1.0,
        proof=proof,
        read_evidence=lambda _: proof_path.read_bytes(),
        settled_at=NOW,
    )
    assert retry["journal_retry"] is True
    assert journal.reconcile(opened["journal_request_id"])["status"] == "reconciled"

    next_review = journal.review({"id": 2}, {}, result)
    assert next_review["decision"]["action"] == "TRADE_PAPER"
    assert next_review["portfolio"]["open_risk_before"] == 0.0


def test_account_scope_isolated_and_settlement_updates_available_capital(tmp_path):
    journal = DurablePaperJournal(tmp_path / "paper.sqlite")
    opened = journal.review(
        {"id": "world"},
        {},
        result,
        account_scope="world-paper-usd",
        quote_currency="USD",
        starting_capital=10.0,
    )
    separate = journal.review(
        {"id": "fomo"},
        {},
        result,
        account_scope="fomo-paper-usd",
        quote_currency="USD",
        starting_capital=5.0,
    )
    assert opened["portfolio"]["open_risk_before"] == 0.0
    assert separate["portfolio"]["open_risk_before"] == 0.0
    assert separate["decision"]["action"] == "TRADE_PAPER"

    proof_bytes = b'{"ticker":"one","payout_per_unit":0}'
    proof = SettlementProof(
        evidence_id="official-settlement",
        source="fixture",
        object_key="settlement.json",
        raw_sha256=hashlib.sha256(proof_bytes).hexdigest(),
        source_url="https://example.org/settlement",
        observed_at=NOW,
        summary="Synthetic loss settlement",
        metadata={"ticker": "one"},
    )
    settled = journal.settle_binary(
        opened["journal_request_id"],
        payout_per_unit=0.0,
        proof=proof,
        read_evidence=lambda _: proof_bytes,
        settled_at=NOW,
    )

    assert settled["portfolio"]["capital"]["starting_capital"] == pytest.approx(10.0)
    assert settled["portfolio"]["capital"]["realized_pnl"] == pytest.approx(-0.51)
    assert settled["portfolio"]["capital"]["available_capital"] == pytest.approx(9.49)
    assert journal.reconcile(opened["journal_request_id"])["capital"]["available_capital"] == pytest.approx(9.49)
    assert journal.reconcile(separate["journal_request_id"])["open_risk_after"] == pytest.approx(0.51)


def test_invalid_settlement_proof_keeps_reservation_open(tmp_path):
    journal = DurablePaperJournal(tmp_path / "paper.sqlite")
    opened = journal.review({"id": 1}, {}, result)
    proof_bytes = b'{"ticker":"one","payout_per_unit":0}'
    proof_path = tmp_path / "settlement.json"
    proof_path.write_bytes(proof_bytes)
    proof = SettlementProof(
        evidence_id="official-settlement",
        source="fixture",
        object_key="settlement.json",
        raw_sha256=hashlib.sha256(proof_bytes).hexdigest(),
        source_url="https://example.org/settlement",
        observed_at=NOW,
        summary="Synthetic binary settlement",
        metadata={"ticker": "one"},
    )

    with pytest.raises(ValueError, match="does not match"):
        journal.settle_binary(
            opened["journal_request_id"],
            payout_per_unit=1.0,
            proof=proof,
            read_evidence=lambda _: proof_path.read_bytes(),
            settled_at=NOW,
        )
    status = journal.reconcile(opened["journal_request_id"])
    assert status["status"] == "pending_settlement"
    assert status["reserved_risk"] == pytest.approx(0.51)
    assert status["open_risk_after"] == pytest.approx(0.51)


def test_settlement_checksum_failure_keeps_reservation_open(tmp_path):
    journal = DurablePaperJournal(tmp_path / "paper.sqlite")
    opened = journal.review({"id": 1}, {}, result)
    proof_path = tmp_path / "settlement.json"
    proof_path.write_bytes(b'{"ticker":"one","payout_per_unit":1}')
    proof = SettlementProof(
        evidence_id="official-settlement",
        source="fixture",
        object_key="settlement.json",
        raw_sha256="0" * 64,
        source_url="https://example.org/settlement",
        observed_at=NOW,
        summary="Synthetic binary settlement",
        metadata={"ticker": "one"},
    )

    with pytest.raises(ValueError, match="checksum"):
        journal.settle_binary(
            opened["journal_request_id"],
            payout_per_unit=1.0,
            proof=proof,
            read_evidence=lambda _: proof_path.read_bytes(),
            settled_at=NOW,
        )
    assert journal.reconcile(opened["journal_request_id"])["status"] == "pending_settlement"
