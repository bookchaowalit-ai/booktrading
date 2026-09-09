#!/usr/bin/env python3
"""Run a redacted, read-only S3/R2 policy and credential-source check."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

STRATEGY_ROOT = Path(__file__).resolve().parents[1]
if str(STRATEGY_ROOT) not in sys.path:
    sys.path.insert(0, str(STRATEGY_ROOT))

from app.market_intel.onchain_provider_policy import (  # noqa: E402
    ProviderPolicyError,
    client_for_s3_uri,
    secret_binding_report,
    verify_s3_bucket_policy,
)
from scripts.solana_lake_preflight import build_preflight  # noqa: E402


def build_report(uri: str | None = None, *, remote: bool = False) -> dict[str, object]:
    """Build a provider report; ``remote=False`` makes no network calls."""

    preflight = build_preflight(uri)
    configured_uri = (uri or os.getenv("SOLANA_DEGEN_LANDING_URI") or "").strip()
    report: dict[str, object] = {
        "status": "not_checked",
        "mode": "read_only_remote" if remote else "no_network_provider_preflight",
        "landing_uri": preflight["landing_uri"],
        "scheme": preflight["scheme"],
        "secret_binding": secret_binding_report(),
        "provider_policy": {
            "status": "not_checked",
            "read_only": True,
            "network_calls": False,
        },
        "credentials_loaded": False,
        "object_storage_writes": False,
        "deletes": False,
    }
    if not remote:
        report["status"] = "pilot_ready" if preflight["status"] != "blocked" else "blocked"
        report["production_ready"] = False
        return report
    try:
        client, bucket = client_for_s3_uri(configured_uri)
        policy = verify_s3_bucket_policy(client, bucket)
        report["provider_policy"] = {**policy, "network_calls": True}
        secret = report["secret_binding"]
        report["production_ready"] = policy["status"] == "pass" and bool(secret["configured"])
        report["status"] = "production_ready" if report["production_ready"] else "blocked"
        return report
    except Exception as exc:
        error_type = "provider_policy_error" if isinstance(exc, ProviderPolicyError) else type(exc).__name__
        report["status"] = "failed"
        report["production_ready"] = False
        report["error"] = {"type": error_type, "provider_message_exposed": False}
        return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uri", help="s3://bucket/prefix; defaults to SOLANA_DEGEN_LANDING_URI")
    parser.add_argument(
        "--remote",
        action="store_true",
        help="perform read-only provider control-plane calls; default mode is offline",
    )
    parser.add_argument(
        "--require-production",
        action="store_true",
        help="return exit code 2 unless policy and a secret source are verified",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = build_report(args.uri, remote=args.remote)
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    else:
        print(f"Solana provider check: {report['status']}")
        print(f"  landing URI: {report['landing_uri'] or '<unset>'}")
        print(f"  secret source: {report['secret_binding']['status']}")
        print(f"  policy: {report['provider_policy']['status']}")
    if args.require_production and not bool(report.get("production_ready")):
        return 2
    if report["status"] == "failed":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
