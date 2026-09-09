#!/usr/bin/env python3
"""Validate and exercise the EVM provider path without network access."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

STRATEGY_ROOT = Path(__file__).resolve().parents[1]
if str(STRATEGY_ROOT) not in sys.path:
    sys.path.insert(0, str(STRATEGY_ROOT))

from app.market_intel.evm_provider import EVMProviderConfigurationError, EVMProviderRegistry  # noqa: E402
from app.market_intel.evm_provider_dry_run import run_sync  # noqa: E402


def load_registry(*, registry_json: str | None = None, registry_file: Path | None = None) -> EVMProviderRegistry:
    """Load only secret-free registry data; never resolve credentials here."""

    if registry_json and registry_file:
        raise EVMProviderConfigurationError("choose either registry JSON or registry file")
    if registry_file:
        try:
            registry_json = registry_file.expanduser().read_text(encoding="utf-8")
        except OSError as exc:
            raise EVMProviderConfigurationError("provider registry file is unavailable") from exc
    if registry_json is not None:
        return EVMProviderRegistry.from_json(registry_json)
    return EVMProviderRegistry.from_env()


def build_preflight(
    *,
    registry_json: str | None = None,
    registry_file: Path | None = None,
    chains: list[str] | None = None,
) -> dict[str, object]:
    """Return a redacted offline preflight and fixture-drill report."""

    registry = load_registry(registry_json=registry_json, registry_file=registry_file)
    report = run_sync(registry, chains=chains)
    report["generated_at"] = datetime.now(UTC).isoformat()
    report["registry_source"] = "argument" if registry_json or registry_file else "environment_or_default"
    return report


def _write_evidence(path: Path, report: dict[str, object]) -> None:
    target = path.expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    evidence = {
        "evidence_version": "evm-provider-preflight.v1",
        "report": report,
    }
    temporary.write_text(json.dumps(evidence, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--registry-json", help="secret-free EVM provider registry JSON")
    source.add_argument("--registry-file", type=Path, help="path to a secret-free registry JSON file")
    parser.add_argument(
        "--chain",
        action="append",
        dest="chains",
        help="chain to exercise; repeat for multiple chains (default: all supported EVM chains)",
    )
    parser.add_argument("--evidence-output", type=Path, help="write redacted evidence JSON to this local path")
    parser.add_argument("--require-release-gate", action="store_true", help="exit 2 unless registry approval is true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        report = build_preflight(
            registry_json=args.registry_json,
            registry_file=args.registry_file,
            chains=args.chains,
        )
    except (EVMProviderConfigurationError, ValueError) as exc:
        report = {
            "status": "blocked",
            "mode": "paper_only_mock_transport",
            "error_class": type(exc).__name__,
            "network_calls": False,
            "credentials_loaded": False,
            "transactions_submitted": False,
            "production_activation": "blocked",
        }

    registry = report.get("registry")
    approved = isinstance(registry, dict) and registry.get("release_gate_approved") is True
    if args.require_release_gate and not approved:
        report["status"] = "blocked"
        report["blocked_reason"] = "release_gate_approval_required"

    if args.evidence_output:
        _write_evidence(args.evidence_output, report)
        report["evidence_output"] = str(args.evidence_output.expanduser().resolve())
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    else:
        print(f"EVM provider preflight: {report['status']}")
        print(f"  mode: {report.get('mode', 'unknown')}")
        print(f"  mock transport calls: {report.get('mock_transport_calls', 0)}")
        print(f"  production activation: {report.get('production_activation', 'blocked')}")

    return 0 if report.get("status") == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
