from __future__ import annotations

from datetime import datetime

import pytest

from app.market_intel.evm_event_schema import (
    EVM_EVENT_SCHEMA_VERSION,
    SUPPORTED_EVM_CHAINS,
    DecoderStatus,
    EVMSellEvent,
    FinalityStatus,
    ReorgStatus,
    append_status_revision,
    compute_event_id,
    event_identity_material,
    is_monitor_eligible,
    make_status_revision,
)

ADDRESS = "0x1111111111111111111111111111111111111111"
TOKEN = "0x2222222222222222222222222222222222222222"
POOL = "0x3333333333333333333333333333333333333333"
SELLER = "0x4444444444444444444444444444444444444444"
QUOTE = "0x5555555555555555555555555555555555555555"
TOPIC = "0x" + "aa" * 32
TRANSACTION = "0x" + "bb" * 32
BLOCK = "0x" + "cc" * 32


def event_values(
    *,
    chain: str = "ethereum",
    block_hash: str = BLOCK,
    finality_status: str = "finalized",
    reorg_status: str = "canonical",
) -> dict[str, object]:
    event_id = compute_event_id(
        chain,
        "fixture",
        ADDRESS,
        TOPIC,
        block_hash,
        TRANSACTION,
        4,
        0,
    )
    return {
        "event_id": event_id,
        "event_schema_version": EVM_EVENT_SCHEMA_VERSION,
        "chain": chain,
        "protocol": "fixture",
        "contract_address": ADDRESS,
        "event_topic": TOPIC,
        "event_type": "sell",
        "transaction_hash": TRANSACTION,
        "block_hash": block_hash,
        "block_number": 7001,
        "log_index": 4,
        "event_index": 0,
        "token_address": TOKEN,
        "pool_address": POOL,
        "seller_wallet": SELLER,
        "token_amount_raw": "123456789012345678901",
        "quote_amount_raw": "987654321",
        "quote_asset": QUOTE,
        "observed_at": "2026-01-02T03:04:05+00:00",
        "source": "fixture",
        "decoder_version": "fixture.v1",
        "decoder_status": "verified",
        "finality_status": finality_status,
        "reorg_status": reorg_status,
    }


@pytest.mark.parametrize("chain", sorted(SUPPORTED_EVM_CHAINS))
def test_supported_chain_names_and_integer_base_units(chain: str):
    event = EVMSellEvent.from_dict(event_values(chain=chain))

    assert event.chain == chain
    assert event.event_type.value == "sell"
    assert event.token_amount_raw == 123456789012345678901
    assert event.quote_amount_raw == 987654321
    assert isinstance(event.token_amount_raw, int)
    assert event.as_dict()["event_schema_version"] == "evm-event.v1"
    assert EVMSellEvent.from_dict(event.as_dict()) == event


def test_identity_normalizes_chain_addresses_topics_and_hashes():
    values = event_values(
        chain="ETHEREUM",
        block_hash=BLOCK.upper(),
    )
    values.update(
        {
            "protocol": "Fixture",
            "contract_address": ADDRESS.upper(),
            "event_topic": TOPIC.upper(),
            "transaction_hash": TRANSACTION.upper(),
        }
    )
    values["event_id"] = compute_event_id(
        "ethereum",
        "fixture",
        ADDRESS,
        TOPIC,
        BLOCK,
        TRANSACTION,
        4,
        0,
    )

    event = EVMSellEvent.from_dict(values)

    assert event.contract_address == ADDRESS
    assert event.event_topic == TOPIC
    assert event.transaction_hash == TRANSACTION
    assert event_identity_material(
        "ETHEREUM",
        "Fixture",
        ADDRESS.upper(),
        TOPIC.upper(),
        BLOCK.upper(),
        TRANSACTION.upper(),
        "0x4",
        "0x0",
    ) == "|".join(("ethereum", "fixture", ADDRESS, TOPIC, BLOCK, TRANSACTION, "4", "0"))


def test_fork_replacement_has_distinct_identity_because_block_hash_is_required():
    first = EVMSellEvent.from_dict(event_values())
    replacement_block = "0x" + "dd" * 32
    replacement = EVMSellEvent.from_dict(event_values(block_hash=replacement_block))

    assert first.event_id != replacement.event_id
    assert first.block_hash != replacement.block_hash

    missing_block = event_values()
    missing_block.pop("block_hash")
    with pytest.raises((TypeError, ValueError)):
        EVMSellEvent.from_dict(missing_block)


@pytest.mark.parametrize(
    "field,value",
    [
        ("token_amount_raw", 1.5),
        ("quote_amount_raw", -1),
        ("event_type", "buy"),
        ("chain", "polygon"),
    ],
)
def test_invalid_sell_evidence_is_rejected(field: str, value: object):
    values = event_values()
    values[field] = value

    with pytest.raises(ValueError):
        EVMSellEvent.from_dict(values)


def test_status_revision_is_append_only_and_monitor_is_finalized_canonical_verified_only():
    observed = EVMSellEvent.from_dict(event_values(finality_status="observed", reorg_status="pending"))
    revision = make_status_revision(
        observed,
        finality_status=FinalityStatus.FINALIZED,
        reorg_status=ReorgStatus.CANONICAL,
        revised_at=datetime.fromisoformat("2026-01-02T03:05:00+00:00"),
        reason="fixture finality update",
    )
    finalized = append_status_revision(observed, revision)

    assert observed.finality_status is FinalityStatus.OBSERVED
    assert observed.reorg_status is ReorgStatus.PENDING
    assert finalized.event_id == observed.event_id
    assert finalized.token_amount_raw == observed.token_amount_raw
    assert finalized.block_hash == observed.block_hash
    assert is_monitor_eligible(finalized)
    assert not is_monitor_eligible(observed)
    assert revision.as_dict()["event_id"] == observed.event_id

    orphaned = append_status_revision(
        finalized,
        finality_status="finalized",
        reorg_status="orphaned",
    )
    assert orphaned.event_id == finalized.event_id
    assert not is_monitor_eligible(orphaned)


def test_status_revision_cannot_change_event_evidence():
    event = EVMSellEvent.from_dict(event_values())
    with pytest.raises(ValueError, match="immutable"):
        append_status_revision(event, token_amount_raw=99)

    with pytest.raises(ValueError, match="event_id"):
        append_status_revision(
            event,
            {
                "event_id": "f" * 64,
                "finality_status": "finalized",
                "reorg_status": "canonical",
            },
        )


def test_decoder_status_is_part_of_monitor_eligibility():
    values = event_values()
    values["decoder_status"] = DecoderStatus.UNVERIFIED.value
    event = EVMSellEvent.from_dict(values)

    assert not event.monitor_eligible
