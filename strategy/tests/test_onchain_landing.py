from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import pyarrow.parquet as parquet
import pytest

import app.market_intel.onchain_landing as landing_module
from app.market_intel.onchain_landing import (
    LandingConflictError,
    ObjectStoreError,
    OnchainLandingWriter,
)

EVENT = {
    "event_id": "Program111:SigLanding:token_created:unknown",
    "event_type": "token_created",
    "signature": "SigLanding",
    "slot": 123,
    "program_id": "Program111",
    "observed_at": "2026-01-02T03:04:05+00:00",
}


def test_landing_preserves_exact_bytes_and_is_idempotent(tmp_path):
    writer = OnchainLandingWriter(tmp_path)
    raw = b'{"method":"logsNotification","params":{"signature":"SigLanding"}}\n'

    first = writer.write_raw(raw, EVENT)
    second = writer.write_raw(raw, EVENT)

    assert first["status"] == "written"
    assert second["status"] == "existing"
    raw_path = tmp_path / first["raw_key"]
    manifest_path = tmp_path / first["manifest_key"]
    assert raw_path.read_bytes() == raw
    manifest = json.loads(manifest_path.read_text())
    assert manifest["source"] == "solana_rpc"
    assert manifest["privacy_class"] == "public"
    assert manifest["retention_class"] == "market_data"
    assert manifest["raw_object_key"] == first["raw_key"]
    assert manifest["raw_sha256"] == hashlib.sha256(raw).hexdigest()
    assert manifest["raw"]["bytes"] == len(raw)
    assert manifest["bronze"]["key"] == first["bronze_key"]
    bronze_path = tmp_path / first["bronze_key"]
    table = parquet.read_table(bronze_path)
    assert table.num_rows == 1
    assert table.column_names == manifest["bronze"]["columns"]
    assert table.column("raw_sha256")[0].as_py() == first["raw_sha256"]
    assert ".." not in first["raw_key"]


def test_landing_rejects_different_bytes_for_same_event(tmp_path):
    writer = OnchainLandingWriter(tmp_path)
    writer.write_raw(b"first", EVENT)

    with pytest.raises(LandingConflictError):
        writer.write_raw(b"second", EVENT)

    raw_key = writer.write_raw(b"first", EVENT)["raw_key"]
    assert (tmp_path / raw_key).read_bytes() == b"first"


def test_restore_drill_reconciles_raw_bronze_and_manifest(tmp_path):
    writer = OnchainLandingWriter(tmp_path / "lake")
    result = writer.write_raw(b"restore-me", EVENT)

    restored = writer.restore_manifest(result["manifest_key"], tmp_path / "restore")

    assert restored["status"] == "restored"
    assert Path(restored["raw_path"]).read_bytes() == b"restore-me"
    assert hashlib.sha256(Path(restored["bronze_path"]).read_bytes()).hexdigest() == result["bronze_sha256"]
    assert Path(restored["manifest_path"]).read_text() == (tmp_path / "lake" / result["manifest_key"]).read_text()


def test_landing_event_id_fallback_is_safe(tmp_path):
    writer = OnchainLandingWriter(tmp_path)
    result = writer.write_raw(
        b"fallback",
        {
            "event_type": "transaction_log",
            "signature": "sig/with/path",
            "slot": 1,
            "observed_at": "not-a-date",
        },
    )

    assert result["event_id"]
    assert result["raw_key"].startswith("landing/source=solana_rpc/")
    assert all(part not in {".", ".."} for part in result["raw_key"].split("/"))


def test_cloud_landing_is_fail_closed_without_explicit_write_flag(monkeypatch):
    monkeypatch.delenv("DATA_LAKE_CLOUD_WRITE_ENABLED", raising=False)
    writer = OnchainLandingWriter("s3://example-bucket/solana")

    with pytest.raises(ObjectStoreError, match="Cloud landing writes are disabled"):
        writer.write_raw(b"cloud-disabled", EVENT)


def test_s3_landing_rejects_credentials_in_uri():
    with pytest.raises(ObjectStoreError, match="must not include credentials"):
        OnchainLandingWriter("s3://access:secret@example-bucket/solana")


def test_s3_store_uses_conditional_immutable_put(monkeypatch):
    class FakeError(RuntimeError):
        def __init__(self, status):
            self.response = {"ResponseMetadata": {"HTTPStatusCode": status}}

    class FakeS3:
        def __init__(self):
            self.objects = {}

        def head_object(self, *, Bucket, Key):
            if Key not in self.objects:
                raise FakeError(404)
            data = self.objects[Key]
            return {"Metadata": {"sha256": hashlib.sha256(data).hexdigest()}}

        def put_object(self, *, Bucket, Key, Body, **_kwargs):
            if Key in self.objects:
                raise FakeError(412)
            self.objects[Key] = Body

        def get_object(self, *, Bucket, Key):
            if Key not in self.objects:
                raise FakeError(404)
            return {"Body": io.BytesIO(self.objects[Key])}

    monkeypatch.setenv("DATA_LAKE_CLOUD_WRITE_ENABLED", "true")
    store = landing_module._S3ObjectStore("s3://bucket/prefix")
    store._client = FakeS3()

    first = store.put_bytes("landing/event.json", b"same", content_type="application/json")
    second = store.put_bytes("landing/event.json", b"same", content_type="application/json")
    assert first.existed is False
    assert second.existed is True
    with pytest.raises(LandingConflictError):
        store.put_bytes("landing/event.json", b"different")


def test_s3_store_lists_keys_relative_to_prefix(monkeypatch):
    class FakePaginator:
        def paginate(self, **_kwargs):
            return [
                {
                    "Contents": [
                        {"Key": "prefix/bronze/a.parquet"},
                        {"Key": "prefix/bronze/b.parquet"},
                    ]
                }
            ]

    class FakeS3:
        def get_paginator(self, name):
            assert name == "list_objects_v2"
            return FakePaginator()

    monkeypatch.setenv("DATA_LAKE_CLOUD_WRITE_ENABLED", "true")
    store = landing_module._S3ObjectStore("s3://bucket/prefix")
    store._client = FakeS3()

    assert store.list_keys("bronze") == ["bronze/a.parquet", "bronze/b.parquet"]


def test_checkpoint_resumes_after_manifest_write_failure(tmp_path):
    writer = OnchainLandingWriter(tmp_path)
    original_put = writer._store.put_bytes
    failed = False

    def flaky_put(key, data, *, content_type=None):
        nonlocal failed
        if key.startswith("control/manifests/") and not failed:
            failed = True
            raise ObjectStoreError("synthetic manifest outage")
        return original_put(key, data, content_type=content_type)

    writer._store.put_bytes = flaky_put
    with pytest.raises(ObjectStoreError, match="synthetic manifest outage"):
        writer.write_raw(b"resume-me", EVENT)

    writer._store.put_bytes = original_put
    resumed = writer.write_raw(b"resume-me", EVENT)
    assert resumed["status"] == "written"
    assert resumed["bronze_existed"] is True
    assert resumed["checkpoint_existed"] is True
