from __future__ import annotations

import json

import httpx
import pytest

from app.market_intel.evm_provider import (
    EVMProviderConfigurationError,
    EVMProviderEndpoint,
    EVMProviderIngestor,
    EVMProviderRegistry,
    EVMRetryPolicy,
    environment_secret_resolver,
)
from app.market_intel.models import MarketQuote, MarketType
from app.market_intel.risk_gate import RiskState, evaluate_risk
from app.market_intel.scanner import MarketScanner


@pytest.mark.asyncio
async def test_transient_provider_failure_retries_and_records_safe_provenance():
    calls = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, json={"error": "temporary"}, request=request)
        return httpx.Response(
            200,
            json={"is_open_source": "1", "is_honeypot": "0", "is_mintable": "0", "is_proxy": "0"},
            request=request,
        )

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    endpoint = EVMProviderEndpoint(
        provider="goplus",
        adapter="goplus",
        url_template="https://provider.test/security/{chain}?contract_addresses={token_address}",
        headers={"X-API-KEY": "secret-key"},
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        metadata = await EVMProviderIngestor(
            [endpoint],
            retry_policy=EVMRetryPolicy(max_attempts=3, initial_backoff_seconds=0.25),
            http_client=client,
            sleep=fake_sleep,
        ).collect(chain="ethereum", token_address="0xToken")

    assert calls == 2
    assert sleeps == [0.25]
    provenance = metadata["risk_evidence"]["provenance"][0]
    assert provenance["provider"] == "goplus"
    assert provenance["attempts"] == 2
    assert provenance["endpoint"] == {"scheme": "https", "host": "provider.test", "path": "/security/ethereum"}
    assert provenance["body_sha256"]
    assert "secret-key" not in repr(metadata)
    assert "contract_addresses" not in repr(provenance)


@pytest.mark.asyncio
async def test_transport_timeout_retries_without_exposing_exception_text():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError("secret endpoint payload", request=request)
        return httpx.Response(
            200,
            json={"status": "passed", "sell_success": True},
            request=request,
        )

    endpoint = EVMProviderEndpoint("simulation", "simulation", "https://simulation.test/{token_address}")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        response = await EVMProviderIngestor(
            [endpoint],
            retry_policy=EVMRetryPolicy(max_attempts=2, initial_backoff_seconds=0),
            http_client=client,
        )._request_json(endpoint, chain="ethereum", token_address="0xToken")

    assert calls == 2
    assert response.ok is True
    assert "secret endpoint payload" not in repr(response.provenance)


@pytest.mark.asyncio
async def test_required_provider_failure_is_retained_and_gate_abstains():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "999"}, json={"error": "rate limited"}, request=request)

    endpoint = EVMProviderEndpoint(
        provider="simulation",
        adapter="simulation",
        url_template="https://simulation.test/quote/{chain}/{token_address}",
        required=True,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        metadata = await EVMProviderIngestor(
            [endpoint],
            retry_policy=EVMRetryPolicy(max_attempts=1, max_backoff_seconds=1),
            http_client=client,
        ).collect(chain="base", token_address="0xToken")

    assert metadata["risk_evidence"]["provider_incomplete"] is True
    assert metadata["risk_evidence"]["provider_failures"][0]["error_class"] == "http_error"
    decision = evaluate_risk({**metadata, "price_usd": 0.01})
    assert decision.state is RiskState.INSUFFICIENT_EVIDENCE
    assert "provider_availability" in decision.missing_evidence
    assert "provider_unavailable" in decision.findings


@pytest.mark.asyncio
async def test_optional_provider_failure_does_not_mark_required_incomplete():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "offline"}, request=request)

    endpoint = EVMProviderEndpoint(
        provider="honeypot",
        adapter="honeypot",
        url_template="https://honeypot.test/{chain}/{token_address}",
        required=False,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        metadata = await EVMProviderIngestor(
            [endpoint],
            retry_policy=EVMRetryPolicy(max_attempts=1),
            http_client=client,
        ).collect(chain="arbitrum", token_address="0xToken")

    assert "provider_incomplete" not in metadata["risk_evidence"]
    assert metadata["risk_evidence"]["provenance"][0]["error_class"] == "http_error"


@pytest.mark.asyncio
async def test_four_provider_observations_merge_into_watchlist_contract():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/goplus":
            payload = {"is_open_source": "1", "is_honeypot": "0", "is_mintable": "0", "is_proxy": "0"}
        elif request.url.path == "/honeypot":
            payload = {
                "honeypotResult": {"isHoneypot": False},
                "simulationResult": {"simulationSuccess": True, "sellSuccess": True},
            }
        elif request.url.path == "/simulation":
            payload = {"status": "passed", "sell_success": True, "simulation_success": True}
        else:
            payload = {"locked_ratio": 95, "custody_verified": True, "liquidity_usd": 25_000}
        return httpx.Response(200, json=payload, request=request)

    endpoints = [
        EVMProviderEndpoint("goplus", "goplus", "https://provider.test/goplus"),
        EVMProviderEndpoint("honeypot", "honeypot", "https://provider.test/honeypot"),
        EVMProviderEndpoint("simulation", "simulation", "https://provider.test/simulation"),
        EVMProviderEndpoint("lp_custody", "lp_custody", "https://provider.test/lp"),
    ]
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        metadata = await EVMProviderIngestor(endpoints, http_client=client).collect(
            chain="ethereum",
            token_address="0xToken",
            holders={"top5_concentration": 0.12},
        )

    decision = evaluate_risk(metadata)
    assert decision.state is RiskState.WATCHLIST
    assert decision.eligible is True
    assert len(metadata["risk_evidence"]["provenance"]) == 4
    assert set(metadata["provider_sources"]) == {"goplus", "honeypot", "simulation", "lp_custody"}
    assert "provider_incomplete" not in metadata["risk_evidence"]


def test_credentials_in_url_and_duplicate_endpoint_names_are_rejected():
    with pytest.raises(ValueError, match="credentials"):
        EVMProviderEndpoint(
            provider="goplus",
            adapter="goplus",
            url_template="https://provider.test/security?api_key=secret",
        )
    with pytest.raises(ValueError, match="embedded"):
        EVMProviderEndpoint(
            provider="goplus",
            adapter="goplus",
            url_template="https://user:secret@provider.test/security",
        )

    first = EVMProviderEndpoint("goplus", "goplus", "https://provider.test/a")
    second = EVMProviderEndpoint("GoPlus", "goplus", "https://provider.test/b")
    with pytest.raises(ValueError, match="unique"):
        EVMProviderIngestor([first, second])


def test_endpoint_and_ingestor_reject_unsafe_identity():
    endpoint = EVMProviderEndpoint("goplus", "goplus", "https://provider.test/{chain}/{token_address}")
    ingestor = EVMProviderIngestor([endpoint])

    with pytest.raises(ValueError, match="unsupported EVM chain"):
        import asyncio

        asyncio.run(ingestor.collect(chain="solana", token_address="Mint"))

    with pytest.raises(ValueError, match="token_address"):
        import asyncio

        asyncio.run(ingestor.collect(chain="ethereum", token_address=""))


@pytest.mark.asyncio
async def test_degen_source_injects_evm_evidence_without_replacing_market_identity():
    class FakeIngestor:
        def __init__(self):
            self.calls = []

        async def collect(self, **kwargs):
            self.calls.append(kwargs)
            return {
                "decoder_status": "verified",
                "provider_sources": ["goplus", "simulation"],
                "provider_observations": {"goplus": {"checked_at": "now"}},
                "risk_evidence": {
                    "evidence_version": "evm-security.v1",
                    "checked_at": "2026-09-08T00:00:00+00:00",
                    "contract": {"verified": True},
                    "exit": {"simulation": {"status": "inconclusive"}},
                    "provider_incomplete": True,
                },
            }

    from app.market_intel.sources.degen import DegenSource

    fake = FakeIngestor()
    quote = MarketQuote(
        symbol="DEGEN_ethereum_0xToken",
        market_type=MarketType.DEGEN,
        source="dexscreener",
        price=0.01,
        metadata={
            "chain": "ethereum",
            "token_address": "0xToken",
            "liquidity_usd": 10_000,
            "provider_sources": ["dexscreener"],
        },
    )

    source = DegenSource(evm_provider_ingestor=fake)
    await source.enrich_evm_evidence([quote])

    assert fake.calls[0]["chain"] == "ethereum"
    assert quote.metadata["token_address"] == "0xToken"
    assert quote.metadata["provider_sources"] == ["dexscreener", "goplus", "simulation"]
    assert quote.metadata["risk_evidence"]["provider_incomplete"] is True


@pytest.mark.asyncio
async def test_degen_enrichment_preserves_existing_risk_and_provider_observations():
    class FakeIngestor:
        async def collect(self, **kwargs):
            return {
                "provider_sources": ["goplus"],
                "provider_observations": {"goplus": {"checked_at": "now"}},
                "risk_evidence": {"provider_incomplete": True},
            }

    from app.market_intel.sources.degen import DegenSource

    quote = MarketQuote(
        symbol="DEGEN_ethereum_0xToken",
        market_type=MarketType.DEGEN,
        source="dexscreener",
        price=0.01,
        metadata={
            "chain": "Ethereum",
            "token_address": "0xToken",
            "risk_evidence": {"demand_observed": True},
            "provider_observations": {"dexscreener": {"liquidity_usd": 10_000}},
        },
    )
    await DegenSource(evm_provider_ingestor=FakeIngestor()).enrich_evm_evidence([quote])

    assert quote.metadata["risk_evidence"]["demand_observed"] is True
    assert set(quote.metadata["provider_observations"]) == {"dexscreener", "goplus"}


def test_registry_is_disabled_by_default_and_never_contains_secret_material():
    registry = EVMProviderRegistry.from_json('{"enabled": false, "endpoints": []}')

    assert registry.safe_status() == {
        "version": "evm-provider-registry.v1",
        "enabled": False,
        "release_gate_approved": False,
        "endpoint_count": 0,
        "providers": [],
        "required_providers": [],
        "secret_bound_providers": [],
        "independence_groups": {},
    }
    ingestor = registry.build_ingestor()
    assert ingestor.endpoints == ()
    with pytest.raises(EVMProviderConfigurationError, match="secret"):
        EVMProviderRegistry.from_mapping(
            {
                "enabled": False,
                "api_key": "fixture-value",
                "endpoints": [],
            }
        )
    with pytest.raises(EVMProviderConfigurationError, match="secret"):
        EVMProviderRegistry.from_mapping({"enabled": False, "metadata": {"api_key": "fixture-value"}})


def test_enabled_registry_requires_release_gate_approval_and_secret_binding():
    config = {
        "enabled": True,
        "release_gate_approved": False,
        "endpoints": [
            {
                "provider": "goplus",
                "adapter": "goplus",
                "url_template": "https://provider.test/{chain}/{token_address}",
                "secret_ref": "secret://market-intel/goplus",
                "secret_header": "X-API-KEY",
            }
        ],
    }
    registry = EVMProviderRegistry.from_mapping(config)
    with pytest.raises(EVMProviderConfigurationError, match="release gate"):
        registry.build_ingestor(secret_resolver={"secret://market-intel/goplus": "fixture-value"})

    approved = EVMProviderRegistry.from_mapping({**config, "release_gate_approved": True})
    with pytest.raises(EVMProviderConfigurationError, match="missing secret"):
        approved.build_ingestor()

    with pytest.raises(EVMProviderConfigurationError, match="invalid secret"):
        approved.build_ingestor(secret_resolver={"secret://market-intel/goplus": "fixture\nsecret"})


def test_endpoint_rejects_header_injection_values():
    with pytest.raises(ValueError, match="header value"):
        EVMProviderEndpoint(
            provider="goplus",
            adapter="goplus",
            url_template="https://provider.test/{chain}/{token_address}",
            headers={"X-API-KEY": "fixture\r\nInjected: true"},
        )


def test_environment_secret_resolver_uses_only_reference_suffix(monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_EVM_SECRET_GOPLUS", "fixture-secret")
    monkeypatch.delenv("MARKET_INTEL_EVM_SECRET_API_KEY", raising=False)

    assert environment_secret_resolver("secret://market-intel/goplus") == "fixture-secret"
    assert environment_secret_resolver("secret://market-intel/goplus/api-key") is None
    assert environment_secret_resolver("secret://market-intel/") is None
    assert environment_secret_resolver("secret://market-intel/goplus") == "fixture-secret"


def test_market_scanner_auto_loads_approved_registry_from_environment(monkeypatch):
    monkeypatch.setenv(
        "MARKET_INTEL_EVM_PROVIDER_REGISTRY_JSON",
        json.dumps(
            {
                "enabled": True,
                "release_gate_approved": True,
                "endpoints": [
                    {
                        "provider": "goplus",
                        "adapter": "goplus",
                        "url_template": "https://provider.test/{chain}/{token_address}",
                        "secret_ref": "secret://market-intel/goplus",
                        "secret_header": "X-API-KEY",
                    }
                ],
            }
        ),
    )
    monkeypatch.setenv("MARKET_INTEL_EVM_SECRET_GOPLUS", "fixture-secret")

    scanner = MarketScanner(enabled_sources=["degen"])
    ingestor = scanner.sources["degen"]._evm_provider_ingestor

    assert ingestor is not None
    assert [endpoint.provider for endpoint in ingestor.endpoints] == ["goplus"]
    assert ingestor.endpoints[0].headers == {"X-API-KEY": "fixture-secret"}


def test_market_scanner_auto_registry_fails_closed_without_release_approval(monkeypatch):
    monkeypatch.setenv(
        "MARKET_INTEL_EVM_PROVIDER_REGISTRY_JSON",
        json.dumps(
            {
                "enabled": True,
                "release_gate_approved": False,
                "endpoints": [
                    {
                        "provider": "goplus",
                        "adapter": "goplus",
                        "url_template": "https://provider.test/{chain}/{token_address}",
                    }
                ],
            }
        ),
    )

    with pytest.raises(EVMProviderConfigurationError, match="release gate"):
        MarketScanner(enabled_sources=["degen"])


@pytest.mark.asyncio
async def test_registry_resolves_secret_into_header_and_keeps_registry_provenance():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "fixture-header-value"
        return httpx.Response(
            200,
            json={"is_open_source": "1", "is_honeypot": "0", "is_mintable": "0", "is_proxy": "0"},
            request=request,
        )

    registry = EVMProviderRegistry.from_mapping(
        {
            "enabled": True,
            "release_gate_approved": True,
            "endpoints": [
                {
                    "provider": "goplus",
                    "adapter": "goplus",
                    "url_template": "https://provider.test/{chain}/{token_address}",
                    "supported_chains": ["ethereum", "base"],
                    "secret_ref": "secret://market-intel/goplus",
                    "secret_header": "X-API-KEY",
                }
            ],
        }
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        metadata = await registry.build_ingestor(
            secret_resolver={"secret://market-intel/goplus": "fixture-header-value"},
            http_client=client,
        ).collect(chain="Ethereum", token_address=" 0xToken ")

    provenance = metadata["risk_evidence"]["provenance"][0]
    assert provenance["registry_version"] == "evm-provider-registry.v1"
    assert "fixture-header-value" not in repr(metadata)
    assert metadata["token_address"] == "0xToken"


@pytest.mark.asyncio
async def test_registry_chain_coverage_failure_is_fail_closed_without_network_call():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={}, request=request)

    registry = EVMProviderRegistry.from_mapping(
        {
            "enabled": True,
            "release_gate_approved": True,
            "endpoints": [
                {
                    "provider": "goplus",
                    "adapter": "goplus",
                    "url_template": "https://provider.test/{chain}/{token_address}",
                    "supported_chains": ["ethereum"],
                }
            ],
        }
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        metadata = await registry.build_ingestor(http_client=client).collect(chain="base", token_address="0xToken")

    assert calls == 0
    assert metadata["risk_evidence"]["provider_incomplete"] is True
    assert metadata["risk_evidence"]["provider_failures"][0]["error_class"] == "no_chain_coverage"


@pytest.mark.asyncio
async def test_independence_group_prevents_same_upstream_from_counting_twice():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"is_open_source": "1", "is_honeypot": "0", "is_mintable": "0", "is_proxy": "0"},
            request=request,
        )

    registry = EVMProviderRegistry.from_mapping(
        {
            "enabled": True,
            "release_gate_approved": True,
            "endpoints": [
                {
                    "provider": "goplus_primary",
                    "adapter": "goplus",
                    "url_template": "https://provider.test/primary/{chain}/{token_address}",
                    "independence_group": "same-upstream",
                },
                {
                    "provider": "goplus_mirror",
                    "adapter": "goplus",
                    "url_template": "https://provider.test/mirror/{chain}/{token_address}",
                    "independence_group": "same-upstream",
                },
            ],
        }
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        metadata = await registry.build_ingestor(http_client=client).collect(chain="ethereum", token_address="0xToken")

    assert metadata["risk_evidence"]["provider_sources"] == ["goplus_mirror", "goplus_primary"]
    assert metadata["risk_evidence"]["independent_provider_count"] == 1
    assert metadata["risk_evidence"]["independence_groups"] == ["same-upstream"]
    assert all(item["independence_group"] == "same-upstream" for item in metadata["risk_evidence"]["provenance"])


def test_market_scanner_wires_explicit_evm_registry_into_degen_source():
    registry = EVMProviderRegistry.from_mapping({"enabled": False, "endpoints": []})
    scanner = MarketScanner(enabled_sources=["degen"], evm_provider_registry=registry)

    source = scanner.sources["degen"]
    assert source._evm_provider_ingestor is not None
    assert source._evm_provider_ingestor.endpoints == ()


def test_market_scanner_rejects_ambiguous_evm_configuration():
    ingestor = EVMProviderIngestor()
    registry = EVMProviderRegistry.from_mapping({"enabled": False, "endpoints": []})

    with pytest.raises(ValueError, match="either evm_provider_ingestor or evm_provider_registry"):
        MarketScanner(
            enabled_sources=["degen"],
            evm_provider_ingestor=ingestor,
            evm_provider_registry=registry,
        )
