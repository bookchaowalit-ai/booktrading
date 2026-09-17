"""Deterministic, side-effect-free paper and reward ledger."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from app.portfolio.models import (
    ActivityMode,
    PaperCapitalAccount,
    PaperTrade,
    PaperTradeStatus,
    PortfolioSnapshot,
    RewardEntry,
    RewardStatus,
)


class LedgerConflictError(ValueError):
    """Raised when an event ID is reused with different content."""


class PaperPortfolioLedger:
    """In-memory ledger for offline replay and paper-mode services.

    The ledger has no broker, wallet, Redis, or network side effects.  A
    caller can persist ``export_events()`` through the owning lake pipeline.
    """

    EVENT_VERSION = 1

    def __init__(self) -> None:
        self._trades: dict[str, PaperTrade] = {}
        self._rewards: dict[str, RewardEntry] = {}
        self._capital_accounts: dict[str, PaperCapitalAccount] = {}

    @property
    def trades(self) -> tuple[PaperTrade, ...]:
        return tuple(self._trades[key] for key in sorted(self._trades))

    @property
    def rewards(self) -> tuple[RewardEntry, ...]:
        return tuple(self._rewards[key] for key in sorted(self._rewards))

    @property
    def capital_accounts(self) -> tuple[PaperCapitalAccount, ...]:
        """Return configured paper capital accounts in stable order."""

        return tuple(self._capital_accounts[key] for key in sorted(self._capital_accounts))

    def register_account(self, account: PaperCapitalAccount) -> PaperCapitalAccount:
        """Register an isolated paper capital account idempotently."""

        if not isinstance(account, PaperCapitalAccount):
            raise TypeError("account must be a PaperCapitalAccount")
        existing = self._capital_accounts.get(account.account_scope)
        if existing is not None:
            if existing == account:
                return existing
            raise LedgerConflictError(f"account_scope already contains different data: {account.account_scope}")
        self._capital_accounts[account.account_scope] = account
        return account

    def record_trade(self, trade: PaperTrade) -> PaperTrade:
        if not isinstance(trade, PaperTrade):
            raise TypeError("trade must be a PaperTrade")
        account = self._capital_accounts.get(trade.account_scope)
        if account is not None and (
            account.platform_id != trade.platform_id
            or account.currency != trade.quote_currency
            or account.activity_mode != trade.activity_mode
        ):
            raise LedgerConflictError(f"trade does not match registered account_scope: {trade.account_scope}")
        existing = self._trades.get(trade.trade_id)
        if existing is not None:
            if existing == trade:
                return existing
            raise LedgerConflictError(f"trade_id already contains different data: {trade.trade_id}")
        self._trades[trade.trade_id] = trade
        return trade

    def record_reward(self, reward: RewardEntry) -> RewardEntry:
        if not isinstance(reward, RewardEntry):
            raise TypeError("reward must be a RewardEntry")
        existing = self._rewards.get(reward.reward_id)
        if existing is not None:
            if existing == reward:
                return existing
            raise LedgerConflictError(f"reward_id already contains different data: {reward.reward_id}")
        self._rewards[reward.reward_id] = reward
        return reward

    def snapshot(
        self,
        *,
        as_of: datetime | None = None,
        marks: Mapping[str, float] | None = None,
        reporting_currency: str | None = None,
    ) -> PortfolioSnapshot:
        """Calculate a split snapshot without valuing pending rewards as cash.

        Open-trade marks accept either ``platform_id:symbol`` or ``symbol``;
        the platform-specific key wins.  Missing marks leave unrealized P&L at
        zero while preserving the open-trade count.  Records updated after an
        explicit ``as_of`` are excluded.  If multiple currencies are present,
        top-level money values are ``None`` unless a reporting currency is
        selected; no implicit FX conversion is performed.
        """

        normalized_marks = {} if marks is None else dict(marks)
        snapshot_time = _snapshot_time(as_of, self.trades, self.rewards)
        selected_currency = _normalize_currency(reporting_currency) if reporting_currency else None
        trades = tuple(trade for trade in self.trades if trade.opened_at <= snapshot_time)
        rewards = tuple(reward for reward in self.rewards if reward.updated_at <= snapshot_time)
        by_currency: dict[str, dict[str, float | int]] = {}
        by_platform: dict[str, dict[str, dict[str, float | int]]] = {}
        by_account: dict[str, dict[str, dict[str, float | int]]] = {}
        open_trade_count = 0
        closed_trade_count = 0

        def metrics(currency: str, platform_id: str | None = None) -> dict[str, float | int]:
            target = by_currency if platform_id is None else by_platform.setdefault(platform_id, {})
            return target.setdefault(currency, _empty_metrics())

        def account_metrics(account_scope: str, currency: str) -> dict[str, float | int]:
            return by_account.setdefault(account_scope, {}).setdefault(currency, _empty_metrics())

        for trade in trades:
            currency_metrics = metrics(trade.quote_currency)
            platform_metrics = metrics(trade.quote_currency, trade.platform_id)
            account_currency_metrics = account_metrics(trade.account_scope, trade.quote_currency)
            _add_money(currency_metrics, "total_costs", trade.cost)
            _add_money(platform_metrics, "total_costs", trade.cost)
            _add_money(account_currency_metrics, "total_costs", trade.cost)
            is_closed = (
                trade.status is PaperTradeStatus.CLOSED
                and trade.closed_at is not None
                and trade.closed_at <= snapshot_time
            )
            is_open = trade.status is PaperTradeStatus.OPEN or (
                trade.status is PaperTradeStatus.CLOSED
                and trade.closed_at is not None
                and trade.closed_at > snapshot_time
            )
            if is_closed:
                closed_trade_count += 1
                _add_count(currency_metrics, "closed_trade_count")
                _add_count(platform_metrics, "closed_trade_count")
                _add_count(account_currency_metrics, "closed_trade_count")
                net_pnl = trade.net_pnl or 0.0
                _add_money(currency_metrics, "paper_realized_pnl", net_pnl)
                _add_money(platform_metrics, "paper_realized_pnl", net_pnl)
                _add_money(account_currency_metrics, "paper_realized_pnl", net_pnl)
            elif is_open:
                open_trade_count += 1
                _add_count(currency_metrics, "open_trade_count")
                _add_count(platform_metrics, "open_trade_count")
                _add_count(account_currency_metrics, "open_trade_count")
                mark = _lookup_mark(trade, normalized_marks)
                if mark is not None:
                    unrealized_pnl = trade.mark_pnl(mark)
                    _add_money(currency_metrics, "paper_unrealized_pnl", unrealized_pnl)
                    _add_money(platform_metrics, "paper_unrealized_pnl", unrealized_pnl)
                    _add_money(account_currency_metrics, "paper_unrealized_pnl", unrealized_pnl)

        for reward in rewards:
            currency_metrics = metrics(reward.currency)
            platform_metrics = metrics(reward.currency, reward.platform_id)
            account_currency_metrics = account_metrics(reward.account_scope, reward.currency)
            _add_money(currency_metrics, "total_costs", reward.cost)
            _add_money(platform_metrics, "total_costs", reward.cost)
            _add_money(account_currency_metrics, "total_costs", reward.cost)
            _add_count(currency_metrics, "reward_count")
            _add_count(platform_metrics, "reward_count")
            _add_count(account_currency_metrics, "reward_count")
            if reward.status is RewardStatus.CLAIMED and reward.realized_value is not None:
                net_value = reward.realized_net_value or 0.0
                _add_money(currency_metrics, "rewards_realized_net", net_value)
                _add_money(platform_metrics, "rewards_realized_net", net_value)
                _add_money(account_currency_metrics, "rewards_realized_net", net_value)
            elif reward.is_pending and reward.estimated_value is not None:
                _add_money(currency_metrics, "rewards_pending_estimate", reward.estimated_value)
                _add_money(platform_metrics, "rewards_pending_estimate", reward.estimated_value)
                _add_money(account_currency_metrics, "rewards_pending_estimate", reward.estimated_value)

        currencies = sorted(by_currency)
        if selected_currency is not None and currencies and selected_currency not in by_currency:
            raise ValueError(f"reporting_currency has no records at snapshot: {selected_currency}")
        if selected_currency is None and len(currencies) == 1:
            selected_currency = currencies[0]
        selected_metrics = by_currency.get(selected_currency, {}) if selected_currency else {}
        capital_by_account = self._capital_snapshot(trades, snapshot_time)

        def scalar_or_zero(key: str) -> float | None:
            if not currencies:
                return 0.0
            if selected_currency is None:
                return None
            return float(selected_metrics.get(key, 0.0))

        return PortfolioSnapshot(
            as_of=snapshot_time,
            paper_realized_pnl=scalar_or_zero("paper_realized_pnl"),
            paper_unrealized_pnl=scalar_or_zero("paper_unrealized_pnl"),
            rewards_realized_net=scalar_or_zero("rewards_realized_net"),
            rewards_pending_estimate=scalar_or_zero("rewards_pending_estimate"),
            total_costs=scalar_or_zero("total_costs"),
            open_trade_count=open_trade_count,
            closed_trade_count=closed_trade_count,
            reward_count=len(rewards),
            by_currency=by_currency,
            by_platform=by_platform,
            reporting_currency=selected_currency,
            by_account=by_account,
            capital_by_account=capital_by_account,
        )

    def export_events(self) -> tuple[dict[str, Any], ...]:
        """Return stable JSON-compatible events for a lake writer or fixture."""

        events: list[dict[str, Any]] = []
        for trade in self.trades:
            events.append(
                {
                    "event_version": self.EVENT_VERSION,
                    "event_type": "paper_trade",
                    "event_id": trade.trade_id,
                    "trade": trade.as_dict(),
                }
            )
        for reward in self.rewards:
            events.append(
                {
                    "event_version": self.EVENT_VERSION,
                    "event_type": "reward",
                    "event_id": reward.reward_id,
                    "reward": reward.as_dict(),
                }
            )
        return tuple(events)

    def export_finance_projections(self) -> tuple[dict[str, Any], ...]:
        """Export non-cash projections for the central finance boundary."""

        from app.portfolio.finance import portfolio_finance_projections

        return tuple(projection.as_dict() for projection in portfolio_finance_projections(self.trades, self.rewards))

    def _capital_snapshot(self, trades: tuple[PaperTrade, ...], snapshot_time: datetime) -> dict[str, dict[str, Any]]:
        snapshot: dict[str, dict[str, Any]] = {}
        for account in self.capital_accounts:
            scoped = tuple(
                trade
                for trade in trades
                if trade.account_scope == account.account_scope and trade.quote_currency == account.currency
            )
            realized_pnl = sum(
                trade.net_pnl or 0.0
                for trade in scoped
                if trade.status is PaperTradeStatus.CLOSED
                and trade.closed_at is not None
                and trade.closed_at <= snapshot_time
            )
            open_trades = tuple(
                trade
                for trade in scoped
                if trade.status is PaperTradeStatus.OPEN
                or (
                    trade.status is PaperTradeStatus.CLOSED
                    and trade.closed_at is not None
                    and trade.closed_at > snapshot_time
                )
            )
            reserved_risk = sum(trade.notional + trade.cost for trade in open_trades)
            snapshot[account.account_scope] = {
                "platform_id": account.platform_id,
                "currency": account.currency,
                "activity_mode": ActivityMode.PAPER.value,
                "starting_capital": account.starting_capital,
                "realized_pnl": realized_pnl,
                "reserved_risk": reserved_risk,
                "available_capital": account.starting_capital + realized_pnl - reserved_risk,
                "open_positions": len(open_trades),
            }
        return snapshot


def _lookup_mark(trade: PaperTrade, marks: Mapping[str, float]) -> float | None:
    for key in (f"{trade.platform_id}:{trade.symbol}", trade.symbol):
        if key in marks:
            value = marks[key]
            if isinstance(value, bool):
                raise ValueError(f"mark for {key} must be numeric")
            return float(value)
    return None


def _empty_metrics() -> dict[str, float | int]:
    return {
        "paper_realized_pnl": 0.0,
        "paper_unrealized_pnl": 0.0,
        "rewards_realized_net": 0.0,
        "rewards_pending_estimate": 0.0,
        "total_costs": 0.0,
        "open_trade_count": 0,
        "closed_trade_count": 0,
        "reward_count": 0,
    }


def _add_money(metrics: dict[str, float | int], key: str, value: float) -> None:
    metrics[key] = float(metrics[key]) + value


def _add_count(metrics: dict[str, float | int], key: str) -> None:
    metrics[key] = int(metrics[key]) + 1


def _normalize_currency(value: str) -> str:
    normalized = value.strip().upper()
    if not re.fullmatch(r"^[A-Z][A-Z0-9._-]{1,15}$", normalized):
        raise ValueError("reporting_currency must be a currency-style code")
    return normalized


def _snapshot_time(
    as_of: datetime | None,
    trades: tuple[PaperTrade, ...],
    rewards: tuple[RewardEntry, ...],
) -> datetime:
    if as_of is not None:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        return as_of.astimezone(UTC)
    return _latest_event_time(trades, rewards) or datetime.now(UTC)


def _latest_event_time(
    trades: tuple[PaperTrade, ...],
    rewards: tuple[RewardEntry, ...],
) -> datetime | None:
    timestamps: list[datetime] = []
    for trade in trades:
        timestamps.append(trade.closed_at or trade.opened_at)
    timestamps.extend(reward.updated_at for reward in rewards)
    return max(timestamps) if timestamps else None
