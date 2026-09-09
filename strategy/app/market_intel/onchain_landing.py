"""Durable landing and Bronze envelope for raw Solana stream notifications.

The source adapter writes the exact provider frame first, then a stable
Bronze Parquet row and an immutable manifest. ``file://`` is the local pilot;
``s3://`` uses the standard boto3 credential chain for an S3-compatible lake.
No credential is read into a payload, object key, log message, or manifest.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import unquote, urlparse

LANDING_SOURCE = "solana_rpc"
DEFAULT_DATASET = "solana_onchain_events"
LANDING_SCHEMA_VERSION = "2"
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


class ObjectStoreError(RuntimeError):
    """Raised when the configured landing store cannot be used safely."""


class ObjectNotFound(ObjectStoreError):
    """Raised when an immutable lake object is missing."""


class LandingConflictError(ObjectStoreError):
    """Raised when an immutable landing object already contains other bytes."""


@dataclass(frozen=True)
class PutResult:
    key: str
    existed: bool
    sha256: str


class _ImmutableStore(Protocol):
    def put_bytes(self, key: str, data: bytes, *, content_type: str | None = None) -> PutResult: ...

    def get_bytes(self, key: str) -> bytes: ...

    def list_keys(self, prefix: str = "") -> list[str]: ...


class _FileObjectStore:
    """Single-writer local store with create-if-absent object semantics."""

    scheme = "file"

    def __init__(self, root: Path):
        self.root = root

    def put_bytes(self, key: str, data: bytes, *, content_type: str | None = None) -> PutResult:
        key = _safe_key(key)
        digest = hashlib.sha256(data).hexdigest()
        destination = self.root / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
                raise LandingConflictError(f"Immutable landing conflict at {key}")
            return PutResult(key=key, existed=True, sha256=digest)

        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                # A hard link is atomic and never overwrites a racing writer.
                os.link(temporary, destination)
            except FileExistsError:
                if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
                    raise LandingConflictError(f"Immutable landing conflict at {key}") from None
                return PutResult(key=key, existed=True, sha256=digest)
            return PutResult(key=key, existed=False, sha256=digest)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def get_bytes(self, key: str) -> bytes:
        key = _safe_key(key)
        try:
            return (self.root / key).read_bytes()
        except FileNotFoundError as exc:
            raise ObjectNotFound(f"Object not found: {key}") from exc

    def list_keys(self, prefix: str = "") -> list[str]:
        prefix = _safe_prefix(prefix)
        base = self.root / prefix if prefix else self.root
        if not base.exists():
            return []
        return sorted(path.relative_to(self.root).as_posix() for path in base.rglob("*") if path.is_file())


class _S3ObjectStore:
    """S3-compatible immutable store using boto3's normal credential chain."""

    scheme = "s3"

    def __init__(self, uri: str):
        parsed = urlparse(uri)
        if parsed.scheme != "s3" or not parsed.netloc:
            raise ObjectStoreError("An S3 landing URI must look like s3://bucket/prefix")
        if parsed.username or parsed.password:
            raise ObjectStoreError("S3 landing URI must not include credentials")
        self.bucket = parsed.netloc
        self.prefix = _safe_prefix(unquote(parsed.path.strip("/")))
        endpoint = os.getenv("SOLANA_DEGEN_S3_ENDPOINT") or os.getenv("DATA_LAKE_S3_ENDPOINT")
        region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
        if not region and endpoint:
            region = "auto"
        self._endpoint = endpoint
        self._region = region
        self._client: Any | None = None
        self._remote_cloud = not _is_local_endpoint(endpoint)

    def _client_instance(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import boto3
        except ImportError as exc:  # pragma: no cover - exercised in minimal images
            raise ObjectStoreError("s3:// landing requires boto3 in the strategy image") from exc
        kwargs: dict[str, Any] = {}
        if self._region:
            kwargs["region_name"] = self._region
        if self._endpoint:
            kwargs["endpoint_url"] = self._endpoint
        self._client = boto3.client("s3", **kwargs)
        return self._client

    def _full_key(self, key: str) -> str:
        key = _safe_key(key)
        return "/".join(part for part in (self.prefix, key) if part)

    def ensure_write_enabled(self) -> None:
        if self._remote_cloud and not _is_true(os.getenv("DATA_LAKE_CLOUD_WRITE_ENABLED")):
            raise ObjectStoreError(
                "Cloud landing writes are disabled; set DATA_LAKE_CLOUD_WRITE_ENABLED=true for an intentional S3/R2 run"
            )

    def _head(self, key: str) -> dict[str, Any] | None:
        try:
            return self._client_instance().head_object(Bucket=self.bucket, Key=self._full_key(key))
        except Exception as exc:
            if _is_not_found_error(exc):
                return None
            raise ObjectStoreError("S3 landing head request failed") from exc

    def _existing_digest(self, key: str, head: dict[str, Any]) -> str:
        metadata = head.get("Metadata") if isinstance(head, dict) else None
        if isinstance(metadata, dict):
            for name, value in metadata.items():
                if str(name).lower() == "sha256" and value:
                    return str(value).lower()
        return hashlib.sha256(self.get_bytes(key)).hexdigest()

    def put_bytes(self, key: str, data: bytes, *, content_type: str | None = None) -> PutResult:
        key = _safe_key(key)
        digest = hashlib.sha256(data).hexdigest()
        self.ensure_write_enabled()
        head = self._head(key)
        if head is not None:
            if self._existing_digest(key, head) != digest:
                raise LandingConflictError(f"Immutable landing conflict at {key}")
            return PutResult(key=key, existed=True, sha256=digest)
        max_bytes = _max_object_bytes()
        if max_bytes and len(data) > max_bytes:
            raise ObjectStoreError(f"Landing object exceeds SOLANA_DEGEN_MAX_OBJECT_BYTES ({len(data)} > {max_bytes})")
        try:
            self._client_instance().put_object(
                Bucket=self.bucket,
                Key=self._full_key(key),
                Body=data,
                Metadata={"sha256": digest},
                ContentType=content_type or "application/octet-stream",
                IfNoneMatch="*",
            )
        except Exception as exc:
            # A concurrent writer may have won the conditional put. Accept it
            # only after re-reading and matching its checksum.
            if _is_precondition_error(exc):
                existing = self._head(key)
                if existing is not None and self._existing_digest(key, existing) == digest:
                    return PutResult(key=key, existed=True, sha256=digest)
                if existing is not None:
                    raise LandingConflictError(f"Immutable landing conflict at {key}") from None
            raise ObjectStoreError("S3 landing put request failed") from exc
        return PutResult(key=key, existed=False, sha256=digest)

    def get_bytes(self, key: str) -> bytes:
        key = _safe_key(key)
        try:
            response = self._client_instance().get_object(Bucket=self.bucket, Key=self._full_key(key))
            return response["Body"].read()
        except Exception as exc:
            if _is_not_found_error(exc):
                raise ObjectNotFound(f"Object not found: {key}") from exc
            raise ObjectStoreError("S3 landing get request failed") from exc

    def list_keys(self, prefix: str = "") -> list[str]:
        prefix = _safe_prefix(prefix)
        full_prefix = self._full_key(prefix) if prefix else self.prefix
        keys: list[str] = []
        try:
            paginator = self._client_instance().get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=self.bucket, Prefix=full_prefix)
            for page in pages:
                for item in page.get("Contents", []):
                    full_key = str(item.get("Key") or "")
                    if self.prefix and full_key.startswith(self.prefix + "/"):
                        keys.append(full_key[len(self.prefix) + 1 :])
                    elif not self.prefix:
                        keys.append(full_key)
        except Exception as exc:
            raise ObjectStoreError("S3 landing list request failed") from exc
        return sorted(key for key in keys if key)


class OnchainLandingWriter:
    """Write exact source frames, Bronze Parquet, and lineage manifests."""

    def __init__(
        self,
        root: str | os.PathLike[str],
        *,
        dataset: str | None = None,
    ) -> None:
        self.uri = str(root)
        parsed = urlparse(self.uri)
        if parsed.scheme == "s3":
            self._store: _ImmutableStore = _S3ObjectStore(self.uri)
            self.root: Path | None = None
        else:
            self.root = _file_root(self.uri)
            self._store = _FileObjectStore(self.root)
        self.dataset = _path_component(dataset or DEFAULT_DATASET, "dataset")

    @classmethod
    def from_env(cls) -> OnchainLandingWriter | None:
        value = os.getenv("SOLANA_DEGEN_LANDING_URI", "").strip()
        if not value:
            value = os.getenv("SOLANA_DEGEN_LANDING_DIR", "").strip()
        if not value:
            return None
        return cls(value, dataset=os.getenv("SOLANA_DEGEN_LANDING_DATASET"))

    def list_keys(self, prefix: str = "") -> list[str]:
        """List relative objects below a bounded landing prefix."""

        return self._store.list_keys(prefix)

    def get_object_bytes(self, key: str) -> bytes:
        """Read one immutable object without exposing provider details."""

        return self._store.get_bytes(key)

    def put_object_bytes(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str | None = None,
    ) -> PutResult:
        """Write one immutable object through the configured store."""

        if isinstance(self._store, _S3ObjectStore):
            self._store.ensure_write_enabled()
        return self._store.put_bytes(key, data, content_type=content_type)

    def write_raw(self, raw: bytes | str, event: dict[str, Any]) -> dict[str, Any]:
        """Persist one frame and its Bronze row exactly once."""

        if isinstance(self._store, _S3ObjectStore):
            self._store.ensure_write_enabled()

        raw_bytes = raw.encode("utf-8") if isinstance(raw, str) else bytes(raw)
        raw_sha256 = hashlib.sha256(raw_bytes).hexdigest()
        event_id = _event_id(event, raw_sha256)
        event_key = _event_key(event_id)
        event_time = _event_time(event)
        event_date = _event_date(event, event_time)
        raw_key = (
            f"landing/source={LANDING_SOURCE}/dataset={self.dataset}/"
            f"schema_version={LANDING_SCHEMA_VERSION}/event_date={event_date}/event_id={event_key}.json"
        )
        bronze_key = (
            f"bronze/domain={BRONZE_DOMAIN}/dataset={self.dataset}/"
            f"schema_version={BRONZE_SCHEMA_VERSION}/event_date={event_date}/"
            f"source={LANDING_SOURCE}/part-{event_key}.parquet"
        )
        manifest_key = (
            f"control/manifests/source={LANDING_SOURCE}/dataset={self.dataset}/"
            f"schema_version={LANDING_SCHEMA_VERSION}/event_id={event_key}.json"
        )
        checkpoint_key = (
            f"control/checkpoints/source={LANDING_SOURCE}/dataset={self.dataset}/"
            f"schema_version={LANDING_SCHEMA_VERSION}/event_id={event_key}.json"
        )

        existing_manifest = self._read_json(manifest_key)
        if existing_manifest is not None:
            _validate_existing_manifest(
                existing_manifest,
                event_id=event_id,
                raw_key=raw_key,
                raw_sha256=raw_sha256,
                bronze_key=bronze_key,
            )
            raw_ref = existing_manifest["raw"]
            bronze_ref = existing_manifest["bronze"]
            return _result(
                status="existing",
                event_id=event_id,
                raw_key=raw_key,
                bronze_key=bronze_key,
                manifest_key=manifest_key,
                checkpoint_key=checkpoint_key,
                raw_sha256=str(raw_ref["sha256"]),
                bronze_sha256=str(bronze_ref["sha256"]),
                raw_existed=True,
                bronze_existed=True,
                manifest_existed=True,
                checkpoint_existed=True,
            )

        checkpoint = self._read_json(checkpoint_key)
        if checkpoint is not None:
            _validate_checkpoint(
                checkpoint,
                event_id=event_id,
                raw_key=raw_key,
                raw_sha256=raw_sha256,
                bronze_key=bronze_key,
            )
            received_at = str(checkpoint["received_at"])
            stable_event_time = checkpoint.get("event_time") or event_time
        else:
            received_at = datetime.now(UTC).isoformat()
            stable_event_time = event_time or received_at
            checkpoint_payload = {
                "checkpoint_version": "1",
                "event_id": event_id,
                "source": LANDING_SOURCE,
                "dataset": self.dataset,
                "schema_version": LANDING_SCHEMA_VERSION,
                "received_at": received_at,
                "event_time": stable_event_time,
                "raw_key": raw_key,
                "raw_sha256": raw_sha256,
                "bronze_key": bronze_key,
                "privacy_class": PRIVACY_CLASS,
                "retention_class": RETENTION_CLASS,
            }
            self._store.put_bytes(
                checkpoint_key,
                _canonical_json_bytes(checkpoint_payload),
                content_type="application/json",
            )

        bronze_bytes = _bronze_bytes(
            event,
            event_id=event_id,
            dataset=self.dataset,
            raw_key=raw_key,
            raw_sha256=raw_sha256,
            received_at=received_at,
            event_time=stable_event_time,
        )
        raw_result = self._store.put_bytes(raw_key, raw_bytes, content_type=CONTENT_TYPE)
        bronze_result = self._store.put_bytes(
            bronze_key,
            bronze_bytes,
            content_type="application/vnd.apache.parquet",
        )
        manifest = {
            "manifest_version": "2",
            "event_id": event_id,
            "source": LANDING_SOURCE,
            "dataset": self.dataset,
            "schema_version": LANDING_SCHEMA_VERSION,
            "bronze_schema_version": BRONZE_SCHEMA_VERSION,
            "received_at": received_at,
            "event_time": stable_event_time,
            "event_type": _text(event.get("event_type")) or "transaction_log",
            "slot": _optional_int(event.get("slot")),
            "signature": _text(event.get("signature")),
            "program_id": _text(event.get("program_id")),
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
        }
        manifest_bytes = _canonical_json_bytes(manifest)
        try:
            manifest_result = self._store.put_bytes(
                manifest_key,
                manifest_bytes,
                content_type="application/json",
            )
        except LandingConflictError:
            concurrent_manifest = self._read_json(manifest_key)
            if concurrent_manifest is None:
                raise
            _validate_existing_manifest(
                concurrent_manifest,
                event_id=event_id,
                raw_key=raw_key,
                raw_sha256=raw_sha256,
                bronze_key=bronze_key,
            )
            manifest_result = PutResult(manifest_key, True, "")
        return _result(
            status="existing" if manifest_result.existed else "written",
            event_id=event_id,
            raw_key=raw_key,
            bronze_key=bronze_key,
            manifest_key=manifest_key,
            checkpoint_key=checkpoint_key,
            raw_sha256=raw_result.sha256,
            bronze_sha256=bronze_result.sha256,
            raw_existed=raw_result.existed,
            bronze_existed=bronze_result.existed,
            manifest_existed=manifest_result.existed,
            checkpoint_existed=checkpoint is not None,
        )

    def restore_manifest(self, manifest_key: str, destination: str | os.PathLike[str]) -> dict[str, Any]:
        """Verify and restore one raw/Bronze/manifest triplet locally."""

        manifest_bytes = self._store.get_bytes(manifest_key)
        try:
            manifest = json.loads(manifest_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ObjectStoreError("Landing manifest is not valid UTF-8 JSON") from exc
        if not isinstance(manifest, dict):
            raise ObjectStoreError("Landing manifest root must be an object")
        raw_ref = manifest.get("raw") if isinstance(manifest.get("raw"), dict) else {}
        bronze_ref = manifest.get("bronze") if isinstance(manifest.get("bronze"), dict) else {}
        raw_key = str(raw_ref.get("key") or manifest.get("raw_object_key") or "")
        bronze_key = str(bronze_ref.get("key") or "")
        expected_raw = str(raw_ref.get("sha256") or manifest.get("raw_sha256") or "")
        expected_bronze = str(bronze_ref.get("sha256") or "")
        if not raw_key or not bronze_key or not expected_raw or not expected_bronze:
            raise ObjectStoreError("Landing manifest is missing raw or Bronze lineage")
        raw_bytes = self._store.get_bytes(raw_key)
        bronze_bytes = self._store.get_bytes(bronze_key)
        raw_sha256 = hashlib.sha256(raw_bytes).hexdigest()
        bronze_sha256 = hashlib.sha256(bronze_bytes).hexdigest()
        if raw_sha256 != expected_raw:
            raise LandingConflictError("Raw restore checksum does not match manifest")
        if bronze_sha256 != expected_bronze:
            raise LandingConflictError("Bronze restore checksum does not match manifest")

        target = Path(destination).expanduser().resolve()
        target.mkdir(parents=True, exist_ok=True)
        manifest_path = target / "manifest.json"
        raw_path = target / "raw" / Path(raw_key).name
        bronze_path = target / "bronze" / Path(bronze_key).name
        _write_restore(manifest_path, manifest_bytes)
        _write_restore(raw_path, raw_bytes)
        _write_restore(bronze_path, bronze_bytes)
        return {
            "status": "restored",
            "event_id": manifest.get("event_id"),
            "manifest_key": manifest_key,
            "raw_key": raw_key,
            "bronze_key": bronze_key,
            "raw_sha256": raw_sha256,
            "bronze_sha256": bronze_sha256,
            "manifest_path": str(manifest_path),
            "raw_path": str(raw_path),
            "bronze_path": str(bronze_path),
        }

    def _read_json(self, key: str) -> dict[str, Any] | None:
        try:
            raw = self._store.get_bytes(key)
        except ObjectNotFound:
            return None
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ObjectStoreError(f"Landing control object is invalid JSON: {key}") from exc
        if not isinstance(value, dict):
            raise ObjectStoreError(f"Landing control object is not an object: {key}")
        return value


def _bronze_bytes(
    event: dict[str, Any],
    *,
    event_id: str,
    dataset: str,
    raw_key: str,
    raw_sha256: str,
    received_at: str,
    event_time: str | None,
) -> bytes:
    try:
        import pyarrow as pa
        import pyarrow.parquet as parquet
    except ImportError as exc:  # pragma: no cover - deployment dependency
        raise ObjectStoreError("Bronze Parquet requires pyarrow in the strategy image") from exc

    stable_event = dict(event)
    if event_time:
        stable_event["observed_at"] = event_time
    payload_json = json.dumps(
        stable_event,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    metadata_json = json.dumps(
        {
            "event_type": _text(event.get("event_type")) or "transaction_log",
            "slot": _optional_int(event.get("slot")),
            "signature": _text(event.get("signature")),
            "program_id": _text(event.get("program_id")),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    row = {
        "event_id": event_id,
        "source": LANDING_SOURCE,
        "source_record_id": _text(event.get("signature")),
        "domain": BRONZE_DOMAIN,
        "dataset": dataset,
        "schema_version": BRONZE_SCHEMA_VERSION,
        "received_at": received_at,
        "event_time": event_time,
        "content_type": CONTENT_TYPE,
        "raw_object_key": raw_key,
        "raw_sha256": raw_sha256,
        "payload_json": payload_json,
        "metadata_json": metadata_json,
        "ingest_run_id": event_id,
        "privacy_class": PRIVACY_CLASS,
        "retention_class": RETENTION_CLASS,
    }
    schema = pa.schema([(column, pa.string()) for column in BRONZE_COLUMNS])
    table = pa.Table.from_pylist([row], schema=schema)
    sink = io.BytesIO()
    parquet.write_table(table, sink, compression="zstd", version="2.6", use_dictionary=False)
    return sink.getvalue()


def _validate_existing_manifest(
    manifest: dict[str, Any],
    *,
    event_id: str,
    raw_key: str,
    raw_sha256: str,
    bronze_key: str,
) -> None:
    raw = manifest.get("raw") if isinstance(manifest.get("raw"), dict) else {}
    bronze = manifest.get("bronze") if isinstance(manifest.get("bronze"), dict) else {}
    expected = {"event_id": event_id, "raw_object_key": raw_key, "raw_sha256": raw_sha256}
    for field, value in expected.items():
        if manifest.get(field) == value:
            continue
        if field == "raw_object_key" and raw.get("key") == value:
            continue
        if field == "raw_sha256" and raw.get("sha256") == value:
            continue
        raise LandingConflictError(f"Landing manifest conflict for {field}")
    if bronze.get("key") != bronze_key or not bronze.get("sha256"):
        raise LandingConflictError("Landing manifest is missing or changing its Bronze lineage")


def _validate_checkpoint(
    checkpoint: dict[str, Any],
    *,
    event_id: str,
    raw_key: str,
    raw_sha256: str,
    bronze_key: str,
) -> None:
    expected = {
        "event_id": event_id,
        "raw_key": raw_key,
        "raw_sha256": raw_sha256,
        "bronze_key": bronze_key,
    }
    for field, value in expected.items():
        if checkpoint.get(field) != value:
            raise LandingConflictError(f"Landing checkpoint conflict for {field}")
    if not checkpoint.get("received_at"):
        raise ObjectStoreError("Landing checkpoint is missing received_at")


def _write_restore(path: Path, data: bytes) -> None:
    digest = hashlib.sha256(data).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise LandingConflictError(f"Restore destination conflict at {path}")
        return
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
    except FileExistsError:
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise LandingConflictError(f"Restore destination conflict at {path}") from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _result(**values: Any) -> dict[str, Any]:
    return values


def _canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _file_root(value: str) -> Path:
    parsed = urlparse(value)
    if parsed.scheme not in {"", "file"}:
        raise ObjectStoreError("Landing URI must use file:// or s3://")
    path = unquote(parsed.path)
    if parsed.netloc and parsed.netloc not in {"", "localhost"}:
        path = f"/{parsed.netloc}{path}"
    return Path(path or ".").expanduser().resolve()


def _safe_key(key: str) -> str:
    normalized = "/".join(part for part in key.strip("/").split("/") if part)
    if not normalized or any(part in {".", ".."} for part in normalized.split("/")):
        raise ObjectStoreError(f"Invalid landing object key: {key!r}")
    return normalized


def _safe_prefix(value: str) -> str:
    return _safe_key(value) if value else ""


def _is_local_endpoint(endpoint: str | None) -> bool:
    if not endpoint:
        return False
    return urlparse(endpoint).hostname in {"localhost", "127.0.0.1", "::1", "minio", "se-minio"}


def _is_true(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _max_object_bytes() -> int:
    raw = os.getenv("SOLANA_DEGEN_MAX_OBJECT_BYTES", str(64 * 1024 * 1024))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ObjectStoreError("SOLANA_DEGEN_MAX_OBJECT_BYTES must be an integer") from exc
    if value < 0:
        raise ObjectStoreError("SOLANA_DEGEN_MAX_OBJECT_BYTES must be non-negative")
    return value


def _is_not_found_error(exc: Exception) -> bool:
    response = getattr(exc, "response", {})
    error = response.get("Error", {}) if isinstance(response, dict) else {}
    code = str(error.get("Code", "")).lower() if isinstance(error, dict) else ""
    status = response.get("ResponseMetadata", {}).get("HTTPStatusCode") if isinstance(response, dict) else None
    return code in {"404", "nosuchkey", "nosuchbucket", "notfound"} or status == 404


def _is_precondition_error(exc: Exception) -> bool:
    response = getattr(exc, "response", {})
    error = response.get("Error", {}) if isinstance(response, dict) else {}
    code = str(error.get("Code", "")).lower() if isinstance(error, dict) else ""
    status = response.get("ResponseMetadata", {}).get("HTTPStatusCode") if isinstance(response, dict) else None
    return code in {"412", "preconditionfailed", "conditionalrequestconflict"} or status in {409, 412}


def _event_id(event: dict[str, Any], raw_sha256: str) -> str:
    value = _text(event.get("event_id"))
    if value:
        return value
    identity = "|".join(
        [
            _text(event.get("signature")) or "",
            str(_optional_int(event.get("slot")) or 0),
            _text(event.get("event_type")) or "transaction_log",
            raw_sha256,
        ]
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _event_key(event_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._=-]+", "-", event_id).strip("-._") or "event"
    suffix = hashlib.sha256(event_id.encode("utf-8")).hexdigest()[:12]
    return f"{safe[:100].rstrip('-._')}-{suffix}"


def _path_component(value: str, field: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._=-]+", "-", str(value).strip()).strip("-._")
    if not safe or safe in {".", ".."}:
        raise ValueError(f"Invalid {field} path component")
    return safe[:100]


def _event_date(event: dict[str, Any], event_time: str | None = None) -> str:
    value = event_time or _text(event.get("observed_at")) or _text(event.get("event_time"))
    if value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC).date().isoformat()
        except ValueError:
            pass
    return datetime.now(UTC).date().isoformat()


def _event_time(event: dict[str, Any]) -> str | None:
    value = _text(event.get("event_time")) or _text(event.get("observed_at"))
    return value[:128] if value else None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text[:512] if text else None


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
