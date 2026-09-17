"""Bounded integration adapters into the shared portfolio ledger."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.portfolio.ledger import PaperPortfolioLedger
from app.portfolio.models import PaperTrade, PortfolioSnapshot
from app.world.replay import WorldReplayFrame, WorldReplayReport, WorldReplayRunner


class PortfolioIntegrationError(ValueError):
    """Raised when a provider-specific replay record cannot be normalized."""


@dataclass(frozen=True, slots=True)
class WorldPortfolioReplayResult:
    """World replay evidence plus its normalized paper portfolio snapshot."""

    market_report: WorldReplayReport
    portfolio_snapshot: PortfolioSnapshot
    paper_trade_ids: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": "world_xyz",
            "mode": "offline_world_to_portfolio_replay",
            "execution_enabled": False,
            "market_replay": self.market_report.as_dict(),
            "portfolio": self.portfolio_snapshot.as_dict(),
            "paper_trade_ids": list(self.paper_trade_ids),
        }


def world_report_to_paper_trades(
    report: WorldReplayReport,
    *,
    quote_currency: str = "USD",
    account_scope: str = "paper-world",
    strategy_id: str = "world_buy_both_research",
) -> tuple[PaperTrade, ...]:
    """Normalize synthetic World buy-both positions into paper trade records.

    World buy-both positions have two legs.  The normalized paper record uses
    the gross cost per filled unit as its entry price and the settled payout
    per filled unit as its exit price, while preserving fees and slippage as
    separate costs.  This keeps the portfolio P&L equal to the replay result.
    """

    trades: list[PaperTrade] = []
    for index, raw in enumerate(report.trades):
        if not isinstance(raw, Mapping):
            raise PortfolioIntegrationError(f"World replay trade {index} is not an object")
        ticker = _required_text(raw, "ticker", index)
        filled_units = _positive_number(raw.get("filled_units"), "filled_units", index)
        gross_cost = _nonnegative_number(raw.get("gross_cost"), "gross_cost", index)
        if gross_cost <= 0:
            raise PortfolioIntegrationError(f"World replay trade {index} has no positive gross cost")
        status = raw.get("status")
        if status not in {"resolved", "unresolved"}:
            raise PortfolioIntegrationError(f"World replay trade {index} has unsupported status")
        opened_at = _parse_timestamp(raw.get("entered_at"), "entered_at", index)
        resolved_at = raw.get("resolved_at")
        payout = raw.get("payout")
        if status == "resolved":
            if resolved_at is None or payout is None:
                raise PortfolioIntegrationError(f"World replay trade {index} is resolved without payout evidence")
            closed_at = _parse_timestamp(resolved_at, "resolved_at", index)
            exit_price = _nonnegative_number(payout, "payout", index) / filled_units
        else:
            closed_at = None
            exit_price = None
        fee = _nonnegative_number(raw.get("fees", 0.0), "fees", index)
        slippage = _nonnegative_number(raw.get("slippage", 0.0), "slippage", index)
        trade_digest = hashlib.sha256(f"{index}:{ticker}".encode()).hexdigest()[:16]
        metadata = {
            "world_ticker": ticker,
            "world_replay": True,
            "world_fill_ratio": raw.get("fill_ratio"),
            "world_yes_ask": raw.get("yes_ask"),
            "world_no_ask": raw.get("no_ask"),
            "world_quote_age_seconds": raw.get("quote_age_seconds"),
            "synthetic_legs": 2,
        }
        trades.append(
            PaperTrade(
                trade_id=f"world-replay-{trade_digest}",
                platform_id="world_xyz",
                symbol=f"{ticker}:BUY_BOTH",
                side="buy",
                quantity=filled_units,
                entry_price=gross_cost / filled_units,
                exit_price=exit_price,
                fee=fee,
                slippage=slippage,
                status="closed" if status == "resolved" else "open",
                opened_at=opened_at,
                closed_at=closed_at,
                strategy_id=strategy_id,
                quote_currency=quote_currency,
                account_scope=account_scope,
                metadata=metadata,
            )
        )
    return tuple(trades)


def replay_world_to_portfolio(
    frames: Sequence[WorldReplayFrame],
    *,
    runner: WorldReplayRunner | None = None,
    ledger: PaperPortfolioLedger | None = None,
    as_of: datetime | None = None,
    marks: Mapping[str, float] | None = None,
    reporting_currency: str | None = None,
    quote_currency: str = "USD",
    account_scope: str = "paper-world",
) -> WorldPortfolioReplayResult:
    """Run offline World replay and idempotently record its paper positions."""

    market_report = (runner or WorldReplayRunner()).run(frames)
    active_ledger = ledger or PaperPortfolioLedger()
    paper_trades = world_report_to_paper_trades(
        market_report,
        quote_currency=quote_currency,
        account_scope=account_scope,
    )
    for trade in paper_trades:
        active_ledger.record_trade(trade)
    snapshot = active_ledger.snapshot(
        as_of=as_of,
        marks=marks,
        reporting_currency=reporting_currency,
    )
    return WorldPortfolioReplayResult(
        market_report=market_report,
        portfolio_snapshot=snapshot,
        paper_trade_ids=tuple(trade.trade_id for trade in paper_trades),
    )


def _required_text(record: Mapping[str, Any], key: str, index: int) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PortfolioIntegrationError(f"World replay trade {index} requires {key}")
    return value.strip()


def _positive_number(value: Any, field_name: str, index: int) -> float:
    number = _nonnegative_number(value, field_name, index)
    if number <= 0:
        raise PortfolioIntegrationError(f"World replay trade {index} {field_name} must be positive")
    return number


def _nonnegative_number(value: Any, field_name: str, index: int) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise PortfolioIntegrationError(f"World replay trade {index} {field_name} is invalid") from exc
    if number < 0 or not math.isfinite(number):
        raise PortfolioIntegrationError(f"World replay trade {index} {field_name} is invalid")
    return number


def _parse_timestamp(value: Any, field_name: str, index: int) -> datetime:
    if not isinstance(value, str):
        raise PortfolioIntegrationError(f"World replay trade {index} requires {field_name}")
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PortfolioIntegrationError(f"World replay trade {index} {field_name} is invalid") from exc
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise PortfolioIntegrationError(f"World replay trade {index} {field_name} requires a timezone")
    return timestamp.astimezone(UTC)
