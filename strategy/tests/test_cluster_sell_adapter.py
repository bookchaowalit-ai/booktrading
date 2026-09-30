from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.market_intel.cluster_sell_adapter import (
    ClusterSellAdapter,
    build_cluster_sell_observation,
)
from app.market_intel.solana_event_schema import (
    SolanaSellEvent,
    append_status_revision,
    compute_event_id,
)
from app.market_intel.sources.solana_sell_events import (
    build_decoder_registry,
    normalize_solana_sell_event,
)
from app.market_intel.wallet_intelligence import ClusterSellMonitor

FIXTURE = Path(__file__).parent / "fixtures" / "solana" / "raydium_sell.json"
RAYDIUM_ID = "FakeRaydiumProgram111111111111111111111111111111"


class Resolver:
    def __init__(self, cluster_id: str | None = "cluster-explicit"):
        self.cluster_id = cluster_id
        self.calls: list[tuple[str, str]] = []

    def __call__(self, chain: str, wallet: str) -> str | None:
        self.calls.append((chain, wallet))
        return self.cluster_id


def event(*, quote_value_usd: float | None = 3.5) -> SolanaSellEvent:
    transaction = json.loads(FIXTURE.read_text(encoding="utf-8"))
    registry = build_decoder_registry(raydium_program_id=RAYDIUM_ID)
    result = normalize_solana_sell_event(
        transaction,
        registry=registry,
        quote_value_usd=quote_value_usd,
    )
    assert result is not None
    return result


def test_adapter_maps_slot_and_event_index_and_attaches_no_trade_alert():
    resolver = Resolver()
    monitor = ClusterSellMonitor(window_seconds=300, min_sell_share=0.05, min_unique_wallets=1)
    adapter = ClusterSellAdapter(monitor, cluster_resolver=resolver)

    route = adapter.ingest(event(), cluster_balance_before=1_000)
    payload = route.as_dict()

    assert route.status == "ingested"
    assert route.observation is not None
    assert route.observation.block_number == 7001
    assert route.observation.log_index == 0
    assert route.observation.cluster_id == "cluster-explicit"
    assert resolver.calls == [("solana", route.observation.wallet)]
    assert payload["trade_instruction"] is False
    assert payload["alert"]["trade_instruction"] is False
    assert "order" not in payload
    assert "opportunity" not in payload


@pytest.mark.parametrize(
    ("finality_status", "reorg_status"),
    [
        ("processed", "canonical"),
        ("confirmed", "canonical"),
        ("finalized", "pending"),
        ("finalized", "orphaned"),
    ],
)
def test_adapter_is_finalized_canonical_only(finality_status: str, reorg_status: str):
    resolver = Resolver()
    monitor = ClusterSellMonitor(min_unique_wallets=1)
    adapter = ClusterSellAdapter(monitor, cluster_resolver=resolver)
    pending = append_status_revision(
        event(),
        finality_status=finality_status,
        reorg_status=reorg_status,
    )

    route = adapter.ingest(pending, cluster_balance_before=1_000)

    assert route.status == "ignored"
    assert route.reason == "monitor_requires_finalized_canonical_event"
    assert resolver.calls == []


def test_adapter_requires_explicit_context_and_never_infers_cluster():
    resolver = Resolver(cluster_id=None)
    monitor = ClusterSellMonitor(min_unique_wallets=1)
    adapter = ClusterSellAdapter(monitor, cluster_resolver=resolver)

    route = adapter.ingest(event(), cluster_balance_before=1_000)
    missing_usd = ClusterSellAdapter(monitor, cluster_resolver=Resolver()).ingest(
        event(quote_value_usd=None),
        cluster_balance_before=1_000,
    )

    assert route.status == "ignored"
    assert route.reason == "explicit_cluster_balance_resolver_or_quote_evidence_required"
    assert missing_usd.status == "ignored"
    assert missing_usd.alert is None

    with pytest.raises(ValueError, match="positive"):
        adapter.ingest(event(), cluster_balance_before=0)


def test_external_quote_evidence_is_passed_without_fabricating_a_value():
    resolver = Resolver()
    observation = build_cluster_sell_observation(
        event(quote_value_usd=None),
        cluster_resolver=resolver,
        cluster_balance_before=1_000,
        quote_value_usd=9.25,
    )

    assert observation is not None
    assert observation.quote_value_usd == 9.25


def test_adapter_deduplicates_event_id_and_requires_event_index_uniqueness():
    resolver = Resolver()
    monitor = ClusterSellMonitor(min_unique_wallets=1)
    adapter = ClusterSellAdapter(monitor, cluster_resolver=resolver)
    first = event()

    accepted = adapter.ingest(first, cluster_balance_before=1_000)
    duplicate = adapter.ingest(first, cluster_balance_before=1_000)

    assert accepted.status == "ingested"
    assert duplicate.status == "deduplicated"

    conflicting_values = first.as_dict()
    conflicting_values.update(
        {
            "protocol": "pumpswap",
            "program_id": "FakePumpSwapProgram",
            "event_id": compute_event_id(
                "solana",
                "pumpswap",
                "FakePumpSwapProgram",
                first.signature,
                first.instruction_index,
                first.event_index,
            ),
        }
    )
    conflicting = SolanaSellEvent.from_dict(conflicting_values)
    with pytest.raises(ValueError, match="event_index must be unique"):
        adapter.ingest(conflicting, cluster_balance_before=1_000)


def test_adapter_has_no_network_or_signing_boundary():
    assert not hasattr(ClusterSellAdapter, "send_transaction")
    assert not hasattr(ClusterSellAdapter, "sign")
    assert not hasattr(ClusterSellAdapter, "rpc")
