from __future__ import annotations

import json

import pytest

from app.market_intel.evm_provider import EVMProviderRegistry
from app.market_intel.evm_provider_dry_run import run_evm_provider_dry_run
from scripts.evm_provider_preflight import build_preflight, main


def _registry(*, enabled: bool = True, approved: bool = False) -> EVMProviderRegistry:
    return EVMProviderRegistry.from_mapping(
        {
            "enabled": enabled,
            "release_gate_approved": approved,
            "endpoints": [
                {
                    "provider": "goplus",
                    "adapter": "goplus",
                    "url_template": "https://provider.example/goplus/{chain}/{token_address}",
                    "secret_ref": "secret://market-intel/goplus",
                    "secret_header": "X-API-KEY",
                },
                {
                    "provider": "honeypot",
                    "adapter": "honeypot",
                    "url_template": "https://provider.example/honeypot/{chain}/{token_address}",
                },
                {
                    "provider": "simulation",
                    "adapter": "simulation",
                    "url_template": "https://provider.example/simulation/{chain}/{token_address}",
                },
                {
                    "provider": "lp_custody",
                    "adapter": "lp_custody",
                    "url_template": "https://provider.example/lp/{chain}/{token_address}",
                },
            ],
        }
    )


@pytest.mark.asyncio
async def test_dry_run_uses_mock_transport_and_keeps_production_blocked():
    report = await run_evm_provider_dry_run(_registry(), chains=["ethereum", "base"])

    assert report["status"] == "passed"
    assert report["mode"] == "paper_only_mock_transport"
    assert report["mock_transport_calls"] == 8
    assert report["network_calls"] is False
    assert report["credentials_loaded"] is False
    assert report["transactions_submitted"] is False
    assert report["production_activation"] == "blocked"
    assert report["all_provenance_redacted"] is True
    assert all(item["risk"]["eligible"] is True for item in report["chains"])
    assert all(item["risk"]["state"] == "watchlist" for item in report["chains"])


@pytest.mark.asyncio
@pytest.mark.parametrize("registry", [EVMProviderRegistry(), _registry(enabled=False)])
async def test_dry_run_disabled_registry_makes_no_mock_requests(registry):
    report = await run_evm_provider_dry_run(registry, chains=["ethereum"])

    assert report["status"] == "passed"
    assert report["mock_transport_calls"] == 0
    assert report["providers_exercised"] is False
    assert report["chains"][0]["risk"]["eligible"] is False
    assert report["chains"][0]["risk"]["state"] == "insufficient_evidence"


@pytest.mark.asyncio
async def test_dry_run_missing_chain_coverage_is_visible_and_fail_closed():
    registry = EVMProviderRegistry.from_mapping(
        {
            "enabled": True,
            "release_gate_approved": False,
            "endpoints": [
                {
                    "provider": "goplus",
                    "adapter": "goplus",
                    "url_template": "https://provider.example/{chain}/{token_address}",
                    "supported_chains": ["ethereum"],
                }
            ],
        }
    )
    report = await run_evm_provider_dry_run(registry, chains=["base"])

    assert report["mock_transport_calls"] == 0
    assert report["chains"][0]["provider_incomplete"] is True
    assert report["chains"][0]["risk"]["eligible"] is False
    assert "provider_availability" in report["chains"][0]["risk"]["missing_evidence"]


def test_preflight_accepts_secret_free_json_and_writes_no_payload():
    config = {
        "enabled": False,
        "release_gate_approved": False,
        "endpoints": [],
    }
    report = build_preflight(registry_json=json.dumps(config), chains=["ethereum"])

    assert report["status"] == "passed"
    assert report["registry_source"] == "argument"
    assert report["provider_payloads_written"] is False
    assert "fixture-secret-binding" not in repr(report)


@pytest.mark.asyncio
async def test_dry_run_redaction_failure_fails_validation(monkeypatch):
    monkeypatch.setattr("app.market_intel.evm_provider_dry_run._provenance_is_safe", lambda _: False)
    report = await run_evm_provider_dry_run(_registry(), chains=["ethereum"])
    assert report["status"] == "failed"
    assert report["all_provenance_redacted"] is False


@pytest.mark.asyncio
async def test_dry_run_explicit_empty_chains_rejected():
    with pytest.raises(ValueError, match="supported EVM chains"):
        await run_evm_provider_dry_run(_registry(), chains=[])


def test_preflight_release_gate_failure_matches_saved_evidence(monkeypatch, tmp_path, capsys):
    output = tmp_path / "evidence.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "preflight",
            "--registry-json",
            '{"enabled":false,"endpoints":[]}',
            "--require-release-gate",
            "--evidence-output",
            str(output),
            "--json",
        ],
    )
    assert main() == 2
    report = json.loads(capsys.readouterr().out)
    evidence = json.loads(output.read_text())
    assert report["status"] == evidence["report"]["status"] == "blocked"
    assert report["blocked_reason"] == "release_gate_approval_required"
