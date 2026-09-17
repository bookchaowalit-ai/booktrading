"""Provider-neutral portfolio and reward models.

These models describe paper activity and reward accounting only.  They do not
contain order credentials, wallet secrets, or a switch that can place a live
order.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from urllib.parse import urlsplit

_IDENTIFIER_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_CURRENCY_RE = re.compile(r"^[A-Z][A-Z0-9._-]{1,15}$")
_CREDENTIAL_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_ALIAS_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_SENSITIVE_KEY_RE = re.compile(
    r"(?:api[_ -]?key|access[_ -]?token|private[_ -]?key|seed|mnemonic|password|cookie|secret)",
    re.IGNORECASE,
)
_SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?:api[_ -]?key|access[_ -]?token|private[_ -]?key|seed(?: phrase)?|mnemonic|password|cookie|secret)"
    r"\s*[:=]\s*\S+",
    re.IGNORECASE,
)
_MAX_TEXT_LENGTH = 512


class CapabilityStatus(StrEnum):
    """Current delivery state of a platform integration."""

    PLANNED = "planned"
    BLOCKED = "blocked"
    READ_ONLY = "read_only"
    PAPER = "paper"
    TESTNET = "testnet"
    LIVE = "live"


class PlatformDomain(StrEnum):
    """High-level type of venue or reward source."""

    PREDICTION = "prediction"
    EXCHANGE = "exchange"
    REWARDS = "rewards"
    UNKNOWN = "unknown"


class PaperTradeStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class ActivityMode(StrEnum):
    """Execution lane represented by the portfolio models.

    This package intentionally accepts only the paper lane. Keeping the mode
    explicit prevents future live/testnet records from being silently mixed
    into paper P&L or the finance projection feed.
    """

    PAPER = "paper"
    TESTNET = "testnet"
    LIVE = "live"


class RewardKind(StrEnum):
    AIRDROP = "airdrop"
    POINTS = "points"
    REBATE = "rebate"
    QUEST = "quest"


class RewardStatus(StrEnum):
    CANDIDATE = "candidate"
    IN_PROGRESS = "in_progress"
    ELIGIBLE = "eligible"
    CLAIMED = "claimed"
    EXPIRED = "expired"
    REJECTED = "rejected"


def _text(value: str, field_name: str, *, max_length: int = _MAX_TEXT_LENGTH) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    value = value.strip()
    if not value:
        raise ValueError(f"{field_name} cannot be empty")
    if len(value) > max_length:
        raise ValueError(f"{field_name} is too long")
    return value


def _identifier(value: str, field_name: str) -> str:
    value = _text(value, field_name, max_length=64).lower()
    if not _IDENTIFIER_RE.fullmatch(value):
        raise ValueError(f"{field_name} must contain lowercase letters, numbers, '-' or '_'")
    return value


def _finite(value: float, field_name: str, *, minimum: float | None = None) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite")
    if minimum is not None and number < minimum:
        raise ValueError(f"{field_name} cannot be less than {minimum}")
    return number


def _timestamp(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)


def _safe_url(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    value = _text(value, field_name, max_length=2048)
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{field_name} must be an absolute HTTP(S) URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError(f"{field_name} cannot contain embedded credentials")
    if _SENSITIVE_ASSIGNMENT_RE.search(value):
        raise ValueError(f"{field_name} cannot contain credential-like query values")
    return value


def _json_metadata(value: Mapping[str, Any], field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping")
    metadata = dict(value)
    if any(not isinstance(key, str) for key in metadata):
        raise ValueError(f"{field_name} keys must be strings")
    if any(_SENSITIVE_KEY_RE.search(key) for key in metadata):
        raise ValueError(f"{field_name} cannot contain credential or secret fields")
    try:
        json.dumps(metadata, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must contain JSON-compatible values") from exc
    return metadata


def _iso(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat()


def _round(value: float) -> float:
    return round(float(value), 10)


@dataclass(frozen=True, slots=True)
class PlatformCapability:
    """A declarative capability record for one venue or source.

    ``execution_gate_passed`` is intentionally false by default.  A platform
    record is a registry description, not authorization to move money.
    """

    platform_id: str
    display_name: str
    domain: PlatformDomain | str
    status: CapabilityStatus | str
    market_data: bool = False
    paper_trading: bool = False
    testnet_execution: bool = False
    live_execution: bool = False
    balance_read: bool = False
    rewards_tracking: bool = False
    source_url: str | None = None
    required_credentials: tuple[str, ...] = ()
    notes: str = ""
    next_gate: str = ""
    execution_gate_passed: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "platform_id", _identifier(self.platform_id, "platform_id"))
        object.__setattr__(self, "display_name", _text(self.display_name, "display_name"))
        object.__setattr__(self, "domain", PlatformDomain(self.domain))
        object.__setattr__(self, "status", CapabilityStatus(self.status))
        object.__setattr__(self, "source_url", _safe_url(self.source_url, "source_url"))

        if isinstance(self.required_credentials, str):
            raise ValueError("required_credentials must contain credential names, not a string")
        credential_names = tuple(self.required_credentials)
        for name in credential_names:
            if not isinstance(name, str) or not _CREDENTIAL_NAME_RE.fullmatch(name):
                raise ValueError("required_credentials must contain environment-style names only")
        object.__setattr__(self, "required_credentials", credential_names)

        object.__setattr__(self, "notes", _text(self.notes, "notes") if self.notes else "")
        object.__setattr__(self, "next_gate", _text(self.next_gate, "next_gate") if self.next_gate else "")
        if self.execution_gate_passed and not self.live_execution:
            raise ValueError("execution_gate_passed requires live_execution")

    @property
    def is_paper_ready(self) -> bool:
        """Whether the declared adapter can feed a paper workflow."""

        return (
            self.market_data
            and self.paper_trading
            and self.status not in {CapabilityStatus.PLANNED, CapabilityStatus.BLOCKED}
        )

    @property
    def is_execution_enabled(self) -> bool:
        """Return the explicit live gate; registry entries never set it by default."""

        return self.execution_gate_passed and self.live_execution and self.status is CapabilityStatus.LIVE

    def as_dict(self) -> dict[str, Any]:
        return {
            "platform_id": self.platform_id,
            "display_name": self.display_name,
            "domain": self.domain.value,
            "status": self.status.value,
            "capabilities": {
                "market_data": self.market_data,
                "paper_trading": self.paper_trading,
                "testnet_execution": self.testnet_execution,
                "live_execution": self.live_execution,
                "balance_read": self.balance_read,
                "rewards_tracking": self.rewards_tracking,
            },
            "required_credentials": list(self.required_credentials),
            "source_url": self.source_url,
            "notes": self.notes,
            "next_gate": self.next_gate,
            "is_paper_ready": self.is_paper_ready,
            "is_execution_enabled": self.is_execution_enabled,
        }


@dataclass(frozen=True, slots=True)
class PaperTrade:
    """One hypothetical position; fees and slippage are absolute quote costs."""

    trade_id: str
    platform_id: str
    symbol: str
    side: str
    quantity: float
    entry_price: float
    exit_price: float | None = None
    fee: float = 0.0
    slippage: float = 0.0
    status: PaperTradeStatus | str = PaperTradeStatus.OPEN
    opened_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    closed_at: datetime | None = None
    strategy_id: str = ""
    quote_currency: str = "USD"
    metadata: Mapping[str, Any] = field(default_factory=dict)
    account_scope: str | None = None
    activity_mode: ActivityMode | str = ActivityMode.PAPER
    source_ref: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "trade_id", _text(self.trade_id, "trade_id", max_length=128))
        object.__setattr__(self, "platform_id", _identifier(self.platform_id, "platform_id"))
        object.__setattr__(self, "symbol", _text(self.symbol, "symbol", max_length=128))
        side = _text(self.side, "side", max_length=16).lower()
        if side not in {"buy", "sell", "long", "short"}:
            raise ValueError("side must be one of buy, sell, long, short")
        object.__setattr__(self, "side", side)
        object.__setattr__(self, "quantity", _finite(self.quantity, "quantity", minimum=0.0))
        if self.quantity <= 0:
            raise ValueError("quantity must be greater than zero")
        object.__setattr__(self, "entry_price", _finite(self.entry_price, "entry_price", minimum=0.0))
        if self.entry_price <= 0:
            raise ValueError("entry_price must be greater than zero")
        if self.exit_price is not None:
            exit_price = _finite(self.exit_price, "exit_price", minimum=0.0)
            object.__setattr__(self, "exit_price", exit_price)
        object.__setattr__(self, "fee", _finite(self.fee, "fee", minimum=0.0))
        object.__setattr__(self, "slippage", _finite(self.slippage, "slippage", minimum=0.0))
        object.__setattr__(self, "status", PaperTradeStatus(self.status))
        opened_at = _timestamp(self.opened_at, "opened_at")
        closed_at = None if self.closed_at is None else _timestamp(self.closed_at, "closed_at")
        object.__setattr__(self, "opened_at", opened_at)
        object.__setattr__(self, "closed_at", closed_at)
        if self.status is PaperTradeStatus.OPEN and (self.exit_price is not None or closed_at is not None):
            raise ValueError("open trades cannot have exit_price or closed_at")
        if self.status is PaperTradeStatus.CLOSED and (self.exit_price is None or closed_at is None):
            raise ValueError("closed trades require exit_price and closed_at")
        if closed_at is not None and closed_at < opened_at:
            raise ValueError("closed_at cannot be before opened_at")
        strategy_id = self.strategy_id.strip() if isinstance(self.strategy_id, str) else self.strategy_id
        object.__setattr__(
            self, "strategy_id", _text(strategy_id, "strategy_id", max_length=128) if strategy_id else ""
        )
        currency = _text(self.quote_currency, "quote_currency", max_length=16).upper()
        if not _CURRENCY_RE.fullmatch(currency):
            raise ValueError("quote_currency must be a currency-style code")
        object.__setattr__(self, "quote_currency", currency)
        account_scope = self.account_scope or f"paper-{self.platform_id}"
        account_scope = _text(account_scope, "account_scope", max_length=128)
        if not _ALIAS_RE.fullmatch(account_scope) or account_scope.lower().startswith("0x"):
            raise ValueError("account_scope must be a non-address alias")
        object.__setattr__(self, "account_scope", account_scope)
        mode = ActivityMode(self.activity_mode)
        if mode is not ActivityMode.PAPER:
            raise ValueError("PaperTrade only supports activity_mode='paper'")
        object.__setattr__(self, "activity_mode", mode)
        if self.source_ref is not None:
            source_ref = _text(self.source_ref, "source_ref", max_length=256)
            if _SENSITIVE_ASSIGNMENT_RE.search(source_ref):
                raise ValueError("source_ref cannot contain credential-like assignments")
            object.__setattr__(self, "source_ref", source_ref)
        metadata = _json_metadata(self.metadata, "metadata")
        if _SENSITIVE_ASSIGNMENT_RE.search(json.dumps(metadata, sort_keys=True, separators=(",", ":"))):
            raise ValueError("metadata cannot contain credential-like values")
        object.__setattr__(self, "metadata", metadata)

    @property
    def direction(self) -> int:
        return 1 if self.side in {"buy", "long"} else -1

    @property
    def notional(self) -> float:
        return self.quantity * self.entry_price

    @property
    def cost(self) -> float:
        return self.fee + self.slippage

    @property
    def gross_pnl(self) -> float | None:
        if self.exit_price is None:
            return None
        return (self.exit_price - self.entry_price) * self.quantity * self.direction

    @property
    def net_pnl(self) -> float | None:
        gross_pnl = self.gross_pnl
        return None if gross_pnl is None else gross_pnl - self.cost

    def mark_pnl(self, mark_price: float) -> float:
        mark_price = _finite(mark_price, "mark_price", minimum=0.0)
        return (mark_price - self.entry_price) * self.quantity * self.direction - self.cost

    def close(
        self,
        exit_price: float,
        *,
        closed_at: datetime | None = None,
        fee: float | None = None,
        slippage: float | None = None,
    ) -> PaperTrade:
        if self.status is not PaperTradeStatus.OPEN:
            raise ValueError("only open trades can be closed")
        return replace(
            self,
            exit_price=exit_price,
            closed_at=closed_at or datetime.now(UTC),
            fee=self.fee if fee is None else fee,
            slippage=self.slippage if slippage is None else slippage,
            status=PaperTradeStatus.CLOSED,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "trade_id": self.trade_id,
            "platform_id": self.platform_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": _round(self.quantity),
            "entry_price": _round(self.entry_price),
            "exit_price": None if self.exit_price is None else _round(self.exit_price),
            "fee": _round(self.fee),
            "slippage": _round(self.slippage),
            "status": self.status.value,
            "opened_at": _iso(self.opened_at),
            "closed_at": _iso(self.closed_at),
            "strategy_id": self.strategy_id,
            "quote_currency": self.quote_currency,
            "account_scope": self.account_scope,
            "activity_mode": self.activity_mode.value,
            "source_ref": self.source_ref,
            "metadata": dict(sorted(self.metadata.items())),
            "notional": _round(self.notional),
            "gross_pnl": None if self.gross_pnl is None else _round(self.gross_pnl),
            "net_pnl": None if self.net_pnl is None else _round(self.net_pnl),
        }


@dataclass(frozen=True, slots=True)
class RewardEntry:
    """A tracked airdrop, points, rebate, or quest value."""

    reward_id: str
    platform_id: str
    program: str
    kind: RewardKind | str
    status: RewardStatus | str
    estimated_value: float | None = None
    realized_value: float | None = None
    cost: float = 0.0
    currency: str = "USD"
    deadline: datetime | None = None
    source_url: str | None = None
    evidence_ref: str | None = None
    wallet_scope: str = "default"
    notes: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    account_scope: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "reward_id", _text(self.reward_id, "reward_id", max_length=128))
        object.__setattr__(self, "platform_id", _identifier(self.platform_id, "platform_id"))
        object.__setattr__(self, "program", _text(self.program, "program", max_length=256))
        object.__setattr__(self, "kind", RewardKind(self.kind))
        object.__setattr__(self, "status", RewardStatus(self.status))
        for name in ("estimated_value", "realized_value"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _finite(value, name, minimum=0.0))
        object.__setattr__(self, "cost", _finite(self.cost, "cost", minimum=0.0))
        currency = _text(self.currency, "currency", max_length=16).upper()
        if not _CURRENCY_RE.fullmatch(currency):
            raise ValueError("currency must be a currency-style code")
        object.__setattr__(self, "currency", currency)
        object.__setattr__(self, "deadline", None if self.deadline is None else _timestamp(self.deadline, "deadline"))
        object.__setattr__(self, "source_url", _safe_url(self.source_url, "source_url"))
        if self.evidence_ref is not None:
            evidence_ref = _text(self.evidence_ref, "evidence_ref", max_length=512)
            if _SENSITIVE_ASSIGNMENT_RE.search(evidence_ref):
                raise ValueError("evidence_ref cannot contain credential-like assignments")
            object.__setattr__(self, "evidence_ref", evidence_ref)
        wallet_scope = _text(self.wallet_scope, "wallet_scope", max_length=128)
        if not _ALIAS_RE.fullmatch(wallet_scope) or wallet_scope.lower().startswith("0x"):
            raise ValueError("wallet_scope must be a non-address alias")
        object.__setattr__(self, "wallet_scope", wallet_scope)
        account_scope = self.account_scope or f"rewards-{self.platform_id}"
        account_scope = _text(account_scope, "account_scope", max_length=128)
        if not _ALIAS_RE.fullmatch(account_scope) or account_scope.lower().startswith("0x"):
            raise ValueError("account_scope must be a non-address alias")
        object.__setattr__(self, "account_scope", account_scope)
        notes = _text(self.notes, "notes") if self.notes else ""
        if _SENSITIVE_ASSIGNMENT_RE.search(notes):
            raise ValueError("notes cannot contain credential-like assignments")
        object.__setattr__(self, "notes", notes)
        created_at = _timestamp(self.created_at, "created_at")
        updated_at = _timestamp(self.updated_at, "updated_at")
        if updated_at < created_at:
            raise ValueError("updated_at cannot be before created_at")
        object.__setattr__(self, "created_at", created_at)
        object.__setattr__(self, "updated_at", updated_at)

    @property
    def realized_net_value(self) -> float | None:
        if self.realized_value is None:
            return None
        return self.realized_value - self.cost

    @property
    def is_pending(self) -> bool:
        return self.status in {
            RewardStatus.CANDIDATE,
            RewardStatus.IN_PROGRESS,
            RewardStatus.ELIGIBLE,
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "reward_id": self.reward_id,
            "platform_id": self.platform_id,
            "program": self.program,
            "kind": self.kind.value,
            "status": self.status.value,
            "estimated_value": None if self.estimated_value is None else _round(self.estimated_value),
            "realized_value": None if self.realized_value is None else _round(self.realized_value),
            "realized_net_value": None if self.realized_net_value is None else _round(self.realized_net_value),
            "cost": _round(self.cost),
            "currency": self.currency,
            "deadline": _iso(self.deadline),
            "source_url": self.source_url,
            "evidence_ref": self.evidence_ref,
            "wallet_scope": self.wallet_scope,
            "account_scope": self.account_scope,
            "notes": self.notes,
            "created_at": _iso(self.created_at),
            "updated_at": _iso(self.updated_at),
        }


@dataclass(frozen=True, slots=True)
class PaperCapitalAccount:
    """Starting capital for one isolated paper account alias."""

    account_scope: str
    platform_id: str
    currency: str
    starting_capital: float
    activity_mode: ActivityMode | str = ActivityMode.PAPER
    source_ref: str | None = None

    def __post_init__(self) -> None:
        account_scope = _text(self.account_scope, "account_scope", max_length=128)
        if not _ALIAS_RE.fullmatch(account_scope) or account_scope.lower().startswith("0x"):
            raise ValueError("account_scope must be a non-address alias")
        object.__setattr__(self, "account_scope", account_scope)
        object.__setattr__(self, "platform_id", _identifier(self.platform_id, "platform_id"))
        currency = _text(self.currency, "currency", max_length=16).upper()
        if not _CURRENCY_RE.fullmatch(currency):
            raise ValueError("currency must be a currency-style code")
        object.__setattr__(self, "currency", currency)
        object.__setattr__(self, "starting_capital", _finite(self.starting_capital, "starting_capital", minimum=0.0))
        mode = ActivityMode(self.activity_mode)
        if mode is not ActivityMode.PAPER:
            raise ValueError("PaperCapitalAccount only supports activity_mode='paper'")
        object.__setattr__(self, "activity_mode", mode)
        if self.source_ref is not None:
            source_ref = _text(self.source_ref, "source_ref", max_length=256)
            if _SENSITIVE_ASSIGNMENT_RE.search(source_ref):
                raise ValueError("source_ref cannot contain credential-like assignments")
            object.__setattr__(self, "source_ref", source_ref)

    def as_dict(self) -> dict[str, Any]:
        return {
            "account_scope": self.account_scope,
            "platform_id": self.platform_id,
            "currency": self.currency,
            "activity_mode": self.activity_mode.value,
            "starting_capital": _round(self.starting_capital),
            "source_ref": self.source_ref,
        }


@dataclass(frozen=True, slots=True)
class PortfolioSnapshot:
    """A deliberately split view of paper trading and reward accounting."""

    as_of: datetime
    paper_realized_pnl: float | None
    paper_unrealized_pnl: float | None
    rewards_realized_net: float | None
    rewards_pending_estimate: float | None
    total_costs: float | None
    open_trade_count: int
    closed_trade_count: int
    reward_count: int
    by_currency: Mapping[str, Mapping[str, float | int]] = field(default_factory=dict)
    by_platform: Mapping[str, Mapping[str, Mapping[str, float | int]]] = field(default_factory=dict)
    reporting_currency: str | None = None
    mode: str = "paper_and_rewards"
    execution_enabled: bool = False
    by_account: Mapping[str, Mapping[str, Mapping[str, float | int]]] = field(default_factory=dict)
    capital_by_account: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "as_of", _timestamp(self.as_of, "as_of"))
        for name in (
            "paper_realized_pnl",
            "paper_unrealized_pnl",
            "rewards_realized_net",
            "rewards_pending_estimate",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _finite(value, name))
        if self.total_costs is not None:
            object.__setattr__(self, "total_costs", _finite(self.total_costs, "total_costs"))
        for name in ("open_trade_count", "closed_trade_count", "reward_count"):
            count = getattr(self, name)
            if not isinstance(count, int) or count < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        object.__setattr__(self, "reporting_currency", _currency(self.reporting_currency, "reporting_currency"))
        object.__setattr__(self, "by_currency", _snapshot_currencies(self.by_currency))
        object.__setattr__(self, "by_platform", _snapshot_platforms(self.by_platform))
        object.__setattr__(self, "by_account", _snapshot_accounts(self.by_account))
        object.__setattr__(self, "capital_by_account", _snapshot_capital_accounts(self.capital_by_account))
        currencies = set(self.by_currency)
        if self.reporting_currency is not None and currencies and self.reporting_currency not in currencies:
            raise ValueError("reporting_currency is not present in by_currency")

    def as_dict(self) -> dict[str, Any]:
        return {
            "as_of": self.as_of.astimezone(UTC).isoformat(),
            "mode": self.mode,
            "execution_enabled": self.execution_enabled,
            "reporting_currency": self.reporting_currency,
            "currencies": sorted(self.by_currency),
            "paper": {
                "realized_pnl": _optional_round(self.paper_realized_pnl),
                "unrealized_pnl": _optional_round(self.paper_unrealized_pnl),
                "open_trade_count": self.open_trade_count,
                "closed_trade_count": self.closed_trade_count,
            },
            "rewards": {
                "realized_net": _optional_round(self.rewards_realized_net),
                "pending_estimate": _optional_round(self.rewards_pending_estimate),
                "entry_count": self.reward_count,
            },
            "total_costs": _optional_round(self.total_costs),
            "by_currency": {
                currency: {
                    key: _round(value) if isinstance(value, float) else value for key, value in sorted(values.items())
                }
                for currency, values in sorted(self.by_currency.items())
            },
            "by_platform": {
                platform_id: {
                    currency: {
                        key: _round(value) if isinstance(value, float) else value
                        for key, value in sorted(metrics.items())
                    }
                    for currency, metrics in sorted(values.items())
                }
                for platform_id, values in sorted(self.by_platform.items())
            },
            "by_account": {
                account_scope: {
                    currency: {
                        key: _round(value) if isinstance(value, float) else value
                        for key, value in sorted(metrics.items())
                    }
                    for currency, metrics in sorted(values.items())
                }
                for account_scope, values in sorted(self.by_account.items())
            },
            "capital_by_account": {
                account_scope: {
                    key: _round(value) if isinstance(value, float) else value for key, value in sorted(values.items())
                }
                for account_scope, values in sorted(self.capital_by_account.items())
            },
        }


def _currency(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    normalized = _text(value, field_name, max_length=16).upper()
    if not _CURRENCY_RE.fullmatch(normalized):
        raise ValueError(f"{field_name} must be a currency-style code")
    return normalized


def _optional_round(value: float | None) -> float | None:
    return None if value is None else _round(value)


def _snapshot_metric_map(value: Mapping[str, float | int], field_name: str) -> dict[str, float | int]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping")
    normalized_metrics: dict[str, float | int] = {}
    for key, metric in value.items():
        key = _text(key, f"{field_name} metric", max_length=64)
        if isinstance(metric, bool):
            raise ValueError(f"{field_name} metrics cannot be booleans")
        if isinstance(metric, int):
            if metric < 0 and key.endswith("_count"):
                raise ValueError("counts cannot be negative")
            normalized_metrics[key] = metric
        else:
            normalized_metrics[key] = _finite(metric, f"{field_name}.{key}")
    return normalized_metrics


def _snapshot_currencies(value: Mapping[str, Mapping[str, float | int]]) -> dict[str, dict[str, float | int]]:
    if not isinstance(value, Mapping):
        raise ValueError("by_currency must be a mapping")
    result: dict[str, dict[str, float | int]] = {}
    for currency, metrics in value.items():
        normalized_currency = _currency(currency, "by_currency currency")
        if normalized_currency is None:
            raise ValueError("by_currency requires a currency")
        result[normalized_currency] = _snapshot_metric_map(metrics, f"by_currency.{normalized_currency}")
    return result


def _snapshot_platforms(
    value: Mapping[str, Mapping[str, Mapping[str, float | int]]],
) -> dict[str, dict[str, dict[str, float | int]]]:
    if not isinstance(value, Mapping):
        raise ValueError("by_platform must be a mapping")
    result: dict[str, dict[str, dict[str, float | int]]] = {}
    for platform_id, currencies in value.items():
        normalized_id = _identifier(platform_id, "by_platform platform_id")
        if not isinstance(currencies, Mapping):
            raise ValueError("by_platform currencies must be mappings")
        normalized_currencies: dict[str, dict[str, float | int]] = {}
        for currency, metrics in currencies.items():
            normalized_currency = _currency(currency, "by_platform currency")
            if normalized_currency is None:
                raise ValueError("by_platform requires a currency")
            normalized_currencies[normalized_currency] = _snapshot_metric_map(
                metrics, f"by_platform.{normalized_id}.{normalized_currency}"
            )
        result[normalized_id] = normalized_currencies
    return result


def _snapshot_accounts(
    value: Mapping[str, Mapping[str, Mapping[str, float | int]]],
) -> dict[str, dict[str, dict[str, float | int]]]:
    if not isinstance(value, Mapping):
        raise ValueError("by_account must be a mapping")
    result: dict[str, dict[str, dict[str, float | int]]] = {}
    for account_scope, currencies in value.items():
        normalized_scope = _text(account_scope, "by_account account_scope", max_length=128)
        if not _ALIAS_RE.fullmatch(normalized_scope) or normalized_scope.lower().startswith("0x"):
            raise ValueError("by_account account_scope must be a non-address alias")
        if not isinstance(currencies, Mapping):
            raise ValueError("by_account currencies must be mappings")
        normalized_currencies: dict[str, dict[str, float | int]] = {}
        for currency, metrics in currencies.items():
            normalized_currency = _currency(currency, "by_account currency")
            if normalized_currency is None:
                raise ValueError("by_account requires a currency")
            normalized_currencies[normalized_currency] = _snapshot_metric_map(
                metrics, f"by_account.{normalized_scope}.{normalized_currency}"
            )
        result[normalized_scope] = normalized_currencies
    return result


def _snapshot_capital_accounts(value: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    if not isinstance(value, Mapping):
        raise ValueError("capital_by_account must be a mapping")
    result: dict[str, dict[str, Any]] = {}
    numeric_fields = {"starting_capital", "realized_pnl", "reserved_risk", "available_capital"}
    for account_scope, values in value.items():
        normalized_scope = _text(account_scope, "capital_by_account account_scope", max_length=128)
        if not _ALIAS_RE.fullmatch(normalized_scope) or normalized_scope.lower().startswith("0x"):
            raise ValueError("capital_by_account account_scope must be a non-address alias")
        if not isinstance(values, Mapping):
            raise ValueError("capital_by_account values must be mappings")
        normalized: dict[str, Any] = {}
        for key, raw_value in values.items():
            key = _text(key, "capital_by_account field", max_length=64)
            if key == "platform_id":
                normalized[key] = _identifier(raw_value, "capital_by_account.platform_id")
            elif key == "currency":
                normalized[key] = _currency(raw_value, "capital_by_account.currency")
            elif key == "activity_mode":
                mode = ActivityMode(raw_value)
                if mode is not ActivityMode.PAPER:
                    raise ValueError("capital_by_account only supports paper activity_mode")
                normalized[key] = mode.value
            elif key in numeric_fields:
                normalized[key] = _finite(raw_value, f"capital_by_account.{key}")
            elif key == "open_positions":
                if isinstance(raw_value, bool) or not isinstance(raw_value, int) or raw_value < 0:
                    raise ValueError("capital_by_account.open_positions must be a non-negative integer")
                normalized[key] = raw_value
            elif raw_value is None or isinstance(raw_value, (str, bool, int, float)):
                normalized[key] = raw_value
            else:
                raise ValueError("capital_by_account values must be JSON-compatible scalars")
        result[normalized_scope] = normalized
    return result
