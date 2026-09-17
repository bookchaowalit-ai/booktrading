"""Read-only conversion from the legacy AirdropTracker into reward entries."""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.portfolio.ledger import PaperPortfolioLedger
from app.portfolio.models import RewardEntry


class AirdropRewardConversionError(ValueError):
    """Raised when an airdrop task cannot become a governed reward entry."""


@dataclass(frozen=True, slots=True)
class AirdropRewardConversionReport:
    """Converted entries plus safe quarantine metadata for invalid tasks."""

    entries: tuple[RewardEntry, ...]
    quarantined: tuple[dict[str, str], ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": "airdrop_tracker",
            "mode": "read_only_reward_conversion",
            "execution_enabled": False,
            "converted_count": len(self.entries),
            "quarantined_count": len(self.quarantined),
            "entries": [entry.as_dict() for entry in self.entries],
            "quarantined": list(self.quarantined),
        }


def convert_airdrop_tasks(
    tasks: Iterable[Mapping[str, Any] | Any],
    *,
    now: datetime | None = None,
) -> AirdropRewardConversionReport:
    """Convert tracker rows without fetching, claiming, or mutating rewards.

    Legacy ``completed`` means the task was completed, so it maps to
    ``eligible``.  It becomes realized only when an explicit claimed status,
    realized value, and evidence are supplied later.
    """

    conversion_time = _normalise_time(now or datetime.now(UTC), "now")
    entries: list[RewardEntry] = []
    quarantined: list[dict[str, str]] = []
    for index, task in enumerate(tasks):
        task_data: Mapping[str, Any] | None = None
        try:
            task_data = _task_mapping(task)
            entries.append(_task_to_reward(task_data, conversion_time, index))
        except (TypeError, ValueError, KeyError) as exc:
            task_id = _safe_task_id(task_data, index) if isinstance(task_data, Mapping) else f"row-{index}"
            quarantined.append(
                {
                    "record_index": str(index),
                    "task_id": task_id,
                    "reason": str(exc),
                }
            )
    return AirdropRewardConversionReport(tuple(entries), tuple(quarantined))


async def sync_airdrop_tracker_to_ledger(
    tracker: Any,
    ledger: PaperPortfolioLedger,
    *,
    now: datetime | None = None,
) -> AirdropRewardConversionReport:
    """Read current tracker tasks and idempotently add valid reward entries."""

    tasks = await tracker.list_tasks()
    report = convert_airdrop_tasks(tasks, now=now)
    for entry in report.entries:
        ledger.record_reward(entry)
    return report


def _task_to_reward(task: Mapping[str, Any], now: datetime, index: int) -> RewardEntry:
    task_id = _safe_task_id(task, index)
    name = _required_text(task, "name")
    status = _status(task.get("status", "not_started"))
    realized_value = _explicit_number(task.get("realized_value"), "realized_value")
    if status == "claimed" and realized_value is None:
        raise AirdropRewardConversionError("claimed task requires explicit realized_value")

    estimated_raw = task.get("estimated_value")
    estimated_value = _estimate_lower_bound(estimated_raw)
    actual_cost = _explicit_number(task.get("actual_cost"), "actual_cost")
    if actual_cost is None:
        legacy_cost = task.get("cost")
        if legacy_cost is None or legacy_cost == "" or isinstance(legacy_cost, str):
            actual_cost = 0.0
        else:
            actual_cost = _explicit_number(legacy_cost, "cost") or 0.0
    created_at = _optional_timestamp(task.get("created_at"), now, "created_at")
    updated_at = _optional_timestamp(task.get("updated_at"), created_at, "updated_at")
    notes = _conversion_notes(task, estimated_raw)
    return RewardEntry(
        reward_id=f"airdrop-tracker-{task_id}",
        platform_id=str(task.get("platform_id") or "airdrop_rewards"),
        program=name,
        kind=str(task.get("kind") or "airdrop"),
        status=status,
        estimated_value=estimated_value,
        realized_value=realized_value,
        cost=actual_cost,
        currency=str(task.get("currency") or "USD"),
        deadline=_optional_timestamp(task.get("deadline"), None, "deadline"),
        source_url=_optional_url(task.get("url")),
        evidence_ref=str(task.get("evidence_ref") or f"airdrop_tracker:{task_id}"),
        wallet_scope=str(task.get("wallet_scope") or "default"),
        account_scope=task.get("account_scope"),
        notes=notes,
        created_at=created_at,
        updated_at=updated_at,
    )


def _task_mapping(task: Any) -> Mapping[str, Any]:
    if isinstance(task, Mapping):
        return task
    to_dict = getattr(task, "to_dict", None)
    if callable(to_dict):
        mapped = to_dict()
        if isinstance(mapped, Mapping):
            return mapped
    raise AirdropRewardConversionError("task must be a mapping or expose to_dict()")


def _safe_task_id(task: Mapping[str, Any], index: int) -> str:
    value = task.get("task_id")
    if not isinstance(value, str) or not value.strip():
        return f"row-{index}"
    return value.strip()[:128]


def _required_text(task: Mapping[str, Any], key: str) -> str:
    value = task.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AirdropRewardConversionError(f"{key} is required")
    return value.strip()


def _status(value: Any) -> str:
    statuses = {
        "not_started": "candidate",
        "candidate": "candidate",
        "in_progress": "in_progress",
        "eligible": "eligible",
        "completed": "eligible",
        "claimed": "claimed",
        "expired": "expired",
        "rejected": "rejected",
    }
    normalized = str(value or "").strip().lower()
    if normalized not in statuses:
        raise AirdropRewardConversionError(f"unsupported tracker status: {normalized or 'empty'}")
    return statuses[normalized]


def _explicit_number(value: Any, field_name: str) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AirdropRewardConversionError(f"{field_name} must be numeric when supplied")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise AirdropRewardConversionError(f"{field_name} must be finite and non-negative")
    return number


def _estimate_lower_bound(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise AirdropRewardConversionError("estimated_value cannot be boolean")
    if isinstance(value, (int, float)):
        return _explicit_number(value, "estimated_value")
    if not isinstance(value, str):
        raise AirdropRewardConversionError("estimated_value must be text or numeric")
    matches = re.findall(r"(?<!\d)(\d+(?:\.\d+)?)", value.replace(",", ""))
    if not matches:
        return None
    number = float(matches[0])
    if not math.isfinite(number):
        raise AirdropRewardConversionError("estimated_value is not finite")
    return number


def _optional_timestamp(value: Any, fallback: datetime | None, field_name: str) -> datetime | None:
    if value is None or value == "":
        return fallback
    if not isinstance(value, str):
        raise AirdropRewardConversionError(f"{field_name} must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AirdropRewardConversionError(f"{field_name} is invalid") from exc
    return _normalise_time(parsed, field_name)


def _normalise_time(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise AirdropRewardConversionError(f"{field_name} must include a timezone")
    return value.astimezone(UTC)


def _optional_url(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise AirdropRewardConversionError("url must be an absolute HTTP(S) URL")
    return value


def _conversion_notes(task: Mapping[str, Any], estimated_raw: Any) -> str:
    parts = ["source=airdrop_tracker", "tracker_record_is_source_evidence_only"]
    chain = task.get("chain")
    if chain:
        parts.append(f"chain={str(chain)[:80]}")
    if estimated_raw not in (None, ""):
        parts.append(f"estimated_value_text={str(estimated_raw)[:120]}")
    cost_text = task.get("cost")
    if isinstance(cost_text, str) and cost_text.strip():
        parts.append(f"cost_text={cost_text.strip()[:120]}")
    if task.get("notes"):
        parts.append(f"legacy_notes={str(task['notes'])[:120]}")
    return "; ".join(parts)
