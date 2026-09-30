"""Versioned, read-only schema for normalized EVM sell observations.

The contract is deliberately independent from an RPC client, an indexer, a
price source, a wallet resolver, and a lake writer.  It records the evidence
needed by a later consumer while keeping token and quote amounts in integer
base units.
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

EVM_EVENT_SCHEMA_VERSION = "evm-event.v1"
EVM_EVENT_VERSION = EVM_EVENT_SCHEMA_VERSION
SUPPORTED_EVM_CHAINS: Final = frozenset({"ethereum", "bsc", "base", "arbitrum"})


class EventType(StrEnum):
    """Event types accepted by the normalized EVM sell contract."""

    SELL = "sell"


class DecoderStatus(StrEnum):
    """Evidence status supplied by the explicit decoder registry."""

    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    UNKNOWN = "unknown"


class FinalityStatus(StrEnum):
    """EVM block finality observed by the outer collector."""

    OBSERVED = "observed"
    SAFE = "safe"
    FINALIZED = "finalized"
    UNKNOWN = "unknown"


class ReorgStatus(StrEnum):
    """Whether the block containing the event is still reorg-sensitive."""

    PENDING = "pending"
    CANONICAL = "canonical"
    ORPHANED = "orphaned"
    UNKNOWN = "unknown"


# Explicit names are useful to callers importing both Solana and EVM
# contracts in one module.  The short enum names remain available for
# symmetry with the Solana schema.
EVMEventType = EventType
EVMDecoderStatus = DecoderStatus
EVMFinalityStatus = FinalityStatus
EVMReorgStatus = ReorgStatus

FINALITY_STATUSES: Final = frozenset(item.value for item in FinalityStatus)
REORG_STATUSES: Final = frozenset(item.value for item in ReorgStatus)

_HEX_ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")
_HEX_32_BYTES = re.compile(r"^0x[0-9a-fA-F]{64}$")
_DECIMAL_INTEGER = re.compile(r"^[0-9]+$")
_HEX_INTEGER = re.compile(r"^0x[0-9a-fA-F]+$")

_IDENTITY_FIELDS: Final = (
    "chain",
    "protocol",
    "contract_address",
    "event_topic",
    "block_hash",
    "transaction_hash",
    "log_index",
    "event_index",
)
_STATUS_FIELDS: Final = ("finality_status", "reorg_status")
_IMMUTABLE_EVENT_FIELDS: Final = (
    "event_id",
    "event_schema_version",
    "chain",
    "protocol",
    "contract_address",
    "event_topic",
    "event_type",
    "transaction_hash",
    "block_hash",
    "block_number",
    "log_index",
    "event_index",
    "token_address",
    "pool_address",
    "seller_wallet",
    "token_amount_raw",
    "quote_amount_raw",
    "quote_asset",
    "observed_at",
    "source",
    "decoder_version",
    "decoder_status",
    "quote_value_usd",
    "finality_reference",
)
_REVISION_METADATA: Final = {
    "event_id",
    "event_schema_version",
    "revision_type",
    "revised_at",
    "reason",
}


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


def _chain(value: Any) -> str:
    result = _text(value, "chain", lower=True, identity=True)
    if result not in SUPPORTED_EVM_CHAINS:
        allowed = ", ".join(sorted(SUPPORTED_EVM_CHAINS))
        raise ValueError(f"chain must be one of: {allowed}")
    return result


def _protocol(value: Any) -> str:
    return _text(value, "protocol", lower=True, identity=True)


def _address(value: Any, field_name: str) -> str:
    result = _text(value, field_name, lower=True, identity=True)
    if _HEX_ADDRESS.fullmatch(result) is None:
        raise ValueError(f"{field_name} must be a 20-byte EVM address")
    return result


def _hash_or_topic(value: Any, field_name: str) -> str:
    result = _text(value, field_name, lower=True, identity=True)
    if _HEX_32_BYTES.fullmatch(result) is None:
        raise ValueError(f"{field_name} must be a 32-byte hex value")
    return result


def _non_negative_int(value: Any, field_name: str, *, allow_hex: bool = False) -> int:
    """Normalize an integer without ever converting through ``float``."""

    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str):
        candidate = value.strip()
        if _DECIMAL_INTEGER.fullmatch(candidate):
            result = int(candidate, 10)
        elif allow_hex and _HEX_INTEGER.fullmatch(candidate):
            result = int(candidate, 16)
        else:
            raise ValueError(f"{field_name} must be an integer")
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


def _optional_text(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return _text(value, field_name)


def _quote_asset(value: Any) -> str:
    """Normalize an address quote asset while retaining native symbols."""

    result = _text(value, "quote_asset")
    if result.lower().startswith("0x"):
        return _address(result.lower(), "quote_asset")
    if "|" in result:
        raise ValueError("quote_asset must not contain '|'")
    return result


def event_identity_material(
    chain: str,
    protocol: str,
    contract_address: str,
    event_topic: str,
    block_hash: str,
    transaction_hash: str,
    log_index: int,
    event_index: int,
) -> str:
    """Return the canonical identity input before SHA-256 hashing."""

    components = (
        _chain(chain),
        _protocol(protocol),
        _address(contract_address, "contract_address"),
        _hash_or_topic(event_topic, "event_topic"),
        _hash_or_topic(block_hash, "block_hash"),
        _hash_or_topic(transaction_hash, "transaction_hash"),
        str(_non_negative_int(log_index, "log_index", allow_hex=True)),
        str(_non_negative_int(event_index, "event_index", allow_hex=True)),
    )
    return "|".join(components)


def compute_event_id(
    chain: str,
    protocol: str,
    contract_address: str,
    event_topic: str,
    block_hash: str,
    transaction_hash: str,
    log_index: int,
    event_index: int,
) -> str:
    """Compute the stable, fork-safe SHA-256 identity for one sell event."""

    material = event_identity_material(
        chain,
        protocol,
        contract_address,
        event_topic,
        block_hash,
        transaction_hash,
        log_index,
        event_index,
    )
    return sha256(material.encode("utf-8")).hexdigest()


deterministic_event_id = compute_event_id
build_event_id = compute_event_id


@dataclass(frozen=True, slots=True)
class EVMSellEvent:
    """One validated ``evm-event.v1`` normalized sell event."""

    event_id: str
    event_schema_version: str
    chain: str
    protocol: str
    contract_address: str
    event_topic: str
    event_type: EventType | str
    transaction_hash: str
    block_hash: str
    block_number: int
    log_index: int
    event_index: int
    token_address: str
    pool_address: str
    seller_wallet: str
    token_amount_raw: int
    quote_amount_raw: int
    quote_asset: str
    observed_at: datetime
    source: str
    decoder_version: str
    decoder_status: DecoderStatus | str
    finality_status: FinalityStatus | str
    reorg_status: ReorgStatus | str
    quote_value_usd: float | None = None
    finality_reference: str | None = None

    def __post_init__(self) -> None:
        event_id = _text(self.event_id, "event_id", lower=True)
        version = _text(self.event_schema_version, "event_schema_version")
        if version != EVM_EVENT_SCHEMA_VERSION:
            raise ValueError(f"event_schema_version must be {EVM_EVENT_SCHEMA_VERSION}")

        chain = _chain(self.chain)
        protocol = _protocol(self.protocol)
        contract_address = _address(self.contract_address, "contract_address")
        event_topic = _hash_or_topic(self.event_topic, "event_topic")
        transaction_hash = _hash_or_topic(self.transaction_hash, "transaction_hash")
        block_hash = _hash_or_topic(self.block_hash, "block_hash")
        block_number = _non_negative_int(self.block_number, "block_number", allow_hex=True)
        log_index = _non_negative_int(self.log_index, "log_index", allow_hex=True)
        event_index = _non_negative_int(self.event_index, "event_index", allow_hex=True)
        expected_id = compute_event_id(
            chain,
            protocol,
            contract_address,
            event_topic,
            block_hash,
            transaction_hash,
            log_index,
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
        object.__setattr__(self, "contract_address", contract_address)
        object.__setattr__(self, "event_topic", event_topic)
        object.__setattr__(self, "event_type", event_type)
        object.__setattr__(self, "transaction_hash", transaction_hash)
        object.__setattr__(self, "block_hash", block_hash)
        object.__setattr__(self, "block_number", block_number)
        object.__setattr__(self, "log_index", log_index)
        object.__setattr__(self, "event_index", event_index)
        object.__setattr__(self, "token_address", _address(self.token_address, "token_address"))
        object.__setattr__(self, "pool_address", _address(self.pool_address, "pool_address"))
        object.__setattr__(self, "seller_wallet", _address(self.seller_wallet, "seller_wallet"))
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
        object.__setattr__(self, "quote_asset", _quote_asset(self.quote_asset))
        object.__setattr__(self, "observed_at", _datetime(self.observed_at, "observed_at"))
        object.__setattr__(self, "source", _text(self.source, "source"))
        object.__setattr__(self, "decoder_version", _text(self.decoder_version, "decoder_version"))
        object.__setattr__(self, "decoder_status", decoder_status)
        object.__setattr__(self, "finality_status", finality_status)
        object.__setattr__(self, "reorg_status", reorg_status)
        object.__setattr__(self, "quote_value_usd", _optional_usd(self.quote_value_usd))
        object.__setattr__(
            self,
            "finality_reference",
            _optional_text(self.finality_reference, "finality_reference"),
        )

    @property
    def monitor_eligible(self) -> bool:
        """Whether this event may enter the cluster-sell monitor."""

        return is_monitor_eligible(self)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation of the normalized event."""

        result: dict[str, Any] = {
            "event_id": self.event_id,
            "event_schema_version": self.event_schema_version,
            "chain": self.chain,
            "protocol": self.protocol,
            "contract_address": self.contract_address,
            "event_topic": self.event_topic,
            "event_type": self.event_type.value,
            "transaction_hash": self.transaction_hash,
            "block_hash": self.block_hash,
            "block_number": self.block_number,
            "log_index": self.log_index,
            "event_index": self.event_index,
            "token_address": self.token_address,
            "pool_address": self.pool_address,
            "seller_wallet": self.seller_wallet,
            "token_amount_raw": self.token_amount_raw,
            "quote_amount_raw": self.quote_amount_raw,
            "quote_asset": self.quote_asset,
            "observed_at": self.observed_at.isoformat(),
            "source": self.source,
            "decoder_version": self.decoder_version,
            "decoder_status": self.decoder_status.value,
            "finality_status": self.finality_status.value,
            "reorg_status": self.reorg_status.value,
        }
        if self.quote_value_usd is not None:
            result["quote_value_usd"] = self.quote_value_usd
        if self.finality_reference is not None:
            result["finality_reference"] = self.finality_reference
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> EVMSellEvent:
        if not isinstance(value, Mapping):
            raise ValueError("an EVM sell event must be a mapping")
        return cls(**dict(value))


EVMEvent = EVMSellEvent


def validate_evm_sell_event(value: EVMSellEvent | Mapping[str, Any]) -> EVMSellEvent:
    """Validate an existing event or construct one from a mapping."""

    if isinstance(value, EVMSellEvent):
        return value
    return EVMSellEvent.from_dict(value)


def is_monitor_eligible(value: EVMSellEvent | Mapping[str, Any]) -> bool:
    """Return true only for verified, finalized, canonical events."""

    event = validate_evm_sell_event(value)
    return (
        event.decoder_status is DecoderStatus.VERIFIED
        and event.finality_status is FinalityStatus.FINALIZED
        and event.reorg_status is ReorgStatus.CANONICAL
    )


monitor_eligible = is_monitor_eligible


@dataclass(frozen=True, slots=True)
class EVMEventStatusRevision:
    """An append-only status record referring to one stable event identity."""

    event_id: str
    finality_status: FinalityStatus | str
    reorg_status: ReorgStatus | str
    revised_at: datetime
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_id", _text(self.event_id, "event_id", lower=True))
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
            "event_schema_version": EVM_EVENT_SCHEMA_VERSION,
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
    event: EVMSellEvent | Mapping[str, Any],
    *,
    finality_status: FinalityStatus | str,
    reorg_status: ReorgStatus | str,
    revised_at: datetime,
    reason: str | None = None,
) -> EVMEventStatusRevision:
    """Create a status-only append record for ``event``."""

    normalized = validate_evm_sell_event(event)
    return EVMEventStatusRevision(
        event_id=normalized.event_id,
        finality_status=finality_status,
        reorg_status=reorg_status,
        revised_at=revised_at,
        reason=reason,
    )


def _canonical_field_value(event: EVMSellEvent, field_name: str) -> Any:
    value = getattr(event, field_name)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def append_status_revision(
    event: EVMSellEvent | Mapping[str, Any],
    revision: EVMEventStatusRevision | Mapping[str, Any] | None = None,
    *,
    finality_status: FinalityStatus | str | None = None,
    reorg_status: ReorgStatus | str | None = None,
    **changes: Any,
) -> EVMSellEvent:
    """Return a new status view while preserving identity and event evidence."""

    normalized = validate_evm_sell_event(event)
    revision_values: dict[str, Any] = {}
    if revision is not None:
        if isinstance(revision, EVMEventStatusRevision):
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

    for field_name in _IMMUTABLE_EVENT_FIELDS:
        if field_name not in revision_values or field_name == "event_id":
            continue
        supplied = revision_values[field_name]
        if field_name == "event_schema_version" and supplied != EVM_EVENT_SCHEMA_VERSION:
            raise ValueError("status revision cannot change event_schema_version")
        if _canonical_field_value(normalized, field_name) != supplied:
            raise ValueError(f"status revision cannot change immutable field: {field_name}")

    unknown_fields = set(revision_values) - set(_STATUS_FIELDS) - _REVISION_METADATA - set(_IMMUTABLE_EVENT_FIELDS)
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
    "EVM_EVENT_SCHEMA_VERSION",
    "EVM_EVENT_VERSION",
    "FINALITY_STATUSES",
    "REORG_STATUSES",
    "SUPPORTED_EVM_CHAINS",
    "DecoderStatus",
    "EVMDecoderStatus",
    "EVMEvent",
    "EVMEventStatusRevision",
    "EVMEventType",
    "EVMFinalityStatus",
    "EVMReorgStatus",
    "EVMSellEvent",
    "EventType",
    "FinalityStatus",
    "ReorgStatus",
    "append_status_revision",
    "build_event_id",
    "compute_event_id",
    "deterministic_event_id",
    "event_identity_material",
    "is_monitor_eligible",
    "make_status_revision",
    "monitor_eligible",
    "revise_event_status",
    "validate_evm_sell_event",
]
