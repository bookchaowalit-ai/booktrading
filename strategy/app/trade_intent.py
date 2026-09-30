"""Provider-neutral, paper-only on-chain trade intent contract.

The strategy layer may propose a bounded intent after the risk gate passes.
This contract deliberately contains no calldata, router address, RPC URL,
private key, signature, or broadcast operation. A future execution gateway
must validate the intent again before selecting a chain-specific adapter.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from math import isfinite
from typing import Any, Final

from app.market_intel.risk_gate import RiskDecision, RiskState

TRADE_INTENT_SCHEMA_VERSION = "trade-intent.v1"
SUPPORTED_TRADE_CHAINS: Final = frozenset({"solana", "ethereum", "bsc", "base", "arbitrum"})
MAX_SLIPPAGE_BPS = 10_000
MAX_EVIDENCE_REFS = 64
_EVM_ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")
_INT = re.compile(r"^[0-9]+$")
_IDENTITY_SEPARATOR = "|"


class TradeIntentMode(StrEnum):
    """Modes accepted by the strategy-side contract."""

    PAPER = "paper"
    SIMULATION = "simulation"


class TradeRouteKind(StrEnum):
    """Routing boundary selected by a future execution gateway."""

    AGGREGATOR = "aggregator"
    DIRECT_DEX = "direct_dex"


def _text(value: Any, field_name: str, *, lower: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be text")
    result = value.strip()
    if not result:
        raise ValueError(f"{field_name} is required")
    if len(result) > 256:
        raise ValueError(f"{field_name} is too long")
    if _IDENTITY_SEPARATOR in result:
        raise ValueError(f"{field_name} must not contain '{_IDENTITY_SEPARATOR}'")
    return result.lower() if lower else result


def _chain(value: Any) -> str:
    result = _text(value, "chain", lower=True)
    if result not in SUPPORTED_TRADE_CHAINS:
        allowed = ", ".join(sorted(SUPPORTED_TRADE_CHAINS))
        raise ValueError(f"chain must be one of: {allowed}")
    return result


def _asset(value: Any, field_name: str, chain: str) -> str:
    result = _text(value, field_name)
    if result.lower() == "native":
        return "native"
    if result.lower().startswith("0x"):
        if _EVM_ADDRESS.fullmatch(result) is None:
            raise ValueError(f"{field_name} must be a 20-byte EVM address")
        return result.lower()
    if chain != "solana":
        raise ValueError(f"{field_name} must be native or a 20-byte EVM address")
    return result


def _wallet(value: Any, field_name: str, chain: str) -> str:
    result = _asset(value, field_name, chain)
    if chain != "solana" and _EVM_ADDRESS.fullmatch(result) is None:
        raise ValueError(f"{field_name} must be a 20-byte EVM address")
    return result


def _integer(value: Any, field_name: str, *, positive: bool = False) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and _INT.fullmatch(value.strip()):
        result = int(value.strip(), 10)
    else:
        raise ValueError(f"{field_name} must be an integer")
    if positive and result <= 0:
        raise ValueError(f"{field_name} must be positive")
    if not positive and result < 0:
        raise ValueError(f"{field_name} must not be negative")
    return result


def _slippage(value: Any) -> int:
    result = _integer(value, "max_slippage_bps")
    if result > MAX_SLIPPAGE_BPS:
        raise ValueError(f"max_slippage_bps must be between 0 and {MAX_SLIPPAGE_BPS}")
    return result


def _ratio(value: Any, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a finite number between 0 and 1")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a finite number between 0 and 1") from exc
    if not isfinite(result) or result < 0 or result > 1:
        raise ValueError(f"{field_name} must be a finite number between 0 and 1")
    return result


def _utc(value: Any, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a datetime")
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _refs(values: Iterable[str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ValueError("evidence_refs must be an iterable of text references")
    try:
        result = tuple(_text(value, "evidence_ref") for value in values)
    except TypeError as exc:
        raise ValueError("evidence_refs must be an iterable of text references") from exc
    if not result:
        raise ValueError("evidence_refs must not be empty")
    if len(result) > MAX_EVIDENCE_REFS:
        raise ValueError(f"evidence_refs must contain at most {MAX_EVIDENCE_REFS} entries")
    if len(set(result)) != len(result):
        raise ValueError("evidence_refs must be unique")
    return result


def _risk_state(value: Any) -> RiskState:
    candidate = value.value if isinstance(value, RiskState) else value
    try:
        state = RiskState(_text(candidate, "risk_state", lower=True))
    except ValueError as exc:
        raise ValueError("risk_state must be a supported risk state") from exc
    if state not in {RiskState.WATCHLIST, RiskState.PAPER_CANDIDATE}:
        raise ValueError("risk_state must be watchlist or paper_candidate")
    return state


def _normalize_payload(
    *,
    chain: Any,
    route_kind: Any,
    venue: Any,
    token_in: Any,
    token_out: Any,
    amount_in_raw: Any,
    max_slippage_bps: Any,
    recipient_wallet: Any,
    risk_state: Any,
    risk_confidence: Any,
    risk_policy_version: Any,
    evidence_refs: Iterable[str],
    created_at: Any,
    expires_at: Any,
    execution_mode: Any,
) -> dict[str, Any]:
    normalized_chain = _chain(chain)
    normalized_route_kind = (
        route_kind.value if isinstance(route_kind, TradeRouteKind) else _text(route_kind, "route_kind", lower=True)
    )
    try:
        normalized_route_kind = TradeRouteKind(normalized_route_kind)
    except ValueError as exc:
        raise ValueError("route_kind must be aggregator or direct_dex") from exc

    normalized_mode = (
        execution_mode.value
        if isinstance(execution_mode, TradeIntentMode)
        else _text(execution_mode, "execution_mode", lower=True)
    )
    try:
        normalized_mode = TradeIntentMode(normalized_mode)
    except ValueError as exc:
        raise ValueError("execution_mode must be paper or simulation") from exc

    normalized_token_in = _asset(token_in, "token_in", normalized_chain)
    normalized_token_out = _asset(token_out, "token_out", normalized_chain)
    if normalized_token_in == normalized_token_out:
        raise ValueError("token_in and token_out must differ")

    normalized_created_at = _utc(created_at, "created_at")
    normalized_expires_at = _utc(expires_at, "expires_at")
    if normalized_expires_at <= normalized_created_at:
        raise ValueError("expires_at must be after created_at")

    return {
        "schema_version": TRADE_INTENT_SCHEMA_VERSION,
        "chain": normalized_chain,
        "route_kind": normalized_route_kind,
        "venue": _text(venue, "venue", lower=True),
        "token_in": normalized_token_in,
        "token_out": normalized_token_out,
        "amount_in_raw": _integer(amount_in_raw, "amount_in_raw", positive=True),
        "max_slippage_bps": _slippage(max_slippage_bps),
        "recipient_wallet": _wallet(recipient_wallet, "recipient_wallet", normalized_chain),
        "risk_state": _risk_state(risk_state),
        "risk_confidence": _ratio(risk_confidence, "risk_confidence"),
        "risk_policy_version": _text(risk_policy_version, "risk_policy_version"),
        "evidence_refs": _refs(evidence_refs),
        "created_at": normalized_created_at,
        "expires_at": normalized_expires_at,
        "execution_mode": normalized_mode,
    }


def trade_intent_identity_material(payload: Mapping[str, Any]) -> str:
    """Return the canonical material used for deterministic intent identity."""

    def value(item: Any) -> str:
        return item.value if isinstance(item, StrEnum) else str(item)

    fields = (
        value(payload["schema_version"]),
        value(payload["chain"]),
        value(payload["route_kind"]),
        value(payload["venue"]),
        value(payload["token_in"]),
        value(payload["token_out"]),
        str(payload["amount_in_raw"]),
        str(payload["max_slippage_bps"]),
        value(payload["recipient_wallet"]),
        value(payload["risk_state"]),
        format(payload["risk_confidence"], ".12g"),
        value(payload["risk_policy_version"]),
        *(value(item) for item in payload["evidence_refs"]),
        payload["created_at"].isoformat(),
        payload["expires_at"].isoformat(),
        value(payload["execution_mode"]),
    )
    return _IDENTITY_SEPARATOR.join(fields)


def compute_trade_intent_id(payload: Mapping[str, Any]) -> str:
    """Compute a stable identity for one immutable strategy proposal."""

    return sha256(trade_intent_identity_material(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class TradeIntent:
    """Risk-approved paper/simulation proposal for a future executor."""

    intent_id: str
    schema_version: str
    chain: str
    route_kind: TradeRouteKind | str
    venue: str
    token_in: str
    token_out: str
    amount_in_raw: int
    max_slippage_bps: int
    recipient_wallet: str
    risk_state: RiskState | str
    risk_confidence: float
    risk_policy_version: str
    evidence_refs: tuple[str, ...]
    created_at: datetime
    expires_at: datetime
    execution_mode: TradeIntentMode | str

    def __post_init__(self) -> None:
        if self.schema_version != TRADE_INTENT_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {TRADE_INTENT_SCHEMA_VERSION}")
        payload = _normalize_payload(
            chain=self.chain,
            route_kind=self.route_kind,
            venue=self.venue,
            token_in=self.token_in,
            token_out=self.token_out,
            amount_in_raw=self.amount_in_raw,
            max_slippage_bps=self.max_slippage_bps,
            recipient_wallet=self.recipient_wallet,
            risk_state=self.risk_state,
            risk_confidence=self.risk_confidence,
            risk_policy_version=self.risk_policy_version,
            evidence_refs=self.evidence_refs,
            created_at=self.created_at,
            expires_at=self.expires_at,
            execution_mode=self.execution_mode,
        )
        expected_id = compute_trade_intent_id(payload)
        if self.intent_id != expected_id:
            raise ValueError("intent_id does not match the normalized trade intent")
        for field_name, value in payload.items():
            if field_name == "schema_version":
                continue
            object.__setattr__(self, field_name, value)

    @classmethod
    def create(cls, **kwargs: Any) -> TradeIntent:
        """Create a validated intent and derive its deterministic identity."""

        payload = _normalize_payload(**kwargs)
        return cls(intent_id=compute_trade_intent_id(payload), **payload)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe payload for a paper/simulation consumer."""

        return {
            "intent_id": self.intent_id,
            "schema_version": self.schema_version,
            "chain": self.chain,
            "route_kind": self.route_kind.value if isinstance(self.route_kind, StrEnum) else self.route_kind,
            "venue": self.venue,
            "token_in": self.token_in,
            "token_out": self.token_out,
            "amount_in_raw": self.amount_in_raw,
            "max_slippage_bps": self.max_slippage_bps,
            "recipient_wallet": self.recipient_wallet,
            "risk_state": self.risk_state.value if isinstance(self.risk_state, StrEnum) else self.risk_state,
            "risk_confidence": self.risk_confidence,
            "risk_policy_version": self.risk_policy_version,
            "evidence_refs": list(self.evidence_refs),
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "execution_mode": (
                self.execution_mode.value if isinstance(self.execution_mode, StrEnum) else self.execution_mode
            ),
            "execution_allowed": False,
        }


def build_trade_intent(
    *,
    risk_decision: RiskDecision,
    chain: str,
    route_kind: TradeRouteKind | str,
    venue: str,
    token_in: str,
    token_out: str,
    amount_in_raw: int | str,
    max_slippage_bps: int | str,
    recipient_wallet: str,
    evidence_refs: Iterable[str],
    created_at: datetime,
    expires_at: datetime,
    execution_mode: TradeIntentMode | str = TradeIntentMode.PAPER,
) -> TradeIntent:
    """Create an intent only after the existing deterministic risk gate passes."""

    if not isinstance(risk_decision, RiskDecision):
        raise ValueError("risk_decision must be a RiskDecision")
    if not risk_decision.eligible or risk_decision.hard_veto:
        raise ValueError("risk decision does not permit a trade intent")
    return TradeIntent.create(
        chain=chain,
        route_kind=route_kind,
        venue=venue,
        token_in=token_in,
        token_out=token_out,
        amount_in_raw=amount_in_raw,
        max_slippage_bps=max_slippage_bps,
        recipient_wallet=recipient_wallet,
        risk_state=risk_decision.state,
        risk_confidence=risk_decision.confidence,
        risk_policy_version=risk_decision.policy_version,
        evidence_refs=evidence_refs,
        created_at=created_at,
        expires_at=expires_at,
        execution_mode=execution_mode,
    )


def validate_trade_intent(value: TradeIntent | Mapping[str, Any]) -> TradeIntent:
    """Validate an existing intent object or serialized mapping."""

    if isinstance(value, TradeIntent):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("trade intent must be a TradeIntent or mapping")
    allowed_fields = {
        "intent_id",
        "schema_version",
        "chain",
        "route_kind",
        "venue",
        "token_in",
        "token_out",
        "amount_in_raw",
        "max_slippage_bps",
        "recipient_wallet",
        "risk_state",
        "risk_confidence",
        "risk_policy_version",
        "evidence_refs",
        "created_at",
        "expires_at",
        "execution_mode",
        "execution_allowed",
    }
    unknown_fields = set(value) - allowed_fields
    if unknown_fields:
        names = ", ".join(sorted(str(field) for field in unknown_fields))
        raise ValueError(f"trade intent contains unsupported fields: {names}")
    if "execution_allowed" in value and value["execution_allowed"] is not False:
        raise ValueError("execution_allowed must remain false in the strategy contract")
    return TradeIntent(
        intent_id=value.get("intent_id"),
        schema_version=value.get("schema_version"),
        chain=value.get("chain"),
        route_kind=value.get("route_kind"),
        venue=value.get("venue"),
        token_in=value.get("token_in"),
        token_out=value.get("token_out"),
        amount_in_raw=value.get("amount_in_raw"),
        max_slippage_bps=value.get("max_slippage_bps"),
        recipient_wallet=value.get("recipient_wallet"),
        risk_state=value.get("risk_state"),
        risk_confidence=value.get("risk_confidence"),
        risk_policy_version=value.get("risk_policy_version"),
        evidence_refs=value.get("evidence_refs"),
        created_at=_parse_datetime(value.get("created_at"), "created_at"),
        expires_at=_parse_datetime(value.get("expires_at"), "expires_at"),
        execution_mode=value.get("execution_mode"),
    )


def _parse_datetime(value: Any, field_name: str) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"{field_name} must be an ISO-8601 datetime") from exc
    raise ValueError(f"{field_name} must be an ISO-8601 datetime")


__all__ = [
    "MAX_EVIDENCE_REFS",
    "MAX_SLIPPAGE_BPS",
    "SUPPORTED_TRADE_CHAINS",
    "TRADE_INTENT_SCHEMA_VERSION",
    "TradeIntent",
    "TradeIntentMode",
    "TradeRouteKind",
    "build_trade_intent",
    "compute_trade_intent_id",
    "trade_intent_identity_material",
    "validate_trade_intent",
]
