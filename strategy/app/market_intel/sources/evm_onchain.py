"""Read-only EVM factory-event discovery for newly-created pools.

The source polls ``eth_getLogs`` for explicitly configured factory addresses
and event topics.  It emits discovery records with no price and no trading
side effects; the risk gate must keep them out of opportunity ranking until
security and exit evidence is attached.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
from collections.abc import Awaitable, Callable, Iterable, Mapping
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qsl, urlsplit

import httpx

from app.market_intel.evm_provider import EVMRetryPolicy
from app.market_intel.evm_security import SUPPORTED_EVM_CHAINS
from app.market_intel.models import (
    MarketOpportunity,
    MarketQuote,
    MarketSummary,
    MarketType,
    OpportunityType,
    Severity,
)
from app.market_intel.risk_gate import annotate_risk, opportunity_allowed
from app.market_intel.sources.base import BaseSource

logger = logging.getLogger(__name__)

EVM_ONCHAIN_VERSION = "evm-onchain-events.v1"
_SENSITIVE_QUERY_KEYS = frozenset({"key", "api_key", "apikey", "token", "access_token", "secret", "password"})
_HEX_32_RE = r"^0x[0-9a-fA-F]{64}$"


def _normalize_chain(chain: str) -> str:
    normalized = str(chain).strip().lower()
    if normalized not in SUPPORTED_EVM_CHAINS:
        raise ValueError(f"unsupported EVM chain: {chain}")
    return normalized


def _validate_url(url: str) -> str:
    value = str(url).strip()
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.netloc or parts.username or parts.password:
        raise ValueError("EVM on-chain RPC URL must use http(s) without embedded credentials")
    if any(key.lower().replace("-", "_") in _SENSITIVE_QUERY_KEYS for key, _ in parse_qsl(parts.query)):
        raise ValueError("EVM on-chain RPC URL cannot contain credential query parameters")
    return value


def _as_hex_int(value: Any) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return max(0, value)
    text = str(value or "0").strip().lower()
    try:
        return max(0, int(text, 16) if text.startswith("0x") else int(text))
    except ValueError:
        return 0


def _required_block_number(value: Any) -> int:
    """Parse an RPC block number without turning malformed data into zero."""

    if isinstance(value, int) and not isinstance(value, bool):
        return max(0, value)
    text = str(value or "").strip().lower()
    if re.fullmatch(r"0x[0-9a-f]+", text) is None:
        raise RuntimeError("EVM RPC block number has invalid shape")
    return int(text, 16)


def _address_from_word(value: Any) -> str | None:
    text = str(value or "").lower()
    if text.startswith("0x"):
        text = text[2:]
    if len(text) < 40:
        return None
    address = "0x" + text[-40:]
    try:
        return None if int(address[2:], 16) == 0 else address
    except ValueError:
        return None


def _topics_for_chain(value: Any) -> tuple[str, ...]:
    raw = [value] if isinstance(value, str) else list(value or [])
    topics = tuple(str(item).strip().lower() for item in raw if str(item).strip())
    if not topics or any(re.fullmatch(_HEX_32_RE, topic) is None for topic in topics):
        raise ValueError("EVM on-chain event topics must be 32-byte hex values")
    return topics


def _parse_json_env(name: str) -> Mapping[str, Any]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{name} must be valid JSON") from exc
    if not isinstance(parsed, Mapping):
        raise ValueError(f"{name} must be a JSON object")
    return parsed


class EVMOnchainSource(BaseSource):
    """Bounded, polling-based EVM factory event source."""

    def __init__(
        self,
        rpc_urls: Mapping[str, str] | None = None,
        factory_addresses: Mapping[str, Iterable[str]] | None = None,
        event_topics: Mapping[str, str | Iterable[str]] | None = None,
        block_lookback: int = 100,
        http_client: httpx.AsyncClient | None = None,
        retry_policy: EVMRetryPolicy | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ):
        if rpc_urls is None:
            rpc_urls = _parse_json_env("EVM_ONCHAIN_RPC_URLS_JSON")
        if factory_addresses is None:
            factory_addresses = _parse_json_env("EVM_ONCHAIN_FACTORY_ADDRESSES_JSON")
        if event_topics is None:
            event_topics = _parse_json_env("EVM_ONCHAIN_EVENT_TOPICS_JSON")

        self.rpc_urls = {
            _normalize_chain(chain): _validate_url(url) for chain, url in rpc_urls.items() if str(url).strip()
        }
        self.factory_addresses: dict[str, tuple[str, ...]] = {}
        for chain, addresses in factory_addresses.items():
            normalized_chain = _normalize_chain(chain)
            if isinstance(addresses, str):
                raise ValueError("EVM factory addresses must be a list")
            values = tuple(str(address).strip().lower() for address in addresses if str(address).strip())
            if not values:
                continue
            if any(re.fullmatch(r"0x[0-9a-f]{40}", address) is None for address in values):
                raise ValueError("EVM factory addresses must be 20-byte hex addresses")
            self.factory_addresses[normalized_chain] = tuple(sorted(set(values)))
        self.event_topics = {
            _normalize_chain(chain): _topics_for_chain(topics) for chain, topics in event_topics.items()
        }
        self.block_lookback = max(1, min(int(block_lookback), 5_000))
        self._http_client = http_client
        self.retry_policy = retry_policy or EVMRetryPolicy(max_attempts=2, timeout_seconds=10)
        self._sleep = sleep or asyncio.sleep
        self._last_scan_at: datetime | None = None
        self._last_blocks: dict[str, int] = {}
        self._seen_event_ids: set[str] = set()
        self._last_errors: dict[str, str] = {}

    @property
    def source_name(self) -> str:
        return "evm_rpc"

    @property
    def market_type(self) -> MarketType:
        return MarketType.DEGEN

    def coverage_status(self) -> dict[str, Any]:
        chains = sorted(set(self.rpc_urls) | set(self.factory_addresses) | set(self.event_topics))
        return {
            "version": EVM_ONCHAIN_VERSION,
            "mode": "polling_eth_getLogs",
            "configured_chains": chains,
            "ready_chains": sorted(
                chain
                for chain in chains
                if chain in self.rpc_urls and chain in self.factory_addresses and chain in self.event_topics
            ),
            "block_lookback": self.block_lookback,
            "last_blocks": dict(self._last_blocks),
            "last_errors": dict(self._last_errors),
            "read_only": True,
            "transactions_submitted": False,
        }

    async def _rpc(self, chain: str, method: str, params: list[Any]) -> Any:
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            client = self._http_client
            try:
                if client is not None:
                    response = await client.post(self.rpc_urls[chain], json=payload)
                    response.raise_for_status()
                    body = response.json()
                else:
                    async with httpx.AsyncClient(timeout=self.retry_policy.timeout_seconds) as owned_client:
                        response = await owned_client.post(self.rpc_urls[chain], json=payload)
                        response.raise_for_status()
                        body = response.json()
                if not isinstance(body, Mapping) or body.get("error"):
                    raise RuntimeError(f"EVM RPC {method} failed")
                return body.get("result")
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                if attempt >= self.retry_policy.max_attempts:
                    raise RuntimeError(f"EVM RPC {method} failed: {exc.__class__.__name__}") from exc
                await self._sleep(self.retry_policy.delay(attempt))
        raise RuntimeError(f"EVM RPC {method} failed")

    async def _fetch_chain(self, chain: str) -> list[MarketQuote]:
        if chain not in self.rpc_urls or chain not in self.factory_addresses or chain not in self.event_topics:
            return []
        latest = _required_block_number(await self._rpc(chain, "eth_blockNumber", []))
        from_block = max(0, latest - self.block_lookback + 1)
        self._last_blocks[chain] = latest
        quotes: list[MarketQuote] = []
        for factory in self.factory_addresses[chain]:
            logs = await self._rpc(
                chain,
                "eth_getLogs",
                [
                    {
                        "fromBlock": hex(from_block),
                        "toBlock": hex(latest),
                        "address": factory,
                        "topics": [list(self.event_topics[chain])],
                    }
                ],
            )
            if not isinstance(logs, list):
                raise RuntimeError("EVM RPC logs result has invalid shape")
            for log in logs:
                if not isinstance(log, Mapping):
                    continue
                quotes.extend(self._log_to_quotes(chain, factory, log))
        return quotes

    def _log_to_quotes(self, chain: str, factory: str, log: Mapping[str, Any]) -> list[MarketQuote]:
        log_address = str(log.get("address") or "").strip().lower()
        if log_address and log_address != factory.lower():
            return []
        topics = [str(item).lower() for item in (log.get("topics") or [])]
        topic = topics[0] if topics else ""
        if topic not in self.event_topics.get(chain, ()):
            return []
        token0 = _address_from_word(topics[1]) if len(topics) > 1 else None
        token1 = _address_from_word(topics[2]) if len(topics) > 2 else None
        data = str(log.get("data") or "")
        pair = _address_from_word(data[2:66]) if data.startswith("0x") and len(data) >= 66 else None
        block_number = _as_hex_int(log.get("blockNumber"))
        tx_hash = str(log.get("transactionHash") or "")
        log_index = _as_hex_int(log.get("logIndex"))
        observed_at = datetime.now(UTC).isoformat()
        event_base = f"{chain}:{factory.lower()}:{tx_hash}:{log_index}:{topic}"
        tokens = ((token0, token1), (token1, token0))
        result: list[MarketQuote] = []
        for token_address, counterparty in tokens:
            if not token_address:
                continue
            event_id = hashlib.sha256(f"{event_base}:{token_address}".encode()).hexdigest()
            decoder_status = "verified" if token0 and token1 and pair else "unverified"
            metadata = {
                "event_id": event_id,
                "event_type": "pool_created",
                "chain": chain,
                "token_address": token_address,
                "counterparty_token": counterparty,
                "pair_address": pair,
                "factory_address": factory,
                "transaction_hash": tx_hash,
                "block_number": block_number,
                "log_index": log_index,
                "event_topic": topic,
                "decoder_version": "evm-pair-created.v1",
                "decoder_status": decoder_status,
                "data_complete": decoder_status == "verified",
                "observed_at": observed_at,
                "checked_at": observed_at,
                "source": self.source_name,
                "provider_sources": [self.source_name],
            }
            result.append(
                MarketQuote(
                    symbol=f"DEGEN_{chain}_{token_address[2:10]}",
                    market_type=MarketType.DEGEN,
                    source=self.source_name,
                    price=0.0,
                    volume_24h=0.0,
                    timestamp=datetime.fromisoformat(observed_at),
                    metadata=metadata,
                )
            )
        return result

    async def fetch_quotes(self, symbols: list[str] | None = None) -> list[MarketQuote]:
        del symbols
        self._last_scan_at = datetime.now(UTC)
        quotes: list[MarketQuote] = []
        for chain in sorted(set(self.rpc_urls) & set(self.factory_addresses) & set(self.event_topics)):
            try:
                quotes.extend(await self._fetch_chain(chain))
                self._last_errors.pop(chain, None)
            except Exception as exc:
                self._last_errors[chain] = exc.__class__.__name__
                logger.warning("EVM on-chain scan failed for %s: %s", chain, exc.__class__.__name__)
        seen: set[str] = set()
        unique: list[MarketQuote] = []
        for quote in quotes:
            event_id = str(quote.metadata.get("event_id") or quote.symbol)
            if event_id in seen or event_id in self._seen_event_ids:
                continue
            seen.add(event_id)
            self._seen_event_ids.add(event_id)
            annotate_risk(quote.metadata)
            unique.append(quote)
        if len(self._seen_event_ids) > 5_000:
            self._seen_event_ids = set(sorted(self._seen_event_ids)[-5_000:])
        return unique

    async def scan_opportunities(self, quotes: list[MarketQuote]) -> list[MarketOpportunity]:
        opportunities: list[MarketOpportunity] = []
        for quote in quotes:
            annotate_risk(quote.metadata)
            if not opportunity_allowed(quote.metadata):
                continue
            opportunities.append(
                MarketOpportunity(
                    opportunity_id=str(quote.metadata.get("event_id") or quote.symbol),
                    symbol=quote.symbol,
                    market_type=MarketType.DEGEN,
                    source=self.source_name,
                    opportunity_type=OpportunityType.EARLY_ALPHA,
                    severity=Severity.MEDIUM,
                    title=f"New EVM pool event: {quote.metadata.get('chain')}",
                    description="On-chain discovery only; price and liquidity are not confirmed.",
                    current_price=0.0,
                    confidence=0.05,
                    metadata=dict(quote.metadata),
                )
            )
        return opportunities

    async def get_summary(self, quotes: list[MarketQuote]) -> MarketSummary:
        return MarketSummary(
            market_type=MarketType.DEGEN,
            total_instruments=len(quotes),
            active_instruments=0,
            total_volume_usd=0.0,
            top_movers=[],
            last_updated=self._last_scan_at,
        )


__all__ = ["EVM_ONCHAIN_VERSION", "EVMOnchainSource"]
