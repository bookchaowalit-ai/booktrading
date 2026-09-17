"""Read a committed local World snapshot into an auditable paper decision."""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.alpha.evaluator import SelectiveAlphaEvaluator
from app.alpha.journal import DecisionJournal
from app.alpha.models import AlphaEvidence, AlphaObservation, AlphaThesis
from app.world.client import _event_markets, _extract_events, parse_world_market

MAX_BYTES = 20 * 1024 * 1024


def timestamp(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("timestamp requires timezone")
    return result.astimezone(UTC)


def local_object(root: Path, key: str) -> bytes:
    """Bounded local read; manifest pointers cannot escape the lake root."""
    base = root.resolve()
    if not isinstance(key, str) or Path(key).is_absolute():
        raise ValueError("object key must be relative")
    path = (base / key).resolve()
    if not path.is_relative_to(base) or not path.is_file():
        raise ValueError("object unavailable or outside lake root")
    with path.open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("object exceeds byte limit")
    return data


def checked_object(root: Path, reference: dict) -> bytes:
    data = local_object(root, reference["key"])
    if hashlib.sha256(data).hexdigest() != reference["sha256"]:
        raise ValueError("object checksum mismatch")
    return data


def load_thesis(path: Path) -> AlphaThesis:
    data = json.loads(local_object(path.parent, path.name))
    data["created_at"] = timestamp(data["created_at"])
    if data.get("expires_at"):
        data["expires_at"] = timestamp(data["expires_at"])
    data["evidence"] = tuple(
        AlphaEvidence(**{**item, "observed_at": timestamp(item["observed_at"])}) for item in data["evidence"]
    )
    return AlphaThesis(**data)


@dataclass(frozen=True)
class ReviewedMapping:
    """Exact contract binding and locally available primary evidence."""

    ticker: str
    thesis_sha256: str
    instrument_id: str
    question: str
    resolution_source: str
    close_time: str
    reviewed_at: datetime
    evidence_objects: dict[str, dict]


def evaluate_world_snapshot(
    root: Path,
    manifest_key: str,
    thesis: AlphaThesis,
    mapping: ReviewedMapping,
    evaluator: SelectiveAlphaEvaluator,
    *,
    now: datetime,
    cost_per_unit: float | None,
    open_risk: float,
    open_positions: int,
) -> dict:
    """Verify lineage and binding, then evaluate once; no network or orders.

    Caller must supply current portfolio exposure. Evidence object records have
    key, sha256, published_at and received_at. Their later timestamp must match
    the thesis evidence availability time.
    """
    import pyarrow.parquet as pq

    if now.tzinfo is None or mapping.reviewed_at.tzinfo is None:
        raise ValueError("evaluation and review timestamps require timezones")
    thesis_digest = hashlib.sha256(
        json.dumps(thesis.as_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    if thesis_digest != mapping.thesis_sha256:
        raise ValueError("thesis changed since review")
    manifest = json.loads(local_object(root, manifest_key))
    if (
        manifest.get("source") != "world_xyz"
        or manifest.get("manifest_version") != "1"
        or manifest.get("record_type") != "events"
    ):
        raise ValueError("unsupported World manifest")
    raw = checked_object(root, manifest["raw"])
    bronze = checked_object(root, manifest["bronze"])
    parquet = pq.ParquetFile(io.BytesIO(bronze))
    if parquet.metadata.num_rows != 1 or parquet.metadata.row_group(0).total_byte_size > MAX_BYTES:
        raise ValueError("unexpected Bronze size or row count")
    row = parquet.read().to_pylist()[0]
    received_at = timestamp(manifest["received_at"])
    if (
        row["source"] != "world_xyz"
        or row["event_id"] != manifest["event_id"]
        or row["raw_sha256"] != manifest["raw"]["sha256"]
        or row["raw_object_key"] != manifest["raw"]["key"]
        or timestamp(row["received_at"]) != received_at
        or row["payload_json"].encode("utf-8") != raw
    ):
        raise ValueError("Bronze lineage mismatch")
    if mapping.reviewed_at > received_at or received_at > now:
        raise ValueError("review or snapshot unavailable at decision time")
    if thesis.platform_id != "world_xyz" or thesis.instrument_id != mapping.instrument_id:
        raise ValueError("thesis is not a World contract")
    if set(mapping.evidence_objects) != {item.evidence_id for item in thesis.evidence}:
        raise ValueError("evidence mapping incomplete")
    for evidence in thesis.evidence:
        reference = mapping.evidence_objects[evidence.evidence_id]
        checked_object(root, reference)
        available_at = max(timestamp(reference["published_at"]), timestamp(reference["received_at"]))
        if (
            reference["sha256"] != evidence.raw_sha256
            or not evidence.source_url
            or reference.get("source_url") != evidence.source_url
            or available_at != evidence.observed_at
            or available_at > mapping.reviewed_at
        ):
            raise ValueError("evidence lineage or availability mismatch")
    matches = [
        parse_world_market(item, event=event)
        for event in _extract_events(json.loads(row["payload_json"]))
        for item in _event_markets(event)
        if item.get("ticker") == mapping.ticker
    ]
    if len(matches) != 1:
        raise ValueError("contract missing or duplicated")
    market = matches[0]
    if (
        market.validation_errors
        or market.resolution_errors
        or (market.question or market.title) != mapping.question
        or market.resolution_source != mapping.resolution_source
        or (market.close_time or market.strike_date) != mapping.close_time
    ):
        raise ValueError("contract rules changed or market invalid")
    if timestamp(mapping.close_time) <= now:
        raise ValueError("contract has reached close time")
    side = "yes" if thesis.direction == "buy_yes" else "no"
    ask = getattr(market, f"{side}_ask")
    if ask is None:
        raise ValueError("selected-side executable ask unavailable")
    if market.updated_at is not None and market.updated_at > received_at:
        raise ValueError("quote timestamp is in the future")
    observation = AlphaObservation(
        observation_id="world-" + manifest["raw"]["sha256"][:32],
        thesis_id=thesis.thesis_id,
        platform_id="world_xyz",
        instrument_id=thesis.instrument_id,
        observed_at=received_at,
        price=ask,
        cost_per_unit=cost_per_unit,
        available_size=getattr(market, f"{side}_ask_size"),
        quote_age_seconds=(None if market.updated_at is None else (received_at - market.updated_at).total_seconds()),
        market_status=market.status,
        metadata={"manifest_key": manifest_key, "ticker": market.ticker},
    )
    decision = evaluator.evaluate(thesis, observation, now=now, open_risk=open_risk, open_positions=open_positions)
    journal = DecisionJournal()
    journal.record_decision(decision, thesis=thesis)
    return {
        "mode": "world_snapshot_paper_review",
        "execution_enabled": False,
        "decision": decision.as_dict(),
        "observation": observation.as_dict(),
        "manifest_key": manifest_key,
        "raw_sha256": manifest["raw"]["sha256"],
        "journal_events": journal.export_events(),
    }
