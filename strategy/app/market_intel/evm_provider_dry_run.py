"""Offline EVM provider preflight and paper-only fixture drill.

This module exercises the registry, adapter normalization, provenance contract,
and risk gate through :class:`httpx.MockTransport`.  It never opens a socket,
loads a real credential, writes provider payloads, or submits a transaction.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import replace
from typing import Any

import httpx

from app.market_intel.evm_provider import (
    EVMProviderEndpoint,
    EVMProviderIngestor,
    EVMProviderRegistry,
    EVMRetryPolicy,
)
from app.market_intel.evm_security import SUPPORTED_EVM_CHAINS
from app.market_intel.risk_gate import RiskDecision, evaluate_risk

DRY_RUN_VERSION = "evm-provider-dry-run.v1"
DRY_RUN_TOKEN_ADDRESS = "0x0000000000000000000000000000000000000001"
_DRY_RUN_SECRET = "fixture-secret-binding"


def _fixture_payload(adapter: str) -> dict[str, Any]:
    if adapter == "goplus":
        return {
            "is_open_source": "1",
            "is_honeypot": "0",
            "is_mintable": "0",
            "is_proxy": "0",
        }
    if adapter == "honeypot":
        return {
            "honeypotResult": {"isHoneypot": False},
            "simulationResult": {"simulationSuccess": True, "sellSuccess": True},
        }
    if adapter == "simulation":
        return {"status": "passed", "sell_success": True, "simulation_success": True}
    if adapter == "lp_custody":
        return {"locked_ratio": 95, "custody_verified": True, "liquidity_usd": 25_000}
    raise ValueError(f"unsupported dry-run adapter: {adapter}")


def _fixture_endpoint(entry: Any) -> EVMProviderEndpoint:
    endpoint = entry.resolve(lambda _reference: _DRY_RUN_SECRET)
    headers = dict(endpoint.headers)
    # This header exists only inside MockTransport and is excluded from
    # provenance by EVMProviderIngestor.  It lets the fixture choose a payload
    # without inspecting a URL, query string, or secret.
    headers["X-EVM-Dry-Run-Provider"] = entry.provider
    return replace(endpoint, headers=headers)


def _safe_decision(decision: RiskDecision) -> dict[str, Any]:
    return {
        "state": decision.state.value,
        "eligible": decision.eligible,
        "confidence": decision.confidence,
        "missing_evidence": list(decision.missing_evidence),
        "findings": list(decision.findings),
        "vetoes": list(decision.vetoes),
        "evidence_coverage": decision.evidence_coverage,
        "policy_version": decision.policy_version,
    }


async def run_evm_provider_dry_run(
    registry: EVMProviderRegistry,
    *,
    chains: Iterable[str] | None = None,
    token_address: str = DRY_RUN_TOKEN_ADDRESS,
) -> dict[str, Any]:
    """Run the provider path with deterministic fixture responses only."""

    requested_chains = SUPPORTED_EVM_CHAINS if chains is None else chains
    normalized_chains = tuple(sorted({str(chain).strip().lower() for chain in requested_chains}))
    if not normalized_chains or any(chain not in SUPPORTED_EVM_CHAINS for chain in normalized_chains):
        raise ValueError("dry-run chains must be supported EVM chains")
    normalized_token = token_address.strip()
    if not normalized_token:
        raise ValueError("dry-run token address is required")

    calls: list[dict[str, str]] = []
    adapter_by_provider = {entry.provider: entry.adapter for entry in registry.entries}

    def handler(request: httpx.Request) -> httpx.Response:
        provider = request.headers.get("X-EVM-Dry-Run-Provider", "")
        adapter = adapter_by_provider.get(provider)
        if not adapter:
            return httpx.Response(500, json={"error": "unknown_fixture_provider"}, request=request)
        calls.append({"provider": provider, "method": request.method})
        return httpx.Response(200, json=_fixture_payload(adapter), request=request)

    endpoints = tuple(_fixture_endpoint(entry) for entry in registry.entries) if registry.enabled else ()
    reports: list[dict[str, Any]] = []
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        ingestor = EVMProviderIngestor(
            endpoints,
            retry_policy=EVMRetryPolicy(max_attempts=1, timeout_seconds=1),
            http_client=client,
            registry_version=registry.version,
        )
        for chain in normalized_chains:
            metadata = await ingestor.collect(
                chain=chain,
                token_address=normalized_token,
                liquidity={"liquidity_usd": 25_000},
                holders={"top5_concentration": 0.12},
            )
            decision = evaluate_risk({**metadata, "price_usd": 0.01})
            provenance = metadata.get("risk_evidence", {}).get("provenance", [])
            reports.append(
                {
                    "chain": chain,
                    "risk": _safe_decision(decision),
                    "provider_count": len(metadata.get("provider_sources", [])),
                    "provenance_count": len(provenance) if isinstance(provenance, list) else 0,
                    "provider_incomplete": bool(metadata.get("risk_evidence", {}).get("provider_incomplete")),
                    "provenance_redacted": _provenance_is_safe(provenance),
                }
            )

    all_provenance_redacted = all(report["provenance_redacted"] for report in reports)
    return {
        "status": "passed" if all_provenance_redacted else "failed",
        "validation_scope": "offline_fixture_only",
        "providers_exercised": bool(calls),
        "mode": "paper_only_mock_transport",
        "dry_run_version": DRY_RUN_VERSION,
        "registry": registry.safe_status(),
        "chains": reports,
        "mock_transport_calls": len(calls),
        "network_calls": False,
        "credentials_loaded": False,
        "provider_payloads_written": False,
        "transactions_submitted": False,
        "production_activation": "blocked",
        "all_provenance_redacted": all_provenance_redacted,
    }


def _provenance_is_safe(value: Any) -> bool:
    if not isinstance(value, list):
        return value in (None, [])
    forbidden_keys = {"query", "headers", "authorization", "api_key", "token", "secret", "payload"}

    def safe_item(item: Any) -> bool:
        if isinstance(item, dict):
            if any(str(key).lower() in forbidden_keys for key in item):
                return False
            return all(safe_item(nested) for nested in item.values()) and _DRY_RUN_SECRET not in repr(item)
        if isinstance(item, (list, tuple)):
            return all(safe_item(nested) for nested in item)
        return _DRY_RUN_SECRET not in repr(item)

    return all(safe_item(item) for item in value)


def run_sync(registry: EVMProviderRegistry, *, chains: Iterable[str] | None = None) -> dict[str, Any]:
    """Synchronous wrapper used by the CLI and offline operator checks."""

    return asyncio.run(run_evm_provider_dry_run(registry, chains=chains))


__all__ = ["DRY_RUN_TOKEN_ADDRESS", "DRY_RUN_VERSION", "run_evm_provider_dry_run", "run_sync"]
