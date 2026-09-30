"""Provider-neutral paper/simulation consumer for validated trade intents.

This module is intentionally an offline execution boundary. It evaluates a
sanitized quote, records an idempotent simulation receipt, and never selects a
provider, signs a transaction, calls RPC, or broadcasts anything.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from hashlib import sha256
from math import ceil
from typing import Any, Final

from app.trade_intent import (
    SUPPORTED_TRADE_CHAINS,
    TradeIntent,
    TradeIntentMode,
    TradeRouteKind,
    validate_trade_intent,
)

PAPER_EXECUTION_SCHEMA_VERSION: Final = "paper-execution.v1"
MAX_QUOTE_ID_LENGTH = 256
DEFAULT_MAX_QUOTE_AGE = timedelta(seconds=30)
_EVM_ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")
_IDENTITY_SEPARATOR = "|"


class PaperExecutionStatus(StrEnum):
    """Terminal outcome of one offline paper/simulation evaluation."""

    SIMULATED = "simulated"
    REJECTED = "rejected"


class PaperExecutionConflictError(ValueError):
    """Raised when an intent identity is reused with different quote data."""


def _text(value: Any, field_name: str, *, max_length: int = 512, lower: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be text")
    result = value.strip()
    if not result:
        raise ValueError(f"{field_name} is required")
    if len(result) > max_length:
        raise ValueError(f"{field_name} is too long")
    if _IDENTITY_SEPARATOR in result:
        raise ValueError(f"{field_name} must not contain '{_IDENTITY_SEPARATOR}'")
    return result.lower() if lower else result


def _integer(value: Any, field_name: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and value.strip().isdigit():
        result = int(value.strip(), 10)
    else:
        raise ValueError(f"{field_name} must be an integer")
    if result < minimum:
        raise ValueError(f"{field_name} must be at least {minimum}")
    return result


def _utc(value: Any, field_name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)


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


def _value(value: Any) -> str:
    return value.value if isinstance(value, StrEnum) else str(value)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _effective_slippage_bps(expected: int, actual: int) -> int:
    if actual >= expected:
        return 0
    loss = expected - actual
    return ceil(loss * 10_000 / expected)


def _execution_id(intent_id: str, quote_id: str) -> str:
    material = _IDENTITY_SEPARATOR.join((PAPER_EXECUTION_SCHEMA_VERSION, intent_id, quote_id))
    return sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class PaperQuote:
    """Sanitized provider output used only for offline fill evaluation."""

    quote_id: str
    chain: str
    route_kind: TradeRouteKind | str
    venue: str
    token_in: str
    token_out: str
    amount_in_raw: int
    expected_amount_out_raw: int
    simulated_amount_out_raw: int
    quoted_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        quote_id = _text(self.quote_id, "quote_id", max_length=MAX_QUOTE_ID_LENGTH)
        chain = _text(self.chain, "chain", lower=True)
        if chain not in SUPPORTED_TRADE_CHAINS:
            raise ValueError(f"chain must be one of: {', '.join(sorted(SUPPORTED_TRADE_CHAINS))}")
        try:
            route_kind = TradeRouteKind(_value(self.route_kind).lower())
        except ValueError as exc:
            raise ValueError("route_kind must be aggregator or direct_dex") from exc
        venue = _text(self.venue, "venue", lower=True)
        token_in = _asset(self.token_in, "token_in", chain)
        token_out = _asset(self.token_out, "token_out", chain)
        if token_in == token_out:
            raise ValueError("token_in and token_out must differ")
        amount_in = _integer(self.amount_in_raw, "amount_in_raw", minimum=1)
        expected = _integer(self.expected_amount_out_raw, "expected_amount_out_raw", minimum=1)
        simulated = _integer(self.simulated_amount_out_raw, "simulated_amount_out_raw")
        quoted_at = _utc(self.quoted_at, "quoted_at")
        expires_at = _utc(self.expires_at, "expires_at")
        if expires_at <= quoted_at:
            raise ValueError("expires_at must be after quoted_at")
        object.__setattr__(self, "quote_id", quote_id)
        object.__setattr__(self, "chain", chain)
        object.__setattr__(self, "route_kind", route_kind)
        object.__setattr__(self, "venue", venue)
        object.__setattr__(self, "token_in", token_in)
        object.__setattr__(self, "token_out", token_out)
        object.__setattr__(self, "amount_in_raw", amount_in)
        object.__setattr__(self, "expected_amount_out_raw", expected)
        object.__setattr__(self, "simulated_amount_out_raw", simulated)
        object.__setattr__(self, "quoted_at", quoted_at)
        object.__setattr__(self, "expires_at", expires_at)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe quote without transaction or provider secrets."""

        return {
            "quote_id": self.quote_id,
            "chain": self.chain,
            "route_kind": _value(self.route_kind),
            "venue": self.venue,
            "token_in": self.token_in,
            "token_out": self.token_out,
            "amount_in_raw": self.amount_in_raw,
            "expected_amount_out_raw": self.expected_amount_out_raw,
            "simulated_amount_out_raw": self.simulated_amount_out_raw,
            "quoted_at": _iso(self.quoted_at),
            "expires_at": _iso(self.expires_at),
        }


@dataclass(frozen=True, slots=True)
class PaperExecutionReceipt:
    """Immutable result of one paper/simulation evaluation."""

    execution_id: str
    schema_version: str
    intent_id: str
    quote_id: str
    execution_mode: TradeIntentMode | str
    status: PaperExecutionStatus | str
    failure_code: str | None
    observed_at: datetime
    quote_expires_at: datetime
    amount_in_raw: int
    expected_amount_out_raw: int
    simulated_amount_out_raw: int
    effective_slippage_bps: int
    replayed: bool = False
    signed: bool = False
    broadcasted: bool = False
    transaction_hash: None = None
    reconciled: bool = False

    def __post_init__(self) -> None:
        execution_id = _text(self.execution_id, "execution_id", max_length=128)
        if self.schema_version != PAPER_EXECUTION_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {PAPER_EXECUTION_SCHEMA_VERSION}")
        intent_id = _text(self.intent_id, "intent_id", max_length=128)
        quote_id = _text(self.quote_id, "quote_id", max_length=MAX_QUOTE_ID_LENGTH)
        try:
            execution_mode = TradeIntentMode(_value(self.execution_mode))
        except ValueError as exc:
            raise ValueError("execution_mode must be paper or simulation") from exc
        try:
            status = PaperExecutionStatus(_value(self.status))
        except ValueError as exc:
            raise ValueError("status must be simulated or rejected") from exc
        if self.failure_code is not None:
            failure_code = _text(self.failure_code, "failure_code", max_length=128, lower=True)
        else:
            failure_code = None
        observed_at = _utc(self.observed_at, "observed_at")
        quote_expires_at = _utc(self.quote_expires_at, "quote_expires_at")
        amount_in = _integer(self.amount_in_raw, "amount_in_raw", minimum=1)
        expected = _integer(self.expected_amount_out_raw, "expected_amount_out_raw", minimum=1)
        simulated = _integer(self.simulated_amount_out_raw, "simulated_amount_out_raw")
        slippage = _integer(self.effective_slippage_bps, "effective_slippage_bps")
        if slippage > 10_000:
            raise ValueError("effective_slippage_bps must be at most 10000")
        if status is PaperExecutionStatus.SIMULATED and failure_code is not None:
            raise ValueError("simulated receipt cannot contain failure_code")
        if status is PaperExecutionStatus.REJECTED and failure_code is None:
            raise ValueError("rejected receipt requires failure_code")
        if self.signed or self.broadcasted or self.transaction_hash is not None or self.reconciled:
            raise ValueError("paper receipt cannot contain live execution state")
        for name, value in (
            ("execution_id", execution_id),
            ("intent_id", intent_id),
            ("quote_id", quote_id),
            ("execution_mode", execution_mode),
            ("status", status),
            ("failure_code", failure_code),
            ("observed_at", observed_at),
            ("quote_expires_at", quote_expires_at),
            ("amount_in_raw", amount_in),
            ("expected_amount_out_raw", expected),
            ("simulated_amount_out_raw", simulated),
            ("effective_slippage_bps", slippage),
        ):
            object.__setattr__(self, name, value)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe, explicitly non-live receipt."""

        return {
            "execution_id": self.execution_id,
            "schema_version": self.schema_version,
            "intent_id": self.intent_id,
            "quote_id": self.quote_id,
            "execution_mode": _value(self.execution_mode),
            "status": _value(self.status),
            "failure_code": self.failure_code,
            "observed_at": _iso(self.observed_at),
            "quote_expires_at": _iso(self.quote_expires_at),
            "amount_in_raw": self.amount_in_raw,
            "expected_amount_out_raw": self.expected_amount_out_raw,
            "simulated_amount_out_raw": self.simulated_amount_out_raw,
            "effective_slippage_bps": self.effective_slippage_bps,
            "replayed": self.replayed,
            "signed": False,
            "broadcasted": False,
            "transaction_hash": None,
            "reconciled": False,
            "execution_allowed": False,
        }


class PaperExecutionGateway:
    """Idempotent offline consumer for ``TradeIntent`` and ``PaperQuote``."""

    EVENT_VERSION = 1

    def __init__(self, *, max_quote_age: timedelta = DEFAULT_MAX_QUOTE_AGE) -> None:
        if not isinstance(max_quote_age, timedelta) or max_quote_age <= timedelta(0):
            raise ValueError("max_quote_age must be a positive timedelta")
        self.max_quote_age = max_quote_age
        self._receipts: dict[str, PaperExecutionReceipt] = {}
        self._fingerprints: dict[str, str] = {}

    @property
    def receipts(self) -> tuple[PaperExecutionReceipt, ...]:
        """Return stored receipts in stable intent order."""

        return tuple(self._receipts[key] for key in sorted(self._receipts))

    def simulate(
        self,
        intent: TradeIntent | Mapping[str, Any],
        quote: PaperQuote,
        *,
        now: datetime | None = None,
    ) -> PaperExecutionReceipt:
        """Evaluate one intent without selecting a provider or creating a tx."""

        normalized_intent = validate_trade_intent(intent)
        if not isinstance(quote, PaperQuote):
            raise ValueError("quote must be a PaperQuote")
        observed_at = datetime.now(UTC) if now is None else _utc(now, "now")
        fingerprint = self._fingerprint(normalized_intent.intent_id, quote)
        existing = self._receipts.get(normalized_intent.intent_id)
        if existing is not None:
            if self._fingerprints[normalized_intent.intent_id] != fingerprint:
                raise PaperExecutionConflictError(
                    f"intent_id already has a different paper quote: {normalized_intent.intent_id}"
                )
            return replace(existing, replayed=True)

        failure_code = self._failure_code(normalized_intent, quote, observed_at)
        simulated = quote.simulated_amount_out_raw
        effective_slippage = _effective_slippage_bps(quote.expected_amount_out_raw, simulated)
        receipt = PaperExecutionReceipt(
            execution_id=_execution_id(normalized_intent.intent_id, quote.quote_id),
            schema_version=PAPER_EXECUTION_SCHEMA_VERSION,
            intent_id=normalized_intent.intent_id,
            quote_id=quote.quote_id,
            execution_mode=normalized_intent.execution_mode,
            status=PaperExecutionStatus.REJECTED if failure_code else PaperExecutionStatus.SIMULATED,
            failure_code=failure_code,
            observed_at=observed_at,
            quote_expires_at=quote.expires_at,
            amount_in_raw=quote.amount_in_raw,
            expected_amount_out_raw=quote.expected_amount_out_raw,
            simulated_amount_out_raw=simulated,
            effective_slippage_bps=effective_slippage,
        )
        self._receipts[normalized_intent.intent_id] = receipt
        self._fingerprints[normalized_intent.intent_id] = fingerprint
        return receipt

    def export_events(self) -> tuple[dict[str, Any], ...]:
        """Return secret-free, versioned events for a lake writer or fixture."""

        return tuple(
            {
                "event_version": self.EVENT_VERSION,
                "event_type": "paper_execution_receipt",
                "event_id": receipt.execution_id,
                "receipt": receipt.as_dict(),
            }
            for receipt in self.receipts
        )

    @staticmethod
    def _fingerprint(intent_id: str, quote: PaperQuote) -> str:
        material = _IDENTITY_SEPARATOR.join(
            (
                intent_id,
                quote.quote_id,
                quote.chain,
                _value(quote.route_kind),
                quote.venue,
                quote.token_in,
                quote.token_out,
                str(quote.amount_in_raw),
                str(quote.expected_amount_out_raw),
                str(quote.simulated_amount_out_raw),
                _iso(quote.quoted_at),
                _iso(quote.expires_at),
            )
        )
        return sha256(material.encode("utf-8")).hexdigest()

    def _failure_code(self, intent: TradeIntent, quote: PaperQuote, now: datetime) -> str | None:
        if (
            quote.chain != intent.chain
            or _value(quote.route_kind) != _value(intent.route_kind)
            or quote.venue != intent.venue
            or quote.token_in != intent.token_in
            or quote.token_out != intent.token_out
            or quote.amount_in_raw != intent.amount_in_raw
        ):
            return "quote_context_mismatch"
        if now >= intent.expires_at:
            return "intent_expired"
        if now < quote.quoted_at:
            return "quote_not_yet_valid"
        if now >= quote.expires_at:
            return "quote_expired"
        if now - quote.quoted_at > self.max_quote_age:
            return "quote_stale"
        if (
            _effective_slippage_bps(quote.expected_amount_out_raw, quote.simulated_amount_out_raw)
            > intent.max_slippage_bps
        ):
            return "quote_slippage_exceeded"
        return None


__all__ = [
    "DEFAULT_MAX_QUOTE_AGE",
    "MAX_QUOTE_ID_LENGTH",
    "PAPER_EXECUTION_SCHEMA_VERSION",
    "PaperExecutionConflictError",
    "PaperExecutionGateway",
    "PaperExecutionReceipt",
    "PaperExecutionStatus",
    "PaperQuote",
]
