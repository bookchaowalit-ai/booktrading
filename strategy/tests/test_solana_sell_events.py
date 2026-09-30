from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from app.market_intel.sources.solana_sell_events import (
    PUMPSWAP_PROTOCOL,
    RAYDIUM_PROTOCOL,
    SolanaProtocolDecoder,
    build_decoder_registry,
    decode_pumpswap_sell,
    decode_raydium_sell,
    normalize_solana_sell_event,
    normalize_solana_sell_events,
)

FIXTURES = Path(__file__).parent / "fixtures" / "solana"
RAYDIUM_ID = "FakeRaydiumProgram111111111111111111111111111111"
PUMPSWAP_ID = "FakePumpSwapProgram1111111111111111111111111111"
LAUNCHPAD_ID = "FakePumpLaunchpadProgram1111111111111111111111"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def registry():
    return build_decoder_registry(
        raydium_program_id=RAYDIUM_ID,
        pumpswap_program_id=PUMPSWAP_ID,
    )


def test_raydium_and_pumpswap_use_distinct_protocol_decoders(registry):
    raydium = normalize_solana_sell_event(
        fixture("raydium_sell.json"),
        registry=registry,
        quote_value_usd=4.25,
    )
    pumpswap = normalize_solana_sell_event(
        fixture("pumpswap_sell.json"),
        registry=registry,
    )

    assert raydium is not None
    assert raydium.protocol == RAYDIUM_PROTOCOL
    assert raydium.token_amount_raw == 123456789012345678901
    assert raydium.quote_value_usd == 4.25
    assert pumpswap is not None
    assert pumpswap.protocol == PUMPSWAP_PROTOCOL
    assert pumpswap.finality_status.value == "confirmed"
    assert pumpswap.quote_value_usd is None


def test_registry_is_explicit_and_does_not_treat_launchpad_as_pumpswap(registry):
    launchpad = fixture("pumpswap_sell.json")
    launchpad["instructions"][0]["program_id"] = LAUNCHPAD_ID

    assert normalize_solana_sell_events(launchpad, registry=registry) == []
    with pytest.raises(ValueError, match="explicit"):
        build_decoder_registry()


def test_registry_rejects_ambiguous_program_identity():
    with pytest.raises(ValueError, match="distinct"):
        build_decoder_registry(
            raydium_program_id=RAYDIUM_ID,
            pumpswap_program_id=RAYDIUM_ID,
        )


def test_wrong_protocol_registration_cannot_decode_a_fixture():
    transaction = fixture("raydium_sell.json")
    wrong_registry = {
        RAYDIUM_ID: SolanaProtocolDecoder(
            protocol=PUMPSWAP_PROTOCOL,
            decoder=decode_pumpswap_sell,
        )
    }

    assert normalize_solana_sell_events(transaction, registry=wrong_registry) == []


@pytest.mark.parametrize(
    "name",
    ["failed_sell.json"],
)
def test_failed_transaction_is_rejected(name, registry):
    assert normalize_solana_sell_events(fixture(name), registry=registry) == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("event_type", "buy"),
        ("side", "buy"),
        ("orientation", "quote_to_token"),
    ],
)
def test_non_sell_and_ambiguous_orientation_are_rejected(field, value, registry):
    transaction = fixture("raydium_sell.json")
    transaction["instructions"][0][field] = value

    assert normalize_solana_sell_events(transaction, registry=registry) == []


@pytest.mark.parametrize(
    "missing",
    [
        ("account_roles", "seller"),
        ("account_roles", "pool"),
        ("instruction", "instruction_index"),
        ("instruction", "event_index"),
    ],
)
def test_missing_seller_pool_or_position_is_rejected(missing, registry):
    transaction = fixture("raydium_sell.json")
    scope, field = missing
    if scope == "account_roles":
        transaction["instructions"][0]["account_roles"].pop(field)
    else:
        transaction["instructions"][0].pop(field)

    assert normalize_solana_sell_events(transaction, registry=registry) == []


def test_duplicate_event_index_is_not_emitted_twice(registry):
    transaction = fixture("raydium_sell.json")
    duplicate = deepcopy(transaction["instructions"][0])
    duplicate["instruction_index"] = 3
    transaction["instructions"].append(duplicate)

    events = normalize_solana_sell_events(transaction, registry=registry)

    assert events == []


def test_normalizer_accepts_only_sanitized_mappings_and_does_not_network():
    with pytest.raises(ValueError, match="sanitized mapping"):
        normalize_solana_sell_events(
            "not-a-transaction", registry={RAYDIUM_ID: (RAYDIUM_PROTOCOL, decode_raydium_sell)}
        )
