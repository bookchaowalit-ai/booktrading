from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.market_intel.risk_gate import RiskDecision, RiskState
from app.paper_execution import (
    PaperExecutionConflictError,
    PaperExecutionGateway,
    PaperExecutionStatus,
    PaperQuote,
)
from app.trade_intent import TradeRouteKind, build_trade_intent

CREATED_AT = datetime(2026, 9, 20, 14, 0, tzinfo=UTC)
NOW = CREATED_AT + timedelta(seconds=10)
EXPIRES_AT = CREATED_AT + timedelta(minutes=5)
EVM_WALLET = "0x4444444444444444444444444444444444444444"
TOKEN_IN = "0x2222222222222222222222222222222222222222"
TOKEN_OUT = "0x3333333333333333333333333333333333333333"


def make_intent(**overrides):
    values = {
        "risk_decision": RiskDecision(
            state=RiskState.WATCHLIST,
            eligible=True,
            confidence=0.91,
            evidence_coverage=1.0,
            checked_at=CREATED_AT.isoformat(),
            evidence_as_of=CREATED_AT.isoformat(),
        ),
        "chain": "base",
        "route_kind": TradeRouteKind.AGGREGATOR,
        "venue": "0x",
        "token_in": TOKEN_IN,
        "token_out": TOKEN_OUT,
        "amount_in_raw": 1_000,
        "max_slippage_bps": 10,
        "recipient_wallet": EVM_WALLET,
        "evidence_refs": ["risk-1", "quote-1"],
        "created_at": CREATED_AT,
        "expires_at": EXPIRES_AT,
    }
    values.update(overrides)
    return build_trade_intent(**values)


def make_quote(**overrides):
    values = {
        "quote_id": "quote-1",
        "chain": "base",
        "route_kind": TradeRouteKind.AGGREGATOR,
        "venue": "0x",
        "token_in": TOKEN_IN,
        "token_out": TOKEN_OUT,
        "amount_in_raw": 1_000,
        "expected_amount_out_raw": 1_000,
        "simulated_amount_out_raw": 999,
        "quoted_at": CREATED_AT + timedelta(seconds=5),
        "expires_at": CREATED_AT + timedelta(seconds=35),
    }
    values.update(overrides)
    return PaperQuote(**values)


def test_gateway_simulates_fill_with_slippage_and_no_live_state():
    receipt = PaperExecutionGateway().simulate(make_intent(), make_quote(), now=NOW)

    assert receipt.status is PaperExecutionStatus.SIMULATED
    assert receipt.execution_mode.value == "paper"
    assert receipt.failure_code is None
    assert receipt.effective_slippage_bps == 10
    assert receipt.as_dict()["execution_allowed"] is False
    assert receipt.as_dict()["signed"] is False
    assert receipt.as_dict()["broadcasted"] is False
    assert receipt.as_dict()["transaction_hash"] is None
    assert receipt.as_dict()["reconciled"] is False


def test_gateway_replays_identical_intent_and_quote_idempotently():
    gateway = PaperExecutionGateway()
    intent = make_intent()
    quote = make_quote()

    first = gateway.simulate(intent, quote, now=NOW)
    replay = gateway.simulate(intent.as_dict(), quote, now=NOW + timedelta(seconds=1))

    assert replay.execution_id == first.execution_id
    assert replay.observed_at == first.observed_at
    assert replay.replayed is True
    assert len(gateway.receipts) == 1
    assert gateway.export_events()[0]["event_id"] == first.execution_id


def test_gateway_rejects_reusing_intent_with_different_quote():
    gateway = PaperExecutionGateway()
    intent = make_intent()
    gateway.simulate(intent, make_quote(), now=NOW)

    with pytest.raises(PaperExecutionConflictError, match="different paper quote"):
        gateway.simulate(intent, make_quote(quote_id="quote-2"), now=NOW)


@pytest.mark.parametrize(
    ("intent_overrides", "quote_overrides", "expected_code"),
    [
        ({}, {"venue": "uniswap"}, "quote_context_mismatch"),
        ({}, {"expires_at": CREATED_AT + timedelta(seconds=9)}, "quote_expired"),
        ({}, {"quoted_at": CREATED_AT - timedelta(minutes=1)}, "quote_stale"),
        ({}, {"simulated_amount_out_raw": 998}, "quote_slippage_exceeded"),
        ({"expires_at": CREATED_AT + timedelta(seconds=9)}, {}, "intent_expired"),
    ],
)
def test_gateway_rejects_unsafe_or_stale_simulation_inputs(intent_overrides, quote_overrides, expected_code):
    receipt = PaperExecutionGateway().simulate(
        make_intent(**intent_overrides),
        make_quote(**quote_overrides),
        now=NOW,
    )

    assert receipt.status is PaperExecutionStatus.REJECTED
    assert receipt.failure_code == expected_code


def test_quote_rejects_invalid_evm_assets_and_non_positive_amounts():
    with pytest.raises(ValueError, match="token_in must be"):
        make_quote(token_in="not-an-address")

    with pytest.raises(ValueError, match="amount_in_raw must be at least 1"):
        make_quote(amount_in_raw=0)


def test_gateway_rejects_future_quotes_before_they_are_valid():
    receipt = PaperExecutionGateway().simulate(
        make_intent(),
        make_quote(
            quoted_at=NOW + timedelta(seconds=1),
            expires_at=NOW + timedelta(seconds=30),
        ),
        now=NOW,
    )

    assert receipt.failure_code == "quote_not_yet_valid"
