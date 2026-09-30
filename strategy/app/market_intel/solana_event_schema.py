"""Versioned, read-only schema for normalized Solana sell observations.

The schema is intentionally independent from an RPC client or a lake writer.
It describes one normalized sell event and the append-only status changes that
may arrive after the initial observation.  Raw token and quote amounts remain
integer base units; a USD value is optional evidence supplied by an outer
valuation boundary and is never calculated here.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import Enum, StrEnum
from hashlib import sha256
from math import isfinite
from typing import Any, Final

SOLANA_EVENT_SCHEMA_VERSION = "solana-event.v1"
SOLANA_EVENT_VERSION = SOLANA_EVENT_SCHEMA_VERSION


class EventType(StrEnum):
    """Event types accepted by the sell-event contract."""

    SELL = "sell"


class DecoderStatus(StrEnum):
    """Decoder evidence status carried by a normalized event."""

    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    UNKNOWN = "unknown"


class FinalityStatus(StrEnum):
    """Provider commitment state observed for an event."""

    PROCESSED = "processed"
    CONFIRMED = "confirmed"
    FINALIZED = "finalized"
    UNKNOWN = "unknown"


class ReorgStatus(StrEnum):
    """Whether the event is still subject to, or survived, a reorg."""

    PENDING = "pending"
    CANONICAL = "canonical"
    ORPHANED = "orphaned"
    UNKNOWN = "unknown"


# More descriptive aliases are useful to callers without changing the wire
# values used by the contract.
SolanaFinalityStatus = FinalityStatus
SolanaReorgStatus = ReorgStatus

FINALITY_STATUSES: Final = frozenset(item.value for item in FinalityStatus)
REORG_STATUSES: Final = frozenset(item.value for item in ReorgStatus)

_IDENTITY_COMPONENT_FIELDS: Final = (
    "chain",
    "protocol",
    "program_id",
    "signature",
    "instruction_index",
    "event_index",
)
_STATUS_FIELDS: Final = ("finality_status", "reorg_status")
_IMMUTABLE_EVENT_FIELDS: Final = (
    "event_id",
    "event_schema_version",
    "chain",
    "protocol",
    "program_id",
    "event_type",
    "signature",
    "slot",
    "instruction_index",
    "event_index",
    "token_address",
    "pool_address",
    "seller_wallet",
    "token_amount_raw",
    "quote_amount_raw",
    "quote_mint",
    "observed_at",
    "source",
    "decoder_version",
    "decoder_status",
    "quote_value_usd",
)
_INTEGER_TEXT = re.compile(r"^[0-9]+$")


def _text(value: Any, field_name: str, *, lower: bool = False, identity: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be text")
    result = value.strip()
    if not result:
        raise ValueError(f"{field_name} is required")
    if len(result) > 512:
        raise ValueError(f"{field_name} is too long")
    if identity and "|" in result:
        raise ValueError(f"{field_name} must not contain '|'")
    return result.lower() if lower else result


def _non_negative_int(value: Any, field_name: str) -> int:
    """Normalize a JSON integer or decimal integer string without float casts."""

    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and _INTEGER_TEXT.fullmatch(value.strip()):
        result = int(value.strip())
    else:
        raise ValueError(f"{field_name} must be an integer")
    if result < 0:
        raise ValueError(f"{field_name} must not be negative")
    return result


def _enum_value(value: Any, enum_type: type[Enum], field_name: str) -> Enum:
    candidate = value.value if isinstance(value, Enum) else value
    if not isinstance(candidate, str):
        raise ValueError(f"{field_name} is invalid")
    try:
        return enum_type(candidate.strip().lower())
    except ValueError as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise ValueError(f"{field_name} must be one of: {allowed}") from exc


def _datetime(value: Any, field_name: str) -> datetime:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        try:
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"{field_name} must be an ISO-8601 datetime") from exc
    else:
        raise ValueError(f"{field_name} must be a datetime")
    return result if result.tzinfo else result.replace(tzinfo=UTC)


def _optional_usd(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("quote_value_usd must be a finite non-negative number")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("quote_value_usd must be a finite non-negative number") from exc
    if not isfinite(result) or result < 0:
        raise ValueError("quote_value_usd must be a finite non-negative number")
    return result


def _identity_text(value: Any, field_name: str, *, lower: bool = False) -> str:
    return _text(value, field_name, lower=lower, identity=True)


def event_identity_material(
    chain: str,
    protocol: str,
    program_id: str,
    signature: str,
    instruction_index: int,
    event_index: int,
) -> str:
    """Return the canonical pipe-delimited identity input before hashing."""

    components = (
        _identity_text(chain, "chain", lower=True),
        _identity_text(protocol, "protocol", lower=True),
        _identity_text(program_id, "program_id"),
        _identity_text(signature, "signature"),
        str(_non_negative_int(instruction_index, "instruction_index")),
        str(_non_negative_int(event_index, "event_index")),
    )
    return "|".join(components)


def compute_event_id(
    chain: str,
    protocol: str,
    program_id: str,
    signature: str,
    instruction_index: int,
    event_index: int,
) -> str:
    """Compute the stable SHA-256 event identity for a normalized sell."""

    material = event_identity_material(
        chain,
        protocol,
        program_id,
        signature,
        instruction_index,
        event_index,
    )
    return sha256(material.encode("utf-8")).hexdigest()


# Common names make the deterministic identity helper discoverable while
# retaining one implementation and one wire identity.
deterministic_event_id = compute_event_id
build_event_id = compute_event_id


@dataclass(frozen=True, slots=True)
class SolanaSellEvent:
    """One validated ``solana-event.v1`` normalized sell event."""

    event_id: str
    event_schema_version: str
    chain: str
    protocol: str
    program_id: str
    event_type: EventType | str
    signature: str
    slot: int
    instruction_index: int
    event_index: int
    token_address: str
    pool_address: str
    seller_wallet: str
    token_amount_raw: int
    quote_amount_raw: int
    quote_mint: str
    observed_at: datetime
    source: str
    decoder_version: str
    decoder_status: DecoderStatus | str
    finality_status: FinalityStatus | str
    reorg_status: ReorgStatus | str
    quote_value_usd: float | None = None

    def __post_init__(self) -> None:
        event_id = _identity_text(self.event_id, "event_id")
        version = _text(self.event_schema_version, "event_schema_version")
        if version != SOLANA_EVENT_SCHEMA_VERSION:
            raise ValueError(f"event_schema_version must be {SOLANA_EVENT_SCHEMA_VERSION}")

        chain = _identity_text(self.chain, "chain", lower=True)
        protocol = _identity_text(self.protocol, "protocol", lower=True)
        program_id = _identity_text(self.program_id, "program_id")
        signature = _identity_text(self.signature, "signature")
        instruction_index = _non_negative_int(self.instruction_index, "instruction_index")
        event_index = _non_negative_int(self.event_index, "event_index")
        expected_id = compute_event_id(
            chain,
            protocol,
            program_id,
            signature,
            instruction_index,
            event_index,
        )
        if event_id != expected_id:
            raise ValueError("event_id does not match the normalized event identity")

        event_type = _enum_value(self.event_type, EventType, "event_type")
        decoder_status = _enum_value(self.decoder_status, DecoderStatus, "decoder_status")
        finality_status = _enum_value(self.finality_status, FinalityStatus, "finality_status")
        reorg_status = _enum_value(self.reorg_status, ReorgStatus, "reorg_status")

        object.__setattr__(self, "event_id", event_id)
        object.__setattr__(self, "event_schema_version", version)
        object.__setattr__(self, "chain", chain)
        object.__setattr__(self, "protocol", protocol)
        object.__setattr__(self, "program_id", program_id)
        object.__setattr__(self, "event_type", event_type)
        object.__setattr__(self, "signature", signature)
        object.__setattr__(self, "slot", _non_negative_int(self.slot, "slot"))
        object.__setattr__(self, "instruction_index", instruction_index)
        object.__setattr__(self, "event_index", event_index)
        object.__setattr__(self, "token_address", _text(self.token_address, "token_address"))
        object.__setattr__(self, "pool_address", _text(self.pool_address, "pool_address"))
        object.__setattr__(self, "seller_wallet", _text(self.seller_wallet, "seller_wallet"))
        object.__setattr__(
            self,
            "token_amount_raw",
            _non_negative_int(self.token_amount_raw, "token_amount_raw"),
        )
        object.__setattr__(
            self,
            "quote_amount_raw",
            _non_negative_int(self.quote_amount_raw, "quote_amount_raw"),
        )
        object.__setattr__(self, "quote_mint", _text(self.quote_mint, "quote_mint"))
        object.__setattr__(self, "observed_at", _datetime(self.observed_at, "observed_at"))
        object.__setattr__(self, "source", _text(self.source, "source"))
        object.__setattr__(self, "decoder_version", _text(self.decoder_version, "decoder_version"))
        object.__setattr__(self, "decoder_status", decoder_status)
        object.__setattr__(self, "finality_status", finality_status)
        object.__setattr__(self, "reorg_status", reorg_status)
        object.__setattr__(self, "quote_value_usd", _optional_usd(self.quote_value_usd))

    @property
    def monitor_eligible(self) -> bool:
        """Whether this event may enter the cluster-sell monitor."""

        return is_monitor_eligible(self)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation without derived guesses."""

        result: dict[str, Any] = {
            "event_id": self.event_id,
            "event_schema_version": self.event_schema_version,
            "chain": self.chain,
            "protocol": self.protocol,
            "program_id": self.program_id,
            "event_type": self.event_type.value,
            "signature": self.signature,
            "slot": self.slot,
            "instruction_index": self.instruction_index,
            "event_index": self.event_index,
            "token_address": self.token_address,
            "pool_address": self.pool_address,
            "seller_wallet": self.seller_wallet,
            "token_amount_raw": self.token_amount_raw,
            "quote_amount_raw": self.quote_amount_raw,
            "quote_mint": self.quote_mint,
            "observed_at": self.observed_at.isoformat(),
            "source": self.source,
            "decoder_version": self.decoder_version,
            "decoder_status": self.decoder_status.value,
            "finality_status": self.finality_status.value,
            "reorg_status": self.reorg_status.value,
        }
        if self.quote_value_usd is not None:
            result["quote_value_usd"] = self.quote_value_usd
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> SolanaSellEvent:
        if not isinstance(value, Mapping):
            raise ValueError("a Solana sell event must be a mapping")
        return cls(**dict(value))


def validate_solana_sell_event(value: SolanaSellEvent | Mapping[str, Any]) -> SolanaSellEvent:
    """Validate an existing event or construct one from a mapping."""

    if isinstance(value, SolanaSellEvent):
        return value
    return SolanaSellEvent.from_dict(value)


def is_monitor_eligible(value: SolanaSellEvent | Mapping[str, Any]) -> bool:
    """Return true only for verified, finalized, canonical events."""

    event = validate_solana_sell_event(value)
    return (
        event.decoder_status is DecoderStatus.VERIFIED
        and event.finality_status is FinalityStatus.FINALIZED
        and event.reorg_status is ReorgStatus.CANONICAL
    )


monitor_eligible = is_monitor_eligible


@dataclass(frozen=True, slots=True)
class SolanaEventStatusRevision:
    """An append-only status record referring to one stable event identity."""

    event_id: str
    finality_status: FinalityStatus | str
    reorg_status: ReorgStatus | str
    revised_at: datetime
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_id", _identity_text(self.event_id, "event_id"))
        object.__setattr__(
            self,
            "finality_status",
            _enum_value(self.finality_status, FinalityStatus, "finality_status"),
        )
        object.__setattr__(
            self,
            "reorg_status",
            _enum_value(self.reorg_status, ReorgStatus, "reorg_status"),
        )
        object.__setattr__(self, "revised_at", _datetime(self.revised_at, "revised_at"))
        if self.reason is not None:
            object.__setattr__(self, "reason", _text(self.reason, "reason"))

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "event_schema_version": SOLANA_EVENT_SCHEMA_VERSION,
            "revision_type": "status",
            "event_id": self.event_id,
            "finality_status": self.finality_status.value,
            "reorg_status": self.reorg_status.value,
            "revised_at": self.revised_at.isoformat(),
        }
        if self.reason is not None:
            result["reason"] = self.reason
        return result


def make_status_revision(
    event: SolanaSellEvent | Mapping[str, Any],
    *,
    finality_status: FinalityStatus | str,
    reorg_status: ReorgStatus | str,
    revised_at: datetime,
    reason: str | None = None,
) -> SolanaEventStatusRevision:
    """Create a status-only append record for ``event``."""

    normalized = validate_solana_sell_event(event)
    return SolanaEventStatusRevision(
        event_id=normalized.event_id,
        finality_status=finality_status,
        reorg_status=reorg_status,
        revised_at=revised_at,
        reason=reason,
    )


def _canonical_field_value(event: SolanaSellEvent, field_name: str) -> Any:
    value = getattr(event, field_name)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def append_status_revision(
    event: SolanaSellEvent | Mapping[str, Any],
    revision: SolanaEventStatusRevision | Mapping[str, Any] | None = None,
    *,
    finality_status: FinalityStatus | str | None = None,
    reorg_status: ReorgStatus | str | None = None,
    **changes: Any,
) -> SolanaSellEvent:
    """Return a new event with status changes and preserve the old event.

    A revision may be supplied as a ``SolanaEventStatusRevision`` or as a
    mapping.  Any event field included in a mapping is compared with the
    original event; a changed identity or evidence field is rejected instead
    of silently creating a second interpretation of the event.
    """

    normalized = validate_solana_sell_event(event)
    revision_values: dict[str, Any] = {}
    if revision is not None:
        if isinstance(revision, SolanaEventStatusRevision):
            if revision.event_id != normalized.event_id:
                raise ValueError("status revision event_id does not match the event")
            revision_values.update(
                {
                    "finality_status": revision.finality_status,
                    "reorg_status": revision.reorg_status,
                }
            )
        elif isinstance(revision, Mapping):
            revision_values.update(dict(revision))
        else:
            raise ValueError("revision must be a status revision or mapping")

    revision_values.update(changes)
    revision_event_id = revision_values.get("event_id")
    if revision_event_id is not None and revision_event_id != normalized.event_id:
        raise ValueError("status revision event_id does not match the event")

    allowed_revision_metadata = {"event_id", "event_schema_version", "revision_type", "revised_at", "reason"}
    for field_name in _IMMUTABLE_EVENT_FIELDS:
        if field_name not in revision_values:
            continue
        supplied = revision_values[field_name]
        if field_name == "event_id":
            continue
        if field_name == "event_schema_version" and supplied != SOLANA_EVENT_SCHEMA_VERSION:
            raise ValueError("status revision cannot change event_schema_version")
        if _canonical_field_value(normalized, field_name) != supplied:
            raise ValueError(f"status revision cannot change immutable field: {field_name}")

    unknown_fields = (
        set(revision_values) - set(_STATUS_FIELDS) - set(allowed_revision_metadata) - set(_IMMUTABLE_EVENT_FIELDS)
    )
    if unknown_fields:
        names = ", ".join(sorted(unknown_fields))
        raise ValueError(f"status revision contains unsupported fields: {names}")

    next_finality = finality_status
    next_reorg = reorg_status
    if "finality_status" in revision_values:
        if next_finality is not None and next_finality != revision_values["finality_status"]:
            raise ValueError("conflicting finality_status values in revision")
        next_finality = revision_values["finality_status"]
    if "reorg_status" in revision_values:
        if next_reorg is not None and next_reorg != revision_values["reorg_status"]:
            raise ValueError("conflicting reorg_status values in revision")
        next_reorg = revision_values["reorg_status"]

    if next_finality is None:
        next_finality = normalized.finality_status
    if next_reorg is None:
        next_reorg = normalized.reorg_status
    return replace(
        normalized,
        finality_status=next_finality,
        reorg_status=next_reorg,
    )


revise_event_status = append_status_revision


__all__ = [
    "FINALITY_STATUSES",
    "REORG_STATUSES",
    "SOLANA_EVENT_SCHEMA_VERSION",
    "SOLANA_EVENT_VERSION",
    "DecoderStatus",
    "EventType",
    "FinalityStatus",
    "ReorgStatus",
    "SolanaEventStatusRevision",
    "SolanaFinalityStatus",
    "SolanaReorgStatus",
    "SolanaSellEvent",
    "append_status_revision",
    "build_event_id",
    "compute_event_id",
    "deterministic_event_id",
    "event_identity_material",
    "is_monitor_eligible",
    "make_status_revision",
    "monitor_eligible",
    "revise_event_status",
    "validate_solana_sell_event",
]
