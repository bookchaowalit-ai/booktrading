"""Read-only Solana discovery for newly-created degen tokens.

This module deliberately stays below the trading boundary.  It observes
program logs and transaction metadata, then emits a quote-shaped record that
the existing market-intelligence pipeline can enrich later.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

import httpx

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

# Pump's public program id.  Other launchpads/AMMs can be added through the
# comma-separated SOLANA_ONCHAIN_PROGRAM_IDS environment variable.
PUMP_PROGRAM_ID = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
SOLANA_RPC_URL = "https://api.mainnet-beta.solana.com"
TOKEN_2022_PROGRAM_ID = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxu"
KNOWN_QUOTE_MINTS = {
    "So11111111111111111111111111111111111111112",  # wrapped SOL
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
    "Es9vMFrzaCERmJfrF4H2FYD4YwGmQX2b9jQxT6J6X7Y",  # USDT
}


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _transaction_mints(transaction: dict[str, Any]) -> list[str]:
    """Return unique token mints visible in a parsed transaction.

    RPC encodings differ between providers, so both pre/post token balances and
    parsed instruction account data are inspected.  Native SOL and wrapped SOL
    are excluded because they are quote assets rather than newly-created coins.
    """

    mints: list[str] = []
    meta = transaction.get("meta") or {}
    for balance_key in ("postTokenBalances", "preTokenBalances"):
        for balance in meta.get(balance_key) or []:
            mint = balance.get("mint") if isinstance(balance, dict) else None
            if mint and mint not in mints:
                mints.append(mint)

    message = ((transaction.get("transaction") or {}).get("message") or {})
    for instruction in message.get("instructions") or []:
        parsed = instruction.get("parsed") if isinstance(instruction, dict) else None
        info = parsed.get("info") if isinstance(parsed, dict) else None
        if isinstance(info, dict):
            mint = info.get("mint")
            if mint and mint not in mints:
                mints.append(mint)

    return [mint for mint in mints if mint not in KNOWN_QUOTE_MINTS]


def classify_logs(logs: Iterable[str]) -> str | None:
    """Classify a transaction using program log text.

    Log text is treated as a hint only.  The source preserves the signature and
    slot so a downstream decoder can reprocess the transaction if a protocol
    changes its wording.
    """

    normalized = " ".join(str(log).lower() for log in logs)
    if any(marker in normalized for marker in ("instruction: create", "create_v2", "program log: create")):
        return "token_created"
    if any(marker in normalized for marker in ("initialize2", "initialize pool", "poolcreated", "create_pool")):
        return "pool_created"
    if any(marker in normalized for marker in ("instruction: migrate", "migrate")):
        return "liquidity_migrated"
    return None


def transaction_to_events(
    transaction: dict[str, Any],
    *,
    signature: str,
    slot: int,
    program_id: str,
    observed_at: datetime | None = None,
) -> list[dict[str, Any]]:
    """Convert one JSON-RPC transaction response into normalized events."""

    meta = transaction.get("meta") or {}
    if meta.get("err") is not None:
        return []
    message = ((transaction.get("transaction") or {}).get("message") or {})
    logs = meta.get("logMessages") or []
    event_type = classify_logs(logs)
    if not event_type:
        return []

    block_time = transaction.get("blockTime")
    observed = observed_at or datetime.now(UTC)
    mints = _transaction_mints(transaction)
    # A creation transaction should normally expose one mint.  Keep one event
    # without a mint when a provider omits parsed balances; it is still useful
    # as a replay/checkpoint marker and is explicitly marked incomplete.
    if not mints:
        mints = [None]

    account_keys = []
    for account in message.get("accountKeys") or []:
        if isinstance(account, dict):
            account_keys.append(account.get("pubkey"))
        elif isinstance(account, str):
            account_keys.append(account)

    # Logs are a discovery hint, not proof of a protocol instruction.  Keep
    # the event for replay/checkpoint purposes, but mark whether a parsed
    # instruction references the subscribed program.  The risk gate
    # quarantines unverified events instead of treating them as opportunities.
    instruction_program_ids: list[str] = []
    for instruction in message.get("instructions") or []:
        if not isinstance(instruction, dict):
            continue
        program = instruction.get("programId") or instruction.get("program")
        if isinstance(program, str):
            instruction_program_ids.append(program)
        program_index = instruction.get("programIdIndex")
        if isinstance(program_index, int) and 0 <= program_index < len(account_keys):
            indexed_program = account_keys[program_index]
            if isinstance(indexed_program, str):
                instruction_program_ids.append(indexed_program)
    decoder_verified = program_id in instruction_program_ids

    events: list[dict[str, Any]] = []
    for mint in mints[:4]:
        event_id = f"{program_id}:{signature}:{event_type}:{mint or 'unknown'}"
        events.append(
            {
                "event_id": str(uuid.uuid5(uuid.NAMESPACE_URL, event_id)),
                "event_type": event_type,
                "signature": signature,
                "slot": _as_int(slot),
                "block_time": block_time,
                "program_id": program_id,
                "chain": "solana",
                "token_address": mint,
                "log_messages": [str(log)[:1000] for log in logs[:100]],
                "account_keys": account_keys[:32],
                "instruction_program_ids": instruction_program_ids[:16],
                "decoder_version": "solana-log-hint.v1",
                "decoder_status": "verified" if decoder_verified else "unverified",
                "observed_at": observed.isoformat(),
                "data_complete": mint is not None and decoder_verified,
                "source": "solana_rpc",
            }
        )
    return events


class SolanaOnchainSource(BaseSource):
    """Bounded RPC backfill source for launchpad and pool events."""

    def __init__(
        self,
        rpc_url: str | None = None,
        program_ids: list[str] | None = None,
        signature_limit: int = 20,
        risk_enabled: bool | None = None,
        risk_max_tokens: int = 10,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.rpc_url = rpc_url or os.getenv("SOLANA_RPC_URL", SOLANA_RPC_URL)
        configured_ids = os.getenv("SOLANA_ONCHAIN_PROGRAM_IDS", "")
        self.program_ids = program_ids or [
            item.strip()
            for item in (configured_ids or PUMP_PROGRAM_ID).split(",")
            if item.strip()
        ]
        self.signature_limit = max(1, min(int(signature_limit), 100))
        configured_risk = os.getenv("SOLANA_ONCHAIN_RISK_ENABLED", "true").lower() in {"1", "true", "yes"}
        self.risk_enabled = configured_risk if risk_enabled is None else risk_enabled
        self.risk_max_tokens = max(0, min(int(risk_max_tokens), 20))
        self._http_client = http_client
        self._last_scan_at: datetime | None = None

    @property
    def source_name(self) -> str:
        return "solana_rpc"

    @property
    def market_type(self) -> MarketType:
        return MarketType.DEGEN

    async def _rpc(self, method: str, params: list[Any]) -> Any:
        payload = {"jsonrpc": "2.0", "id": int(time.time() * 1000), "method": method, "params": params}
        if self._http_client:
            response = await self._http_client.post(self.rpc_url, json=payload)
            response.raise_for_status()
            body = response.json()
        else:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(self.rpc_url, json=payload)
                response.raise_for_status()
                body = response.json()
        if body.get("error"):
            raise RuntimeError(f"Solana RPC {method} failed: {body['error']}")
        return body.get("result")

    async def fetch_quotes(self, symbols: list[str] | None = None) -> list[MarketQuote]:
        del symbols
        quotes: list[MarketQuote] = []
        self._last_scan_at = datetime.now(UTC)
        for program_id in self.program_ids:
            try:
                signatures = await self._rpc(
                    "getSignaturesForAddress",
                    [program_id, {"limit": self.signature_limit, "commitment": "confirmed"}],
                ) or []
                for item in signatures:
                    signature = item.get("signature") if isinstance(item, dict) else None
                    if not signature or item.get("err") is not None:
                        continue
                    transaction = await self._rpc(
                        "getTransaction",
                        [
                            signature,
                            {
                                "encoding": "jsonParsed",
                                "commitment": "confirmed",
                                "maxSupportedTransactionVersion": 0,
                            },
                        ],
                    )
                    if not transaction:
                        continue
                    events = transaction_to_events(
                        transaction,
                        signature=signature,
                        slot=_as_int(item.get("slot")),
                        program_id=program_id,
                    )
                    quotes.extend(self._event_to_quote(event) for event in events)
            except Exception as exc:
                logger.warning("Solana on-chain scan failed for %s: %s", program_id, exc)
        quotes = self._deduplicate(quotes)
        if self.risk_enabled:
            for quote in quotes[: self.risk_max_tokens]:
                token_address = quote.metadata.get("token_address")
                if token_address:
                    quote.metadata["onchain_risk"] = await self.inspect_token_risk(token_address)
        for quote in quotes:
            annotate_risk(quote.metadata)
        return quotes

    async def inspect_token_risk(self, token_address: str) -> dict[str, Any]:
        """Inspect mint controls and holder concentration without trading."""
        inspected_at = datetime.now(UTC).isoformat()
        try:
            account_result = await self._rpc(
                "getAccountInfo",
                [token_address, {"encoding": "jsonParsed", "commitment": "confirmed"}],
            ) or {}
            account = account_result.get("value") if isinstance(account_result, dict) else None
            owner = account.get("owner") if isinstance(account, dict) else None
            parsed = ((account or {}).get("data") or {}).get("parsed") or {}
            info = parsed.get("info") if isinstance(parsed, dict) else {}
            info = info if isinstance(info, dict) else {}
            extensions = info.get("extensions") or []
            extension_names = {
                str(item.get("extension", item.get("type", ""))).lower()
                for item in extensions
                if isinstance(item, dict)
            }

            flags: list[str] = []
            if info.get("mintAuthority"):
                flags.append("mint_authority_present")
            if info.get("freezeAuthority"):
                flags.append("freeze_authority_present")
            if "permanentdelegate" in extension_names:
                flags.append("permanent_delegate")
            if "transferhook" in extension_names:
                flags.append("transfer_hook")
            if "transferfeeconfig" in extension_names:
                flags.append("transfer_fee_config")
            if "defaultaccountstate" in extension_names:
                flags.append("default_account_state")
            if owner == TOKEN_2022_PROGRAM_ID:
                flags.append("token_2022")

            holder_concentration = await self._holder_concentration(token_address, info.get("supply"))
            if holder_concentration is not None:
                if holder_concentration >= 0.50:
                    flags.append("top5_holder_concentration_high")
                elif holder_concentration >= 0.20:
                    flags.append("top5_holder_concentration_elevated")
            else:
                flags.append("holder_concentration_unavailable")

            return {
                "status": "observed",
                "inspected_at": inspected_at,
                "checked_at": inspected_at,
                "evidence_version": "solana-token-risk.v1",
                "owner_program": owner,
                "mint_authority": info.get("mintAuthority"),
                "freeze_authority": info.get("freezeAuthority"),
                "extensions": sorted(extension_names),
                "top5_holder_concentration": holder_concentration,
                "holder_concentration_basis": "largest_token_accounts_raw; pool_and_vault_exclusion_pending",
                "risk_flags": flags,
            }
        except Exception as exc:
            logger.debug("Solana token risk inspection failed for %s: %s", token_address, exc)
            return {
                "status": "unavailable",
                "inspected_at": inspected_at,
                "risk_flags": ["risk_data_unavailable"],
            }

    async def _holder_concentration(self, token_address: str, supply: Any) -> float | None:
        """Calculate top-five holder share from raw integer balances."""
        try:
            supply_value = int(supply)
            if supply_value <= 0:
                return None
            largest = await self._rpc(
                "getTokenLargestAccounts",
                [token_address, {"commitment": "confirmed"}],
            ) or {}
            accounts = largest.get("value") if isinstance(largest, dict) else None
            amounts = [int(item.get("amount", 0)) for item in (accounts or [])[:5] if isinstance(item, dict)]
            return min(1.0, sum(amounts) / supply_value) if amounts else None
        except (TypeError, ValueError, RuntimeError):
            return None

    @staticmethod
    def _event_to_quote(event: dict[str, Any]) -> MarketQuote:
        token_address = event.get("token_address")
        event_id = event["event_id"]
        symbol = f"DEGEN_SOL_{token_address[:8]}" if token_address else f"DEGEN_SOL_{event_id[:8]}"
        return MarketQuote(
            symbol=symbol,
            market_type=MarketType.DEGEN,
            source="solana_rpc",
            price=0.0,
            volume_24h=0.0,
            timestamp=datetime.fromisoformat(event["observed_at"]),
            metadata=event,
        )

    @staticmethod
    def _deduplicate(quotes: list[MarketQuote]) -> list[MarketQuote]:
        seen: set[str] = set()
        result: list[MarketQuote] = []
        for quote in quotes:
            key = quote.metadata.get("event_id") or quote.symbol
            if key in seen:
                continue
            seen.add(key)
            result.append(quote)
        return result

    async def scan_opportunities(self, quotes: list[MarketQuote]) -> list[MarketOpportunity]:
        opportunities: list[MarketOpportunity] = []
        for quote in quotes:
            metadata = quote.metadata
            annotate_risk(metadata)
            if not opportunity_allowed(metadata):
                continue
            completeness = 0.15 if metadata.get("data_complete") else 0.05
            opportunities.append(
                MarketOpportunity(
                    opportunity_id=str(uuid.uuid4()),
                    symbol=quote.symbol,
                    market_type=MarketType.DEGEN,
                    source="solana_rpc",
                    opportunity_type=OpportunityType.EARLY_ALPHA,
                    severity=Severity.MEDIUM,
                    title=f"New Solana on-chain event: {metadata.get('event_type', 'unknown')}",
                    description=(
                        "On-chain discovery only; no trade recommendation. "
                        f"Signature: {metadata.get('signature', 'unknown')}"
                    ),
                    current_price=0.0,
                    confidence=completeness,
                    metadata={**metadata, "risk_flags": ["price_unavailable", "onchain_event_unenriched"]},
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
