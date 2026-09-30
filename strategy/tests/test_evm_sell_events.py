from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from app.market_intel.sources.evm_sell_events import (
    EVMProtocolDecoder,
    build_decoder_registry,
    make_fixture_decoder,
    normalize_evm_sell_event,
    normalize_evm_sell_events,
)

FIXTURES = Path(__file__).parent / "fixtures" / "evm"
CONTRACT = "0x1111111111111111111111111111111111111111"
TOPIC = "0x" + "aa" * 32
PROTOCOL = "fixture_protocol"
DECODER_VERSION = "fixture-decoder.v1"


def fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def registry_for(chain: str = "ethereum") -> dict[tuple[str, str, str], EVMProtocolDecoder]:
    decoder = make_fixture_decoder(
        discriminator="fixture.generic.sell.v1",
        orientation="token_to_quote",
        required_account_roles=("pool", "seller", "token_source", "quote_destination"),
        protocol=PROTOCOL,
        decoder_version=DECODER_VERSION,
    )
    return build_decoder_registry(
        chain=chain,
        contract_address=CONTRACT,
        event_topic=TOPIC,
        protocol=PROTOCOL,
        decoder=decoder,
        decoder_version=DECODER_VERSION,
    )


@pytest.mark.parametrize("chain", ["ethereum", "bsc", "base", "arbitrum"])
def test_generic_fixture_decoder_normalizes_all_supported_chain_names(chain: str):
    transaction = fixture("sell.json")
    transaction["chain"] = chain
    event = normalize_evm_sell_event(transaction, registry=registry_for(chain), quote_value_usd=12.5)

    assert event is not None
    assert event.chain == chain
    assert event.protocol == PROTOCOL
    assert event.decoder_version == DECODER_VERSION
    assert event.token_amount_raw == 123456789012345678901
    assert event.quote_amount_raw == 987654321
    assert event.quote_value_usd == 12.5
    assert event.quote_asset == "0x5555555555555555555555555555555555555555"
    assert event.log_index == 4
    assert event.event_index == 0


def test_registry_is_empty_by_default_and_lookup_is_case_normalized():
    assert build_decoder_registry() == {}
    decoder = make_fixture_decoder(
        discriminator="fixture.generic.sell.v1",
        orientation="token_to_quote",
        required_roles=("pool", "seller", "token_source", "quote_destination"),
    )
    event = normalize_evm_sell_event(
        fixture("sell.json"),
        registry=build_decoder_registry(
            chain="ETHEREUM",
            contract_address=CONTRACT.upper(),
            event_topic=TOPIC.upper(),
            protocol=PROTOCOL,
            decoder=decoder,
            decoder_version=DECODER_VERSION,
        ),
    )

    assert event is not None
    assert event.protocol == PROTOCOL


@pytest.mark.parametrize(
    "name",
    ["failed_sell.json", "removed_sell.json", "ambiguous_sell.json"],
)
def test_failed_removed_and_ambiguous_fixtures_are_ignored(name: str):
    assert normalize_evm_sell_events(fixture(name), registry=registry_for()) == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("event_type", "buy"),
        ("side", "buy"),
        ("orientation", "ambiguous"),
    ],
)
def test_non_sell_or_ambiguous_orientation_is_ignored(field: str, value: str):
    transaction = fixture("sell.json")
    transaction["logs"][0][field] = value  # type: ignore[index]

    assert normalize_evm_sell_events(transaction, registry=registry_for()) == []


def test_missing_block_hash_or_decoder_event_index_is_ignored():
    missing_block = fixture("sell.json")
    missing_block.pop("block_hash")
    missing_block["logs"][0].pop("blockHash")  # type: ignore[index]
    assert normalize_evm_sell_events(missing_block, registry=registry_for()) == []

    missing_event_index = fixture("sell.json")
    missing_event_index["logs"][0].pop("event_index")  # type: ignore[index]
    assert normalize_evm_sell_events(missing_event_index, registry=registry_for()) == []


def test_duplicate_log_or_event_position_quarantines_transaction():
    duplicate_log = fixture("sell.json")
    duplicate_log["logs"].append(deepcopy(duplicate_log["logs"][0]))  # type: ignore[index]
    assert normalize_evm_sell_events(duplicate_log, registry=registry_for()) == []

    duplicate_event = fixture("sell.json")
    second_log = deepcopy(duplicate_event["logs"][0])  # type: ignore[index]
    second_log["logIndex"] = 5
    duplicate_event["logs"].append(second_log)  # type: ignore[index]
    assert normalize_evm_sell_events(duplicate_event, registry=registry_for()) == []


def test_unverified_decoder_output_is_ignored():
    def unverified_decoder(transaction, log):
        del transaction
        return {
            "protocol": PROTOCOL,
            "orientation": "token_to_quote",
            "event_type": "sell",
            "decoder_status": "unverified",
            "event_index": log["event_index"],
            "token_address": "0x2222222222222222222222222222222222222222",
            "pool_address": "0x3333333333333333333333333333333333333333",
            "seller_wallet": "0x4444444444444444444444444444444444444444",
            "token_amount_raw": 1,
            "quote_amount_raw": 2,
            "quote_asset": "0x5555555555555555555555555555555555555555",
        }

    registry = build_decoder_registry(
        chain="ethereum",
        contract_address=CONTRACT,
        event_topic=TOPIC,
        protocol=PROTOCOL,
        decoder=unverified_decoder,
    )
    assert normalize_evm_sell_events(fixture("sell.json"), registry=registry) == []


def test_raw_quote_asset_and_amounts_do_not_use_float_conversion():
    transaction = fixture("sell.json")
    transaction["logs"][0]["quote"]["asset"] = "ETH"  # type: ignore[index]
    event = normalize_evm_sell_event(transaction, registry=registry_for())
    assert event is not None
    assert event.quote_asset == "ETH"

    fractional_amount = fixture("sell.json")
    fractional_amount["logs"][0]["token"]["amount_raw"] = "1.5"  # type: ignore[index]
    assert normalize_evm_sell_events(fractional_amount, registry=registry_for()) == []


def test_normalizer_requires_sanitized_mapping_and_has_no_network_boundary():
    with pytest.raises(ValueError, match="sanitized mapping"):
        normalize_evm_sell_events("not-a-transaction", registry=registry_for())  # type: ignore[arg-type]

    assert not hasattr(normalize_evm_sell_events, "rpc")
    assert not hasattr(normalize_evm_sell_events, "send_transaction")
