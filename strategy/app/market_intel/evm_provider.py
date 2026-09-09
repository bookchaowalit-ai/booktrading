"""Bounded, read-only EVM provider ingestion.

The ingestion boundary owns network behavior; ``evm_security`` owns provider
field normalization.  This module retries only transient failures, records a
safe provenance summary, and never logs URLs with query strings, headers, or
provider payloads.  A caller must explicitly supply endpoint specifications,
so importing the module or constructing the ingestor never makes a network
request.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qsl, quote, urlsplit

import httpx

from app.market_intel.evm_security import (
    EVM_EVIDENCE_VERSION,
    SUPPORTED_EVM_CHAINS,
    merge_evm_observations,
    normalize_goplus_response,
    normalize_honeypot_response,
    normalize_lp_custody,
    normalize_sell_simulation,
)

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS_CODES = frozenset({408, 425, 429, 500, 502, 503, 504})
_SENSITIVE_QUERY_KEYS = frozenset(
    {"key", "api_key", "apikey", "token", "access_token", "secret", "password", "signature"}
)
_ADAPTERS: dict[str, Callable[..., dict[str, Any]]] = {
    "goplus": normalize_goplus_response,
    "honeypot": normalize_honeypot_response,
    "simulation": normalize_sell_simulation,
    "lp_custody": normalize_lp_custody,
}
EVM_PROVIDER_REGISTRY_VERSION = "evm-provider-registry.v1"
_SECRET_CONFIG_KEYS = frozenset(
    {
        "secret",
        "secret_value",
        "api_key",
        "apikey",
        "token",
        "access_token",
        "password",
        "credential",
        "credentials",
        "private_key",
    }
)
_HEADER_NAME_RE = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
_INDEPENDENCE_GROUP_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$")


def _is_sensitive_query_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return normalized in _SENSITIVE_QUERY_KEYS or normalized.endswith(("_key", "_token", "_secret"))


@dataclass(frozen=True, slots=True)
class EVMRetryPolicy:
    """Bounded retry policy for read-only provider requests."""

    max_attempts: int = 3
    timeout_seconds: float = 8.0
    initial_backoff_seconds: float = 0.25
    max_backoff_seconds: float = 2.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "max_attempts", max(1, min(int(self.max_attempts), 5)))
        object.__setattr__(self, "timeout_seconds", max(0.1, min(float(self.timeout_seconds), 60.0)))
        object.__setattr__(
            self,
            "initial_backoff_seconds",
            max(0.0, min(float(self.initial_backoff_seconds), 30.0)),
        )
        object.__setattr__(self, "max_backoff_seconds", max(0.0, min(float(self.max_backoff_seconds), 60.0)))

    def delay(self, retry_number: int) -> float:
        """Return deterministic exponential backoff for the next retry."""

        return min(self.max_backoff_seconds, self.initial_backoff_seconds * (2 ** max(0, retry_number - 1)))


@dataclass(frozen=True, slots=True)
class EVMProviderEndpoint:
    """A provider endpoint supplied by deployment configuration.

    ``headers`` may contain a secret injected by the caller's secret manager;
    it is excluded from repr and all provenance.  Endpoint URLs must not put
    credentials in query strings.
    """

    provider: str
    adapter: str
    url_template: str
    method: str = "GET"
    chain_id: str | int | None = None
    headers: Mapping[str, str] = field(default_factory=dict, repr=False, compare=False)
    body_template: Mapping[str, Any] | None = field(default=None, repr=False, compare=False)
    required: bool = True
    supported_chains: tuple[str, ...] | None = None
    independence_group: str | None = None

    def __post_init__(self) -> None:
        provider = self.provider.strip().lower()
        adapter = self.adapter.strip().lower()
        method = self.method.strip().upper()
        if not provider:
            raise ValueError("provider is required")
        if adapter not in _ADAPTERS:
            raise ValueError(f"unsupported EVM evidence adapter: {self.adapter}")
        if method not in {"GET", "POST"}:
            raise ValueError("EVM provider method must be GET or POST")
        if self.chain_id is not None and (isinstance(self.chain_id, bool) or not isinstance(self.chain_id, (str, int))):
            raise ValueError("chain_id must be a string or integer")
        if not isinstance(self.headers, Mapping):
            raise ValueError("headers must be a mapping")
        for header_name, header_value in self.headers.items():
            if not isinstance(header_name, str) or _HEADER_NAME_RE.fullmatch(header_name) is None:
                raise ValueError("headers contain an invalid HTTP header name")
            if not isinstance(header_value, str) or any(character in header_value for character in "\r\n"):
                raise ValueError("headers contain an invalid HTTP header value")
        parts = urlsplit(self.url_template)
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            raise ValueError("EVM provider URL must use http(s) and include a host")
        if parts.username or parts.password:
            raise ValueError("provider credentials must not be embedded in the URL")
        for key, _ in parse_qsl(parts.query, keep_blank_values=True):
            if _is_sensitive_query_key(key):
                raise ValueError("provider credentials must be sent through secret-managed headers")
        if self.supported_chains is not None:
            if isinstance(self.supported_chains, str) or not self.supported_chains:
                raise ValueError("supported_chains must be a non-empty sequence")
            supported_chains = tuple(str(chain).strip().lower() for chain in self.supported_chains)
            if any(chain not in SUPPORTED_EVM_CHAINS for chain in supported_chains):
                raise ValueError("supported_chains contains an unsupported EVM chain")
            if len(supported_chains) != len(set(supported_chains)):
                raise ValueError("supported_chains must be unique")
            object.__setattr__(self, "supported_chains", supported_chains)
        if self.independence_group is not None:
            group = str(self.independence_group).strip().lower()
            if _INDEPENDENCE_GROUP_RE.fullmatch(group) is None:
                raise ValueError("independence_group must be a short safe identifier")
            object.__setattr__(self, "independence_group", group)
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "adapter", adapter)
        object.__setattr__(self, "method", method)

    def supports_chain(self, chain: str) -> bool:
        """Return whether this endpoint is approved for the requested chain."""

        return self.supported_chains is None or chain.strip().lower() in self.supported_chains


@dataclass(frozen=True, slots=True)
class EVMProviderResponse:
    """Payload plus safe request provenance; raw bytes are never retained."""

    provider: str
    payload: Mapping[str, Any] | None
    provenance: Mapping[str, Any]
    error_class: str | None = None

    @property
    def ok(self) -> bool:
        return self.payload is not None and self.error_class is None


class EVMProviderConfigurationError(ValueError):
    """Raised when a provider registry cannot be safely materialized."""


@dataclass(frozen=True, slots=True)
class EVMProviderRegistryEntry:
    """Secret-free endpoint declaration resolved at deployment time."""

    provider: str
    adapter: str
    url_template: str
    method: str = "GET"
    chain_id: str | int | None = None
    supported_chains: tuple[str, ...] | None = None
    required: bool = True
    secret_ref: str | None = None
    secret_header: str | None = None
    body_template: Mapping[str, Any] | None = None
    independence_group: str | None = None

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> EVMProviderRegistryEntry:
        if not isinstance(value, Mapping):
            raise EVMProviderConfigurationError("provider registry endpoint must be an object")
        allowed = {
            "provider",
            "adapter",
            "url_template",
            "method",
            "chain_id",
            "supported_chains",
            "required",
            "secret_ref",
            "secret_header",
            "body_template",
            "independence_group",
        }
        unknown = set(value) - allowed
        if unknown:
            raise EVMProviderConfigurationError("provider registry contains an unsupported endpoint field")
        if any(_is_secret_config_key(str(key)) for key in value):
            raise EVMProviderConfigurationError("provider registry cannot contain secret values")
        supported = value.get("supported_chains")
        if supported is not None:
            if isinstance(supported, str) or not isinstance(supported, (list, tuple)):
                raise EVMProviderConfigurationError("supported_chains must be a list")
            supported = tuple(str(chain).strip().lower() for chain in supported)
        secret_ref = value.get("secret_ref")
        if secret_ref is not None:
            if (
                not isinstance(secret_ref, str)
                or not secret_ref.strip()
                or any(character in secret_ref for character in "\r\n")
            ):
                raise EVMProviderConfigurationError("secret_ref must be a non-empty safe reference")
            secret_ref = secret_ref.strip()
        secret_header = value.get("secret_header")
        if secret_header is not None:
            if not isinstance(secret_header, str) or not _HEADER_NAME_RE.fullmatch(secret_header.strip()):
                raise EVMProviderConfigurationError("secret_header must be a valid HTTP header name")
            secret_header = secret_header.strip()
        if secret_ref and not secret_header:
            raise EVMProviderConfigurationError("secret_header is required when secret_ref is configured")
        if secret_header and not secret_ref:
            raise EVMProviderConfigurationError("secret_ref is required when secret_header is configured")
        body_template = value.get("body_template")
        if body_template is not None:
            if not isinstance(body_template, Mapping) or _contains_secret_config_key(body_template):
                raise EVMProviderConfigurationError("body_template cannot contain secret fields")
            body_template = dict(body_template)
        independence_group = value.get("independence_group")
        if independence_group is not None:
            if (
                not isinstance(independence_group, str)
                or _INDEPENDENCE_GROUP_RE.fullmatch(independence_group.strip()) is None
            ):
                raise EVMProviderConfigurationError("independence_group must be a short safe identifier")
            independence_group = independence_group.strip().lower()
        try:
            return cls(
                provider=str(value.get("provider", "")).strip().lower(),
                adapter=str(value.get("adapter", "")).strip().lower(),
                url_template=str(value.get("url_template", "")).strip(),
                method=str(value.get("method", "GET")).strip().upper(),
                chain_id=value.get("chain_id"),
                supported_chains=supported,
                required=_strict_bool(value.get("required", True), "required"),
                secret_ref=secret_ref,
                secret_header=secret_header,
                body_template=body_template,
                independence_group=independence_group,
            )
        except (TypeError, ValueError) as exc:
            raise EVMProviderConfigurationError("invalid provider registry endpoint") from exc

    def resolve(self, secret_resolver: SecretResolver | Mapping[str, str] | None) -> EVMProviderEndpoint:
        """Materialize an endpoint without ever placing a secret in config."""

        headers: dict[str, str] = {}
        if self.secret_ref:
            if secret_resolver is None:
                raise EVMProviderConfigurationError(f"missing secret binding for provider {self.provider}")
            try:
                value = (
                    secret_resolver.get(self.secret_ref)
                    if isinstance(secret_resolver, Mapping)
                    else secret_resolver(self.secret_ref)
                )
            except Exception as exc:
                raise EVMProviderConfigurationError(f"secret binding failed for provider {self.provider}") from exc
            if not isinstance(value, str) or not value.strip():
                raise EVMProviderConfigurationError(f"missing secret binding for provider {self.provider}")
            if any(character in value for character in "\r\n"):
                raise EVMProviderConfigurationError(f"invalid secret binding for provider {self.provider}")
            headers[self.secret_header or ""] = value
        return EVMProviderEndpoint(
            provider=self.provider,
            adapter=self.adapter,
            url_template=self.url_template,
            method=self.method,
            chain_id=self.chain_id,
            headers=headers,
            body_template=self.body_template,
            required=self.required,
            supported_chains=self.supported_chains,
            independence_group=self.independence_group,
        )


SecretResolver = Callable[[str], str | None]


def environment_secret_resolver(reference: str) -> str | None:
    """Resolve a registry ``secret_ref`` from one explicitly named env var.

    The registry remains secret-free.  Only the final reference component is
    converted to an allowlisted variable name, so a reference such as
    ``secret://market-intel/goplus`` maps to
    ``MARKET_INTEL_EVM_SECRET_GOPLUS``.  The value is returned to the caller
    for in-memory header injection and is never included in diagnostics.
    """

    if not isinstance(reference, str):
        return None
    suffix = reference.rsplit("/", 1)[-1].strip()
    suffix = re.sub(r"[^A-Za-z0-9]+", "_", suffix).strip("_").upper()
    if not suffix:
        return None
    return os.getenv(f"MARKET_INTEL_EVM_SECRET_{suffix}")


def _is_secret_config_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return normalized in _SECRET_CONFIG_KEYS or normalized.endswith(("_key", "_token", "_secret"))


def _contains_secret_config_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(_is_secret_config_key(str(key)) or _contains_secret_config_key(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return any(_contains_secret_config_key(item) for item in value)
    return False


def _strict_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise EVMProviderConfigurationError(f"{field_name} must be boolean")
    return value


@dataclass(frozen=True, slots=True)
class EVMProviderRegistry:
    """Validated, secret-free provider registry for explicit runtime injection."""

    version: str = EVM_PROVIDER_REGISTRY_VERSION
    enabled: bool = False
    release_gate_approved: bool = False
    entries: tuple[EVMProviderRegistryEntry, ...] = ()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> EVMProviderRegistry:
        if not isinstance(value, Mapping):
            raise EVMProviderConfigurationError("provider registry must be an object")
        if _contains_secret_config_key(value):
            raise EVMProviderConfigurationError("provider registry cannot contain secret values")
        allowed = {"version", "enabled", "release_gate_approved", "endpoints"}
        if set(value) - allowed:
            raise EVMProviderConfigurationError("provider registry contains an unsupported field")
        version = str(value.get("version", EVM_PROVIDER_REGISTRY_VERSION)).strip()
        if version != EVM_PROVIDER_REGISTRY_VERSION:
            raise EVMProviderConfigurationError("unsupported EVM provider registry version")
        raw_entries = value.get("endpoints", [])
        if not isinstance(raw_entries, (list, tuple)):
            raise EVMProviderConfigurationError("provider registry endpoints must be a list")
        entries = tuple(EVMProviderRegistryEntry.from_mapping(item) for item in raw_entries)
        providers = [entry.provider.strip().lower() for entry in entries]
        if len(providers) != len(set(providers)):
            raise EVMProviderConfigurationError("provider registry endpoint names must be unique")
        return cls(
            version=version,
            enabled=_strict_bool(value.get("enabled", False), "enabled"),
            release_gate_approved=_strict_bool(value.get("release_gate_approved", False), "release_gate_approved"),
            entries=entries,
        )

    @classmethod
    def from_json(cls, raw: str) -> EVMProviderRegistry:
        try:
            value = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as exc:
            raise EVMProviderConfigurationError("provider registry JSON is invalid") from exc
        try:
            return cls.from_mapping(value)
        except EVMProviderConfigurationError:
            raise
        except (TypeError, ValueError) as exc:
            raise EVMProviderConfigurationError("provider registry JSON is invalid") from exc

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> EVMProviderRegistry:
        values = environ if environ is not None else os.environ
        raw = str(values.get("MARKET_INTEL_EVM_PROVIDER_REGISTRY_JSON", "")).strip()
        return cls() if not raw else cls.from_json(raw)

    def safe_status(self) -> dict[str, Any]:
        """Return diagnostics without secret references or endpoint credentials."""

        return {
            "version": self.version,
            "enabled": self.enabled,
            "release_gate_approved": self.release_gate_approved,
            "endpoint_count": len(self.entries),
            "providers": [entry.provider for entry in self.entries],
            "required_providers": [entry.provider for entry in self.entries if entry.required],
            "secret_bound_providers": [entry.provider for entry in self.entries if entry.secret_ref],
            "independence_groups": {
                entry.provider: entry.independence_group or entry.provider for entry in self.entries
            },
        }

    def build_ingestor(
        self,
        *,
        secret_resolver: SecretResolver | Mapping[str, str] | None = None,
        retry_policy: EVMRetryPolicy | None = None,
        http_client: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> EVMProviderIngestor:
        """Build an ingestor only after explicit enablement and release approval."""

        if not self.enabled:
            return EVMProviderIngestor(
                retry_policy=retry_policy,
                http_client=http_client,
                sleep=sleep,
                registry_version=self.version,
            )
        if not self.release_gate_approved:
            raise EVMProviderConfigurationError("EVM provider release gate is not approved")
        if not self.entries:
            raise EVMProviderConfigurationError("enabled EVM provider registry has no endpoints")
        endpoints = tuple(entry.resolve(secret_resolver) for entry in self.entries)
        return EVMProviderIngestor(
            endpoints,
            retry_policy=retry_policy,
            http_client=http_client,
            sleep=sleep,
            registry_version=self.version,
        )


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


def _render_template(value: Any, values: Mapping[str, Any]) -> Any:
    if isinstance(value, str):
        return value.format_map({key: str(item) for key, item in values.items()})
    if isinstance(value, Mapping):
        return {key: _render_template(item, values) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_render_template(item, values) for item in value]
    return value


def _render_url(endpoint: EVMProviderEndpoint, *, chain: str, token_address: str) -> str:
    values = {
        "chain": chain,
        "chain_id": endpoint.chain_id if endpoint.chain_id is not None else chain,
        "token_address": quote(token_address, safe=""),
    }
    rendered = endpoint.url_template.format_map({key: str(value) for key, value in values.items()})
    parts = urlsplit(rendered)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError("EVM provider URL must use http(s) and include a host")
    if parts.username or parts.password:
        raise ValueError("provider credentials must not be embedded in the URL")
    for key, _ in parse_qsl(parts.query, keep_blank_values=True):
        if _is_sensitive_query_key(key):
            raise ValueError("provider credentials must be sent through secret-managed headers")
    return rendered


def _safe_endpoint_provenance(url: str) -> dict[str, str]:
    parts = urlsplit(url)
    return {
        "scheme": parts.scheme,
        "host": parts.hostname or "",
        "path": parts.path or "/",
    }


def _retry_after(response: httpx.Response, policy: EVMRetryPolicy) -> float | None:
    raw = response.headers.get("retry-after")
    if raw is None:
        return None
    try:
        return max(0.0, min(float(raw), policy.max_backoff_seconds))
    except ValueError:
        return None


class EVMProviderIngestor:
    """Fetch and normalize explicitly configured EVM provider observations."""

    def __init__(
        self,
        endpoints: list[EVMProviderEndpoint] | tuple[EVMProviderEndpoint, ...] = (),
        *,
        retry_policy: EVMRetryPolicy | None = None,
        http_client: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
        registry_version: str | None = None,
    ):
        self.endpoints = tuple(endpoints)
        providers = [endpoint.provider for endpoint in self.endpoints]
        if len(providers) != len(set(providers)):
            raise ValueError("EVM provider endpoint names must be unique")
        self.retry_policy = retry_policy or EVMRetryPolicy()
        self._http_client = http_client
        self._sleep = sleep or asyncio.sleep
        self.registry_version = registry_version

    async def _request_json(
        self,
        endpoint: EVMProviderEndpoint,
        *,
        chain: str,
        token_address: str,
    ) -> EVMProviderResponse:
        started = time.monotonic()
        fetched_at = _iso_now()
        url = _render_url(endpoint, chain=chain, token_address=token_address)
        values = {
            "chain": chain,
            "chain_id": endpoint.chain_id if endpoint.chain_id is not None else chain,
            "token_address": token_address,
        }
        body = _render_template(endpoint.body_template, values) if endpoint.body_template is not None else None
        status_code: int | None = None
        attempts = 0
        last_error: str | None = None
        last_hash: str | None = None
        retry_after: float | None = None
        client = self._http_client
        owns_client = client is None
        if owns_client:
            client = httpx.AsyncClient(timeout=self.retry_policy.timeout_seconds)
        try:
            for attempt in range(1, self.retry_policy.max_attempts + 1):
                attempts = attempt
                try:
                    response = await client.request(
                        endpoint.method,
                        url,
                        headers=dict(endpoint.headers),
                        json=body if endpoint.method == "POST" else None,
                    )
                    status_code = response.status_code
                    raw = response.content
                    last_hash = hashlib.sha256(raw).hexdigest()
                    if status_code in _RETRYABLE_STATUS_CODES and attempt < self.retry_policy.max_attempts:
                        retry_after = _retry_after(response, self.retry_policy)
                        await self._sleep(retry_after if retry_after is not None else self.retry_policy.delay(attempt))
                        continue
                    if status_code >= 400:
                        last_error = "http_error"
                        break
                    try:
                        payload = response.json()
                    except ValueError:
                        last_error = "invalid_json"
                        break
                    if not isinstance(payload, Mapping):
                        last_error = "invalid_payload_shape"
                        break
                    provenance = self._provenance(
                        endpoint,
                        url=url,
                        fetched_at=fetched_at,
                        attempts=attempts,
                        status_code=status_code,
                        body_sha256=last_hash,
                        elapsed_ms=(time.monotonic() - started) * 1000,
                        registry_version=self.registry_version,
                    )
                    return EVMProviderResponse(endpoint.provider, payload, provenance)
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    last_error = exc.__class__.__name__.lower()
                    if attempt < self.retry_policy.max_attempts:
                        await self._sleep(self.retry_policy.delay(attempt))
                        continue
                    break
        finally:
            if owns_client and client is not None:
                await client.aclose()

        provenance = self._provenance(
            endpoint,
            url=url,
            fetched_at=fetched_at,
            attempts=attempts,
            status_code=status_code,
            body_sha256=last_hash,
            elapsed_ms=(time.monotonic() - started) * 1000,
            error_class=last_error or "provider_unavailable",
            registry_version=self.registry_version,
        )
        logger.warning("EVM provider unavailable provider=%s status=%s", endpoint.provider, status_code)
        return EVMProviderResponse(endpoint.provider, None, provenance, last_error or "provider_unavailable")

    @staticmethod
    def _provenance(
        endpoint: EVMProviderEndpoint,
        *,
        url: str,
        fetched_at: str,
        attempts: int,
        status_code: int | None,
        body_sha256: str | None,
        elapsed_ms: float,
        error_class: str | None = None,
        registry_version: str | None = None,
    ) -> dict[str, Any]:
        provenance = {
            "provider": endpoint.provider,
            "adapter": endpoint.adapter,
            "method": endpoint.method,
            "endpoint": _safe_endpoint_provenance(url),
            "fetched_at": fetched_at,
            "attempts": attempts,
            "status_code": status_code,
            "body_sha256": body_sha256,
            "elapsed_ms": round(elapsed_ms, 3),
        }
        if endpoint.independence_group:
            provenance["independence_group"] = endpoint.independence_group
        if registry_version:
            provenance["registry_version"] = registry_version
        if error_class:
            provenance["error_class"] = error_class
        return provenance

    async def collect(
        self,
        *,
        chain: str,
        token_address: str,
        liquidity: Mapping[str, Any] | None = None,
        holders: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Fetch configured observations and return canonical risk metadata.

        Required endpoint failures are retained as bounded error metadata.  The
        risk gate turns that marker into ``insufficient_evidence`` instead of
        allowing the successful providers to create a false pass.
        """

        normalized_chain = chain.strip().lower()
        if normalized_chain not in SUPPORTED_EVM_CHAINS:
            raise ValueError(f"unsupported EVM chain: {chain}")
        normalized_token_address = token_address.strip()
        if not normalized_token_address:
            raise ValueError("token_address is required")
        active_endpoints = tuple(endpoint for endpoint in self.endpoints if endpoint.supports_chain(normalized_chain))
        responses = await asyncio.gather(
            *(
                self._request_json(endpoint, chain=normalized_chain, token_address=normalized_token_address)
                for endpoint in active_endpoints
            )
        )
        observations: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        provenance: list[dict[str, Any]] = []
        endpoint_by_provider = {endpoint.provider: endpoint for endpoint in active_endpoints}
        for response in responses:
            provenance.append(dict(response.provenance))
            if not response.ok:
                endpoint = endpoint_by_provider[response.provider]
                if endpoint.required:
                    failures.append(
                        {
                            "provider": response.provider,
                            "adapter": endpoint.adapter,
                            "error_class": response.error_class or "provider_unavailable",
                            "status_code": response.provenance.get("status_code"),
                        }
                    )
                continue
            endpoint = endpoint_by_provider[response.provider]
            normalizer = _ADAPTERS[endpoint.adapter]
            normalized = normalizer(
                response.payload,
                chain=normalized_chain,
                token_address=normalized_token_address,
                checked_at=response.provenance.get("fetched_at"),
            )
            normalized["provenance"] = dict(response.provenance)
            normalized["provider_id"] = endpoint.provider
            if endpoint.independence_group:
                normalized["independence_group"] = endpoint.independence_group
            observations.append(normalized)

        if observations:
            metadata = merge_evm_observations(
                observations,
                chain=normalized_chain,
                token_address=normalized_token_address,
                checked_at=_iso_now(),
                liquidity=liquidity,
                holders=holders,
            )
        else:
            metadata = {
                "chain": normalized_chain,
                "token_address": token_address,
                "decoder_status": "verified",
                "risk_evidence": {
                    "evidence_version": EVM_EVIDENCE_VERSION,
                    "checked_at": _iso_now(),
                    "provider_sources": [],
                    "independent_provider_count": 0,
                    "lp_custody_verification_required": True,
                },
                "provider_sources": [],
                "provider_observations": {},
            }
        risk = metadata.setdefault("risk_evidence", {})
        risk["provenance"] = provenance
        if failures:
            risk["provider_failures"] = failures
            risk["provider_incomplete"] = True
        elif self.endpoints and not active_endpoints and any(endpoint.required for endpoint in self.endpoints):
            risk["provider_failures"] = [
                {
                    "provider": endpoint.provider,
                    "adapter": endpoint.adapter,
                    "error_class": "no_chain_coverage",
                    "status_code": None,
                }
                for endpoint in self.endpoints
                if endpoint.required
            ]
            risk["provider_incomplete"] = True
        return metadata


__all__ = [
    "EVM_PROVIDER_REGISTRY_VERSION",
    "EVMProviderConfigurationError",
    "EVMProviderEndpoint",
    "EVMProviderIngestor",
    "EVMProviderRegistry",
    "EVMProviderRegistryEntry",
    "EVMProviderResponse",
    "EVMRetryPolicy",
    "environment_secret_resolver",
]
