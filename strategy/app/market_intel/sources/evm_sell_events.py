"""Pure, fixture-bound EVM sell-event decoders.

This module accepts only caller-supplied decoder registrations and sanitized
transaction/log mappings.  It does not call an RPC, indexer, price service,
wallet service, or order/execution path.  The empty registry is intentional:
no production DEX ABI, address, topic, or protocol is enabled here.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from app.market_intel.evm_event_schema import (
    EVM_EVENT_SCHEMA_VERSION,
    SUPPORTED_EVM_CHAINS,
    DecoderStatus,
    EVMSellEvent,
    compute_event_id,
)

EVM_SELL_DECODER_VERSION = "evm-sell-decoder.v1"
EVM_REGISTRY_KEY_SEPARATOR = "|"

_HEX_ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")
_HEX_32_BYTES = re.compile(r"^0x[0-9a-fA-F]{64}$")
_DECIMAL_INTEGER = re.compile(r"^[0-9]+$")
_HEX_INTEGER = re.compile(r"^0x[0-9a-fA-F]+$")
_TRUE_TEXT = frozenset({"true", "yes", "y", "1"})
_FAILED_STATUS = frozenset({"failed", "error", "reverted", "failure"})

RegistryKey = tuple[str, str, str]


def _required_text(value: Any, field_name: str) -> str | None:
    if not isinstance(value, str):
        return None
    result = value.strip()
    return result or None


def _normalize_chain(value: Any) -> str | None:
    text = _required_text(value, "chain")
    if text is None:
        return None
    normalized = text.lower()
    return normalized if normalized in SUPPORTED_EVM_CHAINS else None


def _normalize_address(value: Any, field_name: str) -> str | None:
    text = _required_text(value, field_name)
    if text is None:
        return None
    normalized = text.lower()
    return normalized if _HEX_ADDRESS.fullmatch(normalized) is not None else None


def _normalize_hash_or_topic(value: Any, field_name: str) -> str | None:
    text = _required_text(value, field_name)
    if text is None:
        return None
    normalized = text.lower()
    return normalized if _HEX_32_BYTES.fullmatch(normalized) is not None else None


def _integer(value: Any, field_name: str, *, allow_hex: bool = True) -> int | None:
    """Read an integer representation without a float conversion."""

    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if _DECIMAL_INTEGER.fullmatch(candidate):
        result = int(candidate, 10)
    elif allow_hex and _HEX_INTEGER.fullmatch(candidate):
        result = int(candidate, 16)
    else:
        return None
    return result if result >= 0 else None


def _quote_asset(value: Any) -> str | None:
    text = _required_text(value, "quote_asset")
    if text is None:
        return None
    if text.lower().startswith("0x"):
        return _normalize_address(text.lower(), "quote_asset")
    if "|" in text:
        return None
    return text


def _mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _same_value(
    values: Iterable[Any],
    normalizer: Callable[[Any], Any],
) -> tuple[bool, Any | None]:
    normalized = [normalizer(value) for value in values]
    if not normalized or any(value is None for value in normalized):
        return False, None
    first = normalized[0]
    return all(value == first for value in normalized), first


def _context_value(
    transaction: Mapping[str, Any],
    log: Mapping[str, Any],
    *,
    transaction_keys: tuple[str, ...] = (),
    log_keys: tuple[str, ...] = (),
    normalizer: Callable[[Any], Any],
) -> tuple[bool, Any | None]:
    values = [transaction[key] for key in transaction_keys if key in transaction]
    values.extend(log[key] for key in log_keys if key in log)
    return _same_value(values, normalizer)


def _transaction_failed(transaction: Mapping[str, Any]) -> bool:
    if transaction.get("failed") is True or transaction.get("success") is False:
        return True
    for status in (transaction.get("status"), transaction.get("receipt_status")):
        if isinstance(status, str):
            normalized_status = status.strip().lower()
            if normalized_status in _FAILED_STATUS:
                return True
            if _integer(normalized_status, "status") == 0:
                return True
        elif isinstance(status, int) and not isinstance(status, bool) and status == 0:
            return True
    if transaction.get("err") is not None:
        return True
    meta = _mapping(transaction.get("meta"))
    return meta is not None and meta.get("err") is not None


def _removed(value: Any) -> bool:
    if value is True:
        return True
    return isinstance(value, str) and value.strip().lower() in _TRUE_TEXT


@dataclass(frozen=True, slots=True)
class DecodedEVMSell:
    """Decoder output before the versioned EVM event envelope is built."""

    token_address: str
    pool_address: str
    seller_wallet: str
    token_amount_raw: int | str
    quote_amount_raw: int | str
    quote_asset: str
    orientation: str
    event_index: int | str
    protocol: str | None = None
    event_type: str = "sell"
    decoder_status: str = DecoderStatus.VERIFIED.value
    decoder_version: str | None = None
    chain: str | None = None
    contract_address: str | None = None
    event_topic: str | None = None
    transaction_hash: str | None = None
    block_hash: str | None = None
    block_number: int | str | None = None
    log_index: int | str | None = None


DecodedSell = DecodedEVMSell
SellDecoder = Callable[
    [Mapping[str, Any], Mapping[str, Any]],
    DecodedEVMSell | Mapping[str, Any] | None,
]


@dataclass(frozen=True, slots=True)
class EVMProtocolDecoder:
    """One explicit chain/contract/topic-to-decoder registration."""

    protocol: str
    decoder: SellDecoder
    decoder_version: str = EVM_SELL_DECODER_VERSION

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


DecoderRegistration = EVMProtocolDecoder
ProtocolDecoder = EVMProtocolDecoder


def _registry_key(chain: Any, contract_address: Any, event_topic: Any) -> RegistryKey:
    normalized_chain = _normalize_chain(chain)
    normalized_address = _normalize_address(contract_address, "contract_address")
    normalized_topic = _normalize_hash_or_topic(event_topic, "event_topic")
    if normalized_chain is None:
        raise ValueError("unsupported EVM chain")
    if normalized_address is None:
        raise ValueError("contract_address must be a 20-byte EVM address")
    if normalized_topic is None:
        raise ValueError("event_topic must be a 32-byte hex value")
    return normalized_chain, normalized_address, normalized_topic


def _registration(
    entry: EVMProtocolDecoder | Mapping[str, Any] | tuple[str, SellDecoder],
) -> EVMProtocolDecoder:
    if isinstance(entry, EVMProtocolDecoder):
        return entry
    if isinstance(entry, Mapping):
        return EVMProtocolDecoder(
            protocol=entry.get("protocol"),
            decoder=entry.get("decoder"),
            decoder_version=entry.get("decoder_version", EVM_SELL_DECODER_VERSION),
        )
    if isinstance(entry, tuple) and len(entry) == 2:
        return EVMProtocolDecoder(protocol=entry[0], decoder=entry[1])
    raise ValueError("registry entries must explicitly name a protocol and decoder")


def _iter_registry_entries(
    entries: Mapping[Any, Any] | Iterable[tuple[Any, Any]],
) -> Iterable[tuple[Any, Any]]:
    if isinstance(entries, Mapping):
        return entries.items()
    return entries


def build_decoder_registry(
    entries: Mapping[Any, Any] | Iterable[tuple[Any, Any]] | None = None,
    *,
    chain: str | None = None,
    contract_address: str | None = None,
    event_topic: str | None = None,
    protocol: str | None = None,
    decoder: SellDecoder | None = None,
    decoder_version: str = EVM_SELL_DECODER_VERSION,
) -> dict[RegistryKey, EVMProtocolDecoder]:
    """Build a registry only from explicit caller-supplied entries.

    Calling this function without entries or registration fields returns an
    empty registry.  It never contains a production address, topic, ABI, or
    protocol by default.
    """

    result: dict[RegistryKey, EVMProtocolDecoder] = {}
    if entries is not None:
        for raw_key, raw_entry in _iter_registry_entries(entries):
            if isinstance(raw_key, tuple) and len(raw_key) == 3:
                key = _registry_key(*raw_key)
            elif isinstance(raw_key, str):
                parts = raw_key.split(EVM_REGISTRY_KEY_SEPARATOR)
                if len(parts) != 3:
                    raise ValueError("serialized registry keys must be chain|contract_address|event_topic")
                key = _registry_key(*parts)
            else:
                raise ValueError("registry keys must be (chain, contract_address, event_topic) tuples")
            if key in result:
                raise ValueError("registry keys must be unique after normalization")
            result[key] = _registration(raw_entry)

    supplied_registration = any(
        value is not None for value in (chain, contract_address, event_topic, protocol, decoder)
    )
    if supplied_registration:
        if any(value is None for value in (chain, contract_address, event_topic, protocol, decoder)):
            raise ValueError("chain, contract_address, event_topic, protocol, and decoder are required")
        key = _registry_key(chain, contract_address, event_topic)
        if key in result:
            raise ValueError("registry keys must be unique after normalization")
        result[key] = EVMProtocolDecoder(
            protocol=protocol,
            decoder=decoder,
            decoder_version=decoder_version,
        )
    return result


make_decoder_registry = build_decoder_registry
build_evm_decoder_registry = build_decoder_registry


def make_fixture_decoder(
    *,
    discriminator: str,
    orientation: str,
    required_account_roles: Iterable[str] | None = None,
    required_roles: Iterable[str] | None = None,
    protocol: str | None = None,
    decoder_version: str | None = None,
    seller_role: str = "seller",
    pool_role: str = "pool",
) -> SellDecoder:
    """Create a generic fixture decoder with explicit sell evidence.

    This helper intentionally understands only a generic sanitized fixture
    shape.  It is not a DEX ABI decoder and is never registered by production
    code.
    """

    normalized_discriminator = _required_text(discriminator, "discriminator")
    normalized_orientation = _required_text(orientation, "orientation")
    if normalized_discriminator is None or normalized_orientation is None:
        raise ValueError("discriminator and orientation are required")
    roles_source = required_account_roles if required_account_roles is not None else required_roles
    if roles_source is None:
        raise ValueError("required_account_roles are required")
    normalized_roles = tuple(_required_text(role, "account_role") for role in roles_source)
    if any(role is None for role in normalized_roles) or len(set(normalized_roles)) != len(normalized_roles):
        raise ValueError("required_account_roles must be distinct non-empty names")
    if seller_role not in normalized_roles or pool_role not in normalized_roles:
        raise ValueError("seller_role and pool_role must be required account roles")

    normalized_protocol = _required_text(protocol, "protocol")
    normalized_version = _required_text(decoder_version, "decoder_version")

    def decode(transaction: Mapping[str, Any], log: Mapping[str, Any]) -> DecodedEVMSell | None:
        del transaction
        if _required_text(log.get("discriminator"), "discriminator") != normalized_discriminator:
            return None
        if _required_text(log.get("event_type"), "event_type") != "sell":
            return None
        if _required_text(log.get("side"), "side") != "sell":
            return None
        if _required_text(log.get("orientation"), "orientation") != normalized_orientation:
            return None

        accounts = _mapping(log.get("account_roles"))
        if accounts is None:
            return None
        role_values: dict[str, str] = {}
        for role in normalized_roles:
            account = _normalize_address(accounts.get(role), f"account_roles.{role}")
            if account is None:
                return None
            role_values[role] = account
        if len(set(role_values.values())) != len(role_values):
            return None

        token = _mapping(log.get("token"))
        quote = _mapping(log.get("quote"))
        if token is None or quote is None:
            return None
        token_address = _normalize_address(
            token.get("address", token.get("token_address")),
            "token.address",
        )
        quote_asset = _quote_asset(quote.get("asset", quote.get("quote_asset", quote.get("address"))))
        token_amount = _integer(token.get("amount_raw"), "token.amount_raw")
        quote_amount = _integer(quote.get("amount_raw"), "quote.amount_raw")
        event_index = _integer(log.get("event_index"), "event_index")
        if (
            token_address is None
            or quote_asset is None
            or token_amount is None
            or quote_amount is None
            or event_index is None
        ):
            return None
        if quote_asset == token_address:
            return None
        return DecodedEVMSell(
            protocol=normalized_protocol,
            token_address=token_address,
            pool_address=role_values[pool_role],
            seller_wallet=role_values[seller_role],
            token_amount_raw=token_amount,
            quote_amount_raw=quote_amount,
            quote_asset=quote_asset,
            orientation=normalized_orientation,
            event_index=event_index,
            event_type="sell",
            decoder_status=DecoderStatus.VERIFIED.value,
            decoder_version=normalized_version,
        )

    return decode


fixture_decoder = make_fixture_decoder


def _lookup_registration(
    registry: Mapping[Any, EVMProtocolDecoder | Mapping[str, Any] | tuple[str, SellDecoder]],
    key: RegistryKey,
) -> EVMProtocolDecoder | None:
    matches: list[EVMProtocolDecoder | Mapping[str, Any] | tuple[str, SellDecoder]] = []
    serialized = EVM_REGISTRY_KEY_SEPARATOR.join(key)
    for raw_key, entry in registry.items():
        if raw_key in (key, serialized):
            matches.append(entry)
            continue
        if isinstance(raw_key, tuple) and len(raw_key) == 3:
            try:
                if _registry_key(*raw_key) == key:
                    matches.append(entry)
            except (TypeError, ValueError):
                continue
        elif isinstance(raw_key, str):
            parts = raw_key.split(EVM_REGISTRY_KEY_SEPARATOR)
            if len(parts) != 3:
                continue
            try:
                if _registry_key(*parts) == key:
                    matches.append(entry)
            except (TypeError, ValueError):
                continue
    if len(matches) != 1:
        return None
    return _registration(matches[0])


def _decoded_mapping(
    decoded: DecodedEVMSell | Mapping[str, Any],
) -> Mapping[str, Any]:
    if isinstance(decoded, DecodedEVMSell):
        return asdict(decoded)
    return decoded


def _decoder_output(
    output: DecodedEVMSell | Mapping[str, Any] | None,
    registration: EVMProtocolDecoder,
    *,
    chain: str,
    contract_address: str,
    event_topic: str,
    transaction_hash: str,
    block_hash: str,
    block_number: int,
    log_index: int,
) -> dict[str, Any] | None:
    if output is None or not isinstance(output, (DecodedEVMSell, Mapping)):
        return None
    values = _decoded_mapping(output)

    protocol = _required_text(values.get("protocol"), "protocol") or registration.protocol
    if protocol.lower() != registration.protocol:
        return None
    if _required_text(values.get("event_type"), "event_type") != "sell":
        return None
    if _required_text(values.get("orientation"), "orientation") != "token_to_quote":
        return None
    if _required_text(values.get("decoder_status"), "decoder_status") != DecoderStatus.VERIFIED.value:
        return None
    supplied_version = values.get("decoder_version")
    if supplied_version is not None and supplied_version != registration.decoder_version:
        return None

    supplied_chain = values.get("chain")
    if supplied_chain is not None and _normalize_chain(supplied_chain) != chain:
        return None
    supplied_contract = values.get("contract_address")
    if supplied_contract is not None and _normalize_address(supplied_contract, "contract_address") != contract_address:
        return None
    supplied_topic = values.get("event_topic")
    if supplied_topic is not None and _normalize_hash_or_topic(supplied_topic, "event_topic") != event_topic:
        return None
    supplied_tx = values.get("transaction_hash")
    if supplied_tx is not None and _normalize_hash_or_topic(supplied_tx, "transaction_hash") != transaction_hash:
        return None
    supplied_block = values.get("block_hash")
    if supplied_block is not None and _normalize_hash_or_topic(supplied_block, "block_hash") != block_hash:
        return None
    supplied_block_number = values.get("block_number")
    if supplied_block_number is not None and _integer(supplied_block_number, "block_number") != block_number:
        return None
    supplied_log_index = values.get("log_index")
    if supplied_log_index is not None and _integer(supplied_log_index, "log_index") != log_index:
        return None

    event_index = _integer(values.get("event_index"), "event_index")
    token_address = _normalize_address(values.get("token_address"), "token_address")
    pool_address = _normalize_address(values.get("pool_address"), "pool_address")
    seller_wallet = _normalize_address(values.get("seller_wallet"), "seller_wallet")
    token_amount = _integer(values.get("token_amount_raw"), "token_amount_raw")
    quote_amount = _integer(values.get("quote_amount_raw"), "quote_amount_raw")
    quote_asset = _quote_asset(values.get("quote_asset"))
    if (
        event_index is None
        or token_address is None
        or pool_address is None
        or seller_wallet is None
        or token_amount is None
        or quote_amount is None
        or quote_asset is None
    ):
        return None
    if quote_asset == token_address:
        return None
    return {
        "protocol": registration.protocol,
        "token_address": token_address,
        "pool_address": pool_address,
        "seller_wallet": seller_wallet,
        "token_amount_raw": token_amount,
        "quote_amount_raw": quote_amount,
        "quote_asset": quote_asset,
        "event_index": event_index,
        "decoder_status": DecoderStatus.VERIFIED.value,
    }


def _log_address(log: Mapping[str, Any]) -> tuple[bool, str | None]:
    values = [log[key] for key in ("address", "contract_address") if key in log]
    if not values:
        return False, None
    return _same_value(values, lambda value: _normalize_address(value, "contract_address"))


def _log_topic(log: Mapping[str, Any]) -> tuple[bool, str | None]:
    values: list[Any] = []
    for key in ("event_topic", "topic0"):
        if key in log:
            values.append(log[key])
    topics = log.get("topics")
    if isinstance(topics, (list, tuple)) and topics:
        values.append(topics[0])
    elif topics is not None:
        return False, None
    if not values:
        return False, None
    return _same_value(values, lambda value: _normalize_hash_or_topic(value, "event_topic"))


def normalize_evm_sell_events(
    transaction: Mapping[str, Any],
    *,
    registry: Mapping[Any, EVMProtocolDecoder | Mapping[str, Any] | tuple[str, SellDecoder]] | None = None,
    chain: str | None = None,
    observed_at: datetime | str | None = None,
    source: str | None = None,
    finality_status: str | None = None,
    reorg_status: str | None = None,
    quote_value_usd: float | int | str | None = None,
    finality_reference: str | None = None,
) -> list[EVMSellEvent]:
    """Normalize accepted sell logs from one already-sanitized transaction."""

    if not isinstance(transaction, Mapping):
        raise ValueError("transaction must be a sanitized mapping")
    if registry is not None and not isinstance(registry, Mapping):
        raise ValueError("registry must be a mapping")
    effective_registry = registry or {}
    if _transaction_failed(transaction) or _removed(transaction.get("removed")):
        return []

    chain_values = [value for value in (chain, transaction.get("chain")) if value is not None]
    if not chain_values:
        return []
    normalized_chains = [_normalize_chain(value) for value in chain_values]
    if any(value is None for value in normalized_chains) or len(set(normalized_chains)) != 1:
        return []
    normalized_chain = normalized_chains[0]
    if normalized_chain is None:
        return []

    normalized_observed_at = observed_at if observed_at is not None else transaction.get("observed_at")
    normalized_source = source if source is not None else transaction.get("source")
    if normalized_observed_at is None or _required_text(normalized_source, "source") is None:
        return []
    normalized_source = str(normalized_source).strip()
    normalized_finality = (
        finality_status if finality_status is not None else transaction.get("finality_status", "unknown")
    )
    normalized_reorg = reorg_status if reorg_status is not None else transaction.get("reorg_status", "unknown")
    normalized_quote_value = quote_value_usd if quote_value_usd is not None else transaction.get("quote_value_usd")
    normalized_finality_reference = (
        finality_reference if finality_reference is not None else transaction.get("finality_reference")
    )

    tx_values = [
        transaction[key] for key in ("transaction_hash", "transactionHash", "tx_hash", "hash") if key in transaction
    ]
    if not tx_values:
        return []
    tx_ok, transaction_hash = _same_value(
        tx_values,
        lambda value: _normalize_hash_or_topic(value, "transaction_hash"),
    )
    if not tx_ok or transaction_hash is None:
        return []

    logs = transaction.get("logs")
    if not isinstance(logs, list):
        return []

    events: list[EVMSellEvent] = []
    seen_log_positions: set[tuple[str, int]] = set()
    seen_event_positions: set[tuple[str, int]] = set()
    for log in logs:
        if not isinstance(log, Mapping) or _removed(log.get("removed")):
            continue
        address_ok, contract_address = _log_address(log)
        topic_ok, event_topic = _log_topic(log)
        if not address_ok or not topic_ok or contract_address is None or event_topic is None:
            continue
        try:
            key = _registry_key(normalized_chain, contract_address, event_topic)
            registration = _lookup_registration(effective_registry, key)
        except (TypeError, ValueError):
            continue
        if registration is None:
            continue

        tx_log_ok, log_transaction_hash = _context_value(
            transaction,
            log,
            transaction_keys=("transaction_hash", "transactionHash", "tx_hash", "hash"),
            log_keys=("transactionHash", "transaction_hash", "tx_hash"),
            normalizer=lambda value: _normalize_hash_or_topic(value, "transaction_hash"),
        )
        block_ok, block_hash = _context_value(
            transaction,
            log,
            transaction_keys=("block_hash", "blockHash"),
            log_keys=("blockHash", "block_hash"),
            normalizer=lambda value: _normalize_hash_or_topic(value, "block_hash"),
        )
        block_number_ok, block_number = _context_value(
            transaction,
            log,
            transaction_keys=("block_number", "blockNumber"),
            log_keys=("blockNumber", "block_number"),
            normalizer=lambda value: _integer(value, "block_number"),
        )
        log_index_values = [log[key] for key in ("log_index", "logIndex") if key in log]
        log_index_ok, log_index = _same_value(
            log_index_values,
            lambda value: _integer(value, "log_index"),
        )
        if (
            not tx_log_ok
            or log_transaction_hash != transaction_hash
            or not block_ok
            or block_hash is None
            or not block_number_ok
            or block_number is None
            or not log_index_ok
            or log_index is None
        ):
            continue
        log_position = (transaction_hash, log_index)
        if log_position in seen_log_positions:
            return []
        # A log position is part of the normalized evidence even when a
        # decoder later rejects the payload.  A second interpretation at the
        # same transaction/log position is therefore ambiguous and must not
        # be allowed to become an event.
        seen_log_positions.add(log_position)

        try:
            decoded = registration.decoder(transaction, log)
            normalized_decoded = _decoder_output(
                decoded,
                registration,
                chain=normalized_chain,
                contract_address=contract_address,
                event_topic=event_topic,
                transaction_hash=transaction_hash,
                block_hash=block_hash,
                block_number=block_number,
                log_index=log_index,
            )
            if normalized_decoded is None:
                continue
            event_index = normalized_decoded["event_index"]
            event_position = (transaction_hash, event_index)
            if event_position in seen_event_positions:
                return []
            event_id = compute_event_id(
                normalized_chain,
                normalized_decoded["protocol"],
                contract_address,
                event_topic,
                block_hash,
                transaction_hash,
                log_index,
                event_index,
            )
            event = EVMSellEvent(
                event_id=event_id,
                event_schema_version=EVM_EVENT_SCHEMA_VERSION,
                chain=normalized_chain,
                protocol=normalized_decoded["protocol"],
                contract_address=contract_address,
                event_topic=event_topic,
                event_type="sell",
                transaction_hash=transaction_hash,
                block_hash=block_hash,
                block_number=block_number,
                log_index=log_index,
                event_index=event_index,
                token_address=normalized_decoded["token_address"],
                pool_address=normalized_decoded["pool_address"],
                seller_wallet=normalized_decoded["seller_wallet"],
                token_amount_raw=normalized_decoded["token_amount_raw"],
                quote_amount_raw=normalized_decoded["quote_amount_raw"],
                quote_asset=normalized_decoded["quote_asset"],
                observed_at=normalized_observed_at,
                source=normalized_source,
                decoder_version=registration.decoder_version,
                decoder_status=normalized_decoded["decoder_status"],
                finality_status=normalized_finality,
                reorg_status=normalized_reorg,
                quote_value_usd=normalized_quote_value,
                finality_reference=normalized_finality_reference,
            )
        except (TypeError, ValueError, KeyError, AttributeError):
            continue
        seen_event_positions.add(event_position)
        events.append(event)
    return events


def normalize_evm_sell_event(
    transaction: Mapping[str, Any],
    *,
    registry: Mapping[Any, EVMProtocolDecoder | Mapping[str, Any] | tuple[str, SellDecoder]] | None = None,
    **kwargs: Any,
) -> EVMSellEvent | None:
    """Normalize one transaction when it contains at most one accepted sell."""

    events = normalize_evm_sell_events(transaction, registry=registry, **kwargs)
    if len(events) > 1:
        raise ValueError("transaction contains multiple sell events; use normalize_evm_sell_events")
    return events[0] if events else None


normalize_sell_transaction = normalize_evm_sell_events
normalize_sell_event = normalize_evm_sell_event


__all__ = [
    "EVM_REGISTRY_KEY_SEPARATOR",
    "EVM_SELL_DECODER_VERSION",
    "DecodedEVMSell",
    "DecodedSell",
    "DecoderRegistration",
    "EVMProtocolDecoder",
    "ProtocolDecoder",
    "RegistryKey",
    "SellDecoder",
    "build_decoder_registry",
    "build_evm_decoder_registry",
    "fixture_decoder",
    "make_decoder_registry",
    "make_fixture_decoder",
    "normalize_evm_sell_event",
    "normalize_evm_sell_events",
    "normalize_sell_event",
    "normalize_sell_transaction",
]
