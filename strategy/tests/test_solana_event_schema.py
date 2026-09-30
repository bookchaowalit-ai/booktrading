from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.market_intel.solana_event_schema import (
    FinalityStatus,
    ReorgStatus,
    SolanaSellEvent,
    append_status_revision,
    compute_event_id,
    is_monitor_eligible,
    make_status_revision,
)

NOW = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


def make_event(**overrides: object) -> SolanaSellEvent:
    values: dict[str, object] = {
        "event_schema_version": "solana-event.v1",
        "chain": "solana",
        "protocol": "raydium",
        "program_id": "FakeRaydiumProgram",
        "event_type": "sell",
        "signature": "FakeSignature",
        "slot": 100,
        "instruction_index": 2,
        "event_index": 0,
        "token_address": "FakeToken",
        "pool_address": "FakePool",
        "seller_wallet": "FakeSeller",
        "token_amount_raw": "123456789012345678901",
        "quote_amount_raw": "987654321",
        "quote_mint": "FakeQuote",
        "observed_at": NOW,
        "source": "fixture",
        "decoder_version": "fixture-decoder.v1",
        "decoder_status": "verified",
        "finality_status": "finalized",
        "reorg_status": "canonical",
    }
    values.update(overrides)
    values["event_id"] = compute_event_id(
        str(values["chain"]),
        str(values["protocol"]),
        str(values["program_id"]),
        str(values["signature"]),
        int(values["instruction_index"]),
        int(values["event_index"]),
    )
    return SolanaSellEvent(**values)


def test_event_identity_is_deterministic_and_position_sensitive():
    first = make_event()
    second = make_event()

    assert first.event_id == second.event_id
    assert first.event_id == compute_event_id("solana", "raydium", "FakeRaydiumProgram", "FakeSignature", 2, 0)
    assert make_event(event_index=1).event_id != first.event_id


def test_raw_amounts_are_integer_base_units_without_float_conversion():
    event = make_event()

    assert event.token_amount_raw == 123456789012345678901
    assert event.quote_amount_raw == 987654321
    assert isinstance(event.as_dict()["token_amount_raw"], int)
    with pytest.raises(ValueError, match="token_amount_raw"):
        make_event(token_amount_raw=1.5)


def test_invalid_status_enum_is_rejected():
    with pytest.raises(ValueError, match="finality_status"):
        make_event(finality_status="settled")
    with pytest.raises(ValueError, match="reorg_status"):
        make_event(reorg_status="reverted")


def test_status_revision_is_append_only_and_preserves_identity():
    original = make_event(finality_status="confirmed", reorg_status="pending")
    revision = make_status_revision(
        original,
        finality_status=FinalityStatus.FINALIZED,
        reorg_status=ReorgStatus.CANONICAL,
        revised_at=NOW,
        reason="fixture finality update",
    )
    revised = append_status_revision(original, revision)

    assert original.finality_status is FinalityStatus.CONFIRMED
    assert revised.finality_status is FinalityStatus.FINALIZED
    assert revised.reorg_status is ReorgStatus.CANONICAL
    assert revised.event_id == original.event_id
    assert revision.as_dict()["event_id"] == original.event_id

    with pytest.raises(ValueError, match="immutable field"):
        append_status_revision(original, {"token_address": "OtherToken"})


@pytest.mark.parametrize(
    ("finality_status", "reorg_status", "eligible"),
    [
        ("processed", "canonical", False),
        ("confirmed", "canonical", False),
        ("finalized", "pending", False),
        ("finalized", "orphaned", False),
        ("finalized", "unknown", False),
        ("finalized", "canonical", True),
    ],
)
def test_only_finalized_canonical_events_are_monitor_eligible(
    finality_status: str,
    reorg_status: str,
    eligible: bool,
):
    event = make_event(finality_status=finality_status, reorg_status=reorg_status)

    assert event.monitor_eligible is eligible
    assert is_monitor_eligible(event) is eligible


def test_unverified_decoder_output_never_reaches_monitor():
    event = make_event(decoder_status="unverified")

    assert event.monitor_eligible is False
    assert is_monitor_eligible(event) is False


def test_usd_valuation_is_optional_evidence_and_not_fabricated():
    without_value = make_event()
    with_value = make_event(quote_value_usd=12.5)

    assert "quote_value_usd" not in without_value.as_dict()
    assert with_value.as_dict()["quote_value_usd"] == 12.5
