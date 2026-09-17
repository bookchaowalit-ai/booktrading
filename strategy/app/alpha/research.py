"""Bounded JSONL replay for selective alpha and forward paper evidence."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.alpha.evaluator import SelectiveAlphaEvaluator
from app.alpha.journal import AlphaJournalSummary, DecisionJournal, summarize_records
from app.alpha.models import (
    AlphaEvidence,
    AlphaObservation,
    AlphaSettlement,
    AlphaThesis,
    RiskBudget,
    SettlementProof,
)

ALPHA_FIXTURE_VERSION = 1
MAX_FIXTURE_BYTES = 20 * 1024 * 1024
MAX_FIXTURE_EVENTS = 100_000


class AlphaResearchError(ValueError):
    """Raised when a research fixture is malformed or unsafe to replay."""


@dataclass(frozen=True, slots=True)
class AlphaResearchCase:
    """A thesis, its point-in-time observation, and optional later outcome."""

    case_id: str
    thesis: AlphaThesis
    observation: AlphaObservation
    settlement: AlphaSettlement | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.case_id, str) or not self.case_id.strip():
            raise ValueError("case_id cannot be empty")
        if not isinstance(self.thesis, AlphaThesis) or not isinstance(self.observation, AlphaObservation):
            raise ValueError("case requires AlphaThesis and AlphaObservation")
        if self.thesis.created_at > self.observation.observed_at:
            raise ValueError("thesis cannot be created after its observation")
        if any(item.observed_at > self.observation.observed_at for item in self.thesis.evidence):
            raise ValueError("evidence cannot be observed after its decision quote")
        if self.settlement is not None and not isinstance(self.settlement, AlphaSettlement):
            raise ValueError("settlement must be an AlphaSettlement")
        if self.settlement is not None and self.settlement.settled_at < self.observation.observed_at:
            raise ValueError("settlement cannot precede the observation")


@dataclass(frozen=True, slots=True)
class AlphaResearchConfig:
    """Frozen replay configuration with an explicit forward-evaluation cut."""

    forward_start: datetime
    risk_budget: RiskBudget = field(
        default_factory=lambda: RiskBudget(
            starting_capital=1000.0,
            max_total_risk=100.0,
            max_trade_risk=10.0,
        )
    )
    market_group: str = "prediction_binary"
    strategy_version: str = "prediction_binary_v1"
    min_forward_cases: int = 3
    min_forward_trades: int = 2
    min_forward_settled: int = 2
    max_cases: int = MAX_FIXTURE_EVENTS

    def __post_init__(self) -> None:
        if self.forward_start.tzinfo is None or self.forward_start.utcoffset() is None:
            raise ValueError("forward_start must be timezone-aware")
        if not isinstance(self.risk_budget, RiskBudget):
            raise TypeError("risk_budget must be a RiskBudget")
        market_group = self.market_group.strip().lower()
        strategy_version = self.strategy_version.strip().lower()
        if not market_group or not strategy_version:
            raise ValueError("market_group and strategy_version cannot be empty")
        object.__setattr__(self, "forward_start", self.forward_start.astimezone(UTC))
        object.__setattr__(self, "market_group", market_group)
        object.__setattr__(self, "strategy_version", strategy_version)
        for field_name in ("min_forward_cases", "min_forward_trades", "min_forward_settled", "max_cases"):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        if self.max_cases == 0:
            raise ValueError("max_cases must be positive")


@dataclass(frozen=True, slots=True)
class AlphaResearchReport:
    """Paper-only research result with train and forward slices separated."""

    fixture_version: int
    market_group: str
    strategy_version: str
    forward_start: datetime
    case_count: int
    train_case_count: int
    forward_case_count: int
    train_summary: AlphaJournalSummary
    forward_summary: AlphaJournalSummary
    pending_paper_trade_count: int
    open_risk_at_end: float
    forward_gate: str
    journal_events: tuple[dict[str, Any], ...] = ()

    @property
    def execution_enabled(self) -> bool:
        return False

    def as_dict(self, *, include_journal: bool = False) -> dict[str, Any]:
        payload = {
            "source": "alpha_research_fixture",
            "mode": "offline_selective_alpha_replay",
            "execution_enabled": False,
            "paper_only": True,
            "fixture_version": self.fixture_version,
            "market_group": self.market_group,
            "strategy_version": self.strategy_version,
            "forward_start": self.forward_start.isoformat(),
            "case_count": self.case_count,
            "train_case_count": self.train_case_count,
            "forward_case_count": self.forward_case_count,
            "train": self.train_summary.as_dict(),
            "forward": self.forward_summary.as_dict(),
            "pending_paper_trade_count": self.pending_paper_trade_count,
            "open_risk_at_end": round(self.open_risk_at_end, 10),
            "forward_gate": self.forward_gate,
            "journal_event_count": len(self.journal_events),
        }
        if include_journal:
            payload["journal_events"] = list(self.journal_events)
        return payload


def load_alpha_cases(path: str | Path) -> tuple[AlphaResearchCase, ...]:
    """Load bounded, versioned JSONL without contacting a provider."""

    fixture_path = Path(path)
    try:
        raw_bytes = fixture_path.read_bytes()
    except OSError as exc:
        raise AlphaResearchError(f"cannot read fixture: {fixture_path}") from exc
    if len(raw_bytes) > MAX_FIXTURE_BYTES:
        raise AlphaResearchError("fixture exceeds the maximum byte size")
    try:
        raw_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AlphaResearchError("fixture must be UTF-8") from exc

    cases: list[AlphaResearchCase] = []
    for line_number, line in enumerate(raw_text.splitlines(), start=1):
        if not line.strip():
            continue
        if len(cases) >= MAX_FIXTURE_EVENTS:
            raise AlphaResearchError("fixture exceeds the maximum event count")
        try:
            payload = json.loads(line)
            cases.append(_parse_case(payload, line_number))
        except AlphaResearchError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise AlphaResearchError(f"invalid alpha case on line {line_number}: {exc}") from exc
    return tuple(cases)


def run_alpha_research(
    cases: Sequence[AlphaResearchCase],
    *,
    config: AlphaResearchConfig,
    evaluator: SelectiveAlphaEvaluator | None = None,
) -> AlphaResearchReport:
    """Replay decisions chronologically and score only later outcome evidence.

    Settlements are never consulted before their timestamp.  Open paper risk
    therefore affects later decisions in the same replay, while a final
    settlement can be applied after the last observation for measurement only.
    """

    if len(cases) > config.max_cases:
        raise AlphaResearchError("case sequence exceeds max_cases")
    sequence = tuple(cases)
    active_evaluator = evaluator or SelectiveAlphaEvaluator(
        config.risk_budget,
        market_group=config.market_group,
        strategy_version=config.strategy_version,
    )
    journal = DecisionJournal()
    active: dict[str, AlphaSettlement | None] = {}
    previous_observed_at: datetime | None = None
    train_case_count = 0
    forward_case_count = 0

    for case in sequence:
        if not isinstance(case, AlphaResearchCase):
            raise AlphaResearchError("cases must contain AlphaResearchCase values")
        observed_at = case.observation.observed_at
        if previous_observed_at is not None and observed_at < previous_observed_at:
            raise AlphaResearchError("cases must be ordered by observation timestamp")
        previous_observed_at = observed_at

        _settle_due(
            journal,
            active,
            observed_at,
        )
        journal.register_thesis(case.thesis)
        open_risk = sum(journal.record_by_id(decision_id).risk_amount for decision_id in active)
        decision = active_evaluator.evaluate(
            case.thesis,
            case.observation,
            open_risk=open_risk,
            open_positions=len(active),
            now=observed_at,
        )
        record = journal.record_decision(decision)
        if observed_at < config.forward_start:
            train_case_count += 1
        else:
            forward_case_count += 1
        if record.is_paper_trade:
            active[record.decision_id] = case.settlement

    _settle_all_with_known_outcomes(journal, active)
    records = journal.records
    train_records = tuple(record for record in records if record.evaluated_at < config.forward_start)
    forward_records = tuple(record for record in records if record.evaluated_at >= config.forward_start)
    train_summary = summarize_records(train_records)
    forward_summary = summarize_records(forward_records)
    pending = sum(record.outcome.value == "pending" for record in records)
    open_risk_at_end = sum(record.risk_amount for record in records if record.outcome.value == "pending")
    forward_gate = _forward_gate(
        forward_case_count=forward_case_count,
        forward_summary=forward_summary,
        min_forward_cases=config.min_forward_cases,
        min_forward_trades=config.min_forward_trades,
        min_forward_settled=config.min_forward_settled,
    )
    return AlphaResearchReport(
        fixture_version=ALPHA_FIXTURE_VERSION,
        market_group=config.market_group,
        strategy_version=config.strategy_version,
        forward_start=config.forward_start,
        case_count=len(sequence),
        train_case_count=train_case_count,
        forward_case_count=forward_case_count,
        train_summary=train_summary,
        forward_summary=forward_summary,
        pending_paper_trade_count=pending,
        open_risk_at_end=open_risk_at_end,
        forward_gate=forward_gate,
        journal_events=journal.export_events(),
    )


def _settle_due(
    journal: DecisionJournal,
    active: dict[str, AlphaSettlement | None],
    observed_at: datetime,
) -> None:
    due = [
        (decision_id, settlement)
        for decision_id, settlement in active.items()
        if settlement is not None and settlement.settled_at <= observed_at
    ]
    for decision_id, settlement in due:
        assert settlement is not None
        journal.settle(decision_id, settlement)
        del active[decision_id]


def _settle_all_with_known_outcomes(
    journal: DecisionJournal,
    active: dict[str, AlphaSettlement | None],
) -> None:
    for decision_id, settlement in tuple(active.items()):
        if settlement is not None:
            journal.settle(decision_id, settlement)
            del active[decision_id]


def _forward_gate(
    *,
    forward_case_count: int,
    forward_summary: AlphaJournalSummary,
    min_forward_cases: int,
    min_forward_trades: int,
    min_forward_settled: int,
) -> str:
    if forward_case_count < min_forward_cases:
        return "INSUFFICIENT_FORWARD_CASES"
    if forward_summary.paper_trade_count < min_forward_trades:
        return "INSUFFICIENT_FORWARD_TRADES"
    if forward_summary.settled_trade_count < min_forward_settled:
        return "INSUFFICIENT_FORWARD_SETTLEMENTS"
    return "PAPER_EVIDENCE_REVIEW_REQUIRED"


def _parse_case(payload: Any, line_number: int) -> AlphaResearchCase:
    if not isinstance(payload, Mapping):
        raise AlphaResearchError(f"line {line_number} must contain an object")
    if payload.get("event_version") != ALPHA_FIXTURE_VERSION:
        raise AlphaResearchError(f"line {line_number} has unsupported event_version")
    if payload.get("event_type") != "alpha_case":
        raise AlphaResearchError(f"line {line_number} has unsupported event_type")
    case_data = _object(payload, "case", line_number)
    case_id = _required_text(case_data, "case_id", line_number)
    if payload.get("event_id") != case_id:
        raise AlphaResearchError(f"line {line_number} event_id does not match case_id")
    thesis_data = _object(case_data, "thesis", line_number)
    evidence_data = thesis_data.get("evidence")
    if not isinstance(evidence_data, Sequence) or isinstance(evidence_data, (str, bytes)):
        raise AlphaResearchError(f"line {line_number} thesis evidence must be a list")
    thesis = AlphaThesis(
        thesis_id=thesis_data["thesis_id"],
        market_group=thesis_data["market_group"],
        platform_id=thesis_data["platform_id"],
        instrument_id=thesis_data["instrument_id"],
        direction=thesis_data["direction"],
        hypothesis=thesis_data["hypothesis"],
        fair_value=thesis_data.get("fair_value"),
        max_entry_price=thesis_data.get("max_entry_price"),
        target_exit_price=thesis_data.get("target_exit_price"),
        invalidation_price=thesis_data.get("invalidation_price"),
        max_loss=thesis_data["max_loss"],
        capital_at_risk=thesis_data["capital_at_risk"],
        confidence=thesis_data["confidence"],
        evidence=tuple(_parse_evidence(item, line_number) for item in evidence_data),
        created_at=_parse_timestamp(thesis_data["created_at"], "created_at", line_number),
        strategy_version=thesis_data["strategy_version"],
        expected_edge=thesis_data.get("expected_edge"),
        target_units=thesis_data.get("target_units", 1.0),
        status=thesis_data.get("status", "candidate"),
        expires_at=(
            None
            if thesis_data.get("expires_at") is None
            else _parse_timestamp(thesis_data["expires_at"], "expires_at", line_number)
        ),
        tags=tuple(thesis_data.get("tags", ())),
        notes=thesis_data.get("notes", ""),
        metadata=thesis_data.get("metadata", {}),
    )
    observation_data = _object(case_data, "observation", line_number)
    observation = AlphaObservation(
        observation_id=observation_data["observation_id"],
        thesis_id=observation_data["thesis_id"],
        platform_id=observation_data["platform_id"],
        instrument_id=observation_data["instrument_id"],
        observed_at=_parse_timestamp(observation_data["observed_at"], "observed_at", line_number),
        price=observation_data["price"],
        cost_per_unit=observation_data.get("cost_per_unit"),
        available_size=observation_data.get("available_size"),
        quote_age_seconds=observation_data.get("quote_age_seconds"),
        market_status=observation_data.get("market_status", "active"),
        metadata=observation_data.get("metadata", {}),
    )
    settlement_data = case_data.get("settlement")
    settlement = None
    if settlement_data is not None:
        if not isinstance(settlement_data, Mapping):
            raise AlphaResearchError(f"line {line_number} settlement must be an object")
        settlement = AlphaSettlement(
            outcome=settlement_data["outcome"],
            realized_pnl=settlement_data["realized_pnl"],
            settled_at=_parse_timestamp(settlement_data["settled_at"], "settled_at", line_number),
            note=settlement_data.get("note", ""),
            evidence=tuple(_parse_settlement_proof(item, line_number) for item in settlement_data.get("evidence", ())),
        )
    return AlphaResearchCase(case_id=case_id, thesis=thesis, observation=observation, settlement=settlement)


def _parse_evidence(payload: Any, line_number: int) -> AlphaEvidence:
    if not isinstance(payload, Mapping):
        raise AlphaResearchError(f"line {line_number} evidence must be an object")
    return AlphaEvidence(
        evidence_id=payload["evidence_id"],
        source=payload["source"],
        observed_at=_parse_timestamp(payload["observed_at"], "evidence.observed_at", line_number),
        summary=payload["summary"],
        source_url=payload.get("source_url"),
        raw_sha256=payload.get("raw_sha256"),
        confidence=payload.get("confidence", 0.0),
        metadata=payload.get("metadata", {}),
    )


def _parse_settlement_proof(payload: Any, line_number: int) -> SettlementProof:
    if not isinstance(payload, Mapping):
        raise AlphaResearchError(f"line {line_number} settlement evidence must be an object")
    return SettlementProof(
        evidence_id=payload["evidence_id"],
        source=payload["source"],
        object_key=payload["object_key"],
        raw_sha256=payload["raw_sha256"],
        source_url=payload["source_url"],
        observed_at=_parse_timestamp(payload["observed_at"], "settlement.evidence.observed_at", line_number),
        summary=payload["summary"],
        metadata=payload.get("metadata", {}),
    )


def _object(payload: Mapping[str, Any], key: str, line_number: int) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise AlphaResearchError(f"line {line_number} requires object field {key}")
    return value


def _required_text(payload: Mapping[str, Any], key: str, line_number: int) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AlphaResearchError(f"line {line_number} requires non-empty {key}")
    return value.strip()


def _parse_timestamp(value: Any, field_name: str, line_number: int) -> datetime:
    if not isinstance(value, str):
        raise AlphaResearchError(f"line {line_number} {field_name} must be an ISO timestamp")
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AlphaResearchError(f"line {line_number} {field_name} is invalid") from exc
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise AlphaResearchError(f"line {line_number} {field_name} requires a timezone")
    return timestamp.astimezone(UTC)
