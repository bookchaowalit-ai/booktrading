from __future__ import annotations

import json

import pyarrow.parquet as parquet
import pytest

from app.market_intel.onchain_compaction import (
    BronzeCompactionError,
    compact_bronze,
    verify_compaction_manifest,
)
from app.market_intel.onchain_landing import LandingConflictError, OnchainLandingWriter


def _event(number: int) -> dict[str, object]:
    return {
        "event_id": f"compact-event-{number}",
        "event_type": "token_created",
        "signature": f"compact-signature-{number}",
        "slot": number,
        "program_id": "compact-program",
        "observed_at": f"2026-01-02T00:00:0{number}+00:00",
    }


def test_compaction_plans_then_writes_immutable_output(tmp_path):
    writer = OnchainLandingWriter(tmp_path / "lake")
    for number in (1, 2, 3):
        event = _event(number)
        writer.write_raw(json.dumps(event, sort_keys=True).encode("utf-8"), event)

    plan = compact_bronze(writer, event_date="2026-01-02")
    assert plan["status"] == "planned"
    assert plan["source_parts"] == 3
    assert plan["deletion_allowed"] is False
    assert not list((tmp_path / "lake" / "bronze_compacted").rglob("*.parquet"))

    applied = compact_bronze(writer, event_date="2026-01-02", apply=True)
    assert applied["status"] == "written"
    assert applied["output_rows"] == 3
    output_path = tmp_path / "lake" / applied["output_key"]
    assert output_path.exists()
    assert parquet.read_table(output_path).num_rows == 3

    verified = verify_compaction_manifest(writer, applied["manifest_key"])
    assert verified["status"] == "verified"
    assert verified["source_parts"] == 3
    assert verified["output_rows"] == 3
    assert verified["deletion_allowed"] is False

    retry = compact_bronze(writer, event_date="2026-01-02", apply=True)
    assert retry["status"] == "existing"
    assert retry["verified"] is True
    assert len(list((tmp_path / "lake" / "bronze").rglob("*.parquet"))) == 3


def test_compaction_skips_small_partition_and_bounds_input(tmp_path):
    writer = OnchainLandingWriter(tmp_path)
    event = _event(1)
    writer.write_raw(b"one", event)

    skipped = compact_bronze(writer, event_date="2026-01-02")
    assert skipped["status"] == "skipped"
    assert skipped["reason"] == "below_min_parts"

    event_two = _event(2)
    writer.write_raw(b"two", event_two)
    with pytest.raises(BronzeCompactionError, match="max_input_bytes"):
        compact_bronze(writer, event_date="2026-01-02", max_input_bytes=1)


def test_compaction_detects_changed_manifest_or_output(tmp_path):
    writer = OnchainLandingWriter(tmp_path)
    for number in (1, 2):
        event = _event(number)
        writer.write_raw(json.dumps(event).encode("utf-8"), event)
    applied = compact_bronze(writer, event_date="2026-01-02", apply=True)

    manifest_path = tmp_path / applied["manifest_key"]
    manifest = json.loads(manifest_path.read_text())
    manifest["source_parts"][0]["sha256"] = "changed"
    manifest_path.write_text(json.dumps(manifest))

    with pytest.raises(LandingConflictError, match="source lineage"):
        compact_bronze(writer, event_date="2026-01-02", apply=True)


def test_compaction_validates_schema_before_write(tmp_path):
    writer = OnchainLandingWriter(tmp_path)
    event = _event(1)
    result = writer.write_raw(b"one", event)
    bronze_path = tmp_path / result["bronze_key"]
    bronze_path.write_bytes(b"not parquet")
    event_two = _event(2)
    writer.write_raw(b"two", event_two)

    with pytest.raises(BronzeCompactionError, match="Invalid Bronze Parquet"):
        compact_bronze(writer, event_date="2026-01-02", apply=True)
