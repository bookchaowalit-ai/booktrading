"""Normalize a settled selective-alpha result into portfolio/finance lanes."""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from app.portfolio.finance import FinanceProjection, paper_trade_to_finance_projection
from app.portfolio.models import PaperTrade


def alpha_settlement_to_paper_trade(
    result: Mapping[str, Any],
    *,
    account_scope: str | None = None,
    quote_currency: str | None = None,
) -> PaperTrade:
    """Convert one durable alpha settlement to one closed paper trade.

    The selected binary side is preserved in metadata while the normalized
    trade uses ``buy`` because the entry price and payout are for that side.
    The journal request ID becomes the stable source reference, making retries
    idempotent in downstream projections.
    """

    if not isinstance(result, Mapping):
        raise TypeError("result must be a mapping")
    decision = _mapping(result, "decision")
    observation = _mapping(result, "observation")
    settlement = _mapping(result, "settlement")
    reconciliation = result.get("reconciliation")
    reconciliation = reconciliation if isinstance(reconciliation, Mapping) else {}
    portfolio = result.get("portfolio")
    portfolio = portfolio if isinstance(portfolio, Mapping) else {}
    if decision.get("action") != "TRADE_PAPER":
        raise ValueError("only TRADE_PAPER results can enter the paper portfolio")
    request_id = _required_text(result, "journal_request_id")
    platform_id = _required_text(decision, "platform_id")
    observation_metadata = observation.get("metadata")
    observation_metadata = observation_metadata if isinstance(observation_metadata, Mapping) else {}
    symbol = str(observation_metadata.get("ticker") or decision.get("instrument_id") or "").strip()
    if not symbol:
        raise ValueError("settled alpha result requires a ticker or instrument_id")
    decision_metadata = decision.get("metadata")
    decision_metadata = decision_metadata if isinstance(decision_metadata, Mapping) else {}
    target_units = _positive_number(decision_metadata.get("target_units"), "target_units")
    entry_price = _positive_number(observation.get("price"), "observation.price")
    cost_per_unit = _nonnegative_number(observation.get("cost_per_unit"), "observation.cost_per_unit")
    payout = _nonnegative_number(
        settlement.get(
            "payout_per_unit",
            settlement.get("payout", reconciliation.get("payout_per_unit")),
        ),
        "settlement.payout_per_unit",
    )
    if payout not in {0.0, 1.0}:
        raise ValueError("settled alpha payout must be 0 or 1")
    closed_at = _parse_timestamp(settlement.get("settled_at"), "settlement.settled_at")
    opened_at = _parse_timestamp(
        observation.get("observed_at") or settlement.get("settled_at"), "observation.observed_at"
    )
    if closed_at < opened_at:
        raise ValueError("settlement cannot precede the observation")
    scope = account_scope or str(portfolio.get("account_scope") or "paper-default")
    currency = quote_currency or str(portfolio.get("quote_currency") or "USD")
    direction = str(decision_metadata.get("direction") or "buy_yes").strip().lower()
    if direction not in {"buy_yes", "buy_no"}:
        raise ValueError("settled alpha result requires a binary direction")
    strategy_id = str(decision.get("strategy_version") or "selective_alpha").strip()
    evidence = settlement.get("evidence")
    evidence = evidence[0] if isinstance(evidence, list) and evidence and isinstance(evidence[0], Mapping) else {}
    return PaperTrade(
        trade_id=f"alpha-paper-{request_id[:24]}",
        platform_id=platform_id,
        symbol=symbol,
        side="buy",
        quantity=target_units,
        entry_price=entry_price,
        exit_price=payout,
        fee=cost_per_unit * target_units,
        status="closed",
        opened_at=opened_at,
        closed_at=closed_at,
        strategy_id=strategy_id,
        quote_currency=currency,
        account_scope=scope,
        source_ref=f"alpha-journal:{request_id}",
        metadata={
            "alpha_journal_request_id": request_id,
            "alpha_direction": direction,
            "thesis_id": decision.get("thesis_id"),
            "decision_id": decision.get("decision_id"),
            "settlement_evidence_id": evidence.get("evidence_id"),
            "settlement_evidence_sha256": evidence.get("raw_sha256"),
            "paper_only": True,
        },
    )


def alpha_settlement_to_finance_projection(result: Mapping[str, Any]) -> FinanceProjection:
    """Return the non-cash finance projection for a settled alpha result."""

    return paper_trade_to_finance_projection(alpha_settlement_to_paper_trade(result))


def _mapping(value: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    nested = value.get(key)
    if not isinstance(nested, Mapping):
        raise ValueError(f"result requires object field {key}")
    return nested


def _required_text(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"result requires {key}")
    return item.strip()


def _positive_number(value: Any, field_name: str) -> float:
    number = _nonnegative_number(value, field_name)
    if number <= 0.0:
        raise ValueError(f"{field_name} must be positive")
    return number


def _nonnegative_number(value: Any, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric") from exc
    if number < 0.0 or not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite and nonnegative")
    return number


def _parse_timestamp(value: Any, field_name: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be an ISO timestamp")
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO timestamp") from exc
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone")
    return timestamp.astimezone(UTC)
