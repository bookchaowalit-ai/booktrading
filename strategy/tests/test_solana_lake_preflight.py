from __future__ import annotations

import json

from scripts.solana_lake_preflight import _write_evidence, build_preflight, run_local_drill


def test_preflight_is_redacted_and_cloud_gate_is_explicit(monkeypatch):
    monkeypatch.delenv("DATA_LAKE_CLOUD_WRITE_ENABLED", raising=False)
    report = build_preflight("s3://bucket/private-prefix")

    assert report["status"] == "pilot_ready"
    assert report["production_ready"] is False
    assert report["landing_uri"] == "s3://bucket/private-prefix"
    assert report["credentials_loaded"] is False
    assert report["checks"]["cloud_write_gate"] is False


def test_preflight_rejects_uri_userinfo():
    report = build_preflight("s3://user:secret@bucket/private-prefix")

    assert report["status"] == "blocked"
    assert report["production_ready"] is False
    assert report["checks"]["uri_has_no_userinfo"] is False
    assert "user:secret@" not in str(report)


def test_local_write_compaction_restore_drill():
    result = run_local_drill()

    assert result["status"] == "passed"
    assert result["landed_events"] == 2
    assert result["compaction_verified"] is True
    assert result["restore_verified"] is True
    assert result["credentials_loaded"] is False


def test_restore_evidence_can_be_written_without_raw_payload(tmp_path):
    evidence_path = tmp_path / "restore-evidence.json"
    _write_evidence(
        evidence_path,
        {"evidence_version": "1", "report": {"restore_verified": True}},
    )

    evidence = json.loads(evidence_path.read_text())
    assert evidence["evidence_version"] == "1"
    assert evidence["report"]["restore_verified"] is True
