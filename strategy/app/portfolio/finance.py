"""Paper-only finance projections for the central finance boundary.

The product repository owns normalized trading/reward events.  This module
emits deterministic projection records for the root finance pipeline; it does
not open accounts, post cash transactions, or contact a provider.  Every
record is explicitly marked as non-cash so a paper result cannot be counted as
real money by accident.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.portfolio.models import ActivityMode, PaperTrade, RewardEntry

_ALIAS_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_CURRENCY_RE = re.compile(r"^[A-Z][A-Z0-9._-]{1,15}$")
_SENSITIVE_KEY_RE = re.compile(
    r"(?:api[_ -]?key|access[_ -]?token|private[_ -]?key|seed|mnemonic|password|cookie|secret)",
    re.IGNORECASE,
)
_SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?:api[_ -]?key|access[_ -]?token|private[_ -]?key|seed(?: phrase)?|mnemonic|password|cookie|secret)"
    r"\s*[:=]\s*\S+",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class FinanceProjection:
    """One non-cash paper valuation event ready for controlled import."""

    projection_id: str
    source_ref: str
    account_scope: str
    platform_id: str
    currency: str
    signed_amount: float
    event_at: datetime
    projection_type: str
    valuation_status: str
    activity_mode: ActivityMode | str = ActivityMode.PAPER
    cash_effect: bool = False
    posting_status: str = "separate_paper_lane"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("projection_id", "source_ref", "projection_type", "valuation_status"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value.strip()) > 256:
                raise ValueError(f"{name} must be a non-empty bounded string")
            object.__setattr__(self, name, value.strip())
        if _SENSITIVE_ASSIGNMENT_RE.search(self.source_ref):
            raise ValueError("source_ref cannot contain credential-like assignments")
        if (
            not isinstance(self.account_scope, str)
            or not _ALIAS_RE.fullmatch(self.account_scope)
            or self.account_scope.lower().startswith("0x")
        ):
            raise ValueError("account_scope must be a non-address alias")
        object.__setattr__(self, "platform_id", _identifier(self.platform_id, "platform_id"))
        currency = self.currency.strip().upper() if isinstance(self.currency, str) else self.currency
        if not isinstance(currency, str) or not _CURRENCY_RE.fullmatch(currency):
            raise ValueError("currency must be a currency-style code")
        object.__setattr__(self, "currency", currency)
        amount = float(self.signed_amount)
        if not math.isfinite(amount):
            raise ValueError("signed_amount must be finite")
        object.__setattr__(self, "signed_amount", amount)
        object.__setattr__(self, "event_at", _timestamp(self.event_at, "event_at"))
        mode = ActivityMode(self.activity_mode)
        if mode is not ActivityMode.PAPER:
            raise ValueError("FinanceProjection only supports activity_mode='paper'")
        object.__setattr__(self, "activity_mode", mode)
        if self.cash_effect:
            raise ValueError("paper finance projections cannot have a cash effect")
        if self.posting_status != "separate_paper_lane":
            raise ValueError("paper finance projections must remain in the separate paper lane")
        if not isinstance(self.metadata, Mapping):
            raise ValueError("metadata must be a mapping")
        metadata = dict(self.metadata)
        if any(not isinstance(key, str) for key in metadata):
            raise ValueError("metadata keys must be strings")
        if any(_SENSITIVE_KEY_RE.search(key) for key in metadata):
            raise ValueError("metadata cannot contain credential or secret fields")
        serialized = json.dumps(metadata, sort_keys=True, separators=(",", ":"), allow_nan=False)
        if _SENSITIVE_ASSIGNMENT_RE.search(serialized):
            raise ValueError("metadata cannot contain credential-like values")
        object.__setattr__(self, "metadata", metadata)

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_version": 1,
            "event_type": "paper_finance_projection",
            "source": "booktrading",
            "projection_id": self.projection_id,
            "source_ref": self.source_ref,
            "account_scope": self.account_scope,
            "platform_id": self.platform_id,
            "currency": self.currency,
            "activity_mode": self.activity_mode.value,
            "projection_type": self.projection_type,
            "valuation_status": self.valuation_status,
            "signed_amount": round(self.signed_amount, 10),
            "event_at": self.event_at.astimezone(UTC).isoformat(),
            "cash_effect": False,
            "posting_status": self.posting_status,
            "metadata": dict(sorted(self.metadata.items())),
        }


def paper_trade_to_finance_projection(trade: PaperTrade) -> FinanceProjection:
    """Project one closed paper trade's net P&L without creating cash."""

    if not isinstance(trade, PaperTrade):
        raise TypeError("trade must be a PaperTrade")
    if trade.exit_price is None or trade.closed_at is None:
        raise ValueError("only closed paper trades can be projected")
    source_ref = trade.source_ref or f"portfolio:paper_trade:{trade.trade_id}"
    return FinanceProjection(
        projection_id=f"paper-pnl:{trade.trade_id}",
        source_ref=source_ref,
        account_scope=trade.account_scope,
        platform_id=trade.platform_id,
        currency=trade.quote_currency,
        signed_amount=trade.net_pnl or 0.0,
        event_at=trade.closed_at,
        projection_type="paper_trade_pnl",
        valuation_status="realized",
        metadata={
            "trade_id": trade.trade_id,
            "symbol": trade.symbol,
            "strategy_id": trade.strategy_id,
            "tracked_cost": trade.cost,
            "paper_only": True,
        },
    )


def reward_to_finance_projection(reward: RewardEntry) -> FinanceProjection | None:
    """Project realized or pending reward value in the separate paper lane."""

    if not isinstance(reward, RewardEntry):
        raise TypeError("reward must be a RewardEntry")
    if reward.status.value == "claimed" and reward.realized_net_value is not None:
        value = reward.realized_net_value
        valuation_status = "realized"
    elif reward.is_pending and reward.estimated_value is not None:
        value = reward.estimated_value
        valuation_status = "pending_estimate"
    else:
        return None
    return FinanceProjection(
        projection_id=f"reward-value:{reward.reward_id}",
        source_ref=reward.evidence_ref or f"portfolio:reward:{reward.reward_id}",
        account_scope=reward.account_scope,
        platform_id=reward.platform_id,
        currency=reward.currency,
        signed_amount=value,
        event_at=reward.updated_at,
        projection_type="reward_value",
        valuation_status=valuation_status,
        metadata={
            "reward_id": reward.reward_id,
            "program": reward.program,
            "kind": reward.kind.value,
            "tracked_cost": reward.cost,
            "gross_value": reward.realized_value if valuation_status == "realized" else reward.estimated_value,
            "net_value": value,
            "paper_only": True,
            "cash_received": False,
        },
    )


def portfolio_finance_projections(
    trades: Iterable[PaperTrade], rewards: Iterable[RewardEntry]
) -> tuple[FinanceProjection, ...]:
    """Return stable, idempotent projection records for portfolio events."""

    projections = [paper_trade_to_finance_projection(trade) for trade in trades if trade.status.value == "closed"]
    projections.extend(
        projection for reward in rewards if (projection := reward_to_finance_projection(reward)) is not None
    )
    return tuple(sorted(projections, key=lambda item: item.projection_id))


def _identifier(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    normalized = value.strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", normalized):
        raise ValueError(f"{field_name} must contain lowercase letters, numbers, '-' or '_'")
    return normalized


def _timestamp(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)
