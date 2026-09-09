from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.market_intel.models import MarketQuote, MarketType
from app.market_intel.risk_gate import RiskEvidence, RiskState, evaluate_risk
from app.market_intel.sources.degen import TARGET_CHAINS, DegenSource
from app.market_intel.sources.solana_onchain import PUMP_PROGRAM_ID, SolanaOnchainSource, transaction_to_events


def _evidence(**overrides):
    now = datetime.now(UTC)
    metadata = {
        "chain": "solana",
        "token_address": "MintHealthy1111111111111111111111111111111",
        "decoder_status": "verified",
        "risk_checked_at": now.isoformat(),
        "price_usd": 0.00001,
        "liquidity_usd": 25_000,
        "active_depth_usd": 18_000,
        "lp_locked_ratio": 0.95,
        "top5_holder_concentration": 0.12,
        "onchain_risk": {"status": "observed", "risk_flags": []},
        "sell_simulation": {"status": "passed", "sell_success": True},
        "volume_24h_usd": 50_000,
        "provider_sources": ["dexscreener", "rpc", "simulator"],
    }
    metadata.update(overrides)
    return metadata


def test_complete_evidence_is_watchlist_eligible_but_not_safe_claim():
    decision = evaluate_risk(_evidence())
    typed = RiskEvidence.from_metadata(_evidence())

    assert decision.state is RiskState.WATCHLIST
    assert decision.eligible is True
    assert decision.hard_veto is False
    assert decision.evidence_coverage == 1.0
    assert typed.chain == "solana"
    assert typed.sell_simulation_proved is True


@pytest.mark.parametrize(
    "override,expected_veto",
    [
        ({"honeypot": True}, "honeypot_detected"),
        ({"sell_simulation": {"status": "failed", "sell_success": False}}, "sell_simulation_failed"),
        ({"liquidity_usd": 1_000}, "liquidity_below_policy"),
        ({"lp_locked_ratio": 0.25}, "lp_lock_below_policy"),
        ({"lp_lock": {"lp_locked": False}}, "lp_not_locked"),
        ({"top5_holder_concentration": 0.70}, "holder_concentration_high"),
        ({"onchain_risk": {"status": "observed", "risk_flags": ["permanent_delegate"]}}, "permanent_delegate"),
        (
            {"onchain_risk": {"status": "observed", "extensions": [{"extension": "permanentDelegate"}]}},
            "permanent_delegate",
        ),
    ],
)
def test_hard_vetoes_never_become_opportunities(override, expected_veto):
    decision = evaluate_risk(_evidence(**override))

    assert decision.state is RiskState.HIGH_RISK
    assert decision.eligible is False
    assert expected_veto in decision.vetoes


def test_missing_or_stale_evidence_abstains():
    missing = evaluate_risk({"chain": "solana", "token_address": "MintMissing"})
    stale = evaluate_risk(_evidence(risk_checked_at=(datetime.now(UTC) - timedelta(hours=2)).isoformat()))

    assert missing.state is RiskState.INSUFFICIENT_EVIDENCE
    assert "sell_simulation" in missing.missing_evidence
    assert stale.state is RiskState.INSUFFICIENT_EVIDENCE
    assert stale.stale_evidence is True


def test_unsupported_chain_is_explicitly_quarantined():
    decision = evaluate_risk(_evidence(chain="polygon"))

    assert decision.state is RiskState.UNSUPPORTED
    assert decision.eligible is False
    assert "chain_or_protocol_unsupported" in decision.findings


def test_provider_conflict_is_not_resolved_by_counting_logos():
    decision = evaluate_risk(
        _evidence(
            provider_observations={
                "dexscreener": {"price": 1.0, "liquidity": 20_000},
                "birdeye": {"price": 1.8, "liquidity": 20_500},
            }
        )
    )

    assert decision.state is RiskState.INSUFFICIENT_EVIDENCE
    assert decision.provider_conflict is True
    assert "provider_reconciliation" in decision.missing_evidence


def test_single_provider_evidence_abstains_until_independent_confirmation():
    decision = evaluate_risk(
        _evidence(
            provider_sources=["one-upstream"],
            provider_observations={},
        )
    )

    assert decision.state is RiskState.INSUFFICIENT_EVIDENCE
    assert decision.eligible is False
    assert "independent_provider_confirmation" in decision.missing_evidence


@pytest.mark.asyncio
async def test_degen_scanner_requires_gate_before_ranking():
    source = DegenSource(risk_gate_enabled=True)
    quote = MarketQuote(
        symbol="DEGEN_solana_MintHeal",
        market_type=MarketType.DEGEN,
        source="dexscreener",
        price=0.00001,
        change_pct_24h=35,
        volume_24h=50_000,
        metadata={**_evidence(), "buys_24h": 100, "sells_24h": 40, "name": "Healthy"},
    )
    high_risk = quote.model_copy(deep=True)
    high_risk.metadata["honeypot"] = True

    opportunities = await source.scan_opportunities([quote, high_risk])

    assert len(opportunities) == 2  # momentum + buy-pressure for the one eligible quote
    assert {item.symbol for item in opportunities} == {quote.symbol}
    assert all(item.metadata["risk_state"] == RiskState.WATCHLIST.value for item in opportunities)


@pytest.mark.asyncio
async def test_dex_discovery_visits_every_configured_target_chain(monkeypatch):
    source = DegenSource(risk_gate_enabled=False)
    visited: list[str] = []

    async def fake_boosts():
        return []

    async def fake_chain(chain):
        visited.append(chain)
        return []

    async def fake_keywords():
        return []

    monkeypatch.setattr(source, "_fetch_boosted_tokens", fake_boosts)
    monkeypatch.setattr(source, "_fetch_chain_trending", fake_chain)
    monkeypatch.setattr(source, "_search_meme_keywords", fake_keywords)

    await source.fetch_quotes()

    assert visited == TARGET_CHAINS


@pytest.mark.asyncio
async def test_unverified_solana_log_is_discovery_only():
    events = transaction_to_events(
        {
            "blockTime": 1_700_000_000,
            "meta": {
                "err": None,
                "logMessages": ["Program log: Instruction: Create"],
                "postTokenBalances": [{"mint": "MintLogHint111111111111111111111111111111"}],
            },
            "transaction": {"message": {"accountKeys": [], "instructions": []}},
        },
        signature="SigLogHint",
        slot=99,
        program_id=PUMP_PROGRAM_ID,
    )
    quote = SolanaOnchainSource._event_to_quote(events[0])
    source = SolanaOnchainSource(risk_enabled=False)

    opportunities = await source.scan_opportunities([quote])

    assert quote.metadata["decoder_status"] == "unverified"
    assert quote.metadata["risk_state"] == RiskState.DETECTED.value
    assert opportunities == []
