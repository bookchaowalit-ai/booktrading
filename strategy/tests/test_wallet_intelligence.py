from datetime import UTC, datetime, timedelta

import pytest

from app.market_intel.risk_gate import RiskEvidence, RiskState, evaluate_risk
from app.market_intel.wallet_intelligence import (
    ClusterSellMonitor,
    ClusterSellObservation,
    WalletRelation,
    build_wallet_clusters,
    calculate_concentration,
)

NOW = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


def relation(left: str, right: str, kind: str, confidence: float = 0.99) -> WalletRelation:
    return WalletRelation(
        chain="ethereum",
        source_wallet=left,
        target_wallet=right,
        relation_type=kind,
        source="fixture",
        confidence=confidence,
        observed_at=NOW,
    )


def observation(
    wallet: str,
    tx_hash: str,
    amount: int,
    *,
    at: datetime = NOW,
    cluster_id: str = "cluster_fixture",
) -> ClusterSellObservation:
    return ClusterSellObservation(
        chain="ethereum",
        token_address="0x" + "11" * 20,
        cluster_id=cluster_id,
        wallet=wallet,
        amount_token=amount,
        quote_value_usd=amount / 10,
        tx_hash=tx_hash,
        log_index=0,
        block_number=100,
        observed_at=at,
        source="fixture",
        cluster_balance_before=1_000,
    )


def test_funding_relation_is_retained_without_merging_wallets():
    result = build_wallet_clusters(
        ["wallet-a", "wallet-b", "wallet-c"],
        [
            relation("wallet-a", "wallet-b", "funded_by"),
            relation("wallet-b", "wallet-c", "common_funder"),
        ],
        chain="ethereum",
    )

    assert len(result.clusters) == 3
    assert len(result.retained_relations) == 2
    assert result.cluster_for("wallet-a") != result.cluster_for("wallet-b")


def test_explicit_control_relation_merges_deterministically():
    first = build_wallet_clusters(
        ["0xAAA", "0xBBB"],
        [relation("0xAAA", "0xBBB", "shared_control")],
        chain="ethereum",
    )
    second = build_wallet_clusters(
        ["0xBBB", "0xAAA"],
        [relation("0xBBB", "0xAAA", "shared_control")],
        chain="ethereum",
    )

    assert len(first.clusters) == 1
    assert first.as_dict() == second.as_dict()
    assert first.clusters[0].confidence == 0.99


def test_low_confidence_control_relation_does_not_merge():
    result = build_wallet_clusters(
        ["wallet-a", "wallet-b"],
        [relation("wallet-a", "wallet-b", "same_owner", confidence=0.89)],
        chain="ethereum",
    )

    assert len(result.clusters) == 2
    assert len(result.retained_relations) == 1


def test_concentration_reports_raw_and_cluster_adjusted_values():
    clustering = build_wallet_clusters(
        ["a", "b", "c", "d", "e", "f", "g"],
        [relation("a", "b", "same_owner")],
        chain="ethereum",
    )
    metrics = calculate_concentration(
        {"a": 300, "b": 200, "c": 100, "d": 90, "e": 80, "f": 70, "g": 60},
        clustering,
        total_supply=1_000,
        excluded_wallets={"g"},
    )

    assert metrics.observed_supply == 840
    assert metrics.excluded_supply == 60
    assert metrics.coverage == pytest.approx(0.84)
    assert metrics.raw_top5_share == pytest.approx(0.77)
    assert metrics.effective_concentration == pytest.approx(0.84)
    assert metrics.cluster_hhi == pytest.approx(0.2794)


def test_cluster_ids_are_scoped_to_chain():
    ethereum = build_wallet_clusters(["wallet-a"], [], chain="ethereum")
    solana = build_wallet_clusters(["wallet-a"], [], chain="solana")

    assert ethereum.clusters[0].cluster_id != solana.clusters[0].cluster_id


def test_cluster_sell_monitor_requires_multiple_wallets_or_critical_share():
    monitor = ClusterSellMonitor(window_seconds=300, min_sell_share=0.05, min_unique_wallets=2)

    assert monitor.ingest(observation("wallet-a", "tx-a", 40)) is None
    alert = monitor.ingest(observation("wallet-b", "tx-b", 20))

    assert alert is not None
    assert alert.severity == "high"
    assert alert.sell_share == pytest.approx(0.06)
    assert alert.unique_wallets == 2
    assert alert.as_dict()["trade_instruction"] is False


def test_cluster_sell_monitor_allows_single_critical_seller_and_deduplicates():
    monitor = ClusterSellMonitor(window_seconds=300, critical_sell_share=0.20)

    alert = monitor.ingest(observation("wallet-a", "tx-a", 250))
    duplicate = monitor.ingest(observation("wallet-a", "tx-a", 250))

    assert alert is not None
    assert alert.severity == "critical"
    assert duplicate is None


def test_cluster_sell_monitor_expires_old_events():
    monitor = ClusterSellMonitor(window_seconds=60, min_sell_share=0.05, min_unique_wallets=2)

    monitor.ingest(observation("wallet-a", "tx-a", 40, at=NOW))
    alert = monitor.ingest(observation("wallet-b", "tx-b", 20, at=NOW + timedelta(seconds=61)))

    assert alert is None


def test_risk_gate_vetoes_high_cluster_sell_pressure():
    metadata = {
        "chain": "ethereum",
        "token_address": "0x" + "11" * 20,
        "decoder_status": "verified",
        "risk_checked_at": NOW.isoformat(),
        "authority_checked": True,
        "liquidity_usd": 25_000,
        "lp_locked_ratio": 0.95,
        "lp_custody_verified": True,
        "sell_simulation": {"status": "passed", "sell_success": True},
        "effective_concentration": 0.12,
        "provider_sources": ["rpc", "simulator"],
        "cluster_sell_alert": {
            "alert": True,
            "severity": "critical",
            "sell_share": 0.25,
        },
    }

    decision = evaluate_risk(metadata, now=NOW)

    assert decision.state is RiskState.HIGH_RISK
    assert "cluster_sell_pressure" in decision.vetoes


def test_risk_gate_prefers_effective_concentration_over_raw_fallback():
    evidence = RiskEvidence.from_metadata(
        {
            "top5_holder_concentration": 0.80,
            "effective_concentration": 0.12,
        }
    )

    assert evidence.effective_concentration == pytest.approx(0.12)
    assert evidence.holder_concentration == pytest.approx(0.12)


def _complete_risk_metadata(cluster_sell: dict) -> dict:
    return {
        "chain": "ethereum",
        "token_address": "0x" + "11" * 20,
        "decoder_status": "verified",
        "risk_checked_at": NOW.isoformat(),
        "authority_checked": True,
        "liquidity_usd": 25_000,
        "lp_locked_ratio": 0.95,
        "lp_custody_verified": True,
        "sell_simulation": {"status": "passed", "sell_success": True},
        "top5_holder_concentration": 0.12,
        "provider_sources": ["rpc", "simulator"],
        "cluster_sell_alert": cluster_sell,
    }


def test_risk_gate_abstains_on_stale_cluster_sell_watch():
    decision = evaluate_risk(
        _complete_risk_metadata(
            {
                "alert": True,
                "severity": "watch",
                "sell_share": 0.06,
                "window_end": (NOW - timedelta(seconds=301)).isoformat(),
            }
        ),
        now=NOW,
        max_age_seconds=300,
    )

    assert decision.state is RiskState.INSUFFICIENT_EVIDENCE
    assert decision.stale_evidence is True
    assert "cluster_sell_stale" in decision.findings


def test_risk_gate_abstains_on_conflicting_cluster_sell_watch():
    decision = evaluate_risk(
        _complete_risk_metadata(
            {
                "alert": True,
                "severity": "watch",
                "sell_share": 0.06,
                "window_end": NOW.isoformat(),
                "conflict": True,
            }
        ),
        now=NOW,
    )

    assert decision.state is RiskState.INSUFFICIENT_EVIDENCE
    assert decision.provider_conflict is True
    assert "cluster_sell_reconciliation" in decision.missing_evidence
