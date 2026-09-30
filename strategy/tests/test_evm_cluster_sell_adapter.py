from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.market_intel.evm_cluster_sell_adapter import EVMClusterSellAdapter
from app.market_intel.evm_event_schema import append_status_revision
from app.market_intel.sources.evm_sell_events import (
    EVMProtocolDecoder,
    build_decoder_registry,
    make_fixture_decoder,
    normalize_evm_sell_event,
)
from app.market_intel.wallet_intelligence import ClusterSellMonitor

FIXTURE = Path(__file__).parent / "fixtures" / "evm" / "sell.json"
CONTRACT = "0x1111111111111111111111111111111111111111"
TOPIC = "0x" + "aa" * 32
PROTOCOL = "fixture_protocol"
TRANSACTION = "0x" + "bb" * 32


class Resolver:
    def __init__(self, cluster_id: str | None = "cluster-explicit"):
        self.cluster_id = cluster_id
        self.calls: list[tuple[str, str]] = []

    def __call__(self, chain: str, wallet: str) -> str | None:
        self.calls.append((chain, wallet))
        return self.cluster_id


def event(*, quote_value_usd: float | None = None):
    transaction = json.loads(FIXTURE.read_text(encoding="utf-8"))
    decoder = make_fixture_decoder(
        discriminator="fixture.generic.sell.v1",
        orientation="token_to_quote",
        required_account_roles=("pool", "seller", "token_source", "quote_destination"),
        protocol=PROTOCOL,
        decoder_version="fixture-decoder.v1",
    )
    registry: dict[tuple[str, str, str], EVMProtocolDecoder] = build_decoder_registry(
        chain="ethereum",
        contract_address=CONTRACT,
        event_topic=TOPIC,
        protocol=PROTOCOL,
        decoder=decoder,
        decoder_version="fixture-decoder.v1",
    )
    result = normalize_evm_sell_event(
        transaction,
        registry=registry,
        quote_value_usd=quote_value_usd,
    )
    assert result is not None
    return result


def test_adapter_maps_evm_position_and_emits_no_trade_fields():
    resolver = Resolver()
    monitor = ClusterSellMonitor(min_unique_wallets=1)
    adapter = EVMClusterSellAdapter(monitor, cluster_resolver=resolver)

    route = adapter.ingest(event(), cluster_balance_before=1_000, quote_value_usd=9.25)
    payload = route.as_dict()

    assert route.status == "ingested"
    assert route.observation is not None
    assert route.observation.tx_hash == TRANSACTION
    assert route.observation.log_index == 4
    assert route.observation.block_number == 7001
    assert route.observation.amount_token == 123456789012345678901
    assert route.observation.quote_value_usd == 9.25
    assert route.observation.cluster_id == "cluster-explicit"
    assert resolver.calls == [("ethereum", route.observation.wallet)]
    assert payload["trade_instruction"] is False
    assert payload["alert"] is not None
    assert payload["alert"]["trade_instruction"] is False
    assert "order" not in payload
    assert "opportunity" not in payload
    assert "execution" not in payload


@pytest.mark.parametrize(
    ("finality_status", "reorg_status"),
    [
        ("observed", "canonical"),
        ("safe", "canonical"),
        ("finalized", "pending"),
        ("finalized", "orphaned"),
    ],
)
def test_adapter_is_finalized_canonical_only(finality_status: str, reorg_status: str):
    resolver = Resolver()
    monitor = ClusterSellMonitor(min_unique_wallets=1)
    adapter = EVMClusterSellAdapter(monitor, cluster_resolver=resolver)
    pending = append_status_revision(
        event(),
        finality_status=finality_status,
        reorg_status=reorg_status,
    )

    route = adapter.ingest(pending, cluster_balance_before=1_000, quote_value_usd=1)

    assert route.status == "ignored"
    assert route.reason == "monitor_requires_verified_finalized_canonical_event"
    assert resolver.calls == []


@pytest.mark.parametrize(
    ("resolver", "balance", "quote"),
    [
        (None, 1_000, 1),
        (Resolver(cluster_id=None), 1_000, 1),
        (Resolver(), None, 1),
        (Resolver(), 1_000, None),
    ],
)
def test_adapter_requires_explicit_resolver_positive_balance_and_usd(resolver, balance, quote):
    adapter = EVMClusterSellAdapter(
        ClusterSellMonitor(min_unique_wallets=1),
        cluster_resolver=resolver,
    )

    route = adapter.ingest(
        event(),
        cluster_balance_before=balance,
        quote_value_usd=quote,
    )

    assert route.status == "ignored"
    assert route.observation is None


def test_adapter_deduplicates_event_id_and_rejects_conflicting_position():
    resolver = Resolver()
    adapter = EVMClusterSellAdapter(
        ClusterSellMonitor(min_unique_wallets=1),
        cluster_resolver=resolver,
    )
    first = event()

    accepted = adapter.ingest(first, cluster_balance_before=1_000, quote_value_usd=1)
    duplicate = adapter.ingest(first, cluster_balance_before=1_000, quote_value_usd=1)

    assert accepted.status == "ingested"
    assert duplicate.status == "deduplicated"

    replacement_transaction = json.loads(FIXTURE.read_text(encoding="utf-8"))
    replacement_transaction["block_hash"] = "0x" + "dd" * 32
    replacement_transaction["logs"][0]["blockHash"] = replacement_transaction["block_hash"]
    replacement = normalize_evm_sell_event(
        replacement_transaction,
        registry={
            (
                "ethereum",
                CONTRACT,
                TOPIC,
            ): {
                "protocol": PROTOCOL,
                "decoder": make_fixture_decoder(
                    discriminator="fixture.generic.sell.v1",
                    orientation="token_to_quote",
                    required_roles=("pool", "seller", "token_source", "quote_destination"),
                    protocol=PROTOCOL,
                ),
            }
        },
    )
    assert replacement is not None
    assert replacement.event_id != first.event_id
    with pytest.raises(ValueError, match="position conflicts"):
        adapter.ingest(replacement, cluster_balance_before=1_000, quote_value_usd=1)


def test_adapter_does_not_infer_ownership_from_common_funder_or_funding():
    resolver = Resolver(cluster_id=None)
    adapter = EVMClusterSellAdapter(
        ClusterSellMonitor(min_unique_wallets=1),
        cluster_resolver=resolver,
    )
    route = adapter.ingest(event(), cluster_balance_before=1_000, quote_value_usd=1)

    assert route.status == "ignored"
    assert route.observation is None


def test_adapter_surfaces_invalid_explicit_context():
    adapter = EVMClusterSellAdapter(
        ClusterSellMonitor(min_unique_wallets=1),
        cluster_resolver=Resolver(),
    )

    with pytest.raises(ValueError, match="positive integer"):
        adapter.ingest(event(), cluster_balance_before=0, quote_value_usd=1)

    with pytest.raises(ValueError, match="finite non-negative"):
        adapter.ingest(event(), cluster_balance_before=1_000, quote_value_usd="invalid")


def test_adapter_has_no_network_signing_or_execution_boundary():
    assert not hasattr(EVMClusterSellAdapter, "send_transaction")
    assert not hasattr(EVMClusterSellAdapter, "sign")
    assert not hasattr(EVMClusterSellAdapter, "rpc")
    assert not hasattr(EVMClusterSellAdapter, "execute")
