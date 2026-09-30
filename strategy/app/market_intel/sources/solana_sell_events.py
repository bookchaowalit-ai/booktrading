"""Pure protocol decoders for sanitized Solana sell transactions.

The module deliberately has no RPC, websocket, wallet, or order dependency.
Callers provide an explicit program-id registry and already-fetched,
sanitized transaction dictionaries.  The fixture-shaped decoder boundary is
strict: a log hint or a familiar program name is not enough to create a sell
event.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.market_intel.solana_event_schema import (
    SOLANA_EVENT_SCHEMA_VERSION,
    DecoderStatus,
    SolanaSellEvent,
    compute_event_id,
)

SOLANA_SELL_DECODER_VERSION = "solana-sell-decoder.v1"
RAYDIUM_PROTOCOL = "raydium"
PUMPSWAP_PROTOCOL = "pumpswap"
RAYDIUM_SELL_DISCRIMINATOR = "raydium.swap.sell.v1"
PUMPSWAP_SELL_DISCRIMINATOR = "pumpswap.swap.sell.v1"

_INTEGER_TEXT = set("0123456789")


def _required_text(value: Any, field_name: str) -> str | None:
    if not isinstance(value, str):
        return None
    result = value.strip()
    return result or None


def _raw_int(value: Any, field_name: str) -> int | None:
    """Accept integer base units without converting floats."""

    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str):
        candidate = value.strip()
        if candidate and set(candidate) <= _INTEGER_TEXT:
            return int(candidate)
    return None


def _index(value: Any, field_name: str) -> int | None:
    return _raw_int(value, field_name)


def _mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _account_roles(
    instruction: Mapping[str, Any],
    required_roles: tuple[str, ...],
) -> dict[str, str] | None:
    roles = _mapping(instruction.get("account_roles"))
    if roles is None:
        return None
    result: dict[str, str] = {}
    for role in required_roles:
        account = _required_text(roles.get(role), f"account_roles.{role}")
        if account is None:
            return None
        result[role] = account
    if len(set(result.values())) < len(result):
        return None
    return result


def _asset(
    instruction: Mapping[str, Any],
    field_name: str,
) -> tuple[str, int] | None:
    asset = _mapping(instruction.get(field_name))
    if asset is None:
        return None
    mint = _required_text(asset.get("mint"), f"{field_name}.mint")
    amount = _raw_int(asset.get("amount_raw"), f"{field_name}.amount_raw")
    if mint is None or amount is None:
        return None
    return mint, amount


def _fixture_sell(
    instruction: Mapping[str, Any],
    *,
    discriminator: str,
    required_roles: tuple[str, ...],
    seller_role: str,
    protocol: str,
    decoder_version: str,
) -> DecodedSolanaSell | None:
    """Decode the shared sanitized fixture shape after protocol checks."""

    if _required_text(instruction.get("discriminator"), "discriminator") != discriminator:
        return None
    if _required_text(instruction.get("event_type"), "event_type") != "sell":
        return None
    if _required_text(instruction.get("side"), "side") != "sell":
        return None
    # The orientation is explicit evidence.  We do not infer it from account
    # ordering or from which mint happens to be common in a transaction.
    if _required_text(instruction.get("orientation"), "orientation") != "token_to_quote":
        return None

    roles = _account_roles(instruction, required_roles)
    token = _asset(instruction, "token")
    quote = _asset(instruction, "quote")
    instruction_index = _index(instruction.get("instruction_index"), "instruction_index")
    event_index = _index(instruction.get("event_index"), "event_index")
    if roles is None or token is None or quote is None:
        return None
    if instruction_index is None or event_index is None:
        return None
    if token[0] == quote[0]:
        return None

    return DecodedSolanaSell(
        protocol=protocol,
        token_address=token[0],
        pool_address=roles["pool"],
        seller_wallet=roles[seller_role],
        token_amount_raw=token[1],
        quote_amount_raw=quote[1],
        quote_mint=quote[0],
        instruction_index=instruction_index,
        event_index=event_index,
        decoder_version=decoder_version,
        decoder_status=DecoderStatus.VERIFIED.value,
    )


@dataclass(frozen=True, slots=True)
class DecodedSolanaSell:
    """Protocol-decoder output before the versioned event envelope is built."""

    protocol: str
    token_address: str
    pool_address: str
    seller_wallet: str
    token_amount_raw: int
    quote_amount_raw: int
    quote_mint: str
    instruction_index: int
    event_index: int
    decoder_version: str
    decoder_status: str = DecoderStatus.VERIFIED.value


DecodedSell = DecodedSolanaSell
SellDecoder = Callable[
    [Mapping[str, Any], Mapping[str, Any]],
    DecodedSolanaSell | None,
]


def _first_instruction(
    transaction: Mapping[str, Any],
    instruction: Mapping[str, Any] | None,
    discriminator: str,
) -> Mapping[str, Any] | None:
    if instruction is not None:
        return instruction
    if transaction.get("discriminator") == discriminator:
        return transaction
    instructions = transaction.get("instructions")
    if not isinstance(instructions, list):
        return None
    matches = [
        candidate
        for candidate in instructions
        if isinstance(candidate, Mapping) and candidate.get("discriminator") == discriminator
    ]
    return matches[0] if len(matches) == 1 else None


def decode_raydium_sell(
    transaction: Mapping[str, Any],
    instruction: Mapping[str, Any] | None = None,
) -> DecodedSolanaSell | None:
    """Decode only the sanitized Raydium fixture discriminator and roles."""

    if not isinstance(transaction, Mapping):
        return None
    candidate = _first_instruction(transaction, instruction, RAYDIUM_SELL_DISCRIMINATOR)
    if candidate is None:
        return None
    return _fixture_sell(
        candidate,
        discriminator=RAYDIUM_SELL_DISCRIMINATOR,
        required_roles=("pool", "seller", "token_source", "quote_destination"),
        seller_role="seller",
        protocol=RAYDIUM_PROTOCOL,
        decoder_version="raydium-fixture-decoder.v1",
    )


def decode_pumpswap_sell(
    transaction: Mapping[str, Any],
    instruction: Mapping[str, Any] | None = None,
) -> DecodedSolanaSell | None:
    """Decode only the sanitized PumpSwap fixture discriminator and roles."""

    if not isinstance(transaction, Mapping):
        return None
    candidate = _first_instruction(transaction, instruction, PUMPSWAP_SELL_DISCRIMINATOR)
    if candidate is None:
        return None
    return _fixture_sell(
        candidate,
        discriminator=PUMPSWAP_SELL_DISCRIMINATOR,
        required_roles=(
            "pool",
            "user",
            "base_vault",
            "quote_vault",
            "user_base_source",
            "user_quote_destination",
        ),
        seller_role="user",
        protocol=PUMPSWAP_PROTOCOL,
        decoder_version="pumpswap-fixture-decoder.v1",
    )


@dataclass(frozen=True, slots=True)
class SolanaProtocolDecoder:
    """One explicit program-id-to-protocol decoder registration."""

    protocol: str
    decoder: SellDecoder
    decoder_version: str = SOLANA_SELL_DECODER_VERSION

    def __post_init__(self) -> None:
        protocol = _required_text(self.protocol, "protocol")
        version = _required_text(self.decoder_version, "decoder_version")
        if protocol is None:
            raise ValueError("protocol is required")
        if version is None:
            raise ValueError("decoder_version is required")
        if not callable(self.decoder):
            raise ValueError("decoder must be callable")
        object.__setattr__(self, "protocol", protocol.lower())
        object.__setattr__(self, "decoder_version", version)


ProtocolDecoder = SolanaProtocolDecoder


def make_decoder_registry(
    *,
    raydium_program_id: str | None = None,
    pumpswap_program_id: str | None = None,
    raydium_decoder: SellDecoder = decode_raydium_sell,
    pumpswap_decoder: SellDecoder = decode_pumpswap_sell,
) -> dict[str, SolanaProtocolDecoder]:
    """Build a registry only from program IDs explicitly supplied by a caller."""

    result: dict[str, SolanaProtocolDecoder] = {}
    if raydium_program_id is not None:
        result[_registry_program_id(raydium_program_id)] = SolanaProtocolDecoder(
            protocol=RAYDIUM_PROTOCOL,
            decoder=raydium_decoder,
            decoder_version="raydium-fixture-decoder.v1",
        )
    if pumpswap_program_id is not None:
        normalized_pumpswap_id = _registry_program_id(pumpswap_program_id)
        if normalized_pumpswap_id in result:
            raise ValueError("Raydium and PumpSwap program IDs must be distinct")
        result[normalized_pumpswap_id] = SolanaProtocolDecoder(
            protocol=PUMPSWAP_PROTOCOL,
            decoder=pumpswap_decoder,
            decoder_version="pumpswap-fixture-decoder.v1",
        )
    if not result:
        raise ValueError("at least one explicit program ID is required")
    return result


build_decoder_registry = make_decoder_registry


def _registry_program_id(value: Any) -> str:
    result = _required_text(value, "program_id")
    if result is None or "|" in result:
        raise ValueError("program_id is required and must not contain '|'")
    return result


def _registration(
    registry: Mapping[str, SolanaProtocolDecoder | Mapping[str, Any] | tuple[str, SellDecoder]],
    program_id: str,
) -> SolanaProtocolDecoder | None:
    entry = registry.get(program_id)
    if entry is None:
        return None
    if isinstance(entry, SolanaProtocolDecoder):
        return entry
    if isinstance(entry, Mapping):
        return SolanaProtocolDecoder(
            protocol=entry.get("protocol"),
            decoder=entry.get("decoder"),
            decoder_version=entry.get("decoder_version", SOLANA_SELL_DECODER_VERSION),
        )
    if isinstance(entry, tuple) and len(entry) == 2:
        return SolanaProtocolDecoder(protocol=entry[0], decoder=entry[1])
    raise ValueError("registry entries must explicitly name a protocol and decoder")


def _transaction_failed(transaction: Mapping[str, Any]) -> bool:
    if transaction.get("failed") is True or transaction.get("success") is False:
        return True
    status = transaction.get("status")
    if isinstance(status, str) and status.strip().lower() in {"failed", "error", "reverted"}:
        return True
    if transaction.get("err") is not None:
        return True
    meta = _mapping(transaction.get("meta"))
    return meta is not None and meta.get("err") is not None


def _transaction_text(
    transaction: Mapping[str, Any],
    override: Any,
    field_name: str,
) -> str | None:
    return _required_text(override if override is not None else transaction.get(field_name), field_name)


def _transaction_index(
    transaction: Mapping[str, Any],
    override: Any,
    field_name: str,
) -> int | None:
    value = override if override is not None else transaction.get(field_name)
    return _index(value, field_name)


def _transaction_datetime(transaction: Mapping[str, Any], override: datetime | str | None) -> datetime | str | None:
    return override if override is not None else transaction.get("observed_at")


def _decoder_output(
    output: DecodedSolanaSell | None,
    registration: SolanaProtocolDecoder,
) -> DecodedSolanaSell | None:
    if output is None or output.protocol != registration.protocol:
        return None
    if output.decoder_status != DecoderStatus.VERIFIED.value:
        return None
    if not _required_text(output.token_address, "token_address"):
        return None
    if not _required_text(output.pool_address, "pool_address"):
        return None
    if not _required_text(output.seller_wallet, "seller_wallet"):
        return None
    if not _required_text(output.quote_mint, "quote_mint"):
        return None
    if _raw_int(output.token_amount_raw, "token_amount_raw") is None:
        return None
    if _raw_int(output.quote_amount_raw, "quote_amount_raw") is None:
        return None
    if _index(output.instruction_index, "instruction_index") is None:
        return None
    if _index(output.event_index, "event_index") is None:
        return None
    return output


def normalize_solana_sell_events(
    transaction: Mapping[str, Any],
    *,
    registry: Mapping[str, SolanaProtocolDecoder | Mapping[str, Any] | tuple[str, SellDecoder]],
    signature: str | None = None,
    slot: int | None = None,
    observed_at: datetime | str | None = None,
    source: str | None = None,
    finality_status: str | None = None,
    reorg_status: str | None = None,
    quote_value_usd: float | int | str | None = None,
) -> list[SolanaSellEvent]:
    """Normalize accepted sell instructions from one sanitized transaction.

    Unknown program IDs, failed transactions, non-sell instructions, and
    decoder failures are ignored.  No field is fetched, inferred from logs, or
    valued from raw amounts.
    """

    if not isinstance(transaction, Mapping):
        raise ValueError("transaction must be a sanitized mapping")
    if not isinstance(registry, Mapping) or not registry:
        raise ValueError("an explicit non-empty decoder registry is required")
    if _transaction_failed(transaction):
        return []

    normalized_signature = _transaction_text(transaction, signature, "signature")
    normalized_slot = _transaction_index(transaction, slot, "slot")
    normalized_observed_at = _transaction_datetime(transaction, observed_at)
    normalized_source = _transaction_text(transaction, source, "source")
    if normalized_signature is None or normalized_slot is None:
        return []
    if normalized_observed_at is None or normalized_source is None:
        return []

    normalized_finality = (
        finality_status if finality_status is not None else transaction.get("finality_status", "unknown")
    )
    normalized_reorg = reorg_status if reorg_status is not None else transaction.get("reorg_status", "unknown")
    instructions = transaction.get("instructions")
    if not isinstance(instructions, list):
        return []

    events: list[SolanaSellEvent] = []
    seen_positions: set[tuple[str, int]] = set()
    for instruction in instructions:
        if not isinstance(instruction, Mapping):
            continue
        program_id = _required_text(instruction.get("program_id"), "program_id")
        if program_id is None:
            continue
        registration = _registration(registry, program_id)
        if registration is None:
            continue
        try:
            decoded = _decoder_output(
                registration.decoder(transaction, instruction),
                registration,
            )
            if decoded is None:
                continue
            position = (normalized_signature, decoded.event_index)
            if position in seen_positions:
                # Two accepted instructions sharing an event position cannot
                # be reconciled safely; quarantine the transaction instead of
                # silently dropping one interpretation.
                return []
            seen_positions.add(position)
            event_id = compute_event_id(
                "solana",
                decoded.protocol,
                program_id,
                normalized_signature,
                decoded.instruction_index,
                decoded.event_index,
            )
            event = SolanaSellEvent(
                event_id=event_id,
                event_schema_version=SOLANA_EVENT_SCHEMA_VERSION,
                chain="solana",
                protocol=decoded.protocol,
                program_id=program_id,
                event_type="sell",
                signature=normalized_signature,
                slot=normalized_slot,
                instruction_index=decoded.instruction_index,
                event_index=decoded.event_index,
                token_address=decoded.token_address,
                pool_address=decoded.pool_address,
                seller_wallet=decoded.seller_wallet,
                token_amount_raw=decoded.token_amount_raw,
                quote_amount_raw=decoded.quote_amount_raw,
                quote_mint=decoded.quote_mint,
                observed_at=normalized_observed_at,
                source=normalized_source,
                decoder_version=registration.decoder_version,
                decoder_status=decoded.decoder_status,
                finality_status=normalized_finality,
                reorg_status=normalized_reorg,
                quote_value_usd=quote_value_usd,
            )
        except (TypeError, ValueError, KeyError):
            # A malformed or ambiguous fixture is not a normalized event.
            continue
        events.append(event)
    return events


def normalize_solana_sell_event(
    transaction: Mapping[str, Any],
    *,
    registry: Mapping[str, SolanaProtocolDecoder | Mapping[str, Any] | tuple[str, SellDecoder]],
    **kwargs: Any,
) -> SolanaSellEvent | None:
    """Normalize one transaction when it contains at most one sell event."""

    events = normalize_solana_sell_events(transaction, registry=registry, **kwargs)
    if len(events) > 1:
        raise ValueError("transaction contains multiple sell events; use normalize_solana_sell_events")
    return events[0] if events else None


normalize_sell_transaction = normalize_solana_sell_events
normalize_sell_event = normalize_solana_sell_event


__all__ = [
    "PUMPSWAP_PROTOCOL",
    "PUMPSWAP_SELL_DISCRIMINATOR",
    "RAYDIUM_PROTOCOL",
    "RAYDIUM_SELL_DISCRIMINATOR",
    "SOLANA_SELL_DECODER_VERSION",
    "DecodedSell",
    "DecodedSolanaSell",
    "ProtocolDecoder",
    "SellDecoder",
    "SolanaProtocolDecoder",
    "build_decoder_registry",
    "decode_pumpswap_sell",
    "decode_raydium_sell",
    "make_decoder_registry",
    "normalize_sell_event",
    "normalize_sell_transaction",
    "normalize_solana_sell_event",
    "normalize_solana_sell_events",
]
