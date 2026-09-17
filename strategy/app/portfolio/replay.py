"""Bounded JSONL replay for the provider-neutral portfolio ledger."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeAlias

from app.portfolio.ledger import PaperPortfolioLedger
from app.portfolio.models import PaperTrade, PortfolioSnapshot, RewardEntry

FIXTURE_VERSION = 1
MAX_FIXTURE_BYTES = 20 * 1024 * 1024
MAX_FIXTURE_EVENTS = 100_000
PortfolioEvent: TypeAlias = PaperTrade | RewardEntry


class PortfolioReplayError(ValueError):
    """Raised when a portfolio fixture is malformed or exceeds its bounds."""


@dataclass(frozen=True, slots=True)
class PortfolioReplayReport:
    """Serializable result of an offline portfolio replay."""

    fixture_version: int
    event_count: int
    paper_trade_count: int
    reward_count: int
    snapshot: PortfolioSnapshot

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": "portfolio_fixture",
            "mode": "offline_paper_and_rewards_replay",
            "execution_enabled": False,
            "fixture_version": self.fixture_version,
            "event_count": self.event_count,
            "paper_trade_count": self.paper_trade_count,
            "reward_count": self.reward_count,
            "snapshot": self.snapshot.as_dict(),
        }


def load_portfolio_fixture(path: str | Path) -> tuple[PortfolioEvent, ...]:
    """Load a bounded, versioned JSONL fixture without contacting a provider."""

    fixture_path = Path(path)
    try:
        raw_bytes = fixture_path.read_bytes()
    except OSError as exc:
        raise PortfolioReplayError(f"cannot read fixture: {fixture_path}") from exc
    if len(raw_bytes) > MAX_FIXTURE_BYTES:
        raise PortfolioReplayError("fixture exceeds the maximum byte size")
    try:
        raw_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PortfolioReplayError("fixture must be UTF-8") from exc

    events: list[PortfolioEvent] = []
    for line_number, line in enumerate(raw_text.splitlines(), start=1):
        if not line.strip():
            continue
        if len(events) >= MAX_FIXTURE_EVENTS:
            raise PortfolioReplayError("fixture exceeds the maximum event count")
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PortfolioReplayError(f"invalid JSON on line {line_number}") from exc
        try:
            events.append(_parse_event(payload, line_number))
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, PortfolioReplayError):
                raise
            raise PortfolioReplayError(f"invalid event on line {line_number}: {exc}") from exc
    return tuple(events)


def replay_portfolio_fixture(
    path: str | Path,
    *,
    as_of: datetime | None = None,
    marks: Mapping[str, float] | None = None,
    reporting_currency: str | None = None,
) -> PortfolioReplayReport:
    """Replay fixture events and return separate paper/reward totals."""

    events = load_portfolio_fixture(path)
    ledger = PaperPortfolioLedger()
    paper_trade_count = 0
    reward_count = 0
    for event in events:
        if isinstance(event, PaperTrade):
            ledger.record_trade(event)
            paper_trade_count += 1
        else:
            ledger.record_reward(event)
            reward_count += 1
    return PortfolioReplayReport(
        fixture_version=FIXTURE_VERSION,
        event_count=len(events),
        paper_trade_count=paper_trade_count,
        reward_count=reward_count,
        snapshot=ledger.snapshot(
            as_of=as_of,
            marks=marks,
            reporting_currency=reporting_currency,
        ),
    )


def _parse_event(payload: Any, line_number: int) -> PortfolioEvent:
    if not isinstance(payload, Mapping):
        raise PortfolioReplayError(f"line {line_number} must contain an object")
    if payload.get("event_version") != FIXTURE_VERSION:
        raise PortfolioReplayError(f"line {line_number} has unsupported event_version")
    event_type = payload.get("event_type")
    event_id = payload.get("event_id")
    if not isinstance(event_id, str) or not event_id.strip():
        raise PortfolioReplayError(f"line {line_number} requires event_id")
    if event_type == "paper_trade":
        trade_data = _object(payload, "trade", line_number)
        trade = PaperTrade(
            trade_id=trade_data["trade_id"],
            platform_id=trade_data["platform_id"],
            symbol=trade_data["symbol"],
            side=trade_data["side"],
            quantity=trade_data["quantity"],
            entry_price=trade_data["entry_price"],
            exit_price=trade_data.get("exit_price"),
            fee=trade_data.get("fee", 0.0),
            slippage=trade_data.get("slippage", 0.0),
            status=trade_data.get("status", "open"),
            opened_at=_parse_timestamp(trade_data["opened_at"], "opened_at"),
            closed_at=(
                None if trade_data.get("closed_at") is None else _parse_timestamp(trade_data["closed_at"], "closed_at")
            ),
            strategy_id=trade_data.get("strategy_id", ""),
            quote_currency=trade_data.get("quote_currency", "USD"),
            metadata=trade_data.get("metadata", {}),
            account_scope=trade_data.get("account_scope"),
            activity_mode=trade_data.get("activity_mode", "paper"),
            source_ref=trade_data.get("source_ref"),
        )
        if trade.trade_id != event_id:
            raise PortfolioReplayError(f"line {line_number} event_id does not match trade_id")
        return trade
    if event_type == "reward":
        reward_data = _object(payload, "reward", line_number)
        reward = RewardEntry(
            reward_id=reward_data["reward_id"],
            platform_id=reward_data["platform_id"],
            program=reward_data["program"],
            kind=reward_data["kind"],
            status=reward_data["status"],
            estimated_value=reward_data.get("estimated_value"),
            realized_value=reward_data.get("realized_value"),
            cost=reward_data.get("cost", 0.0),
            currency=reward_data.get("currency", "USD"),
            deadline=(
                None if reward_data.get("deadline") is None else _parse_timestamp(reward_data["deadline"], "deadline")
            ),
            source_url=reward_data.get("source_url"),
            evidence_ref=reward_data.get("evidence_ref"),
            wallet_scope=reward_data.get("wallet_scope", "default"),
            notes=reward_data.get("notes", ""),
            created_at=_parse_timestamp(reward_data["created_at"], "created_at"),
            updated_at=_parse_timestamp(reward_data["updated_at"], "updated_at"),
            account_scope=reward_data.get("account_scope"),
        )
        if reward.reward_id != event_id:
            raise PortfolioReplayError(f"line {line_number} event_id does not match reward_id")
        return reward
    raise PortfolioReplayError(f"line {line_number} has unsupported event_type")


def _object(payload: Mapping[str, Any], key: str, line_number: int) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise PortfolioReplayError(f"line {line_number} requires object field {key}")
    return value


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
