"""Lake-first landing for World Markets source responses."""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.market_intel.onchain_landing import (
    LandingConflictError,
    ObjectNotFound,
    ObjectStoreError,
    OnchainLandingWriter,
)

WORLD_SOURCE = "world_xyz"
WORLD_DATASET = "world_markets"
LANDING_SCHEMA_VERSION = "1"
BRONZE_SCHEMA_VERSION = "1"
BRONZE_DOMAIN = "market_intelligence"
CONTENT_TYPE = "application/json"
PRIVACY_CLASS = "public"
RETENTION_CLASS = "market_data"
BRONZE_COLUMNS = (
    "event_id",
    "source",
    "source_record_id",
    "domain",
    "dataset",
    "schema_version",
    "received_at",
    "event_time",
    "content_type",
    "raw_object_key",
    "raw_sha256",
    "payload_json",
    "metadata_json",
    "ingest_run_id",
    "privacy_class",
    "retention_class",
)


class WorldLandingWriter:
    """Write immutable raw JSON, Bronze Parquet, and a lineage manifest.

    The underlying object-store implementation is shared with the existing
    Solana landing pilot, but all World objects use their own source and
    dataset prefixes.  Cloud writes remain fail-closed by that shared store.
    """

    def __init__(self, root: str | os.PathLike[str], *, dataset: str | None = None) -> None:
        self._writer = OnchainLandingWriter(root, dataset=dataset or WORLD_DATASET)
        self.uri = str(root)
        self.dataset = self._writer.dataset

    @classmethod
    def from_env(cls) -> WorldLandingWriter | None:
        value = os.getenv("WORLD_MARKETS_LANDING_URI", "").strip() or os.getenv("WORLD_MARKETS_LANDING_DIR", "").strip()
        if not value:
            return None
        return cls(value, dataset=os.getenv("WORLD_MARKETS_LANDING_DATASET") or WORLD_DATASET)

    def list_keys(self, prefix: str = "") -> list[str]:
        return self._writer.list_keys(prefix)

    def write_snapshot(
        self,
        raw: bytes | str,
        *,
        endpoint: str,
        record_type: str = "events",
        request_params: Mapping[str, Any] | None = None,
        received_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Persist one exact provider response exactly once."""

        raw_bytes = raw.encode("utf-8") if isinstance(raw, str) else bytes(raw)
        if not raw_bytes:
            raise ObjectStoreError("World landing cannot persist an empty response")
        endpoint_path = _safe_endpoint(endpoint)
        record_component = _safe_component(record_type, fallback="events")
        raw_sha256 = hashlib.sha256(raw_bytes).hexdigest()
        event_id = f"world-{record_component}-{raw_sha256[:32]}"
        manifest_key = (
            f"control/manifests/source={WORLD_SOURCE}/dataset={self.dataset}/"
            f"schema_version={LANDING_SCHEMA_VERSION}/event_id={event_id}.json"
        )
        checkpoint_key = (
            f"control/checkpoints/source={WORLD_SOURCE}/dataset={self.dataset}/"
            f"schema_version={LANDING_SCHEMA_VERSION}/event_id={event_id}.json"
        )

        existing = self._read_json(manifest_key)
        if existing is not None:
            _validate_manifest(existing, event_id=event_id, raw_sha256=raw_sha256)
            raw_ref = existing.get("raw") if isinstance(existing.get("raw"), Mapping) else {}
            bronze_ref = existing.get("bronze") if isinstance(existing.get("bronze"), Mapping) else {}
            raw_key = str(raw_ref.get("key") or existing.get("raw_object_key") or "")
            bronze_key = str(bronze_ref.get("key") or "")
            if not raw_key or not bronze_key:
                raise ObjectStoreError("World landing manifest is missing immutable object references")
            return {
                "status": "existing",
                "event_id": event_id,
                "raw_key": raw_key,
                "bronze_key": bronze_key,
                "manifest_key": manifest_key,
                "checkpoint_key": checkpoint_key,
                "raw_sha256": raw_sha256,
                "bronze_sha256": str(existing["bronze"]["sha256"]),
                "raw_existed": True,
                "bronze_existed": True,
                "manifest_existed": True,
                "checkpoint_existed": True,
            }

        checkpoint = self._read_json(checkpoint_key)
        checkpoint_existed = checkpoint is not None
        if checkpoint is not None:
            if checkpoint.get("raw_sha256") != raw_sha256:
                raise LandingConflictError("World landing checkpoint conflict")
            raw_key = str(checkpoint.get("raw_key") or "")
            bronze_key = str(checkpoint.get("bronze_key") or "")
            if not raw_key or not bronze_key or event_id not in raw_key or event_id not in bronze_key:
                raise LandingConflictError("World landing checkpoint object lineage conflict")
            stable_received_at = str(checkpoint.get("received_at") or "")
            if not stable_received_at:
                raise ObjectStoreError("World landing checkpoint is missing received_at")
        else:
            event_date = _event_date(received_at)
            raw_key = (
                f"landing/source={WORLD_SOURCE}/dataset={self.dataset}/schema_version={LANDING_SCHEMA_VERSION}/"
                f"event_date={event_date}/event_id={event_id}.json"
            )
            bronze_key = (
                f"bronze/domain={BRONZE_DOMAIN}/dataset={self.dataset}/schema_version={BRONZE_SCHEMA_VERSION}/"
                f"event_date={event_date}/source={WORLD_SOURCE}/part-{event_id}.parquet"
            )
            stable_received_at = _iso(received_at or datetime.now(UTC))
            checkpoint = {
                "checkpoint_version": "1",
                "event_id": event_id,
                "source": WORLD_SOURCE,
                "dataset": self.dataset,
                "schema_version": LANDING_SCHEMA_VERSION,
                "received_at": stable_received_at,
                "event_date": event_date,
                "raw_key": raw_key,
                "raw_sha256": raw_sha256,
                "bronze_key": bronze_key,
                "privacy_class": PRIVACY_CLASS,
                "retention_class": RETENTION_CLASS,
            }
            self._writer.put_object_bytes(
                checkpoint_key,
                _canonical_json_bytes(checkpoint),
                content_type=CONTENT_TYPE,
            )

        metadata = _redact_metadata(
            {
                "endpoint": endpoint_path,
                "request_params": dict(request_params or {}),
                "record_type": record_component,
            }
        )
        payload_json = raw_bytes.decode("utf-8")
        bronze_bytes = _bronze_bytes(
            payload_json,
            event_id=event_id,
            dataset=self.dataset,
            raw_key=raw_key,
            raw_sha256=raw_sha256,
            received_at=stable_received_at,
            metadata=metadata,
        )
        raw_result = self._writer.put_object_bytes(raw_key, raw_bytes, content_type=CONTENT_TYPE)
        bronze_result = self._writer.put_object_bytes(
            bronze_key,
            bronze_bytes,
            content_type="application/vnd.apache.parquet",
        )
        manifest = {
            "manifest_version": "1",
            "event_id": event_id,
            "source": WORLD_SOURCE,
            "dataset": self.dataset,
            "schema_version": LANDING_SCHEMA_VERSION,
            "bronze_schema_version": BRONZE_SCHEMA_VERSION,
            "received_at": stable_received_at,
            "event_time": stable_received_at,
            "record_type": record_component,
            "endpoint": endpoint_path,
            "content_type": CONTENT_TYPE,
            "privacy_class": PRIVACY_CLASS,
            "retention_class": RETENTION_CLASS,
            "checkpoint_key": checkpoint_key,
            "raw_object_key": raw_key,
            "raw_sha256": raw_sha256,
            "raw": {"key": raw_key, "sha256": raw_sha256, "bytes": len(raw_bytes)},
            "bronze": {
                "key": bronze_key,
                "sha256": bronze_result.sha256,
                "bytes": len(bronze_bytes),
                "columns": list(BRONZE_COLUMNS),
            },
            "metadata": metadata,
        }
        manifest_result = self._writer.put_object_bytes(
            manifest_key,
            _canonical_json_bytes(manifest),
            content_type=CONTENT_TYPE,
        )
        return {
            "status": "existing" if manifest_result.existed else "written",
            "event_id": event_id,
            "raw_key": raw_key,
            "bronze_key": bronze_key,
            "manifest_key": manifest_key,
            "checkpoint_key": checkpoint_key,
            "raw_sha256": raw_result.sha256,
            "bronze_sha256": bronze_result.sha256,
            "raw_existed": raw_result.existed,
            "bronze_existed": bronze_result.existed,
            "manifest_existed": manifest_result.existed,
            "checkpoint_existed": checkpoint_existed,
        }

    def _read_json(self, key: str) -> dict[str, Any] | None:
        try:
            raw = self._writer.get_object_bytes(key)
        except ObjectNotFound:
            return None
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ObjectStoreError(f"World landing control object is invalid JSON: {key}") from exc
        if not isinstance(value, dict):
            raise ObjectStoreError(f"World landing control object is not an object: {key}")
        return value


def _bronze_bytes(
    payload_json: str,
    *,
    event_id: str,
    dataset: str,
    raw_key: str,
    raw_sha256: str,
    received_at: str,
    metadata: Mapping[str, Any],
) -> bytes:
    try:
        import pyarrow as pa
        import pyarrow.parquet as parquet
    except ImportError as exc:  # pragma: no cover - dependency is pinned in the image
        raise ObjectStoreError("World Bronze Parquet requires pyarrow in the strategy image") from exc
    row = {
        "event_id": event_id,
        "source": WORLD_SOURCE,
        "source_record_id": event_id,
        "domain": BRONZE_DOMAIN,
        "dataset": dataset,
        "schema_version": BRONZE_SCHEMA_VERSION,
        "received_at": received_at,
        "event_time": received_at,
        "content_type": CONTENT_TYPE,
        "raw_object_key": raw_key,
        "raw_sha256": raw_sha256,
        "payload_json": payload_json,
        "metadata_json": json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        "ingest_run_id": event_id,
        "privacy_class": PRIVACY_CLASS,
        "retention_class": RETENTION_CLASS,
    }
    schema = pa.schema([(column, pa.string()) for column in BRONZE_COLUMNS])
    table = pa.Table.from_pylist([row], schema=schema)
    sink = io.BytesIO()
    parquet.write_table(table, sink, compression="zstd", version="2.6", use_dictionary=False)
    return sink.getvalue()


def _validate_manifest(manifest: Mapping[str, Any], *, event_id: str, raw_sha256: str) -> None:
    raw = manifest.get("raw") if isinstance(manifest.get("raw"), Mapping) else {}
    bronze = manifest.get("bronze") if isinstance(manifest.get("bronze"), Mapping) else {}
    if manifest.get("event_id") != event_id:
        raise LandingConflictError("World landing manifest event conflict")
    if (
        manifest.get("raw_sha256") is not None
        and manifest.get("raw_sha256") != raw_sha256
        and raw.get("sha256") != raw_sha256
    ):
        raise LandingConflictError("World landing manifest raw checksum conflict")
    raw_key = raw.get("key") or manifest.get("raw_object_key")
    if not raw_key or raw.get("sha256") != raw_sha256:
        raise LandingConflictError("World landing manifest raw lineage conflict")
    if not bronze.get("key") or not bronze.get("sha256"):
        raise LandingConflictError("World landing manifest Bronze lineage conflict")


def _redact_metadata(value: Any, *, key_name: str = "") -> Any:
    sensitive = ("authorization", "api_key", "apikey", "password", "secret", "token", "cookie")
    if any(part in key_name.lower() for part in sensitive):
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {str(key): _redact_metadata(item, key_name=str(key)) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact_metadata(item, key_name=key_name) for item in value]
    return value


def _safe_endpoint(value: str) -> str:
    parsed = urlparse(str(value))
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or not str(value).startswith("/"):
        raise ObjectStoreError("World landing endpoint must be a relative path without query parameters")
    if ".." in Path(value).parts:
        raise ObjectStoreError("World landing endpoint cannot contain parent traversal")
    return value


def _safe_component(value: str, *, fallback: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value).strip())
    return clean[:80] or fallback


def _event_date(value: datetime | None) -> str:
    return (value or datetime.now(UTC)).astimezone(UTC).date().isoformat()


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
