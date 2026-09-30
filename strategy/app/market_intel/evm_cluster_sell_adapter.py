"""Read-only adapter from finalized EVM sells to cluster-sell monitoring.

The adapter accepts only the normalized EVM event contract.  Cluster
membership, pre-sell balance, and USD valuation are explicit caller-owned
context.  No ownership is inferred from funding, a common funder, or
transaction proximity, and no opportunity/order/execution field is emitted.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from math import isfinite
from typing import Any, Protocol

from app.market_intel.evm_event_schema import (
    EVMSellEvent,
    is_monitor_eligible,
    validate_evm_sell_event,
)
from app.market_intel.wallet_intelligence import (
    ClusterSellAlert,
    ClusterSellMonitor,
    ClusterSellObservation,
)

EVM_CLUSTER_SELL_ADAPTER_VERSION = "evm-cluster-sell-adapter.v1"


class EVMChainScopedClusterResolver(Protocol):
    """Resolve an explicitly established cluster for one chain and wallet."""

    def __call__(self, chain: str, wallet: str) -> str | None: ...


class EVMClusterResolverObject(Protocol):
    """Object form of the same explicit resolver boundary."""

    def resolve(self, chain: str, wallet: str) -> str | None: ...


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} is required")
    result = value.strip()
    if not result:
        raise ValueError(f"{field_name} is required")
    return result


def _positive_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def _usd(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError("quote_value_usd must be a finite non-negative number")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("quote_value_usd must be a finite non-negative number") from exc
    if not isfinite(result) or result < 0:
        raise ValueError("quote_value_usd must be a finite non-negative number")
    return result


def _resolve_cluster(
    resolver: EVMChainScopedClusterResolver | EVMClusterResolverObject | None,
    *,
    chain: str,
    wallet: str,
) -> str | None:
    if resolver is None:
        return None
    if hasattr(resolver, "resolve"):
        value = resolver.resolve(chain, wallet)  # type: ignore[attr-defined]
    elif callable(resolver):
        value = resolver(chain, wallet)
    else:
        raise ValueError("cluster_resolver must be a chain-scoped callable or object")
    if value is None:
        return None
    return _required_text(value, "cluster_id")


def _quote_value(
    event: EVMSellEvent,
    externally_supplied_quote_value_usd: float | int | str | None,
) -> float | None:
    event_value = _usd(event.quote_value_usd) if event.quote_value_usd is not None else None
    supplied_value = (
        _usd(externally_supplied_quote_value_usd) if externally_supplied_quote_value_usd is not None else None
    )
    if event.quote_value_usd is not None and event_value is None:
        return None
    if externally_supplied_quote_value_usd is not None and supplied_value is None:
        return None
    if event_value is not None and supplied_value is not None and event_value != supplied_value:
        raise ValueError("event and external quote_value_usd evidence disagree")
    return event_value if event_value is not None else supplied_value


def build_evm_cluster_sell_observation(
    event: EVMSellEvent | Mapping[str, Any],
    *,
    cluster_resolver: EVMChainScopedClusterResolver | EVMClusterResolverObject | None = None,
    cluster_balance_before: int | None = None,
    quote_value_usd: float | int | str | None = None,
) -> ClusterSellObservation | None:
    """Build one monitor observation only when all explicit context exists."""

    normalized = validate_evm_sell_event(event)
    if not is_monitor_eligible(normalized):
        return None
    balance = (
        _positive_int(cluster_balance_before, "cluster_balance_before") if cluster_balance_before is not None else None
    )
    if balance is None or normalized.token_amount_raw <= 0:
        return None
    usd = _quote_value(normalized, quote_value_usd)
    if usd is None:
        return None
    cluster_id = _resolve_cluster(
        cluster_resolver,
        chain=normalized.chain,
        wallet=normalized.seller_wallet,
    )
    if cluster_id is None:
        return None
    return ClusterSellObservation(
        chain=normalized.chain,
        token_address=normalized.token_address,
        cluster_id=cluster_id,
        wallet=normalized.seller_wallet,
        amount_token=normalized.token_amount_raw,
        quote_value_usd=usd,
        tx_hash=normalized.transaction_hash,
        log_index=normalized.log_index,
        block_number=normalized.block_number,
        observed_at=normalized.observed_at,
        source=normalized.source,
        cluster_balance_before=balance,
    )


build_cluster_sell_observation = build_evm_cluster_sell_observation


@dataclass(frozen=True, slots=True)
class EVMClusterSellRoute:
    """Pure route result with an alert payload and an explicit no-trade flag."""

    status: str
    event_id: str
    observation: ClusterSellObservation | None = None
    alert: ClusterSellAlert | None = None
    reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "version": EVM_CLUSTER_SELL_ADAPTER_VERSION,
            "status": self.status,
            "event_id": self.event_id,
            "observation": self.observation.as_dict() if self.observation is not None else None,
            "alert": self.alert.as_dict() if self.alert is not None else None,
            "trade_instruction": False,
        }
        if self.reason is not None:
            result["reason"] = self.reason
        return result


ClusterSellRoute = EVMClusterSellRoute


class EVMClusterSellAdapter:
    """Deduplicating, finality-gated adapter around ``ClusterSellMonitor``."""

    def __init__(
        self,
        monitor: ClusterSellMonitor,
        *,
        cluster_resolver: EVMChainScopedClusterResolver | EVMClusterResolverObject | None = None,
    ) -> None:
        if not hasattr(monitor, "ingest"):
            raise ValueError("monitor must expose ingest")
        self.monitor = monitor
        self.cluster_resolver = cluster_resolver
        self._seen_event_ids: set[str] = set()
        self._seen_positions: dict[tuple[str, str, int, int], str] = {}

    def ingest(
        self,
        event: EVMSellEvent | Mapping[str, Any],
        *,
        cluster_balance_before: int | None = None,
        quote_value_usd: float | int | str | None = None,
    ) -> EVMClusterSellRoute:
        """Route one event and never cross into opportunity or execution code."""

        normalized = validate_evm_sell_event(event)
        if not is_monitor_eligible(normalized):
            return EVMClusterSellRoute(
                status="ignored",
                event_id=normalized.event_id,
                reason="monitor_requires_verified_finalized_canonical_event",
            )
        if normalized.event_id in self._seen_event_ids:
            return EVMClusterSellRoute(
                status="deduplicated",
                event_id=normalized.event_id,
                reason="event_id_already_ingested",
            )

        position = (
            normalized.chain,
            normalized.transaction_hash,
            normalized.log_index,
            normalized.event_index,
        )
        existing_event_id = self._seen_positions.get(position)
        if existing_event_id is not None:
            raise ValueError(f"event position conflicts with an existing event (existing event_id={existing_event_id})")

        observation = build_evm_cluster_sell_observation(
            normalized,
            cluster_resolver=self.cluster_resolver,
            cluster_balance_before=cluster_balance_before,
            quote_value_usd=quote_value_usd,
        )
        if observation is None:
            return EVMClusterSellRoute(
                status="ignored",
                event_id=normalized.event_id,
                reason="explicit_cluster_resolver_positive_balance_and_quote_value_required",
            )

        self._seen_event_ids.add(normalized.event_id)
        self._seen_positions[position] = normalized.event_id
        alert = self.monitor.ingest(observation)
        return EVMClusterSellRoute(
            status="ingested",
            event_id=normalized.event_id,
            observation=observation,
            alert=alert,
        )

    def route(
        self,
        event: EVMSellEvent | Mapping[str, Any],
        *,
        cluster_balance_before: int | None = None,
        quote_value_usd: float | int | str | None = None,
    ) -> dict[str, Any]:
        """Return the JSON-safe route payload for a monitoring consumer."""

        return self.ingest(
            event,
            cluster_balance_before=cluster_balance_before,
            quote_value_usd=quote_value_usd,
        ).as_dict()


def route_evm_sell_event(
    event: EVMSellEvent | Mapping[str, Any],
    *,
    monitor: ClusterSellMonitor,
    cluster_resolver: EVMChainScopedClusterResolver | EVMClusterResolverObject | None = None,
    cluster_balance_before: int | None = None,
    quote_value_usd: float | int | str | None = None,
) -> EVMClusterSellRoute:
    """Pure one-shot route helper for callers that own adapter lifecycle."""

    adapter = EVMClusterSellAdapter(monitor, cluster_resolver=cluster_resolver)
    return adapter.ingest(
        event,
        cluster_balance_before=cluster_balance_before,
        quote_value_usd=quote_value_usd,
    )


def ingest_evm_sell_events(
    events: list[EVMSellEvent | Mapping[str, Any]],
    *,
    monitor: ClusterSellMonitor,
    cluster_resolver: EVMChainScopedClusterResolver | EVMClusterResolverObject | None = None,
    cluster_balance_before: int | Callable[[EVMSellEvent], int | None] | None = None,
    quote_value_usd: float | int | str | None = None,
) -> list[EVMClusterSellRoute]:
    """Route a bounded batch through one deduplicating adapter instance."""

    adapter = EVMClusterSellAdapter(monitor, cluster_resolver=cluster_resolver)
    routes: list[EVMClusterSellRoute] = []
    for raw_event in events:
        event = validate_evm_sell_event(raw_event)
        balance = cluster_balance_before(event) if callable(cluster_balance_before) else cluster_balance_before
        routes.append(
            adapter.ingest(
                event,
                cluster_balance_before=balance,
                quote_value_usd=quote_value_usd,
            )
        )
    return routes


adapt_evm_sell_event = build_evm_cluster_sell_observation


__all__ = [
    "EVM_CLUSTER_SELL_ADAPTER_VERSION",
    "ClusterSellRoute",
    "EVMChainScopedClusterResolver",
    "EVMClusterResolverObject",
    "EVMClusterSellAdapter",
    "EVMClusterSellRoute",
    "adapt_evm_sell_event",
    "build_cluster_sell_observation",
    "build_evm_cluster_sell_observation",
    "ingest_evm_sell_events",
    "route_evm_sell_event",
]
