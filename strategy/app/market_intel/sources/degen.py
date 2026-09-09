"""
Degen/Meme coin scanner — finds trending early-stage tokens via DexScreener API.
Focuses on Solana and BSC chains (low gas, high activity).

DexScreener API is FREE and requires no API key.
"""

import logging
import os
import uuid
from datetime import UTC, datetime

import httpx

from app.market_intel.evm_provider import EVMProviderIngestor
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
from app.market_intel.sources.evm_onchain import EVMOnchainSource
from app.market_intel.sources.solana_onchain import SolanaOnchainSource

logger = logging.getLogger(__name__)

# DexScreener API (free, no key)
DEXSCREENER_BASE = "https://api.dexscreener.com"

# Chains to scan (low gas, high meme activity)
TARGET_CHAINS = ["solana", "bsc", "ethereum", "base", "arbitrum"]

# Filters for quality
MIN_LIQUIDITY_USD = 5000  # At least $5k liquidity
MIN_VOLUME_24H_USD = 10000  # At least $10k 24h volume
MIN_TXNS_24H = 50  # At least 50 transactions
REQUIRED_EVM_ADAPTERS = frozenset({"goplus", "honeypot", "simulation", "lp_custody"})


class DegenSource(BaseSource):
    """
    Scans DexScreener for trending meme/degen tokens.
    Returns early-stage tokens with momentum signals.
    """

    def __init__(
        self,
        onchain_source: SolanaOnchainSource | None = None,
        risk_gate_enabled: bool | None = None,
        evm_provider_ingestor: EVMProviderIngestor | None = None,
        evm_onchain_source: EVMOnchainSource | None = None,
    ):
        self._name = "degen"
        # On-chain polling is opt-in for the existing five-minute scanner.  A
        # dedicated SolanaOnchainStream provides low-latency discovery when
        # SOLANA_WS_URL/MARKET_INTEL_ONCHAIN_ENABLED is configured.
        enabled = os.getenv("MARKET_INTEL_ONCHAIN_ENABLED", "false").lower() in {"1", "true", "yes"}
        self._onchain_source = (
            onchain_source if onchain_source is not None else (SolanaOnchainSource() if enabled else None)
        )
        configured_gate = os.getenv("MARKET_INTEL_RISK_GATE_ENABLED", "true").lower() in {"1", "true", "yes"}
        self._risk_gate_enabled = configured_gate if risk_gate_enabled is None else risk_gate_enabled
        # Provider ingestion is dependency-injected and therefore opt-in.  An
        # empty/default scanner never creates network calls to security APIs.
        self._evm_provider_ingestor = evm_provider_ingestor
        self._evm_onchain_source = evm_onchain_source

    @property
    def source_name(self) -> str:
        return self._name

    @property
    def market_type(self) -> MarketType:
        return MarketType.DEGEN

    def coverage_status(self) -> dict[str, object]:
        """Return configured discovery paths without exposing credentials."""

        provider = self._evm_provider_ingestor
        endpoints = tuple(getattr(provider, "endpoints", ())) if provider is not None else ()
        evm_chains = ("ethereum", "bsc", "base", "arbitrum")
        return {
            "version": "degen-coverage.v1",
            "target_chains": list(TARGET_CHAINS),
            "priced_discovery": {"provider": "dexscreener", "mode": "bounded_polling"},
            "solana_onchain": {"enabled": self._onchain_source is not None},
            "evm_onchain": (
                self._evm_onchain_source.coverage_status()
                if self._evm_onchain_source is not None
                else {"enabled": False, "ready_chains": []}
            ),
            "evm_security": {
                "enabled": bool(endpoints),
                "providers": [endpoint.provider for endpoint in endpoints],
                "chain_coverage": {
                    chain: {
                        "present_adapters": sorted(
                            {endpoint.adapter for endpoint in endpoints if endpoint.supports_chain(chain)}
                        ),
                        "missing_required_adapters": sorted(
                            REQUIRED_EVM_ADAPTERS
                            - {endpoint.adapter for endpoint in endpoints if endpoint.supports_chain(chain)}
                        ),
                    }
                    for chain in evm_chains
                }
                if endpoints
                else {},
            },
        }

    async def fetch_quotes(self, symbols: list[str] | None = None) -> list[MarketQuote]:
        """
        Fetch trending tokens from DexScreener.
        Uses multiple endpoints to find early movers.
        """
        quotes = []

        # 1. Search for boosted/trending tokens
        try:
            boosted = await self._fetch_boosted_tokens()
            quotes.extend(boosted)
        except Exception as e:
            logger.warning(f"DexScreener boosted tokens failed: {e}")

        # 2. Search specific chains for new pairs
        for chain in TARGET_CHAINS:
            try:
                chain_quotes = await self._fetch_chain_trending(chain)
                quotes.extend(chain_quotes)
            except Exception as e:
                logger.warning(f"DexScreener {chain} failed: {e}")

        # 3. Search for specific meme keywords
        try:
            meme_quotes = await self._search_meme_keywords()
            quotes.extend(meme_quotes)
        except Exception as e:
            logger.warning(f"Meme keyword search failed: {e}")

        # Direct chain discovery catches launches before an indexer has priced
        # them.  It intentionally emits price=0 until a market-data provider
        # can confirm a tradeable pair.
        if self._onchain_source:
            try:
                quotes.extend(await self._onchain_source.fetch_quotes())
            except Exception as e:
                logger.warning(f"Solana on-chain discovery failed: {e}")

        if self._evm_onchain_source:
            try:
                quotes.extend(await self._evm_onchain_source.fetch_quotes())
            except Exception as e:
                logger.warning("EVM on-chain discovery failed: %s", e.__class__.__name__)

        quotes = self._deduplicate_quotes(quotes)
        await self._enrich_birdeye(quotes)
        await self.enrich_evm_evidence(quotes)
        self._annotate_risk(quotes)
        return quotes

    async def enrich_evm_evidence(self, quotes: list[MarketQuote]) -> None:
        """Attach configured EVM provider evidence without changing identity.

        The ingestor owns retries and provenance.  This source only merges its
        canonical metadata and re-runs the deterministic gate afterwards.
        """

        if self._evm_provider_ingestor is None:
            return
        candidates = [
            quote
            for quote in quotes
            if str(quote.metadata.get("chain", "")).strip().lower() in {"bsc", "ethereum", "base", "arbitrum"}
            and quote.metadata.get("token_address")
        ]
        try:
            max_candidates = max(0, min(int(os.getenv("MARKET_INTEL_EVM_PROVIDER_MAX_TOKENS", "20")), 50))
        except ValueError:
            max_candidates = 20
        for quote in candidates[:max_candidates]:
            metadata = quote.metadata
            try:
                evidence = await self._evm_provider_ingestor.collect(
                    chain=str(metadata["chain"]),
                    token_address=str(metadata["token_address"]),
                    liquidity={
                        key: metadata[key]
                        for key in ("liquidity_usd", "active_depth_usd")
                        if metadata.get(key) is not None
                    },
                    holders=(
                        {"top5_concentration": metadata["top5_holder_concentration"]}
                        if metadata.get("top5_holder_concentration") is not None
                        else None
                    ),
                )
            except Exception as exc:
                # A provider outage is represented as incomplete evidence when
                # the ingestor can return it.  Unexpected boundary/config
                # errors are logged without payloads and leave the quote gated.
                logger.warning(
                    "EVM provider enrichment failed chain=%s: %s", metadata.get("chain"), exc.__class__.__name__
                )
                metadata.setdefault("risk_evidence", {})["provider_incomplete"] = True
                metadata.setdefault("risk_evidence", {})["provider_failures"] = [
                    {"error_class": exc.__class__.__name__.lower()}
                ]
                continue
            existing_risk = metadata.get("risk_evidence")
            merged_risk = dict(existing_risk) if isinstance(existing_risk, dict) else {}
            incoming_risk = evidence.get("risk_evidence")
            if isinstance(incoming_risk, dict):
                merged_risk.update(incoming_risk)
            metadata["risk_evidence"] = merged_risk
            existing_observations = metadata.get("provider_observations")
            merged_observations = dict(existing_observations) if isinstance(existing_observations, dict) else {}
            incoming_observations = evidence.get("provider_observations")
            if isinstance(incoming_observations, dict):
                merged_observations.update(incoming_observations)
            metadata["provider_observations"] = merged_observations
            metadata["provider_sources"] = sorted(
                set(metadata.get("provider_sources", [])) | set(evidence.get("provider_sources", []))
            )
            if evidence.get("decoder_status"):
                metadata["decoder_status"] = evidence["decoder_status"]
            metadata["evm_evidence_version"] = metadata["risk_evidence"].get("evidence_version")

    async def _enrich_birdeye(self, quotes: list[MarketQuote]) -> None:
        """Optionally attach a second provider observation for Solana tokens.

        Birdeye access is deliberately disabled without an explicit key.  The
        key is read only from the environment and is never placed in metadata,
        logs, or URLs.
        """
        api_key = os.getenv("BIRDEYE_API_KEY")
        if not api_key:
            return
        candidates = [q for q in quotes if q.metadata.get("chain") == "solana" and q.metadata.get("token_address")]
        if not candidates:
            return
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                for quote in candidates[:20]:
                    response = await client.get(
                        "https://public-api.birdeye.so/defi/token_overview",
                        params={"address": quote.metadata["token_address"]},
                        headers={"X-API-KEY": api_key},
                    )
                    if response.status_code != 200:
                        continue
                    payload = response.json()
                    data = payload.get("data") if isinstance(payload, dict) else None
                    if isinstance(data, dict):
                        observations = quote.metadata.setdefault("provider_observations", {})
                        observations["birdeye"] = {
                            key: data.get(key)
                            for key in ("price", "liquidity", "v24hUSD", "mc", "holder")
                            if data.get(key) is not None
                        }
                        quote.metadata["provider_sources"] = sorted(
                            set(quote.metadata.get("provider_sources", [])) | {"birdeye"}
                        )
        except Exception as e:
            logger.debug("Birdeye enrichment unavailable: %s", e)

    @staticmethod
    def _deduplicate_quotes(quotes: list[MarketQuote]) -> list[MarketQuote]:
        """Merge provider observations using chain/address identity."""
        grouped: dict[str, MarketQuote] = {}
        for quote in quotes:
            metadata = quote.metadata
            address = metadata.get("token_address")
            key = f"{metadata.get('chain', 'unknown')}:{address}" if address else quote.symbol
            provider_sources = set(metadata.get("provider_sources", []))
            provider_sources.add(quote.source)
            metadata["provider_sources"] = sorted(provider_sources)
            current = grouped.get(key)
            if current is None:
                grouped[key] = quote
                continue
            current_sources = set(current.metadata.get("provider_sources", [])) | provider_sources
            merged_metadata = DegenSource._merge_metadata(current.metadata, metadata)
            merged_metadata["provider_sources"] = sorted(current_sources)
            current_liquidity = current.metadata.get("liquidity_usd", 0) or 0
            quote_liquidity = metadata.get("liquidity_usd", 0) or 0
            if quote_liquidity > current_liquidity:
                grouped[key] = quote
                grouped[key].metadata = merged_metadata
            else:
                current.metadata = merged_metadata
        return list(grouped.values())

    @staticmethod
    def _merge_metadata(current: dict, incoming: dict) -> dict:
        """Preserve evidence when the highest-liquidity duplicate changes."""
        merged = dict(current)
        for key, value in incoming.items():
            if key == "provider_observations" and isinstance(value, dict):
                observations = dict(merged.get(key) or {})
                observations.update(value)
                merged[key] = observations
            elif key == "provider_sources":
                merged[key] = sorted(set(merged.get(key, [])) | set(value or []))
            elif key not in merged or merged[key] in (None, "", [], {}):
                merged[key] = value
        return merged

    def _annotate_risk(self, quotes: list[MarketQuote]) -> None:
        """Attach a deterministic risk decision to every quote."""
        if not self._risk_gate_enabled:
            return
        for quote in quotes:
            annotate_risk(quote.metadata)

    async def _fetch_boosted_tokens(self) -> list[MarketQuote]:
        """Fetch boosted tokens as discovery hints, never as risk evidence."""
        quotes = []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{DEXSCREENER_BASE}/token-boosts/latest/v1")
                resp.raise_for_status()
                data = resp.json()

                if isinstance(data, list):
                    for item in data[:15]:
                        chain = item.get("chainId", "unknown")
                        token_address = item.get("tokenAddress", "")

                        # Fetch pair data for this token
                        if token_address:
                            pair_data = await self._fetch_pair_by_address(chain, token_address)
                            if pair_data:
                                quote = self._pair_to_quote(pair_data)
                                quote.metadata["discovery_signals"] = ["dexscreener_boost"]
                                quote.metadata["paid_promotion"] = True
                                quotes.append(quote)
        except Exception as e:
            logger.error(f"Boosted tokens fetch error: {e}")

        return quotes

    async def _fetch_pair_by_address(self, chain: str, address: str) -> dict | None:
        """Fetch pair data for a specific token address."""
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(f"{DEXSCREENER_BASE}/latest/dex/tokens/{address}")
                resp.raise_for_status()
                data = resp.json()
                pairs = data.get("pairs", [])
                if pairs:
                    # Return the pair with highest liquidity
                    return max(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))
        except Exception as e:
            logger.debug(f"Pair fetch failed for {address}: {e}")
        return None

    async def _fetch_chain_trending(self, chain: str) -> list[MarketQuote]:
        """Fetch new/trending pairs on a specific chain."""
        quotes = []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Search for high-volume pairs on this chain
                resp = await client.get(
                    f"{DEXSCREENER_BASE}/latest/dex/search",
                    params={"q": "trending"},
                )
                resp.raise_for_status()
                data = resp.json()

                pairs = data.get("pairs", [])
                for pair in pairs[:10]:
                    if pair.get("chainId") != chain:
                        continue

                    liquidity = float(pair.get("liquidity", {}).get("usd", 0) or 0)
                    volume_24h = float(pair.get("volume", {}).get("h24", 0) or 0)

                    # Filter for quality
                    txns = pair.get("txns", {}).get("h24", {}) or {}
                    tx_count = int(txns.get("buys", 0) or 0) + int(txns.get("sells", 0) or 0)
                    if liquidity < MIN_LIQUIDITY_USD or volume_24h < MIN_VOLUME_24H_USD or tx_count < MIN_TXNS_24H:
                        continue

                    quotes.append(self._pair_to_quote(pair))
        except Exception as e:
            logger.error(f"Chain trending fetch error ({chain}): {e}")

        return quotes

    async def _search_meme_keywords(self) -> list[MarketQuote]:
        """Search DexScreener for meme-related tokens."""
        quotes = []
        keywords = ["pepe", "doge", "shib", "cat", "moon", "elon"]

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                for keyword in keywords[:3]:  # Limit requests
                    try:
                        resp = await client.get(
                            f"{DEXSCREENER_BASE}/latest/dex/search",
                            params={"q": keyword},
                        )
                        resp.raise_for_status()
                        data = resp.json()

                        pairs = data.get("pairs", [])
                        for pair in pairs[:5]:
                            liquidity = float(pair.get("liquidity", {}).get("usd", 0) or 0)
                            txns = pair.get("txns", {}).get("h24", {}) or {}
                            tx_count = int(txns.get("buys", 0) or 0) + int(txns.get("sells", 0) or 0)
                            if liquidity < MIN_LIQUIDITY_USD or tx_count < MIN_TXNS_24H:
                                continue

                            quote = self._pair_to_quote(pair)
                            # Avoid duplicates
                            if not any(q.symbol == quote.symbol for q in quotes):
                                quotes.append(quote)
                    except Exception as e:
                        logger.debug(f"Keyword search failed for {keyword}: {e}")
        except Exception as e:
            logger.error(f"Meme keyword search error: {e}")

        return quotes

    def _pair_to_quote(self, pair: dict) -> MarketQuote:
        """Convert DexScreener pair data to MarketQuote."""
        base_token = pair.get("baseToken", {})
        price_usd = float(pair.get("priceUsd", 0) or 0)
        change_24h = float(pair.get("priceChange", {}).get("h24", 0) or 0)
        volume_24h = float(pair.get("volume", {}).get("h24", 0) or 0)
        liquidity = float(pair.get("liquidity", {}).get("usd", 0) or 0)
        txns_24h = pair.get("txns", {}).get("h24", {})
        buys = txns_24h.get("buys", 0)
        sells = txns_24h.get("sells", 0)
        fdv = float(pair.get("fdv", 0) or 0)

        token_address = base_token.get("address", "")
        symbol = base_token.get("symbol", "UNKNOWN")
        chain = pair.get("chainId", "unknown")
        created_at_ms = pair.get("pairCreatedAt")
        created_at_ms = int(created_at_ms) if created_at_ms else None
        age_seconds = None
        if created_at_ms:
            age_seconds = max(0.0, datetime.now(UTC).timestamp() - (created_at_ms / 1000.0))

        return MarketQuote(
            # Address is the identity; symbol remains display metadata only.
            symbol=f"DEGEN_{chain}_{token_address[:8]}" if token_address else f"DEGEN_{chain}_{symbol}",
            market_type=MarketType.DEGEN,
            source="dexscreener",
            price=price_usd,
            change_24h=price_usd * (change_24h / 100) if change_24h else 0,
            change_pct_24h=change_24h,
            volume_24h=volume_24h,
            metadata={
                "name": base_token.get("name", ""),
                "chain": chain,
                "token_address": token_address,
                "pair_address": pair.get("pairAddress", ""),
                "dex": pair.get("dexId", ""),
                "liquidity_usd": liquidity,
                "fdv": fdv,
                "buys_24h": buys,
                "sells_24h": sells,
                "pair_created_at_ms": created_at_ms,
                "pair_age_seconds": age_seconds,
                "pair_url": pair.get("url", ""),
                "price_usd": price_usd,
                "volume_24h_usd": volume_24h,
                "tx_count_24h": int(buys or 0) + int(sells or 0),
                "provider_sources": ["dexscreener"],
            },
        )

    async def scan_opportunities(self, quotes: list[MarketQuote]) -> list[MarketOpportunity]:
        """
        Scan for degen opportunities:
        - High momentum tokens (>20% in 24h)
        - New pairs with high volume (potential early entry)
        - Tokens with buy pressure (buys >> sells)
        """
        opportunities = []

        for q in quotes:
            meta = q.metadata
            if self._risk_gate_enabled:
                # Re-evaluate manually supplied quotes as well as quotes from
                # fetch_quotes; callers must never be able to bypass the gate
                # by omitting the cached metadata fields.
                annotate_risk(meta)
                if not opportunity_allowed(meta):
                    continue
            change_pct = q.change_pct_24h or 0
            liquidity = meta.get("liquidity_usd", 0)
            volume = q.volume_24h or 0
            buys = meta.get("buys_24h", 0)
            sells = meta.get("sells_24h", 0)
            tx_count = int(buys or 0) + int(sells or 0)
            event_type = meta.get("event_type")

            # A launch event is useful before pricing exists, but it is not a
            # momentum signal and must remain visibly low-confidence.
            if event_type in {"token_created", "pool_created", "liquidity_migrated"}:
                opportunities.append(
                    MarketOpportunity(
                        opportunity_id=str(uuid.uuid4()),
                        symbol=q.symbol,
                        market_type=MarketType.DEGEN,
                        source=q.source,
                        opportunity_type=OpportunityType.EARLY_ALPHA,
                        severity=Severity.MEDIUM,
                        title=f"New on-chain {event_type.replace('_', ' ')}",
                        description=(
                            "Discovery event only; price and liquidity are not confirmed yet. "
                            f"Signature: {meta.get('signature', 'unknown')}"
                        ),
                        current_price=q.price,
                        confidence=0.15 if meta.get("data_complete") else 0.05,
                        metadata={**meta, "risk_flags": ["price_unavailable", "onchain_event_unenriched"]},
                    )
                )
                continue

            if tx_count < MIN_TXNS_24H:
                continue

            # 1. High momentum (>20% move)
            if abs(change_pct) > 20:
                direction = "pumping" if change_pct > 0 else "dumping"
                severity = Severity.HIGH if change_pct > 50 else Severity.MEDIUM
                confidence = 0.3
                if liquidity >= 100_000:
                    confidence += 0.15
                if volume >= 100_000:
                    confidence += 0.15
                if tx_count >= 500:
                    confidence += 0.1
                if buys > sells * 2 and sells > 0:
                    confidence += 0.05
                confidence = min(0.75, confidence)
                opportunities.append(
                    MarketOpportunity(
                        opportunity_id=str(uuid.uuid4()),
                        symbol=q.symbol,
                        market_type=MarketType.DEGEN,
                        source="dexscreener",
                        opportunity_type=OpportunityType.TRENDING_DEGEN,
                        severity=severity,
                        title=f"Degen {direction}: {meta.get('name', q.symbol)} ({change_pct:+.0f}%)",
                        description=(
                            f"Chain: {meta.get('chain', 'unknown')}\n"
                            f"Price: ${q.price:.8f}\n"
                            f"Liquidity: ${liquidity:,.0f}\n"
                            f"24h Volume: ${volume:,.0f}\n"
                            f"DEX: {meta.get('dex', 'unknown')}\n"
                            f"URL: {meta.get('pair_url', 'N/A')}"
                        ),
                        current_price=q.price,
                        confidence=confidence,
                        metadata={**meta, "signal_direction": direction, "risk_flags": ["high_volatility"]},
                    )
                )

            # 2. Buy pressure (buys > 2x sells)
            if sells > 0 and buys > sells * 2 and liquidity > 10000:
                ratio = buys / sells
                opportunities.append(
                    MarketOpportunity(
                        opportunity_id=str(uuid.uuid4()),
                        symbol=q.symbol,
                        market_type=MarketType.DEGEN,
                        source="dexscreener",
                        opportunity_type=OpportunityType.VOLUME_SPIKE,
                        severity=Severity.MEDIUM,
                        title=f"Buy pressure: {meta.get('name', q.symbol)} ({ratio:.1f}x buys)",
                        description=(
                            f"Buys: {buys} | Sells: {sells}\nChain: {meta.get('chain')}\nLiquidity: ${liquidity:,.0f}"
                        ),
                        current_price=q.price,
                        confidence=min(0.75, 0.35 + min(ratio / 20, 0.25)),
                        metadata={**meta, "buy_sell_ratio": ratio, "signal_direction": "buy_pressure"},
                    )
                )

        # Sort by severity then volume
        severity_order = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2}
        opportunities.sort(key=lambda o: (severity_order.get(o.severity, 3), -(o.metadata.get("liquidity_usd", 0))))
        return opportunities[:20]

    async def get_summary(self, quotes: list[MarketQuote]) -> MarketSummary:
        """Summary of degen market."""
        chains = {}
        for q in quotes:
            chain = q.metadata.get("chain", "unknown")
            chains[chain] = chains.get(chain, 0) + 1

        return MarketSummary(
            market_type=MarketType.DEGEN,
            total_instruments=len(quotes),
            active_instruments=len([q for q in quotes if (q.volume_24h or 0) > 0]),
            total_volume_usd=sum(q.volume_24h or 0 for q in quotes),
            top_movers=[
                {
                    "name": q.metadata.get("name", q.symbol),
                    "chain": q.metadata.get("chain"),
                    "price_usd": q.price,
                    "change_24h_pct": q.change_pct_24h,
                    "liquidity": q.metadata.get("liquidity_usd", 0),
                    "risk_state": q.metadata.get("risk_state", "unassessed"),
                    "risk_vetoes": q.metadata.get("risk_vetoes", []),
                }
                for q in sorted(quotes, key=lambda x: abs(x.change_pct_24h or 0), reverse=True)[:5]
            ],
            last_updated=datetime.utcnow(),
        )
