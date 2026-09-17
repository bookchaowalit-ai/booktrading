"""Validated models for selective, paper-only alpha research.

The models deliberately describe observations and decisions, not orders.  A
``TRADE_PAPER`` decision is a research action and carries no broker or wallet
credentials.  Source payloads belong in the lake landing/Bronze boundary;
these records keep bounded evidence references and normalized values only.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from urllib.parse import urlsplit

_IDENTIFIER_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_SENSITIVE_KEY_RE = re.compile(
    r"(?:api[_ -]?key|access[_ -]?token|private[_ -]?key|seed|mnemonic|password|cookie|secret)",
    re.IGNORECASE,
)
_SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?:api[_ -]?key|access[_ -]?token|private[_ -]?key|seed(?: phrase)?|mnemonic|password|cookie|secret)"
    r"\s*[:=]\s*\S+",
    re.IGNORECASE,
)
_MAX_TEXT_LENGTH = 1024


class AlphaAction(StrEnum):
    """Decision returned by the selective alpha gate."""

    WAIT = "WAIT"
    WATCH = "WATCH"
    TRADE_PAPER = "TRADE_PAPER"


class ThesisStatus(StrEnum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    INVALIDATED = "invalidated"
    RESOLVED = "resolved"
    EXPIRED = "expired"


class AlphaOutcome(StrEnum):
    PENDING = "pending"
    NOT_TAKEN = "not_taken"
    WIN = "win"
    LOSS = "loss"
    VOID = "void"


def _text(value: str, field_name: str, *, max_length: int = _MAX_TEXT_LENGTH) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} cannot be empty")
    if len(normalized) > max_length:
        raise ValueError(f"{field_name} is too long")
    return normalized


def _identifier(value: str, field_name: str) -> str:
    normalized = _text(value, field_name, max_length=64).lower()
    if not _IDENTIFIER_RE.fullmatch(normalized):
        raise ValueError(f"{field_name} must contain lowercase letters, numbers, '-' or '_'")
    return normalized


def _finite(value: float, field_name: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric") from exc
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite")
    if minimum is not None and number < minimum:
        raise ValueError(f"{field_name} cannot be less than {minimum}")
    return number


def _probability(value: float | None, field_name: str) -> float | None:
    if value is None:
        return None
    number = _finite(value, field_name, minimum=0.0)
    if number > 1.0:
        raise ValueError(f"{field_name} must be between 0 and 1")
    return number


def _confidence(value: float, field_name: str = "confidence") -> float:
    number = _probability(value, field_name)
    assert number is not None
    return number


def _timestamp(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)


def _safe_url(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    normalized = _text(value, field_name, max_length=2048)
    parsed = urlsplit(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{field_name} must be an absolute HTTP(S) URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError(f"{field_name} cannot contain embedded credentials")
    if _SENSITIVE_ASSIGNMENT_RE.search(normalized):
        raise ValueError(f"{field_name} cannot contain credential-like query values")
    return normalized


def _safe_object_key(value: str, field_name: str = "object_key") -> str:
    """Validate a relative lake object key before a caller opens it."""

    normalized = _text(value, field_name, max_length=1024)
    if (
        normalized.startswith(("/", "\\"))
        or "\\" in normalized
        or re.match(r"^[A-Za-z]:", normalized)
        or any(part in {"", ".", ".."} for part in normalized.split("/"))
    ):
        raise ValueError(f"{field_name} must be a normalized relative object key")
    return normalized


def _json_metadata(value: Mapping[str, Any], field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping")
    metadata = dict(value)
    if any(not isinstance(key, str) for key in metadata):
        raise ValueError(f"{field_name} keys must be strings")
    if any(_SENSITIVE_KEY_RE.search(key) for key in metadata):
        raise ValueError(f"{field_name} cannot contain credential or secret fields")
    try:
        serialized = json.dumps(metadata, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must contain JSON-compatible values") from exc
    if _SENSITIVE_ASSIGNMENT_RE.search(serialized):
        raise ValueError(f"{field_name} cannot contain credential-like values")
    return metadata


def _iso(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat()


def _round(value: float | None) -> float | None:
    return None if value is None else round(float(value), 10)


def _codes(values: tuple[str, ...] | list[str], field_name: str) -> tuple[str, ...]:
    normalized = tuple(_identifier(value, field_name) for value in values)
    if not normalized:
        raise ValueError(f"{field_name} cannot be empty")
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{field_name} cannot contain duplicates")
    return normalized


@dataclass(frozen=True, slots=True)
class AlphaEvidence:
    """A short, attributable evidence reference; never a raw provider payload."""

    evidence_id: str
    source: str
    observed_at: datetime
    summary: str
    source_url: str | None = None
    raw_sha256: str | None = None
    confidence: float = 0.0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_id", _identifier(self.evidence_id, "evidence_id"))
        object.__setattr__(self, "source", _identifier(self.source, "source"))
        object.__setattr__(self, "observed_at", _timestamp(self.observed_at, "observed_at"))
        object.__setattr__(self, "summary", _text(self.summary, "summary"))
        object.__setattr__(self, "source_url", _safe_url(self.source_url, "source_url"))
        if self.raw_sha256 is not None:
            if not isinstance(self.raw_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", self.raw_sha256.lower()):
                raise ValueError("raw_sha256 must be a lowercase hexadecimal SHA-256 checksum")
            object.__setattr__(self, "raw_sha256", self.raw_sha256.lower())
        object.__setattr__(self, "confidence", _confidence(self.confidence))
        object.__setattr__(self, "metadata", _json_metadata(self.metadata, "metadata"))

    def as_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "source": self.source,
            "observed_at": _iso(self.observed_at),
            "summary": self.summary,
            "source_url": self.source_url,
            "raw_sha256": self.raw_sha256,
            "confidence": _round(self.confidence),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class SettlementProof:
    """Bounded evidence reference required by the durable settlement path."""

    evidence_id: str
    source: str
    object_key: str
    raw_sha256: str
    source_url: str
    observed_at: datetime
    summary: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_id", _identifier(self.evidence_id, "evidence_id"))
        object.__setattr__(self, "source", _identifier(self.source, "source"))
        object.__setattr__(self, "object_key", _safe_object_key(self.object_key))
        if not isinstance(self.raw_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", self.raw_sha256.lower()):
            raise ValueError("raw_sha256 must be a lowercase hexadecimal SHA-256 checksum")
        object.__setattr__(self, "raw_sha256", self.raw_sha256.lower())
        source_url = _safe_url(self.source_url, "source_url")
        if source_url is None:
            raise ValueError("source_url is required")
        object.__setattr__(self, "source_url", source_url)
        object.__setattr__(self, "observed_at", _timestamp(self.observed_at, "observed_at"))
        object.__setattr__(self, "summary", _text(self.summary, "summary"))
        object.__setattr__(self, "metadata", _json_metadata(self.metadata, "metadata"))

    def as_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "source": self.source,
            "object_key": self.object_key,
            "raw_sha256": self.raw_sha256,
            "source_url": self.source_url,
            "observed_at": _iso(self.observed_at),
            "summary": self.summary,
            "metadata": dict(self.metadata),
        }


def _settlement_proofs(value: tuple[SettlementProof, ...] | list[SettlementProof]) -> tuple[SettlementProof, ...]:
    if isinstance(value, (str, bytes)):
        raise ValueError("settlement evidence must be a sequence of SettlementProof records")
    try:
        proofs = tuple(value)
    except TypeError as exc:
        raise ValueError("settlement evidence must be a sequence of SettlementProof records") from exc
    if any(not isinstance(item, SettlementProof) for item in proofs):
        raise ValueError("settlement evidence must contain SettlementProof records")
    if len({item.evidence_id for item in proofs}) != len(proofs):
        raise ValueError("settlement evidence IDs must be unique")
    return proofs


@dataclass(frozen=True, slots=True)
class AlphaThesis:
    """A falsifiable hypothesis with explicit entry, exit, and risk bounds."""

    thesis_id: str
    market_group: str
    platform_id: str
    instrument_id: str
    direction: str
    hypothesis: str
    fair_value: float | None
    max_entry_price: float | None
    target_exit_price: float | None
    invalidation_price: float | None
    max_loss: float
    capital_at_risk: float
    confidence: float
    evidence: tuple[AlphaEvidence, ...]
    created_at: datetime
    strategy_version: str
    expected_edge: float | None = None
    target_units: float = 1.0
    status: ThesisStatus | str = ThesisStatus.CANDIDATE
    expires_at: datetime | None = None
    tags: tuple[str, ...] = ()
    notes: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "thesis_id", _identifier(self.thesis_id, "thesis_id"))
        object.__setattr__(self, "market_group", _identifier(self.market_group, "market_group"))
        object.__setattr__(self, "platform_id", _identifier(self.platform_id, "platform_id"))
        object.__setattr__(self, "instrument_id", _identifier(self.instrument_id, "instrument_id"))
        direction = _identifier(self.direction, "direction")
        if direction not in {"buy_yes", "buy_no"}:
            raise ValueError("direction must be buy_yes or buy_no")
        object.__setattr__(self, "direction", direction)
        object.__setattr__(self, "hypothesis", _text(self.hypothesis, "hypothesis"))
        object.__setattr__(self, "fair_value", _probability(self.fair_value, "fair_value"))
        object.__setattr__(self, "max_entry_price", _probability(self.max_entry_price, "max_entry_price"))
        object.__setattr__(self, "target_exit_price", _probability(self.target_exit_price, "target_exit_price"))
        object.__setattr__(self, "invalidation_price", _probability(self.invalidation_price, "invalidation_price"))
        object.__setattr__(self, "expected_edge", _probability(self.expected_edge, "expected_edge"))
        object.__setattr__(self, "max_loss", _finite(self.max_loss, "max_loss", minimum=0.0))
        object.__setattr__(self, "capital_at_risk", _finite(self.capital_at_risk, "capital_at_risk", minimum=0.0))
        object.__setattr__(self, "target_units", _finite(self.target_units, "target_units", minimum=0.0))
        if self.max_loss <= 0.0:
            raise ValueError("max_loss must be positive")
        if self.capital_at_risk <= 0.0:
            raise ValueError("capital_at_risk must be positive")
        if self.max_loss > self.capital_at_risk:
            raise ValueError("max_loss cannot exceed capital_at_risk")
        if self.target_units <= 0.0:
            raise ValueError("target_units must be positive")
        object.__setattr__(self, "confidence", _confidence(self.confidence))
        if not self.evidence:
            raise ValueError("evidence cannot be empty")
        if isinstance(self.evidence, (str, bytes)):
            raise ValueError("evidence must be a sequence of AlphaEvidence records")
        evidence = tuple(self.evidence)
        if any(not isinstance(item, AlphaEvidence) for item in evidence):
            raise ValueError("evidence must contain AlphaEvidence records")
        if len({item.evidence_id for item in evidence}) != len(evidence):
            raise ValueError("evidence IDs must be unique within a thesis")
        object.__setattr__(self, "evidence", evidence)
        object.__setattr__(self, "created_at", _timestamp(self.created_at, "created_at"))
        object.__setattr__(self, "strategy_version", _identifier(self.strategy_version, "strategy_version"))
        object.__setattr__(self, "status", ThesisStatus(self.status))
        if self.expires_at is not None:
            expires_at = _timestamp(self.expires_at, "expires_at")
            if expires_at <= self.created_at:
                raise ValueError("expires_at must be after created_at")
            object.__setattr__(self, "expires_at", expires_at)
        if isinstance(self.tags, (str, bytes)):
            raise ValueError("tags must be a sequence of identifiers")
        tags = tuple(_identifier(tag, "tags") for tag in self.tags)
        if len(set(tags)) != len(tags):
            raise ValueError("tags cannot contain duplicates")
        object.__setattr__(self, "tags", tags)
        object.__setattr__(self, "notes", _text(self.notes, "notes") if self.notes else "")
        object.__setattr__(self, "metadata", _json_metadata(self.metadata, "metadata"))

    def as_dict(self) -> dict[str, Any]:
        return {
            "thesis_id": self.thesis_id,
            "market_group": self.market_group,
            "platform_id": self.platform_id,
            "instrument_id": self.instrument_id,
            "direction": self.direction,
            "hypothesis": self.hypothesis,
            "fair_value": _round(self.fair_value),
            "max_entry_price": _round(self.max_entry_price),
            "target_exit_price": _round(self.target_exit_price),
            "invalidation_price": _round(self.invalidation_price),
            "max_loss": _round(self.max_loss),
            "capital_at_risk": _round(self.capital_at_risk),
            "confidence": _round(self.confidence),
            "evidence": [item.as_dict() for item in self.evidence],
            "created_at": _iso(self.created_at),
            "strategy_version": self.strategy_version,
            "expected_edge": _round(self.expected_edge),
            "target_units": _round(self.target_units),
            "status": self.status.value,
            "expires_at": _iso(self.expires_at),
            "tags": list(self.tags),
            "notes": self.notes,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class AlphaObservation:
    """One point-in-time quote and fillability observation."""

    observation_id: str
    thesis_id: str
    platform_id: str
    instrument_id: str
    observed_at: datetime
    price: float
    cost_per_unit: float | None = None
    available_size: float | None = None
    quote_age_seconds: float | None = None
    market_status: str = "active"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "observation_id", _identifier(self.observation_id, "observation_id"))
        object.__setattr__(self, "thesis_id", _identifier(self.thesis_id, "thesis_id"))
        object.__setattr__(self, "platform_id", _identifier(self.platform_id, "platform_id"))
        object.__setattr__(self, "instrument_id", _identifier(self.instrument_id, "instrument_id"))
        object.__setattr__(self, "observed_at", _timestamp(self.observed_at, "observed_at"))
        object.__setattr__(self, "price", _probability(self.price, "price"))
        assert self.price is not None
        if self.cost_per_unit is not None:
            object.__setattr__(self, "cost_per_unit", _finite(self.cost_per_unit, "cost_per_unit", minimum=0.0))
        if self.available_size is not None:
            object.__setattr__(self, "available_size", _finite(self.available_size, "available_size", minimum=0.0))
        if self.quote_age_seconds is not None:
            object.__setattr__(
                self,
                "quote_age_seconds",
                _finite(self.quote_age_seconds, "quote_age_seconds", minimum=0.0),
            )
        object.__setattr__(self, "market_status", _identifier(self.market_status, "market_status"))
        object.__setattr__(self, "metadata", _json_metadata(self.metadata, "metadata"))

    def as_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "thesis_id": self.thesis_id,
            "platform_id": self.platform_id,
            "instrument_id": self.instrument_id,
            "observed_at": _iso(self.observed_at),
            "price": _round(self.price),
            "cost_per_unit": _round(self.cost_per_unit),
            "available_size": _round(self.available_size),
            "quote_age_seconds": _round(self.quote_age_seconds),
            "market_status": self.market_status,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class RiskBudget:
    """Paper-only bankroll and exposure constraints."""

    starting_capital: float
    max_total_risk: float
    max_trade_risk: float
    max_open_positions: int = 3
    min_confidence: float = 0.65
    min_expected_edge: float = 0.05
    max_quote_age_seconds: float = 30.0
    require_available_size: bool = True
    paper_only: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "starting_capital", _finite(self.starting_capital, "starting_capital", minimum=0.0))
        object.__setattr__(self, "max_total_risk", _finite(self.max_total_risk, "max_total_risk", minimum=0.0))
        object.__setattr__(self, "max_trade_risk", _finite(self.max_trade_risk, "max_trade_risk", minimum=0.0))
        if self.starting_capital <= 0.0 or self.max_total_risk <= 0.0 or self.max_trade_risk <= 0.0:
            raise ValueError("capital and risk limits must be positive")
        if self.max_total_risk > self.starting_capital:
            raise ValueError("max_total_risk cannot exceed starting_capital")
        if self.max_trade_risk > self.max_total_risk:
            raise ValueError("max_trade_risk cannot exceed max_total_risk")
        if not isinstance(self.max_open_positions, int) or isinstance(self.max_open_positions, bool):
            raise ValueError("max_open_positions must be an integer")
        if self.max_open_positions <= 0:
            raise ValueError("max_open_positions must be positive")
        object.__setattr__(self, "min_confidence", _confidence(self.min_confidence, "min_confidence"))
        object.__setattr__(self, "min_expected_edge", _confidence(self.min_expected_edge, "min_expected_edge"))
        object.__setattr__(
            self,
            "max_quote_age_seconds",
            _finite(self.max_quote_age_seconds, "max_quote_age_seconds", minimum=0.0),
        )
        if not self.paper_only:
            raise ValueError("RiskBudget is paper-only; live execution is not supported")

    def as_dict(self) -> dict[str, Any]:
        return {
            "starting_capital": _round(self.starting_capital),
            "max_total_risk": _round(self.max_total_risk),
            "max_trade_risk": _round(self.max_trade_risk),
            "max_open_positions": self.max_open_positions,
            "min_confidence": _round(self.min_confidence),
            "min_expected_edge": _round(self.min_expected_edge),
            "max_quote_age_seconds": _round(self.max_quote_age_seconds),
            "require_available_size": self.require_available_size,
            "paper_only": self.paper_only,
        }


@dataclass(frozen=True, slots=True)
class AlphaDecision:
    """The immutable result of evaluating one thesis against one observation."""

    decision_id: str
    thesis_id: str
    platform_id: str
    instrument_id: str
    evaluated_at: datetime
    action: AlphaAction | str
    reason_codes: tuple[str, ...]
    observed_price: float
    expected_edge: float | None
    risk_amount: float
    confidence: float
    strategy_version: str
    execution_enabled: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", _identifier(self.decision_id, "decision_id"))
        object.__setattr__(self, "thesis_id", _identifier(self.thesis_id, "thesis_id"))
        object.__setattr__(self, "platform_id", _identifier(self.platform_id, "platform_id"))
        object.__setattr__(self, "instrument_id", _identifier(self.instrument_id, "instrument_id"))
        object.__setattr__(self, "evaluated_at", _timestamp(self.evaluated_at, "evaluated_at"))
        object.__setattr__(self, "action", AlphaAction(self.action))
        object.__setattr__(self, "reason_codes", _codes(self.reason_codes, "reason_codes"))
        object.__setattr__(self, "observed_price", _probability(self.observed_price, "observed_price"))
        object.__setattr__(
            self, "expected_edge", None if self.expected_edge is None else _finite(self.expected_edge, "expected_edge")
        )
        object.__setattr__(self, "risk_amount", _finite(self.risk_amount, "risk_amount", minimum=0.0))
        object.__setattr__(self, "confidence", _confidence(self.confidence))
        object.__setattr__(self, "strategy_version", _identifier(self.strategy_version, "strategy_version"))
        if self.execution_enabled:
            raise ValueError("alpha decisions cannot enable execution")
        object.__setattr__(self, "metadata", _json_metadata(self.metadata, "metadata"))

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "thesis_id": self.thesis_id,
            "platform_id": self.platform_id,
            "instrument_id": self.instrument_id,
            "evaluated_at": _iso(self.evaluated_at),
            "action": self.action.value,
            "reason_codes": list(self.reason_codes),
            "observed_price": _round(self.observed_price),
            "expected_edge": _round(self.expected_edge),
            "risk_amount": _round(self.risk_amount),
            "confidence": _round(self.confidence),
            "strategy_version": self.strategy_version,
            "execution_enabled": False,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class AlphaSettlement:
    """Outcome evidence used only after a paper decision was made."""

    outcome: AlphaOutcome | str
    realized_pnl: float
    settled_at: datetime
    note: str = ""
    evidence: tuple[SettlementProof, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "outcome", AlphaOutcome(self.outcome))
        if self.outcome in {AlphaOutcome.PENDING, AlphaOutcome.NOT_TAKEN}:
            raise ValueError("settlement outcome must be win, loss, or void")
        object.__setattr__(self, "realized_pnl", _finite(self.realized_pnl, "realized_pnl"))
        object.__setattr__(self, "settled_at", _timestamp(self.settled_at, "settled_at"))
        object.__setattr__(self, "note", _text(self.note, "note") if self.note else "")
        object.__setattr__(self, "evidence", _settlement_proofs(self.evidence))

    def as_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "realized_pnl": _round(self.realized_pnl),
            "settled_at": _iso(self.settled_at),
            "note": self.note,
            "evidence": [item.as_dict() for item in self.evidence],
        }


@dataclass(frozen=True, slots=True)
class DecisionRecord:
    """Decision journal row, including eventual paper outcome when known."""

    decision_id: str
    thesis_id: str
    platform_id: str
    instrument_id: str
    evaluated_at: datetime
    action: AlphaAction | str
    reason_codes: tuple[str, ...]
    observed_price: float
    expected_edge: float | None
    risk_amount: float
    confidence: float
    strategy_version: str
    outcome: AlphaOutcome | str
    realized_pnl: float | None = None
    settled_at: datetime | None = None
    note: str = ""
    settlement_evidence: tuple[SettlementProof, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", _identifier(self.decision_id, "decision_id"))
        object.__setattr__(self, "thesis_id", _identifier(self.thesis_id, "thesis_id"))
        object.__setattr__(self, "platform_id", _identifier(self.platform_id, "platform_id"))
        object.__setattr__(self, "instrument_id", _identifier(self.instrument_id, "instrument_id"))
        object.__setattr__(self, "evaluated_at", _timestamp(self.evaluated_at, "evaluated_at"))
        object.__setattr__(self, "action", AlphaAction(self.action))
        object.__setattr__(self, "reason_codes", _codes(self.reason_codes, "reason_codes"))
        object.__setattr__(self, "observed_price", _probability(self.observed_price, "observed_price"))
        object.__setattr__(
            self, "expected_edge", None if self.expected_edge is None else _finite(self.expected_edge, "expected_edge")
        )
        object.__setattr__(self, "risk_amount", _finite(self.risk_amount, "risk_amount", minimum=0.0))
        object.__setattr__(self, "confidence", _confidence(self.confidence))
        object.__setattr__(self, "strategy_version", _identifier(self.strategy_version, "strategy_version"))
        object.__setattr__(self, "outcome", AlphaOutcome(self.outcome))
        if self.realized_pnl is not None:
            object.__setattr__(self, "realized_pnl", _finite(self.realized_pnl, "realized_pnl"))
        if self.settled_at is not None:
            settled_at = _timestamp(self.settled_at, "settled_at")
            if settled_at < self.evaluated_at:
                raise ValueError("settled_at cannot be before evaluated_at")
            object.__setattr__(self, "settled_at", settled_at)
        if self.outcome in {AlphaOutcome.WIN, AlphaOutcome.LOSS, AlphaOutcome.VOID}:
            if self.realized_pnl is None or self.settled_at is None:
                raise ValueError("settled records require realized_pnl and settled_at")
        elif self.realized_pnl is not None or self.settled_at is not None:
            raise ValueError("unsettled records cannot contain settlement fields")
        object.__setattr__(self, "note", _text(self.note, "note") if self.note else "")
        proofs = _settlement_proofs(self.settlement_evidence)
        if self.outcome in {AlphaOutcome.PENDING, AlphaOutcome.NOT_TAKEN} and proofs:
            raise ValueError("unsettled records cannot contain settlement evidence")
        object.__setattr__(self, "settlement_evidence", proofs)

    @classmethod
    def from_decision(cls, decision: AlphaDecision) -> DecisionRecord:
        outcome = AlphaOutcome.PENDING if decision.action is AlphaAction.TRADE_PAPER else AlphaOutcome.NOT_TAKEN
        return cls(
            decision_id=decision.decision_id,
            thesis_id=decision.thesis_id,
            platform_id=decision.platform_id,
            instrument_id=decision.instrument_id,
            evaluated_at=decision.evaluated_at,
            action=decision.action,
            reason_codes=decision.reason_codes,
            observed_price=decision.observed_price,
            expected_edge=decision.expected_edge,
            risk_amount=decision.risk_amount,
            confidence=decision.confidence,
            strategy_version=decision.strategy_version,
            outcome=outcome,
        )

    @property
    def is_paper_trade(self) -> bool:
        return self.action is AlphaAction.TRADE_PAPER

    @property
    def is_settled(self) -> bool:
        return self.outcome in {AlphaOutcome.WIN, AlphaOutcome.LOSS, AlphaOutcome.VOID}

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "thesis_id": self.thesis_id,
            "platform_id": self.platform_id,
            "instrument_id": self.instrument_id,
            "evaluated_at": _iso(self.evaluated_at),
            "action": self.action.value,
            "reason_codes": list(self.reason_codes),
            "observed_price": _round(self.observed_price),
            "expected_edge": _round(self.expected_edge),
            "risk_amount": _round(self.risk_amount),
            "confidence": _round(self.confidence),
            "strategy_version": self.strategy_version,
            "outcome": self.outcome.value,
            "realized_pnl": _round(self.realized_pnl),
            "settled_at": _iso(self.settled_at),
            "note": self.note,
            "settlement_evidence": [item.as_dict() for item in self.settlement_evidence],
        }
