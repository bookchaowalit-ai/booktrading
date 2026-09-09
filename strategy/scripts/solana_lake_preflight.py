#!/usr/bin/env python3
"""Run a no-network readiness check and optional local Solana lake drill."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

STRATEGY_ROOT = Path(__file__).resolve().parents[1]
if str(STRATEGY_ROOT) not in sys.path:
    sys.path.insert(0, str(STRATEGY_ROOT))

from app.market_intel.onchain_compaction import compact_bronze, verify_compaction_manifest  # noqa: E402
from app.market_intel.onchain_landing import OnchainLandingWriter  # noqa: E402

ATTESTATION_ENV = {
    "bucket_policy": "SOLANA_DEGEN_BUCKET_POLICY_ATTESTED",
    "bucket_versioning": "SOLANA_DEGEN_BUCKET_VERSIONING_ATTESTED",
    "bucket_encryption": "SOLANA_DEGEN_BUCKET_ENCRYPTION_ATTESTED",
    "bucket_lifecycle": "SOLANA_DEGEN_BUCKET_LIFECYCLE_ATTESTED",
    "secret_binding": "SOLANA_DEGEN_SECRET_BINDING_ATTESTED",
    "restore_approved": "SOLANA_DEGEN_RESTORE_APPROVED",
    "compaction_approved": "SOLANA_DEGEN_COMPACTION_APPROVED",
}


def build_preflight(uri: str | None = None) -> dict[str, object]:
    """Build a redacted, no-network readiness report."""

    configured_uri = (
        uri or os.getenv("SOLANA_DEGEN_LANDING_URI") or os.getenv("SOLANA_DEGEN_LANDING_DIR") or ""
    ).strip()
    parsed = urlparse(configured_uri) if configured_uri else None
    scheme = (parsed.scheme if parsed and parsed.scheme else "file") if configured_uri else ""
    has_userinfo = bool(parsed and (parsed.username or parsed.password))
    supported_scheme = scheme in {"file", "s3"}
    uri_valid = bool(configured_uri) and supported_scheme and not has_userinfo
    cloud_write_enabled = _is_true(os.getenv("DATA_LAKE_CLOUD_WRITE_ENABLED"))
    attestations = {name: _is_true(os.getenv(env_name)) for name, env_name in ATTESTATION_ENV.items()}
    checks = {
        "landing_uri_configured": bool(configured_uri),
        "supported_scheme": supported_scheme,
        "uri_has_no_userinfo": not has_userinfo,
        "cloud_write_gate": cloud_write_enabled,
        "attestations": attestations,
    }
    production_requirements = {
        "s3_landing_uri": scheme == "s3",
        "cloud_write_enabled": cloud_write_enabled,
        **attestations,
    }
    production_ready = uri_valid and all(production_requirements.values())
    return {
        "status": "production_ready" if production_ready else ("pilot_ready" if uri_valid else "blocked"),
        "mode": "no_network_preflight",
        "landing_uri": _redact_uri(configured_uri),
        "scheme": scheme,
        "checks": checks,
        "production_requirements": production_requirements,
        "production_ready": production_ready,
        "cloud_writes_default": False,
        "network_calls": False,
        "credentials_loaded": False,
    }


def run_local_drill() -> dict[str, object]:
    """Write, compact, verify, and restore synthetic data in a temp lake."""

    with tempfile.TemporaryDirectory(prefix="solana-lake-drill-") as temporary:
        writer = OnchainLandingWriter(Path(temporary) / "lake")
        event_date = "2026-01-02"
        events = [
            {
                "event_id": "drill-event-1",
                "event_type": "token_created",
                "signature": "drill-signature-1",
                "slot": 1,
                "program_id": "drill-program",
                "observed_at": f"{event_date}T00:00:01+00:00",
            },
            {
                "event_id": "drill-event-2",
                "event_type": "pool_created",
                "signature": "drill-signature-2",
                "slot": 2,
                "program_id": "drill-program",
                "observed_at": f"{event_date}T00:00:02+00:00",
            },
        ]
        landed = [
            writer.write_raw(
                json.dumps(event, sort_keys=True, separators=(",", ":")).encode("utf-8"),
                event,
            )
            for event in events
        ]
        compacted = compact_bronze(writer, event_date=event_date, apply=True)
        verified = verify_compaction_manifest(writer, str(compacted["manifest_key"]))
        restored = writer.restore_manifest(landed[0]["manifest_key"], Path(temporary) / "restore")
        restored_raw_sha = hashlib.sha256(Path(restored["raw_path"]).read_bytes()).hexdigest()
        return {
            "status": "passed",
            "landed_events": len(landed),
            "compaction_status": compacted["status"],
            "compacted_rows": verified["output_rows"],
            "compaction_verified": verified["status"] == "verified",
            "restore_verified": restored["status"] == "restored",
            "restored_raw_sha256": restored_raw_sha,
            "network_calls": False,
            "credentials_loaded": False,
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uri", help="file:// or s3:// URI; defaults to environment")
    parser.add_argument("--drill", action="store_true", help="run a synthetic local write/compact/restore drill")
    parser.add_argument(
        "--evidence-output",
        type=Path,
        help="write the redacted preflight and local-drill evidence JSON to this local path",
    )
    parser.add_argument(
        "--require-production",
        action="store_true",
        help="return exit code 2 unless all explicit production attestations pass",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = build_preflight(args.uri)
    if args.drill:
        try:
            report["local_drill"] = run_local_drill()
        except Exception as exc:
            report["local_drill"] = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
    if args.evidence_output:
        if not args.drill:
            raise SystemExit("--evidence-output requires --drill")
        evidence = {
            "evidence_version": "1",
            "generated_at": datetime.now(UTC).isoformat(),
            "report": report,
        }
        _write_evidence(args.evidence_output, evidence)
        report["evidence_output"] = str(args.evidence_output.expanduser().resolve())
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    else:
        print(f"Solana lake preflight: {report['status']}")
        print(f"  landing URI: {report['landing_uri'] or '<unset>'}")
        print(f"  production ready: {report['production_ready']}")
        if "local_drill" in report:
            print(f"  local drill: {report['local_drill']['status']}")
    if args.require_production and not bool(report["production_ready"]):
        return 2
    if isinstance(report.get("local_drill"), dict) and report["local_drill"].get("status") != "passed":
        return 2
    return 0


def _is_true(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _redact_uri(value: str) -> str:
    if not value:
        return ""
    parsed = urlparse(value)
    if parsed.username or parsed.password:
        host = parsed.hostname or ""
        if parsed.port:
            host = f"{host}:{parsed.port}"
        return f"{parsed.scheme}://{host}{parsed.path}".rstrip("/")
    if parsed.scheme == "s3" and parsed.netloc:
        return f"s3://{parsed.hostname or parsed.netloc}{parsed.path}".rstrip("/")
    return value


def _write_evidence(path: Path, evidence: dict[str, object]) -> None:
    target = path.expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(evidence, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)


if __name__ == "__main__":
    raise SystemExit(main())
