from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.market_intel.evm_security import (
    EVM_EVIDENCE_VERSION,
    build_evm_risk_evidence,
    merge_evm_observations,
    normalize_goplus_response,
    normalize_honeypot_response,
    normalize_lp_custody,
    normalize_sell_simulation,
)
from app.market_intel.risk_gate import RiskState, evaluate_risk


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _complete_evm_metadata(**overrides):
    checked_at = _now()
    metadata = build_evm_risk_evidence(
        chain="ethereum",
        token_address="0xTokenEvidence",
        checked_at=checked_at,
        goplus={
            "is_open_source": "1",
            "is_honeypot": "0",
            "is_mintable": "0",
            "is_proxy": "0",
            "sell_tax": "3",
        },
        honeypot={
            "honeypotResult": {"isHoneypot": False},
            "simulationResult": {"simulationSuccess": True, "sellSuccess": True},
        },
        simulation={"status": "passed", "sell_success": True, "route": ["WETH", "TOKEN"]},
        lp_custody={
            "locked_ratio": 95,
            "custody_verified": True,
            "expires_at": (datetime.now(UTC) + timedelta(days=10)).isoformat(),
            "liquidity_usd": 25_000,
            "active_depth_usd": 18_000,
        },
        holders={"top5_concentration": 0.12},
    )
    metadata.update({"price_usd": 0.00001, "volume_24h": 50_000})
    metadata.update(overrides)
    return metadata


def test_goplus_string_fields_are_normalized_without_false_proxy_admin():
    result = normalize_goplus_response(
        {
            "result": {
                "is_open_source": "1",
                "is_honeypot": "0",
                "is_mintable": "0",
                "is_proxy": "0",
                "buy_tax": "1.5",
                "sell_tax": "3",
                "owner_address": "0xOwner",
            }
        },
        chain="base",
        token_address="0xToken",
        checked_at=_now(),
    )

    contract = result["contract"]
    assert contract["verified"] is True
    assert contract["honeypot"] is False
    assert contract["mintable"] is False
    assert contract["is_proxy"] is False
    assert "proxy_admin" not in contract
    assert contract["tax_bps"] == 300


def test_honeypot_sell_failure_becomes_high_risk():
    observation = normalize_honeypot_response(
        {
            "honeypotResult": {"isHoneypot": True, "honeypotReason": "sell reverts"},
            "simulationResult": {"simulationSuccess": True, "sellSuccess": False},
        },
        chain="arbitrum",
        token_address="0xHoney",
        checked_at=_now(),
    )
    metadata = _complete_evm_metadata()
    metadata["risk_evidence"]["contract"].update(observation["contract"])
    metadata["risk_evidence"]["exit"] = observation["exit"]

    decision = evaluate_risk(metadata)

    assert decision.state is RiskState.HIGH_RISK
    assert "honeypot_detected" in decision.vetoes
    assert "sell_simulation_failed" in decision.vetoes


def test_simulation_sell_tax_above_policy_is_a_veto():
    metadata = _complete_evm_metadata()
    metadata["risk_evidence"]["exit"]["simulation"]["sell_tax_bps"] = 1_500

    decision = evaluate_risk(metadata)

    assert decision.state is RiskState.HIGH_RISK
    assert "transfer_fee_above_policy" in decision.vetoes


def test_simulation_timeout_is_inconclusive_and_never_a_pass():
    observation = normalize_sell_simulation(
        {"status": "timeout", "error": "provider unavailable"},
        chain="bsc",
        token_address="0xTimeout",
        checked_at=_now(),
    )

    assert observation["exit"]["simulation"]["status"] == "inconclusive"
    metadata = _complete_evm_metadata()
    metadata["risk_evidence"]["exit"] = observation["exit"]
    decision = evaluate_risk(metadata)

    assert decision.state is RiskState.INSUFFICIENT_EVIDENCE
    assert "sell_simulation" in decision.missing_evidence
    assert decision.eligible is False


def test_simulation_success_conflict_stays_inconclusive():
    observation = normalize_sell_simulation(
        {"simulation_success": False, "sell_success": True},
        chain="ethereum",
        token_address="0xMixedResult",
        checked_at=_now(),
    )

    assert observation["exit"]["simulation"]["status"] == "inconclusive"


def test_partial_or_expiring_lp_custody_is_rejected():
    partial = normalize_lp_custody(
        {"locked_ratio": 50, "custody_verified": True, "liquidity_usd": 25_000},
        chain="base",
        token_address="0xPartial",
        checked_at=_now(),
    )
    partial_metadata = _complete_evm_metadata(chain="base", token_address="0xPartial")
    partial_metadata["risk_evidence"]["liquidity"] = partial["liquidity"]
    partial_decision = evaluate_risk(partial_metadata)
    assert partial_decision.state is RiskState.HIGH_RISK
    assert "lp_lock_below_policy" in partial_decision.vetoes

    expiring = _complete_evm_metadata(
        risk_evidence={
            **_complete_evm_metadata()["risk_evidence"],
            "liquidity": {
                "lp_locked_ratio": 0.95,
                "custody_verified": True,
                "lock_expires_at": (datetime.now(UTC) + timedelta(hours=2)).isoformat(),
                "liquidity_usd": 25_000,
            },
        }
    )
    expiring_decision = evaluate_risk(expiring)
    assert expiring_decision.state is RiskState.HIGH_RISK
    assert "lp_lock_expiring_soon" in expiring_decision.vetoes

    unverified = _complete_evm_metadata(
        risk_evidence={
            **_complete_evm_metadata()["risk_evidence"],
            "liquidity": {
                "lp_locked_ratio": 0.95,
                "custody_verified": False,
                "liquidity_usd": 25_000,
            },
        }
    )
    unverified_decision = evaluate_risk(unverified)
    assert unverified_decision.state is RiskState.INSUFFICIENT_EVIDENCE
    assert "liquidity_custody_verification" in unverified_decision.missing_evidence


def test_invalid_ratio_and_emergency_withdrawal_fail_closed():
    invalid = _complete_evm_metadata(
        risk_evidence={
            **_complete_evm_metadata()["risk_evidence"],
            "liquidity": {"lp_locked_ratio": 150, "custody_verified": True, "liquidity_usd": 25_000},
        }
    )
    invalid_decision = evaluate_risk(invalid)
    assert invalid_decision.state is RiskState.INSUFFICIENT_EVIDENCE
    assert "liquidity_custody" in invalid_decision.missing_evidence

    emergency = _complete_evm_metadata(
        risk_evidence={
            **_complete_evm_metadata()["risk_evidence"],
            "liquidity": {
                "lp_locked_ratio": 0.95,
                "custody_verified": True,
                "emergency_withdrawal": True,
                "liquidity_usd": 25_000,
            },
        }
    )
    emergency_decision = evaluate_risk(emergency)
    assert emergency_decision.state is RiskState.HIGH_RISK
    assert "lp_emergency_withdrawal" in emergency_decision.vetoes


def test_provider_conflict_is_preserved_and_does_not_pass():
    now = _now()
    observations = [
        normalize_sell_simulation(
            {"status": "passed", "sell_success": True},
            chain="ethereum",
            token_address="0xConflict",
            checked_at=now,
        ),
        normalize_sell_simulation(
            {"status": "failed", "sell_success": False, "error": "revert"},
            chain="ethereum",
            token_address="0xConflict",
            checked_at=now,
        ),
    ]
    metadata = merge_evm_observations(
        observations,
        chain="ethereum",
        token_address="0xConflict",
        checked_at=now,
        liquidity={"liquidity_usd": 25_000, "lp_locked_ratio": 0.95, "custody_verified": True},
        holders={"top5_concentration": 0.12},
    )
    metadata["price_usd"] = 0.1
    metadata["volume_24h"] = 100
    metadata["risk_evidence"]["contract"] = {"verified": True}

    decision = evaluate_risk(metadata)

    assert metadata["risk_evidence"]["provider_conflict"] is True
    assert decision.state is RiskState.INSUFFICIENT_EVIDENCE
    assert "provider_reconciliation" in decision.missing_evidence
    assert decision.eligible is False


def test_independence_group_is_used_for_provider_count():
    now = _now()
    first = normalize_sell_simulation(
        {"status": "passed", "sell_success": True},
        chain="base",
        token_address="0xGrouped",
        checked_at=now,
    )
    second = normalize_goplus_response(
        {"is_open_source": "1", "is_honeypot": "0"},
        chain="base",
        token_address="0xGrouped",
        checked_at=now,
    )
    first["independence_group"] = "same-upstream"
    second["independence_group"] = "same-upstream"

    metadata = merge_evm_observations(
        [first, second],
        chain="base",
        token_address="0xGrouped",
        checked_at=now,
    )

    assert metadata["risk_evidence"]["independent_provider_count"] == 1
    assert metadata["risk_evidence"]["independence_groups"] == ["same-upstream"]


def test_complete_evm_evidence_is_watchlist_only():
    metadata = _complete_evm_metadata()
    decision = evaluate_risk(metadata)

    assert metadata["risk_evidence"]["evidence_version"] == EVM_EVIDENCE_VERSION
    assert decision.state is RiskState.WATCHLIST
    assert decision.eligible is True
    assert decision.hard_veto is False


def test_adapter_rejects_non_evm_chain_before_marking_decoder_verified():
    with pytest.raises(ValueError, match="unsupported EVM chain"):
        normalize_sell_simulation(
            {"status": "passed", "sell_success": True},
            chain="solana",
            token_address="MintNotEvm",
            checked_at=_now(),
        )
