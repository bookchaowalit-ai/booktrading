import hashlib
import json
import subprocess
import sys
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.alpha import AlphaEvidence, AlphaResearchConfig, SelectiveAlphaEvaluator, load_alpha_cases
from app.alpha.world_snapshot import ReviewedMapping, evaluate_world_snapshot, local_object
from app.world.landing import WorldLandingWriter

NOW = datetime(2026, 9, 12, tzinfo=UTC)


@pytest.fixture
def snapshot(tmp_path):
    raw_evidence = b"Synthetic official release; fixture only."
    evidence_path = tmp_path / "landing" / "release.txt"
    evidence_path.parent.mkdir()
    evidence_path.write_bytes(raw_evidence)
    digest = hashlib.sha256(raw_evidence).hexdigest()
    available = NOW - timedelta(seconds=10)
    evidence = AlphaEvidence(
        evidence_id="release",
        source="fixture",
        observed_at=available,
        summary="Synthetic release",
        source_url="https://example.org/release",
        raw_sha256=digest,
    )
    base = load_alpha_cases(Path(__file__).parent / "fixtures/alpha/prediction_binary_cases.jsonl")[0]
    thesis = replace(base.thesis, evidence=(evidence,), created_at=available)
    market = {
        "ticker": "EXACT-TICKER",
        "question": "Synthetic outcome?",
        "status": "active",
        "yes_ask": 0.5,
        "yes_ask_size": 2,
        "no_ask": 0.51,
        "no_ask_size": 2,
        "close_time": "2026-09-12T01:00:00Z",
        "resolution_source": "fixture rule v1",
        "updated_at": NOW.isoformat(),
    }
    result = WorldLandingWriter(tmp_path).write_snapshot(
        json.dumps({"events": [{"markets": [market]}]}).encode(),
        endpoint="/events",
        received_at=NOW,
    )
    mapping = ReviewedMapping(
        ticker="EXACT-TICKER",
        thesis_sha256=hashlib.sha256(
            json.dumps(thesis.as_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        ).hexdigest(),
        instrument_id=thesis.instrument_id,
        question=market["question"],
        resolution_source=market["resolution_source"],
        close_time=market["close_time"],
        reviewed_at=available,
        evidence_objects={
            "release": {
                "key": "landing/release.txt",
                "sha256": digest,
                "source_url": evidence.source_url,
                "published_at": available.isoformat(),
                "received_at": available.isoformat(),
            }
        },
    )
    return tmp_path, result, thesis, mapping


def review(snapshot, **overrides):
    root, result, thesis, mapping = snapshot
    args = dict(
        root=root,
        manifest_key=result["manifest_key"],
        thesis=thesis,
        mapping=mapping,
        evaluator=SelectiveAlphaEvaluator(AlphaResearchConfig(forward_start=NOW).risk_budget),
        now=NOW,
        cost_per_unit=0.01,
        open_risk=0,
        open_positions=0,
    )
    args.update(overrides)
    return evaluate_world_snapshot(**args)


def test_committed_snapshot_reaches_journal(snapshot):
    result = review(snapshot)
    assert result["decision"]["action"] == "TRADE_PAPER"
    assert result["decision"]["expected_edge"] == pytest.approx(0.11)
    assert result["observation"]["price"] == 0.5
    assert result["execution_enabled"] is False
    assert len(result["journal_events"]) == 2


def test_selected_no_uses_no_ask(snapshot):
    thesis = replace(snapshot[2], direction="buy_no")
    digest = hashlib.sha256(
        json.dumps(thesis.as_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    assert (
        review(snapshot, thesis=thesis, mapping=replace(snapshot[3], thesis_sha256=digest))["observation"]["price"]
        == 0.51
    )


def test_unreviewed_probability_change_blocks(snapshot):
    with pytest.raises(ValueError, match="changed since review"):
        review(snapshot, thesis=replace(snapshot[2], fair_value=0.99))


@pytest.mark.parametrize(
    "field,value",
    [
        ("question", "Different question"),
        ("ticker", "OTHER"),
        ("resolution_source", "v2"),
        ("instrument_id", "wrong-id"),
    ],
)
def test_contract_mismatch_blocks(snapshot, field, value):
    with pytest.raises(ValueError):
        review(snapshot, mapping=replace(snapshot[3], **{field: value}))


@pytest.mark.parametrize("reference", ["raw_key", "bronze_key"])
def test_corrupted_objects_block(snapshot, reference):
    (snapshot[0] / snapshot[1][reference]).write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="checksum"):
        review(snapshot)


def test_future_review_and_late_evidence_block(snapshot):
    with pytest.raises(ValueError, match="unavailable"):
        review(snapshot, mapping=replace(snapshot[3], reviewed_at=NOW + timedelta(seconds=1)))
    mapping = snapshot[3]
    refs = {"release": {**mapping.evidence_objects["release"], "received_at": (NOW + timedelta(seconds=1)).isoformat()}}
    with pytest.raises(ValueError, match="availability"):
        review(snapshot, mapping=replace(mapping, evidence_objects=refs))


def test_old_snapshot_waits(snapshot):
    result = review(snapshot, now=NOW + timedelta(minutes=1))
    assert result["decision"]["action"] == "WAIT"
    assert "stale_quote" in result["decision"]["reason_codes"]


def test_object_path_cannot_escape(tmp_path):
    with pytest.raises(ValueError):
        local_object(tmp_path, "../outside")


@pytest.mark.parametrize("persistent", [False, True])
def test_cli_replays_snapshot_without_outcome_labels(snapshot, persistent):
    root, manifest, thesis, mapping = snapshot
    thesis_path = root / "thesis.json"
    thesis_path.write_text(json.dumps(thesis.as_dict()))
    policy_path = root / "review.json"
    policy_path.write_text(
        json.dumps(
            {
                "mapping": {**asdict(mapping), "reviewed_at": mapping.reviewed_at.isoformat()},
                "risk_budget": AlphaResearchConfig(forward_start=NOW).risk_budget.as_dict(),
                "cost_per_unit": 0.01,
                "account_scope": "world-paper-usd",
                "quote_currency": "USD",
                "starting_capital": 10.0,
            }
        )
    )
    command = [
        sys.executable,
        "scripts/world_alpha_review.py",
        "--lake-root",
        str(root),
        "--manifest-key",
        manifest["manifest_key"],
        "--thesis",
        str(thesis_path),
        "--review",
        str(policy_path),
        "--open-risk",
        "0",
        "--open-positions",
        "0",
        "--as-of",
        NOW.isoformat(),
    ]
    if persistent:
        i = command.index("--open-risk")
        command[i : i + 4] = ["--journal-db", str(root / "paper.sqlite")]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    report = json.loads(result.stdout)
    assert report["decision"]["action"] == "TRADE_PAPER"
    assert report["historical_replay"] is True
    if persistent:
        retry = subprocess.run(command, capture_output=True, text=True, check=True)
        assert json.loads(retry.stdout)["journal_retry"] is True
        assert report["portfolio"]["open_positions_after"] == 1
        settlement_path = root / "landing" / "settlement.json"
        settlement_bytes = b'{"ticker":"EXACT-TICKER","payout_per_unit":1}'
        settlement_path.write_bytes(settlement_bytes)
        settle_command = [
            sys.executable,
            "scripts/world_alpha_settle.py",
            "--journal-db",
            str(root / "paper.sqlite"),
            "--request-id",
            report["journal_request_id"],
            "--lake-root",
            str(root),
            "--payout-per-unit",
            "1",
            "--evidence-id",
            "official-settlement",
            "--evidence-source",
            "fixture",
            "--evidence-object-key",
            "landing/settlement.json",
            "--evidence-sha256",
            hashlib.sha256(settlement_bytes).hexdigest(),
            "--evidence-url",
            "https://example.org/settlement",
            "--evidence-observed-at",
            NOW.isoformat(),
            "--evidence-summary",
            "Synthetic official result",
            "--ticker",
            "EXACT-TICKER",
            "--settled-at",
            NOW.isoformat(),
        ]
        settled = json.loads(subprocess.run(settle_command, capture_output=True, text=True, check=True).stdout)
        assert settled["settlement"]["outcome"] == "win"
        assert settled["reconciliation"]["realized_pnl"] == pytest.approx(0.49)
        assert settled["reconciliation"]["open_risk_after"] == 0.0
        assert settled["paper_trade"]["account_scope"] == "world-paper-usd"
        assert settled["finance_projection"]["cash_effect"] is False
        assert settled["portfolio"]["capital"]["available_capital"] == pytest.approx(10.49)
        settlement_retry = json.loads(subprocess.run(settle_command, capture_output=True, text=True, check=True).stdout)
        assert settlement_retry["journal_retry"] is True
    assert all("realized_pnl" not in event or event["realized_pnl"] is None for event in report["journal_events"])
