from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.market_intel.risk_gate import RiskDecision, RiskState
from app.trade_intent import (
    TRADE_INTENT_SCHEMA_VERSION,
    TradeIntentMode,
    TradeRouteKind,
    build_trade_intent,
    validate_trade_intent,
)

CREATED_AT = datetime(2026, 9, 20, 14, 0, tzinfo=UTC)
EXPIRES_AT = CREATED_AT + timedelta(minutes=5)
EVM_WALLET = "0x4444444444444444444444444444444444444444"
TOKEN_IN = "0x2222222222222222222222222222222222222222"
TOKEN_OUT = "0x3333333333333333333333333333333333333333"


def risk_decision(*, state: RiskState = RiskState.WATCHLIST, eligible: bool = True) -> RiskDecision:
    return RiskDecision(
        state=state,
        eligible=eligible,
        confidence=0.91,
        evidence_coverage=1.0,
        checked_at=CREATED_AT.isoformat(),
        evidence_as_of=CREATED_AT.isoformat(),
    )


def make_intent(**overrides):
    values = {
        "risk_decision": risk_decision(),
        "chain": "base",
        "route_kind": TradeRouteKind.AGGREGATOR,
        "venue": "0x",
        "token_in": TOKEN_IN,
        "token_out": TOKEN_OUT,
        "amount_in_raw": "1000000",
        "max_slippage_bps": 100,
        "recipient_wallet": EVM_WALLET,
        "evidence_refs": ["quote-1", "risk-1"],
        "created_at": CREATED_AT,
        "expires_at": EXPIRES_AT,
    }
    values.update(overrides)
    return build_trade_intent(**values)


def test_builds_deterministic_paper_intent_without_execution_payload():
    first = make_intent()
    second = make_intent()

    assert first.intent_id == second.intent_id
    assert first.schema_version == TRADE_INTENT_SCHEMA_VERSION
    assert first.execution_mode is TradeIntentMode.PAPER
    payload = first.as_dict()
    assert payload["execution_allowed"] is False
    assert payload["amount_in_raw"] == 1_000_000
    assert payload["evidence_refs"] == ["quote-1", "risk-1"]
    assert not {"private_key", "signature", "calldata", "rpc_url", "tx_hash"} & payload.keys()


def test_round_trip_serialization_preserves_identity():
    original = make_intent()
    restored = validate_trade_intent(original.as_dict())

    assert restored == original
    assert restored.intent_id == original.intent_id


def test_serialized_intent_rejects_execution_or_secret_fields():
    payload = make_intent().as_dict()

    live_payload = {**payload, "execution_allowed": True}
    with pytest.raises(ValueError, match="execution_allowed"):
        validate_trade_intent(live_payload)

    secret_payload = {**payload, "calldata": "0xdeadbeef"}
    with pytest.raises(ValueError, match="unsupported fields"):
        validate_trade_intent(secret_payload)


@pytest.mark.parametrize(
    "decision",
    [
        risk_decision(state=RiskState.HIGH_RISK, eligible=False),
        risk_decision(state=RiskState.INSUFFICIENT_EVIDENCE, eligible=False),
        risk_decision(state=RiskState.INVALIDATED, eligible=False),
        risk_decision(eligible=False),
    ],
)
def test_risk_veto_or_ineligible_decision_cannot_create_intent(decision):
    with pytest.raises(ValueError, match="does not permit"):
        make_intent(risk_decision=decision)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("chain", "polygon", "chain must be"),
        ("amount_in_raw", 0, "amount_in_raw must be positive"),
        ("amount_in_raw", 1.5, "amount_in_raw must be an integer"),
        ("max_slippage_bps", 10_001, "max_slippage_bps must be"),
        ("token_in", "not-an-evm-address", "token_in must be native or"),
        ("token_out", TOKEN_IN, "token_in and token_out must differ"),
        ("recipient_wallet", "0x1234", "recipient_wallet must be"),
    ],
)
def test_intent_rejects_unsafe_or_ambiguous_parameters(field, value, message):
    with pytest.raises(ValueError, match=message):
        make_intent(**{field: value})


def test_live_mode_is_not_available_in_strategy_contract():
    with pytest.raises(ValueError, match="paper or simulation"):
        make_intent(execution_mode="live")


def test_direct_dex_route_remains_provider_neutral():
    intent = make_intent(route_kind=TradeRouteKind.DIRECT_DEX, venue="uniswap")

    assert intent.route_kind is TradeRouteKind.DIRECT_DEX
    assert intent.venue == "uniswap"
    assert intent.as_dict()["execution_allowed"] is False
