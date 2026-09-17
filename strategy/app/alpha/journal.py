"""Idempotent decision journal and outcome statistics for alpha research."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any

from app.alpha.models import (
    AlphaAction,
    AlphaDecision,
    AlphaOutcome,
    AlphaSettlement,
    AlphaThesis,
    DecisionRecord,
)


class JournalConflictError(ValueError):
    """Raised when an immutable journal identity is reused with new data."""


@dataclass(frozen=True, slots=True)
class AlphaJournalSummary:
    """Metrics that distinguish selected trades from rejected opportunities."""

    decision_count: int
    paper_trade_count: int
    wait_count: int
    watch_count: int
    not_taken_count: int
    settled_trade_count: int
    pending_paper_trade_count: int
    wins: int
    losses: int
    voids: int
    realized_pnl: float
    win_rate: float | None
    max_drawdown: float
    average_expected_edge: float | None
    reason_counts: dict[str, int]

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision_count": self.decision_count,
            "paper_trade_count": self.paper_trade_count,
            "wait_count": self.wait_count,
            "watch_count": self.watch_count,
            "not_taken_count": self.not_taken_count,
            "settled_trade_count": self.settled_trade_count,
            "pending_paper_trade_count": self.pending_paper_trade_count,
            "wins": self.wins,
            "losses": self.losses,
            "voids": self.voids,
            "realized_pnl": round(self.realized_pnl, 10),
            "win_rate": None if self.win_rate is None else round(self.win_rate, 10),
            "max_drawdown": round(self.max_drawdown, 10),
            "average_expected_edge": (
                None if self.average_expected_edge is None else round(self.average_expected_edge, 10)
            ),
            "reason_counts": dict(self.reason_counts),
        }


class DecisionJournal:
    """An in-memory, idempotent journal suitable for lake persistence.

    The journal records every decision, including ``WAIT`` and ``WATCH``.  A
    rejected candidate is evidence too: without it, a later backtest cannot
    tell whether the strategy actually passed on the opportunity.
    """

    EVENT_VERSION = 1

    def __init__(self) -> None:
        self._theses: dict[str, AlphaThesis] = {}
        self._records: dict[str, DecisionRecord] = {}
        self._decisions: dict[str, AlphaDecision] = {}

    @property
    def theses(self) -> tuple[AlphaThesis, ...]:
        return tuple(self._theses[key] for key in sorted(self._theses))

    @property
    def records(self) -> tuple[DecisionRecord, ...]:
        return tuple(sorted(self._records.values(), key=lambda item: (item.evaluated_at, item.decision_id)))

    def record_by_id(self, decision_id: str) -> DecisionRecord:
        """Return one immutable record for replay bookkeeping."""

        try:
            return self._records[decision_id]
        except KeyError as exc:
            raise KeyError(f"unknown decision_id: {decision_id}") from exc

    def register_thesis(self, thesis: AlphaThesis) -> AlphaThesis:
        if not isinstance(thesis, AlphaThesis):
            raise TypeError("thesis must be an AlphaThesis")
        existing = self._theses.get(thesis.thesis_id)
        if existing is not None:
            if existing == thesis:
                return existing
            raise JournalConflictError(f"thesis_id already contains different data: {thesis.thesis_id}")
        self._theses[thesis.thesis_id] = thesis
        return thesis

    def record_decision(self, decision: AlphaDecision, *, thesis: AlphaThesis | None = None) -> DecisionRecord:
        if not isinstance(decision, AlphaDecision):
            raise TypeError("decision must be an AlphaDecision")
        if thesis is not None:
            self.register_thesis(thesis)
        registered = self._theses.get(decision.thesis_id)
        if registered is not None and (
            registered.platform_id != decision.platform_id
            or registered.instrument_id != decision.instrument_id
            or registered.strategy_version != decision.strategy_version
        ):
            raise JournalConflictError(f"decision does not match registered thesis: {decision.thesis_id}")
        record = DecisionRecord.from_decision(decision)
        existing = self._records.get(record.decision_id)
        if existing is not None:
            if self._decisions[record.decision_id] == decision:
                return existing
            raise JournalConflictError(f"decision_id already contains different data: {record.decision_id}")
        self._records[record.decision_id] = record
        self._decisions[record.decision_id] = decision
        return record

    def settle(self, decision_id: str, settlement: AlphaSettlement) -> DecisionRecord:
        if not isinstance(settlement, AlphaSettlement):
            raise TypeError("settlement must be an AlphaSettlement")
        record = self._records.get(decision_id)
        if record is None:
            raise KeyError(f"unknown decision_id: {decision_id}")
        if not record.is_paper_trade:
            raise ValueError("only TRADE_PAPER decisions can be settled")
        if record.is_settled:
            expected = (
                record.outcome is settlement.outcome
                and record.realized_pnl == settlement.realized_pnl
                and record.settled_at == settlement.settled_at
                and record.note == settlement.note
                and record.settlement_evidence == settlement.evidence
            )
            if expected:
                return record
            raise JournalConflictError(f"decision_id already has a different settlement: {decision_id}")
        updated = replace(
            record,
            outcome=settlement.outcome,
            realized_pnl=settlement.realized_pnl,
            settled_at=settlement.settled_at,
            note=settlement.note,
            settlement_evidence=settlement.evidence,
        )
        self._records[decision_id] = updated
        return updated

    def summary(self) -> AlphaJournalSummary:
        return summarize_records(self.records)

    def export_events(self) -> tuple[dict[str, Any], ...]:
        """Return versioned, secret-free events for lake persistence."""

        events: list[dict[str, Any]] = []
        for thesis in self.theses:
            events.append(
                {
                    "event_version": self.EVENT_VERSION,
                    "event_type": "alpha_thesis",
                    "event_id": thesis.thesis_id,
                    "thesis": thesis.as_dict(),
                }
            )
        for record in self.records:
            events.append(
                {
                    "event_version": self.EVENT_VERSION,
                    "event_type": "alpha_decision",
                    "event_id": record.decision_id,
                    "decision": record.as_dict(),
                    "evaluation": self._decisions[record.decision_id].as_dict(),
                }
            )
        return tuple(events)


def summarize_records(records: tuple[DecisionRecord, ...] | list[DecisionRecord]) -> AlphaJournalSummary:
    """Calculate deterministic metrics for a selected slice of journal rows."""

    ordered = tuple(sorted(records, key=lambda item: (item.evaluated_at, item.decision_id)))
    paper_trades = tuple(item for item in ordered if item.action is AlphaAction.TRADE_PAPER)
    settled = tuple(item for item in paper_trades if item.is_settled)
    wins = sum(item.outcome is AlphaOutcome.WIN for item in settled)
    losses = sum(item.outcome is AlphaOutcome.LOSS for item in settled)
    voids = sum(item.outcome is AlphaOutcome.VOID for item in settled)
    realized_pnl = sum(item.realized_pnl or 0.0 for item in settled)
    decided = wins + losses
    cumulative = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for item in sorted(settled, key=lambda row: (row.settled_at or row.evaluated_at, row.decision_id)):
        cumulative += item.realized_pnl or 0.0
        peak = max(peak, cumulative)
        max_drawdown = max(max_drawdown, peak - cumulative)
    edges = [item.expected_edge for item in paper_trades if item.expected_edge is not None]
    action_counts = Counter(item.action.value for item in ordered)
    reason_counts = Counter(reason for item in ordered for reason in item.reason_codes)
    return AlphaJournalSummary(
        decision_count=len(ordered),
        paper_trade_count=len(paper_trades),
        wait_count=action_counts[AlphaAction.WAIT.value],
        watch_count=action_counts[AlphaAction.WATCH.value],
        not_taken_count=sum(item.outcome is AlphaOutcome.NOT_TAKEN for item in ordered),
        settled_trade_count=len(settled),
        pending_paper_trade_count=sum(item.outcome is AlphaOutcome.PENDING for item in paper_trades),
        wins=wins,
        losses=losses,
        voids=voids,
        realized_pnl=realized_pnl,
        win_rate=(wins / decided if decided else None),
        max_drawdown=max_drawdown,
        average_expected_edge=(sum(edges) / len(edges) if edges else None),
        reason_counts=dict(sorted(reason_counts.items())),
    )


def as_of_records(records: tuple[DecisionRecord, ...], as_of: datetime) -> tuple[DecisionRecord, ...]:
    """Return a point-in-time slice without exposing outcomes settled later."""

    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")
    cutoff = as_of.astimezone(UTC)
    visible: list[DecisionRecord] = []
    for record in records:
        if record.evaluated_at > cutoff:
            continue
        if record.settled_at is not None and record.settled_at > cutoff:
            visible.append(
                replace(
                    record,
                    outcome=AlphaOutcome.PENDING,
                    realized_pnl=None,
                    settled_at=None,
                    note="",
                    settlement_evidence=(),
                )
            )
        else:
            visible.append(record)
    return tuple(visible)
