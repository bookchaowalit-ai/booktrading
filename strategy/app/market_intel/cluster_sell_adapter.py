"""Read-only adapter from finalized Solana sells to cluster-sell monitoring.

The adapter accepts only the versioned normalized event contract.  Ownership
and balance context are explicit inputs: it never derives a cluster from
funding, a common funder, or transaction proximity, and it never fabricates a
USD quote value.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from math import isfinite
from typing import Any, Protocol

from app.market_intel.solana_event_schema import (
    SolanaSellEvent,
    is_monitor_eligible,
    validate_solana_sell_event,
)
from app.market_intel.wallet_intelligence import (
    ClusterSellAlert,
    ClusterSellMonitor,
    ClusterSellObservation,
)

SOLANA_CLUSTER_SELL_ADAPTER_VERSION = "solana-cluster-sell-adapter.v1"


class ChainScopedClusterResolver(Protocol):
    """Resolve an explicitly established cluster for one chain and wallet."""

    def __call__(self, chain: str, wallet: str) -> str | None: ...


class ClusterResolverObject(Protocol):
    """Object form of the same explicit resolver boundary."""

    def resolve(self, chain: str, wallet: str) -> str | None: ...


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} is required")
    return value.strip()


def _positive_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be a positive integer")
    if value <= 0:
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
    resolver: ChainScopedClusterResolver | ClusterResolverObject,
    *,
    chain: str,
    wallet: str,
) -> str | None:
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
    event: SolanaSellEvent,
    externally_supplied_quote_value_usd: float | int | str | None,
) -> float | None:
    if event.quote_value_usd is not None and externally_supplied_quote_value_usd is not None:
        supplied = _usd(externally_supplied_quote_value_usd)
        if supplied != event.quote_value_usd:
            raise ValueError("event and external quote_value_usd evidence disagree")
    if event.quote_value_usd is not None:
        return event.quote_value_usd
    if externally_supplied_quote_value_usd is not None:
        return _usd(externally_supplied_quote_value_usd)
    return None


def build_cluster_sell_observation(
    event: SolanaSellEvent | Mapping[str, Any],
    *,
    cluster_resolver: ChainScopedClusterResolver | ClusterResolverObject,
    cluster_balance_before: int,
    quote_value_usd: float | int | str | None = None,
) -> ClusterSellObservation | None:
    """Build an observation when all explicit monitor context is available.

    A missing resolver result or missing external USD evidence returns
    ``None`` without calling the monitor.  A non-positive balance is a caller
    error because it cannot be a valid pre-sell denominator.
    """

    normalized = validate_solana_sell_event(event)
    if not is_monitor_eligible(normalized):
        return None
    balance = _positive_int(cluster_balance_before, "cluster_balance_before")
    if normalized.token_amount_raw <= 0:
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
        tx_hash=normalized.signature,
        log_index=normalized.event_index,
        block_number=normalized.slot,
        observed_at=normalized.observed_at,
        source=normalized.source,
        cluster_balance_before=balance,
    )


@dataclass(frozen=True, slots=True)
class ClusterSellRoute:
    """Pure route result with an alert payload and an explicit no-trade flag."""

    status: str
    event_id: str
    observation: ClusterSellObservation | None = None
    alert: ClusterSellAlert | None = None
    reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "version": SOLANA_CLUSTER_SELL_ADAPTER_VERSION,
            "status": self.status,
            "event_id": self.event_id,
            "observation": self.observation.as_dict() if self.observation is not None else None,
            "alert": self.alert.as_dict() if self.alert is not None else None,
            "trade_instruction": False,
        }
        if self.reason is not None:
            result["reason"] = self.reason
        return result


class ClusterSellAdapter:
    """Deduplicating, finality-gated adapter around ``ClusterSellMonitor``."""

    def __init__(
        self,
        monitor: ClusterSellMonitor,
        *,
        cluster_resolver: ChainScopedClusterResolver | ClusterResolverObject,
    ) -> None:
        if not hasattr(monitor, "ingest"):
            raise ValueError("monitor must expose ingest")
        self.monitor = monitor
        self.cluster_resolver = cluster_resolver
        self._seen_event_ids: set[str] = set()
        self._seen_positions: dict[tuple[str, str, int], str] = {}

    def ingest(
        self,
        event: SolanaSellEvent | Mapping[str, Any],
        *,
        cluster_balance_before: int,
        quote_value_usd: float | int | str | None = None,
    ) -> ClusterSellRoute:
        """Route one event and never cross into opportunity or execution code."""

        normalized = validate_solana_sell_event(event)
        if not is_monitor_eligible(normalized):
            return ClusterSellRoute(
                status="ignored",
                event_id=normalized.event_id,
                reason="monitor_requires_finalized_canonical_event",
            )
        if normalized.event_id in self._seen_event_ids:
            return ClusterSellRoute(
                status="deduplicated",
                event_id=normalized.event_id,
                reason="event_id_already_ingested",
            )

        position = (normalized.chain, normalized.signature, normalized.event_index)
        existing_event_id = self._seen_positions.get(position)
        if existing_event_id is not None:
            raise ValueError(
                f"event_index must be unique per chain and transaction (existing event_id={existing_event_id})"
            )

        observation = build_cluster_sell_observation(
            normalized,
            cluster_resolver=self.cluster_resolver,
            cluster_balance_before=cluster_balance_before,
            quote_value_usd=quote_value_usd,
        )
        if observation is None:
            return ClusterSellRoute(
                status="ignored",
                event_id=normalized.event_id,
                reason="explicit_cluster_balance_resolver_or_quote_evidence_required",
            )

        self._seen_event_ids.add(normalized.event_id)
        self._seen_positions[position] = normalized.event_id
        alert = self.monitor.ingest(observation)
        return ClusterSellRoute(
            status="ingested",
            event_id=normalized.event_id,
            observation=observation,
            alert=alert,
        )

    def route(
        self,
        event: SolanaSellEvent | Mapping[str, Any],
        *,
        cluster_balance_before: int,
        quote_value_usd: float | int | str | None = None,
    ) -> dict[str, Any]:
        """Return the JSON-safe route payload for a monitoring consumer."""

        return self.ingest(
            event,
            cluster_balance_before=cluster_balance_before,
            quote_value_usd=quote_value_usd,
        ).as_dict()


def route_solana_sell_event(
    event: SolanaSellEvent | Mapping[str, Any],
    *,
    monitor: ClusterSellMonitor,
    cluster_resolver: ChainScopedClusterResolver | ClusterResolverObject,
    cluster_balance_before: int,
    quote_value_usd: float | int | str | None = None,
) -> ClusterSellRoute:
    """Pure one-shot route helper for callers that own adapter lifecycle."""

    adapter = ClusterSellAdapter(monitor, cluster_resolver=cluster_resolver)
    return adapter.ingest(
        event,
        cluster_balance_before=cluster_balance_before,
        quote_value_usd=quote_value_usd,
    )


def ingest_solana_sell_events(
    events: list[SolanaSellEvent | Mapping[str, Any]],
    *,
    monitor: ClusterSellMonitor,
    cluster_resolver: ChainScopedClusterResolver | ClusterResolverObject,
    cluster_balance_before: int | Callable[[SolanaSellEvent], int],
    quote_value_usd: float | int | str | None = None,
) -> list[ClusterSellRoute]:
    """Route a bounded batch through one deduplicating adapter instance."""

    adapter = ClusterSellAdapter(monitor, cluster_resolver=cluster_resolver)
    routes: list[ClusterSellRoute] = []
    for raw_event in events:
        event = validate_solana_sell_event(raw_event)
        balance = cluster_balance_before(event) if callable(cluster_balance_before) else cluster_balance_before
        routes.append(
            adapter.ingest(
                event,
                cluster_balance_before=balance,
                quote_value_usd=quote_value_usd,
            )
        )
    return routes


adapt_solana_sell_event = build_cluster_sell_observation


__all__ = [
    "SOLANA_CLUSTER_SELL_ADAPTER_VERSION",
    "ChainScopedClusterResolver",
    "ClusterResolverObject",
    "ClusterSellAdapter",
    "ClusterSellRoute",
    "adapt_solana_sell_event",
    "build_cluster_sell_observation",
    "ingest_solana_sell_events",
    "route_solana_sell_event",
]
