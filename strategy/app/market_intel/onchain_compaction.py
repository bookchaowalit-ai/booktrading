"""Bounded, immutable Bronze compaction for Solana on-chain observations.

Compaction is deliberately separate from ingestion. It reads immutable
per-event Bronze parts, validates the shared envelope, writes one new
``bronze_compacted/`` Parquet part, and commits a control manifest last. Source
parts are never edited or deleted, so a failed run can be retried safely and
readers can choose the compacted manifest explicitly.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import tempfile
from datetime import UTC, datetime
from typing import Any

from app.market_intel.onchain_landing import (
    BRONZE_COLUMNS,
    BRONZE_DOMAIN,
    BRONZE_SCHEMA_VERSION,
    CONTENT_TYPE,
    LANDING_SOURCE,
    LandingConflictError,
    ObjectNotFound,
    ObjectStoreError,
    OnchainLandingWriter,
    PutResult,
    _canonical_json_bytes,
)

DEFAULT_MIN_PARTS = 2
DEFAULT_MAX_PARTS = 1000
DEFAULT_MAX_INPUT_BYTES = 512 * 1024 * 1024
COMPACTION_SCHEMA_VERSION = "1"


class BronzeCompactionError(ObjectStoreError):
    """Raised when a Bronze compaction plan cannot be committed safely."""


def compact_bronze(
    writer: OnchainLandingWriter,
    *,
    event_date: str,
    apply: bool = False,
    min_parts: int = DEFAULT_MIN_PARTS,
    max_parts: int = DEFAULT_MAX_PARTS,
    max_input_bytes: int = DEFAULT_MAX_INPUT_BYTES,
) -> dict[str, Any]:
    """Plan or commit one bounded date partition without deleting sources."""

    _validate_date(event_date)
    if min_parts < 1:
        raise ValueError("min_parts must be positive")
    if max_parts < min_parts:
        raise ValueError("max_parts must be greater than or equal to min_parts")
    if max_input_bytes < 1:
        raise ValueError("max_input_bytes must be positive")

    source_prefix = _bronze_prefix(writer, event_date)
    source_keys = [
        key for key in writer.list_keys(source_prefix) if key.startswith(source_prefix) and key.endswith(".parquet")
    ]
    source_keys = sorted(source_keys)
    if len(source_keys) < min_parts:
        return {
            "status": "skipped",
            "mode": "apply" if apply else "dry_run",
            "reason": "below_min_parts",
            "event_date": event_date,
            "source_prefix": source_prefix,
            "source_parts": len(source_keys),
            "min_parts": min_parts,
            "deletion_allowed": False,
        }
    if len(source_keys) > max_parts:
        raise BronzeCompactionError(f"Bronze compaction would read {len(source_keys)} parts; max_parts={max_parts}")

    source_refs: list[dict[str, Any]] = []
    tables: list[Any] = []
    total_input_bytes = 0
    for key in source_keys:
        data = writer.get_object_bytes(key)
        total_input_bytes += len(data)
        if total_input_bytes > max_input_bytes:
            raise BronzeCompactionError(
                f"Bronze compaction input exceeds max_input_bytes ({total_input_bytes} > {max_input_bytes})"
            )
        digest = hashlib.sha256(data).hexdigest()
        table = _read_bronze_table(data, key)
        tables.append(table)
        source_refs.append(
            {
                "key": key,
                "sha256": digest,
                "bytes": len(data),
                "rows": table.num_rows,
            }
        )

    combined = _concat_tables(tables)
    output_bytes = _write_parquet(combined)
    output_sha256 = hashlib.sha256(output_bytes).hexdigest()
    compaction_id = hashlib.sha256(
        _canonical_json_bytes(
            {
                "schema_version": COMPACTION_SCHEMA_VERSION,
                "source_parts": source_refs,
            }
        )
    ).hexdigest()
    output_key = _compacted_key(writer, event_date, compaction_id, combined.num_rows)
    manifest_key = _compaction_manifest_key(writer, event_date, compaction_id)
    manifest = {
        "compaction_manifest_version": COMPACTION_SCHEMA_VERSION,
        "compaction_id": compaction_id,
        "source": LANDING_SOURCE,
        "domain": BRONZE_DOMAIN,
        "dataset": writer.dataset,
        "bronze_schema_version": BRONZE_SCHEMA_VERSION,
        "event_date": event_date,
        "created_at": datetime.now(UTC).isoformat(),
        "source_parts": source_refs,
        "output": {
            "key": output_key,
            "sha256": output_sha256,
            "bytes": len(output_bytes),
            "rows": combined.num_rows,
            "columns": list(BRONZE_COLUMNS),
        },
        "privacy_class": "public",
        "retention_class": "market_data",
        "deletion_allowed": False,
        "source_parts_immutable": True,
    }
    result: dict[str, Any] = {
        "status": "planned",
        "mode": "apply" if apply else "dry_run",
        "event_date": event_date,
        "source_prefix": source_prefix,
        "source_parts": len(source_refs),
        "source_rows": combined.num_rows,
        "input_bytes": total_input_bytes,
        "output_key": output_key,
        "output_sha256": output_sha256,
        "output_bytes": len(output_bytes),
        "output_rows": combined.num_rows,
        "manifest_key": manifest_key,
        "deletion_allowed": False,
    }
    if not apply:
        return result

    existing_manifest = _read_json_if_present(writer, manifest_key)
    if existing_manifest is not None:
        _validate_existing_compaction(
            existing_manifest,
            compaction_id=compaction_id,
            output_key=output_key,
            output_sha256=output_sha256,
            source_refs=source_refs,
        )
        verified = verify_compaction_manifest(writer, manifest_key)
        result.update(
            {
                "status": "existing",
                "output_existed": True,
                "manifest_existed": True,
                "manifest_sha256": hashlib.sha256(_canonical_json_bytes(existing_manifest)).hexdigest(),
                "verified": verified["status"] == "verified",
            }
        )
        return result

    output_result = writer.put_object_bytes(
        output_key,
        output_bytes,
        content_type="application/vnd.apache.parquet",
    )
    manifest_bytes = _canonical_json_bytes(manifest)
    try:
        manifest_result = writer.put_object_bytes(
            manifest_key,
            manifest_bytes,
            content_type=CONTENT_TYPE,
        )
    except LandingConflictError:
        concurrent_manifest = _read_json_if_present(writer, manifest_key)
        if concurrent_manifest is None:
            raise
        _validate_existing_compaction(
            concurrent_manifest,
            compaction_id=compaction_id,
            output_key=output_key,
            output_sha256=output_sha256,
            source_refs=source_refs,
        )
        manifest_result = PutResult(
            key=manifest_key,
            existed=True,
            sha256=hashlib.sha256(_canonical_json_bytes(concurrent_manifest)).hexdigest(),
        )
    result.update(
        {
            "status": "existing" if output_result.existed and manifest_result.existed else "written",
            "output_existed": output_result.existed,
            "manifest_existed": manifest_result.existed,
            "manifest_sha256": manifest_result.sha256,
        }
    )
    return result


def _read_json_if_present(
    writer: OnchainLandingWriter,
    key: str,
) -> dict[str, Any] | None:
    try:
        raw = writer.get_object_bytes(key)
    except ObjectNotFound:
        return None
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BronzeCompactionError(f"Control object is invalid JSON: {key}") from exc
    if not isinstance(value, dict):
        raise BronzeCompactionError(f"Control object is not an object: {key}")
    return value


def _validate_existing_compaction(
    manifest: dict[str, Any],
    *,
    compaction_id: str,
    output_key: str,
    output_sha256: str,
    source_refs: list[dict[str, Any]],
) -> None:
    if manifest.get("compaction_id") != compaction_id:
        raise LandingConflictError("Compaction manifest identity changed")
    output = manifest.get("output") if isinstance(manifest.get("output"), dict) else {}
    if output.get("key") != output_key or output.get("sha256") != output_sha256:
        raise LandingConflictError("Compaction manifest output lineage changed")
    existing_refs = manifest.get("source_parts")
    if existing_refs != source_refs:
        raise LandingConflictError("Compaction manifest source lineage changed")


def verify_compaction_manifest(
    writer: OnchainLandingWriter,
    manifest_key: str,
) -> dict[str, Any]:
    """Verify a compacted Parquet object and every immutable input reference."""

    try:
        manifest_bytes = writer.get_object_bytes(manifest_key)
    except ObjectNotFound:
        raise
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BronzeCompactionError("Compaction manifest is not valid UTF-8 JSON") from exc
    if not isinstance(manifest, dict):
        raise BronzeCompactionError("Compaction manifest root must be an object")
    output = manifest.get("output") if isinstance(manifest.get("output"), dict) else {}
    output_key = str(output.get("key") or "")
    expected_output_sha = str(output.get("sha256") or "")
    if not output_key or not expected_output_sha:
        raise BronzeCompactionError("Compaction manifest is missing output lineage")
    output_bytes = writer.get_object_bytes(output_key)
    output_sha = hashlib.sha256(output_bytes).hexdigest()
    if output_sha != expected_output_sha:
        raise LandingConflictError("Compacted output checksum does not match manifest")
    table = _read_bronze_table(output_bytes, output_key)
    if int(output.get("rows", table.num_rows)) != table.num_rows:
        raise BronzeCompactionError("Compacted output row count does not match manifest")
    source_parts = manifest.get("source_parts")
    if not isinstance(source_parts, list) or not source_parts:
        raise BronzeCompactionError("Compaction manifest has no source parts")
    verified_inputs = 0
    for reference in source_parts:
        if not isinstance(reference, dict) or not reference.get("key"):
            raise BronzeCompactionError("Compaction manifest has an invalid source reference")
        source_key = str(reference["key"])
        source_bytes = writer.get_object_bytes(source_key)
        if hashlib.sha256(source_bytes).hexdigest() != str(reference.get("sha256") or ""):
            raise LandingConflictError(f"Compaction source checksum does not match manifest: {source_key}")
        if int(reference.get("rows", -1)) != _read_bronze_table(source_bytes, source_key).num_rows:
            raise BronzeCompactionError(f"Compaction source row count does not match manifest: {source_key}")
        verified_inputs += 1
    return {
        "status": "verified",
        "manifest_key": manifest_key,
        "compaction_id": manifest.get("compaction_id"),
        "event_date": manifest.get("event_date"),
        "source_parts": verified_inputs,
        "output_key": output_key,
        "output_sha256": output_sha,
        "output_rows": table.num_rows,
        "deletion_allowed": manifest.get("deletion_allowed") is True,
        "object_storage_writes": False,
    }


def _bronze_prefix(writer: OnchainLandingWriter, event_date: str) -> str:
    return (
        f"bronze/domain={BRONZE_DOMAIN}/dataset={writer.dataset}/"
        f"schema_version={BRONZE_SCHEMA_VERSION}/event_date={event_date}/source={LANDING_SOURCE}/"
    )


def _compacted_key(
    writer: OnchainLandingWriter,
    event_date: str,
    compaction_id: str,
    rows: int,
) -> str:
    return (
        f"bronze_compacted/domain={BRONZE_DOMAIN}/dataset={writer.dataset}/"
        f"schema_version={BRONZE_SCHEMA_VERSION}/event_date={event_date}/source={LANDING_SOURCE}/"
        f"part-{compaction_id[:32]}-rows-{rows}.parquet"
    )


def _compaction_manifest_key(
    writer: OnchainLandingWriter,
    event_date: str,
    compaction_id: str,
) -> str:
    return (
        f"control/compactions/source={LANDING_SOURCE}/dataset={writer.dataset}/"
        f"schema_version={COMPACTION_SCHEMA_VERSION}/event_date={event_date}/"
        f"compaction_id={compaction_id}.json"
    )


def _validate_date(value: str) -> None:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("event_date must be YYYY-MM-DD")
    try:
        datetime.fromisoformat(value).date()
    except ValueError as exc:
        raise ValueError("event_date must be a valid calendar date") from exc


def _read_bronze_table(data: bytes, key: str) -> Any:
    try:
        import pyarrow.parquet as parquet
    except ImportError as exc:  # pragma: no cover - deployment dependency
        raise BronzeCompactionError("Bronze compaction requires pyarrow") from exc
    try:
        # PyArrow's file-like reader can abort the interpreter after several
        # independent BytesIO reads on some slim Python images. A bounded
        # temporary path keeps the CLI restore/compaction process stable.
        with tempfile.NamedTemporaryFile(suffix=".parquet") as handle:
            handle.write(data)
            handle.flush()
            table = parquet.read_table(handle.name)
    except Exception as exc:
        raise BronzeCompactionError(f"Invalid Bronze Parquet object: {key}") from exc
    if tuple(table.column_names) != BRONZE_COLUMNS:
        raise BronzeCompactionError(
            f"Bronze schema mismatch for {key}: expected {list(BRONZE_COLUMNS)}, got {table.column_names}"
        )
    return table


def _concat_tables(tables: list[Any]) -> Any:
    try:
        import pyarrow as pa
    except ImportError as exc:  # pragma: no cover - deployment dependency
        raise BronzeCompactionError("Bronze compaction requires pyarrow") from exc
    try:
        return pa.concat_tables(tables)
    except Exception as exc:
        raise BronzeCompactionError("Bronze parts could not be concatenated") from exc


def _write_parquet(table: Any) -> bytes:
    try:
        import pyarrow.parquet as parquet
    except ImportError as exc:  # pragma: no cover - deployment dependency
        raise BronzeCompactionError("Bronze compaction requires pyarrow") from exc
    sink = io.BytesIO()
    parquet.write_table(table, sink, compression="zstd", version="2.6", use_dictionary=False)
    return sink.getvalue()


def compact_limits_from_env() -> dict[str, int]:
    """Return bounded compaction limits from environment without network access."""

    return {
        "min_parts": _env_int("SOLANA_DEGEN_COMPACTION_MIN_PARTS", DEFAULT_MIN_PARTS, minimum=1),
        "max_parts": _env_int("SOLANA_DEGEN_COMPACTION_MAX_PARTS", DEFAULT_MAX_PARTS, minimum=1),
        "max_input_bytes": _env_int(
            "SOLANA_DEGEN_COMPACTION_MAX_INPUT_BYTES",
            DEFAULT_MAX_INPUT_BYTES,
            minimum=1,
        ),
    }


def _env_int(name: str, default: int, *, minimum: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value
