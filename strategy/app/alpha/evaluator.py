"""Fail-closed selective alpha and paper-risk evaluation."""

from __future__ import annotations

import hashlib
import math
from datetime import UTC, datetime

from app.alpha.models import (
    AlphaAction,
    AlphaDecision,
    AlphaObservation,
    AlphaThesis,
    RiskBudget,
    ThesisStatus,
)


class SelectiveAlphaEvaluator:
    """Evaluate a frozen thesis against a single point-in-time observation.

    The evaluator is intentionally narrow: binary YES/NO markets only, no
    parameter optimization, and no execution adapter.  A price that is not
    inside the thesis entry range becomes ``WATCH``; missing or unsafe data
    becomes ``WAIT``.
    """

    def __init__(
        self,
        budget: RiskBudget,
        *,
        market_group: str = "prediction_binary",
        strategy_version: str = "prediction_binary_v1",
    ) -> None:
        if not isinstance(budget, RiskBudget):
            raise TypeError("budget must be a RiskBudget")
        self.budget = budget
        self.market_group = market_group.strip().lower()
        self.strategy_version = strategy_version.strip().lower()
        if not self.market_group or not self.strategy_version:
            raise ValueError("market_group and strategy_version cannot be empty")

    def evaluate(
        self,
        thesis: AlphaThesis,
        observation: AlphaObservation,
        *,
        open_risk: float = 0.0,
        open_positions: int = 0,
        now: datetime | None = None,
    ) -> AlphaDecision:
        """Return a deterministic paper decision without side effects."""

        if not isinstance(thesis, AlphaThesis) or not isinstance(observation, AlphaObservation):
            raise TypeError("thesis and observation must use alpha models")
        open_risk = _nonnegative(open_risk, "open_risk")
        if not isinstance(open_positions, int) or isinstance(open_positions, bool) or open_positions < 0:
            raise ValueError("open_positions must be a non-negative integer")
        evaluated_at = observation.observed_at if now is None else _utc(now, "now")
        hard: list[str] = []
        soft: list[str] = []
        if observation.observed_at > evaluated_at:
            hard.append("future_observation")
        if thesis.created_at > observation.observed_at:
            hard.append("future_thesis")
        if any(item.observed_at > observation.observed_at for item in thesis.evidence):
            hard.append("future_evidence")
        if self.market_group != "prediction_binary":
            hard.append("unsupported_evaluator_group")
        cost = observation.cost_per_unit
        if cost is None:
            hard.append("cost_unknown")
        total_unit_cost = observation.price + (cost or 0.0)
        risk_amount = total_unit_cost * thesis.target_units
        if risk_amount > thesis.max_loss + 1e-9:
            hard.append("thesis_loss_budget_exceeded")
        if risk_amount > thesis.capital_at_risk + 1e-9:
            hard.append("thesis_capital_budget_exceeded")

        if thesis.market_group != self.market_group:
            hard.append("unsupported_market_group")
        if thesis.strategy_version != self.strategy_version:
            hard.append("strategy_version_mismatch")
        if observation.thesis_id != thesis.thesis_id:
            hard.append("thesis_identity_mismatch")
        if observation.platform_id != thesis.platform_id:
            hard.append("platform_identity_mismatch")
        if observation.instrument_id != thesis.instrument_id:
            hard.append("instrument_identity_mismatch")
        if thesis.status not in {ThesisStatus.CANDIDATE, ThesisStatus.ACTIVE}:
            hard.append("thesis_not_active")
        if thesis.expires_at is not None and evaluated_at >= thesis.expires_at:
            hard.append("thesis_expired")
        if observation.market_status != "active":
            hard.append("market_not_active")
        if not thesis.evidence:
            hard.append("evidence_missing")
        if thesis.confidence < self.budget.min_confidence:
            hard.append("confidence_below_threshold")

        if observation.quote_age_seconds is None:
            if self.budget.max_quote_age_seconds >= 0.0:
                hard.append("quote_age_unknown")
        elif (
            observation.quote_age_seconds + max(0.0, (evaluated_at - observation.observed_at).total_seconds())
            > self.budget.max_quote_age_seconds
        ):
            hard.append("stale_quote")

        if self.budget.require_available_size and observation.available_size is None:
            hard.append("available_size_unknown")

        if thesis.fair_value is None:
            hard.append("fair_value_missing")
        if thesis.max_entry_price is None:
            hard.append("max_entry_price_missing")
        if thesis.target_exit_price is None:
            hard.append("target_exit_missing")
        if thesis.invalidation_price is None:
            hard.append("invalidation_missing")

        computed_edge: float | None = None
        if thesis.fair_value is not None and cost is not None:
            computed_edge = thesis.fair_value - total_unit_cost
            if thesis.expected_edge is not None and computed_edge + 1e-9 < thesis.expected_edge:
                soft.append("edge_claim_not_reproduced")
            if computed_edge <= 0.0 or computed_edge < self.budget.min_expected_edge:
                soft.append("edge_below_threshold")

        if thesis.max_entry_price is not None and observation.price > thesis.max_entry_price:
            soft.append("entry_above_max_price")
        if thesis.invalidation_price is not None and observation.price <= thesis.invalidation_price:
            hard.append("invalidation_breached")
        if thesis.target_exit_price is not None and thesis.target_exit_price <= observation.price:
            hard.append("target_not_above_entry")
        if observation.available_size is not None and observation.available_size < thesis.target_units:
            soft.append("insufficient_available_size")

        if risk_amount > self.budget.max_trade_risk:
            hard.append("trade_risk_limit_exceeded")
        if open_risk + risk_amount > self.budget.max_total_risk + 1e-9:
            hard.append("total_risk_budget_exceeded")
        if open_positions >= self.budget.max_open_positions:
            hard.append("open_position_limit_exceeded")

        if hard:
            action = AlphaAction.WAIT
            reasons = tuple(hard + soft)
        elif soft:
            action = AlphaAction.WATCH
            reasons = tuple(soft)
        else:
            action = AlphaAction.TRADE_PAPER
            reasons = ("paper_only_gate_passed", "edge_passed", "entry_price_passed", "risk_budget_passed")

        decision_id = _decision_id(thesis, observation, evaluated_at)
        return AlphaDecision(
            decision_id=decision_id,
            thesis_id=thesis.thesis_id,
            platform_id=thesis.platform_id,
            instrument_id=thesis.instrument_id,
            evaluated_at=evaluated_at,
            action=action,
            reason_codes=reasons,
            observed_price=observation.price,
            expected_edge=computed_edge,
            risk_amount=risk_amount,
            confidence=thesis.confidence,
            strategy_version=self.strategy_version,
            execution_enabled=False,
            metadata={
                "market_group": thesis.market_group,
                "direction": thesis.direction,
                "fair_value": thesis.fair_value,
                "max_entry_price": thesis.max_entry_price,
                "target_exit_price": thesis.target_exit_price,
                "invalidation_price": thesis.invalidation_price,
                "open_risk_before": open_risk,
                "open_positions_before": open_positions,
                "quote_age_seconds": observation.quote_age_seconds,
                "cost_per_unit": cost,
                "target_units": thesis.target_units,
                "risk_basis": "full_purchase_cost_plus_cost_reserve",
            },
        )


def _decision_id(thesis: AlphaThesis, observation: AlphaObservation, evaluated_at: datetime) -> str:
    material = "|".join(
        (
            thesis.thesis_id,
            observation.observation_id,
            thesis.strategy_version,
            evaluated_at.astimezone(UTC).isoformat(),
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]
    return f"alpha-{digest}"


def _utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)


def _nonnegative(value: float, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric") from exc
    if number < 0.0 or not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite and nonnegative")
    return number
